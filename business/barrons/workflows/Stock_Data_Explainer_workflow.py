from typing import Dict, Any, Optional
from langchain_core.output_parsers import JsonOutputParser

from infrastructure.llm.llm_base import LLMModel
from infrastructure.llm.agent_manager import AgentManager
from application.services.prompt_service import PromptService
from business.interfaces.workflow_interface import WorkflowInterface
from business.barrons.workflows.Stock_DB_Query_workflow import StockDBQueryWorkflow


def clean_up_generated_text(text:str) -> str:
    return text.replace("$", "$")

class StockDataExplainerWorkflow(WorkflowInterface[str, str]):
    """
    A workflow that queries news articles based on LLM-generated search terms.
    """
    
    def __init__(self, agent_manager: AgentManager, prompt_service: PromptService, llm: LLMModel):
        """
        Initialize the news query workflow.
        
        Args:
            agent_manager: Manager for LLM agent interactions
        """
        self.agent_manager = agent_manager
        self.prompt_service = prompt_service
        self.llm = llm
        self.stock_db_query_workflow = StockDBQueryWorkflow(agent_manager=agent_manager, prompt_service=prompt_service, llm=llm)
        self.status = {"state": "idle"}
    
    def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the Stock DB query workflow.
        
        Args:
            query: The user Question
            parameters: Optional parameters for execution
        Returns:
            The workflow result
        """
        self.status = {"state": "processing"}
        sql_data = parameters.get("sql_data", None)
        if sql_data is None or not isinstance(sql_data, dict) or ("error_message" in sql_data.keys() and len(sql_data["error_message"].strip()) > 0):
            sql_data = self.stock_db_query_workflow.execute(query, parameters=parameters)
            if sql_data is None or not isinstance(sql_data, dict) or ("error_message" in sql_data.keys() and len(sql_data["error_message"].strip()) > 0):
                try:
                    self.status = {"state": "failed", "error": sql_data["error_message"]}
                except:
                    self.status = {"state": "failed", "error": "Unable to execute the SQL Queries"}
                return sql_data
        history = None
        if parameters is not None and "history" in parameters.keys():
            history = parameters.get("history", None)
        
        # prompts
        sys_tpl, user_tpl = self.prompt_service.get_prompts(
            sys_prompt_id="BDCFG0GF45",
            sys_prompt_version="1",
            user_prompt_id="2SX9C1PLOK",
            user_prompt_version="1",
        )
        system_prompt = sys_tpl.format(dataframe=sql_data)
        user_prompt = user_tpl.format(question=query, conversation=history)
        
        analysis_output = self.agent_manager.generate_response(self.llm, user_prompt, {"system_prompt": system_prompt, "parser": JsonOutputParser()})
        if 'analysis' in analysis_output:
            sql_data["explanation"] = clean_up_generated_text(analysis_output['analysis'])
        self.status = {"state": "completed"}
        
        return sql_data
