import datetime
from typing import Dict, Any, Optional
from langchain_core.output_parsers import JsonOutputParser

from NewsAgents.infrastructure.llm.llm_base import LLMModel
from NewsAgents.infrastructure.llm.agent_manager import AgentManager
from NewsAgents.application.services.prompt_service import PromptService
from NewsAgents.infrastructure.data.plugins.SQL_plugin import SQLQueryPlugin
from NewsAgents.business.interfaces.workflow_interface import WorkflowInterface
from NewsAgents.services.aws_credentials import AWSCredentialsProvider

class StockDBQueryWorkflow(WorkflowInterface[str, str]):
    """
    A workflow that queries Stock Data from RDS based on user Question.
    """
    def __init__(self, agent_manager: AgentManager, prompt_service: PromptService, llm: LLMModel, aws_creds: Dict[str, Any]):
        """
        Initialize the news query workflow.
        
        Args:
            agent_manager: Manager for LLM agent interactions
        """
        self.agent_manager = agent_manager
        self.prompt_service = prompt_service
        if aws_creds is None or len(aws_creds.keys()) == 0:
            self.renew_sql_query_plugin()
        else:
            self.table_name = aws_creds["STOCK_DATA_TABLE_NAME"]
            db_host, db_username, db_pass, db_name = aws_creds["MYSQL_DB_HOST"], aws_creds["MYSQL_DB_USER"], aws_creds["MYSQL_DB_PASS"], aws_creds["MYSQL_DB_NAME"]
            self.sql_plugin = SQLQueryPlugin(db_host, db_username, db_pass, db_name)
        self.llm = llm
        self.status = {"state": "idle"}
    
    def renew_sql_query_plugin(self):
        aws_credential_provider = AWSCredentialsProvider()
        aws_creds = aws_credential_provider.get_credentials()
        self.table_name = aws_creds["STOCK_DATA_TABLE_NAME"]
        db_host, db_username, db_pass, db_name = aws_creds["MYSQL_DB_HOST"], aws_creds["MYSQL_DB_USER"], aws_creds["MYSQL_DB_PASS"], aws_creds["MYSQL_DB_NAME"]
        self.sql_plugin = SQLQueryPlugin(db_host, db_username, db_pass, db_name)
    
    def get_column_definitions(self, stock_data_system_prompt: str) -> Dict[str, Any]:
        ret = {}
        if stock_data_system_prompt is None or len(stock_data_system_prompt.strip()) == 0:
            if self.prompt_service is None:
                return ret
            stock_data_system_prompt = self.prompt_service.manager._fetch_prompt(prompt_id="RT94K576N5", prompt_version="2")
        if stock_data_system_prompt is None or len(stock_data_system_prompt.strip()) == 0:
            return ret
        schema_txt = stock_data_system_prompt.split("<Schema>")[-1].split("</Schema>")[0]
        for schema_val in schema_txt.splitlines():
            schema_val = schema_val.strip()
            if len(schema_val) == 0:
                continue
            col_def = schema_val.split(", - ")[-1].strip()
            if col_def is None or len(col_def) == 0:
                continue
            col_name = schema_val.split('"')[1::2]
            if len(col_name) == 0:
                continue
            col_name = col_name[0].strip()
            if col_name is None or len(col_name) == 0:
                continue
            ret[col_name] = col_def
        return ret
    
    def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None, has_retried: bool = False) -> Dict[str, Any]:
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
        sql_query = None
        if parameters is not None:
            if "user_hardset_indicators" in parameters.keys():
                user_hardset_indicators = parameters.get("user_hardset_indicators")
            if "history" in parameters.keys():
                history = parameters.get("history")
            if "sql_query" in parameters.keys():
                sql_query = parameters.get("sql_query")
        system_prompt = None
        if sql_query is None or len(sql_query.strip()) == 0:
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
            sql_query = self.agent_manager.generate_response(self.llm, user_prompt, {"system_prompt": system_prompt, "parser": JsonOutputParser()})["llm_stock_sql_query"]
        sql_data = self.sql_plugin.process_query(sql_query, is_update_query=False)
        self.sql_plugin.close_connection()
        if sql_data is not None and "error_message" in sql_data.keys() and str(sql_data["error_message"]).endswith("Unable to Connect to DB."):
            self.renew_sql_query_plugin()
            sql_data = self.sql_plugin.process_query(sql_query, is_update_query=False)
            self.sql_plugin.close_connection()
        if sql_data is None:
            self.status = {"state": "failed", "error": "Returned None Data from DB SQL Query"}
            return {"error_message": "Returned None Data from DB SQL Query", "rds_data": [], "rds_columns": []}
        if "error_message" in sql_data.keys() and len(sql_data["error_message"].strip()) > 0:
            if str(sql_data["error_message"]).lower().startswith("unable to connect"):
                if not has_retried:
                    obj = StockDBQueryWorkflow(self.agent_manager, self.prompt_service, self.llm, aws_creds=None)
                    parameters["sql_query"] = sql_query
                    sql_data = obj.execute(query, parameters=parameters, has_retried=True)
            if sql_data is None:
                self.status = {"state": "failed", "error": "Returned None Data from DB SQL Query"}
                return {"error_message": "Returned None Data from DB SQL Query", "rds_data": [], "rds_columns": []}
            if "error_message" in sql_data.keys() and len(sql_data["error_message"].strip()) > 0:
                self.status = {"state": "failed", "error": sql_data["error_message"]}
            return sql_data
        sql_data["rds_column_definitions"] = []
        col_def_map = self.get_column_definitions(system_prompt)
        for col_name in sql_data["rds_columns"]:
            if col_name not in col_def_map.keys():
                continue
            tmp = {"column_name": col_name, "column_def": col_def_map[col_name]}
            sql_data["rds_column_definitions"].append(tmp)
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