import datetime
from typing import Dict, Any, Optional
from langchain_core.output_parsers import JsonOutputParser

from infrastructure.llm.llm_base import LLMModel
from infrastructure.llm.agent_manager import AgentManager
from application.services.prompt_service import PromptService
from infrastructure.data.plugins.SQL_plugin import SQLQueryPlugin
from business.interfaces.workflow_interface import WorkflowInterface
from business.barrons.services.aws_credentials import AWSCredentialsProvider


class StockDBQueryWorkflow(WorkflowInterface[str, str]):
    """
    A workflow that queries Stock Data from RDS based on user Question.
    """
    def __init__(self, agent_manager: AgentManager, prompt_service: PromptService, llm: LLMModel):
        """
        Initialize the news query workflow.
        
        Args:
            agent_manager: Manager for LLM agent interactions
        """
        self.agent_manager = agent_manager
        self.prompt_service = prompt_service
        self.aws_credential_provider = AWSCredentialsProvider()
        aws_creds = self.aws_credential_provider.get_credentials()
        self.table_name = aws_creds["STOCK_DATA_TABLE_NAME"]
        db_host, db_username, db_pass, db_name = aws_creds["MYSQL_DB_HOST"], aws_creds["MYSQL_DB_USER"], aws_creds["MYSQL_DB_PASS"], aws_creds["MYSQL_DB_NAME"]
        self.sql_plugin = SQLQueryPlugin(db_host, db_username, db_pass, db_name)
        self.llm = llm
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
        if self.agent_manager is None:
            self.agent_manager = AgentManager()
        self.status = {"state": "processing"}
        user_hardset_indicators = []
        history = None
        if parameters is not None:
            if "user_hardset_indicators" in parameters.keys():
                user_hardset_indicators = parameters.get("user_hardset_indicators")
            if "history" in parameters.keys():
                history = parameters.get("history")
        
		# prompt defaults
        if self.table_name is None or len(self.table_name.strip()) == 0:
            self.table_name = "stock_analysis_data"
        table_name = self.table_name.strip()
        yesterday = datetime.date.today() - datetime.timedelta(days=1)
        formatted_date = yesterday.strftime("%B %d, %Y")
        
		# prompts
        sys_tpl, user_tpl = self.prompt_service.get_prompts(
            sys_prompt_id="RT94K576N5", sys_prompt_version="2", user_prompt_id="MRUK3G8TQW", user_prompt_version="1"
        )
        system_prompt = sys_tpl.format(table_name=table_name, formatted_date=formatted_date)
        user_prompt = user_tpl.format(
            question=query,
            conversation=history,
            indicator_list=user_hardset_indicators,
        )
        
        sql_query_llm_generated = self.agent_manager.generate_response(self.llm, user_prompt, {"system_prompt": system_prompt, "parser": JsonOutputParser()})["llm_stock_sql_query"]
        sql_data = self.sql_plugin.process_query(sql_query_llm_generated, is_update_query=False)
        if sql_data is None or ("error_message" in sql_data.keys() and len(sql_data["error_message"].strip()) > 0):
            self.status = {"state": "failed", "error": sql_data["error_message"]}
            return sql_data
        ticker_idx = -1
        if "Ticker" in sql_data["rds_columns"]:
            ticker_idx = sql_data["rds_columns"].index("Ticker")
        elif "Symbol" in sql_data["rds_columns"]:
            ticker_idx = sql_data["rds_columns"].index("Symbol")
        if ticker_idx >= 0:
            for row in sql_data["rds_data"]:
                row[ticker_idx] = f"https://www.barrons.com/market-data/stocks/{row[ticker_idx]}"
        self.status = {"state": "completed"}
        return sql_data
