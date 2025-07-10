from typing import Dict, AsyncGenerator, Any, Optional
import datetime
import json
import ast
from business.barrons.config.prompt_registry import (
    StockDBQueryPrompts,
    StockDataExplainerPrompts,
    NewsQueryAnalysisPrompts,
    NewsQuerySearchTermsPrompts,
    FollowUpQuestionsPrompts,
)
from application.services.prompt_service import PromptService
from infrastructure.llm.agent_manager import AgentManager
from business.barrons.tools.fetch_sql_data import FetchSQLData
from business.barrons.tools.fetch_articles import FetchArticles
from agent_workflow.providers import register_tool


class MasterChatWorkflow:
    """
    Orchestrates the full Barron’s pipeline by:
    """

    PROVIDER_MAPPING = {
        "generate_sql_query": "openai_gpt4",
        "fetch_sql_data": "openai_gpt4",
        "explain_sql_data": "openai_gpt4",
        "generate_search_terms": "openai_gpt4",
        "fetch_articles": "openai_gpt4",
        "analyze_news_data": "openai_gpt4",
        "generate_followup_questions": "openai_gpt4",
    }
    RESPONSE_MAPPING = {
        "Fetch SQL Data": "stock_data",
        "Explain SQL Data": "stock_data_explanation",
        "Analyze News Data": "news_data_analysis",
        "Generate Followup Questions": "follow_up_questions",
    }

    def __init__(
        self,
        agent_manager: AgentManager,
        prompt_service: PromptService,
        aws_creds: Dict[str, Any],
    ):
        self.agent_manager = agent_manager
        self.prompt_service = prompt_service
        self.aws_creds = aws_creds

    def _init_prompts(self, user_prompt: str, parameters: Optional[Dict] = None) -> Dict[str, str]:
        """
        Fetch all system & user prompts required by the workflow.
        Returns dict with the exact fields needed by the YAML template.
        """
        history = (parameters or {}).get("history") or []
        indicators = (parameters or {}).get("user_hardset_indicators") or []
        today = datetime.date.today()
        yesterday = (today - datetime.timedelta(days=1)).strftime("%B %d, %Y")
        table_name = self.aws_creds["STOCK_DATA_TABLE_NAME"].strip()

        # SQL: generate + explain
        sql_sys, sql_user = self.prompt_service.get_prompts(*StockDBQueryPrompts().get_all_prompt_info())
        sql_sys = sql_sys.format(table_name=table_name, formatted_date=yesterday)
        sql_user = sql_user.format(question=user_prompt, conversation=history, indicator_list=indicators)
        explain_sys = self.prompt_service.get_prompt(*StockDataExplainerPrompts().get_system_prompt_info())

        # News: search terms + analyze
        terms_sys, terms_user = self.prompt_service.get_prompts(*NewsQuerySearchTermsPrompts().get_all_prompt_info())
        terms_user = terms_user.format(question=user_prompt, conversation=history)
        news_sys, news_user = self.prompt_service.get_prompts(*NewsQueryAnalysisPrompts().get_all_prompt_info())
        news_sys = news_sys.format(date=today)
        news_user = news_user.format(conversation=history, question=user_prompt)

        # Followup questions
        fuq_sys, fuq_user = self.prompt_service.get_prompts(*FollowUpQuestionsPrompts().get_all_prompt_info())
        fuq_user = fuq_user.format(conversation=history, question=user_prompt)

        return {
            "generate_sql_sys_prompt": sql_sys,
            "generate_sql_user_prompt": sql_user,
            "explain_sql_sys_prompt": explain_sys,
            "search_terms_sys_prompt": terms_sys,
            "search_terms_user_prompt": terms_user,
            "news_analysis_sys_prompt": news_sys,
            "news_analysis_user_prompt": news_user,
            "followup_questions_user_prompt": fuq_user,
            "followup_questions_sys_prompt": fuq_sys,
        }

    def _init_tools(self, prompts: Dict[str, str]):
        """
        Register tools so the Agent manager has access to them.
        """
        register_tool(
            FetchSQLData(aws_creds=self.aws_creds, generate_sql_sys_prompt=prompts["generate_sql_sys_prompt"]).asFunctionalTool
        )
        register_tool(FetchArticles(aws_creds=self.aws_creds).asFunctionalTool)

    def _format_response(self, raw: Dict[str, Any]) -> Dict[str, Any]:
        """
        Remap top-level keys and unwrap nested objects.
        """

        def flatten(v):
            return next(iter(v.values())) if isinstance(v, dict) and len(v) == 1 else v

        def coerce(val: Any) -> Any:
            if isinstance(val, str):
                s = val.strip()
                if (s.startswith("[") and s.endswith("]")) or (s.startswith("{") and s.endswith("}")):
                    try:
                        return coerce(json.loads(s))
                    except Exception:
                        try:
                            return coerce(ast.literal_eval(s))
                        except Exception:
                            pass
            elif isinstance(val, dict):
                return {k: coerce(v) for k, v in val.items()}
            elif isinstance(val, list):
                return [coerce(v) for v in val]
            return val

        return {
            self.RESPONSE_MAPPING[task_name]: coerce(flatten(payload))
            for task_name, payload in raw.items()
            if task_name in self.RESPONSE_MAPPING
        }

    async def execute(
        self,
        query: str,
        parameters: Optional[Dict] = None,
    ) -> AsyncGenerator[Dict, None]:
        
        ### TEST DEPLOYMENT ISSUE 2025-06-20 ###
        print("HELLO WORLD")

        # Build workflow inputs
        runtime_inputs = self._init_prompts(query, parameters)

        # Register tools
        self._init_tools(runtime_inputs)

        # Run the full pipeline
        raw = await self.agent_manager.run_workflow(
            user_prompt=query,
            provider_mapping=self.PROVIDER_MAPPING,
            runtime_inputs=runtime_inputs,
        )
        formatted = self._format_response(raw)

        yield {"response": formatted}