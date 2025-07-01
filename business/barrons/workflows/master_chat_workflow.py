from typing import Dict, Any, Optional
from business.interfaces.workflow_interface import WorkflowInterface
from infrastructure.llm.agent_manager import AgentManager
from application.services.prompt_service import PromptService
from business.barrons.workflows.news_query_execution import NewsQueryWorkflow
from business.barrons.workflows.Stock_DB_Query_workflow import StockDBQueryWorkflow
from business.barrons.workflows.Stock_Data_Explainer_workflow import StockDataExplainerWorkflow
from business.barrons.workflows.followUpQuestions_workflow import FollowUpQuestionsWorkflow
from infrastructure.llm.llm_base import LLMModel

class MasterChatWorkflow(WorkflowInterface[str, str]):
    """
    A simple workflow that passes a prompt directly to the LLM and returns the response.
    """

    def __init__(self, agent_manager: AgentManager, prompt_service: PromptService, llm: LLMModel):
        """
        Initialize the direct query workflow.

        Args:
            agent_manager: Manager for LLM agent interactions
        """
        self.agent_manager = agent_manager
        self.prompt_service = prompt_service
        self.stock_db_query_workflow = StockDBQueryWorkflow(agent_manager=agent_manager, prompt_service=prompt_service, llm=llm)
        self.stock_data_explainer_workflow = StockDataExplainerWorkflow(agent_manager=agent_manager, prompt_service=prompt_service, llm=llm)
        self.news_workflow = NewsQueryWorkflow(agent_manager=agent_manager, prompt_service=prompt_service, llm=llm)
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
                yield sql_data
            sql_data_for_prompts = {"data": sql_data["rds_data"], "columns": sql_data["rds_columns"]}
            response["stock_data"] = {**sql_data_for_prompts}
            response["stock_data"]["message_id"] = self.llm.langfuse_handler.get_trace_id()
            if stream:
                yield response
            parameters["sql_data"] = sql_data_for_prompts
            sql_data_explaination = self.stock_data_explainer_workflow.execute(query, parameters)
            sql_data_explaination_response = {"stock_data_explanation": {"explanation": sql_data_explaination["explanation"], "message_id": self.llm.langfuse_handler.get_trace_id()}}
            if stream:
                yield sql_data_explaination_response
            for k, v in sql_data_explaination_response.items():
                response[k] = v
            news_data = await self.news_workflow.execute(query)
            news_data_response = {"news_data_analysis": {"news_data_analysis": news_data["news_data_analysis"], "message_id": self.llm.langfuse_handler.get_trace_id()}}
            if stream:
                yield news_data_response
            for k, v in news_data_response.items():
                response[k] = v
            try:
                parameters["news_data"] = news_data["news_data_analysis"]
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
