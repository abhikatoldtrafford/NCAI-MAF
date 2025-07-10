import ast
import datetime
import json
from typing import Any, AsyncGenerator, Dict, Optional

from NewsAgents.application import PromptService
from NewsAgents.business.interfaces.workflow_interface import WorkflowInterface
from NewsAgents.infrastructure.llm import AgentManager, LLMModel

from barrons.config.prompt_registry import (
    FollowUpQuestionsPrompts,
    NewsQueryAnalysisPrompts,
    NewsQuerySearchTermsPrompts,
    StockDBQueryPrompts,
    StockDataExplainerPrompts,
)
from barrons.tools.fetch_articles import FetchArticles
from barrons.tools.fetch_sql_data import FetchSQLData

from .news_query_execution import NewsQueryWorkflow
from .news_query_execution_factiva import NewsQueryWorkflowFactiva
from .Stock_DB_Query_workflow import StockDBQueryWorkflow
from .Stock_Data_Explainer_workflow import StockDataExplainerWorkflow
from barrons.workflows.followUpQuestions_workflow import FollowUpQuestionsWorkflow

from agent_workflow.providers import register_tool

class MasterChatWorkflow(WorkflowInterface[str, str]):
    """
    A simple workflow that passes a prompt directly to the LLM and returns the response.
    """

    def __init__(self, agent_manager: AgentManager, prompt_service: PromptService, llm: LLMModel, aws_creds: Dict[str, Any]):
        """
        Initialize the direct query workflow.

        Args:
            agent_manager: Manager for LLM agent interactions
        """
        self.agent_manager = agent_manager
        self.prompt_service = prompt_service
        self.stock_db_query_workflow = StockDBQueryWorkflow(agent_manager=agent_manager, prompt_service=prompt_service, llm=llm, aws_creds=aws_creds)
        self.stock_data_explainer_workflow = StockDataExplainerWorkflow(agent_manager=agent_manager, prompt_service=prompt_service, llm=llm, aws_creds=aws_creds)
        self.news_workflow = NewsQueryWorkflow(agent_manager=agent_manager, prompt_service=prompt_service, llm=llm, aws_creds=aws_creds)
        self.llm = llm
        self.status = {"state": "idle"}

    async def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None):
        response = {}
        self.status = {"state": "processing"}
        try:
            stream = parameters.get("stream", False)
            sql_data = self.stock_db_query_workflow.execute(query, parameters)
            if sql_data is None or not isinstance(sql_data, dict) or ("error_message" in sql_data.keys() and len(sql_data["error_message"].strip()) > 0):
                try:
                    self.status = {"state": "failed", "error": sql_data["error_message"]}
                except:
                    self.status = {"state": "failed", "error": "Unable to execute the SQL Queries"}
            response["stock_data"] = {**sql_data}
            response["stock_data"]["message_id"] = self.llm.langfuse_handler.get_trace_id()
            proceed_further = not (sql_data is None or ("rds_data" not in sql_data.keys()) or (len(sql_data["rds_data"]) == 0))
            if not proceed_further:
                response["stock_data_explanation"] = {"message_id": self.llm.langfuse_handler.get_trace_id()}
                response["stock_data_explanation"]["explanation"] = """I couldn’t retrieve stock data for your request.
                This could be due to limited data availability or the way the query was phrased. Want to try:
                    Asking about a specific company’s dividend, valuation, or fundamentals?
                    Exploring top stocks by a specific metric like “highest free cash flow” or “best dividend growth”?
                I can also provide market commentary or news if helpful!"""
            if stream:
                yield response
            if proceed_further:
                sql_data_for_prompts = {"data": sql_data["rds_data"], "columns": sql_data["rds_columns"]}
                parameters["sql_data"] = sql_data_for_prompts
                sql_data_explaination = self.stock_data_explainer_workflow.execute(query, parameters)
                sql_data_explaination_response = {"stock_data_explanation": {"explanation": sql_data_explaination["explanation"], "message_id": self.llm.langfuse_handler.get_trace_id()}}
                if stream:
                    yield sql_data_explaination_response
                for k, v in sql_data_explaination_response.items():
                    response[k] = v
                response["news_data_analysis"] = await self.news_workflow.execute(query)
                response["news_data_analysis"]["message_id"] = self.llm.langfuse_handler.get_trace_id()
                if stream:
                    yield {"news_data_analysis": response["news_data_analysis"]}
                try:
                    parameters["news_data"] = response["news_data_analysis"]["news_data_analysis"]
                    followup_question_workflow = FollowUpQuestionsWorkflow(self.agent_manager, self.prompt_service, self.llm)
                    followup_questions = followup_question_workflow.execute(query, parameters)
                    fuq_response = {"follow_up_questions": {"follow_up_questions": followup_questions["follow_up_questions"], "message_id": self.llm.langfuse_handler.get_trace_id()}}
                    if stream:
                        yield fuq_response
                    for k, v in fuq_response.items():
                        response[k] = v
                except Exception as e1:
                    self.status = {"state": "failed", "error": str(e1)}
                    response["error_message"] = str(e1)
        except Exception as e:
            self.status = {"state": "failed", "error": str(e)}
            response["error_message"] = str(e)
        self.status = {"state": "completed"}
        if not stream:
            yield response