from typing import Dict, Any
from NewsAgents.infrastructure import SQLQueryPlugin
from NewsAgents.services.aws_credentials import AWSCredentialsProvider
from agent_workflow.providers import FunctionTool, Tool


class FetchSQLData(Tool):
    """
    Fetch SQL data from stocks database.
    """

    def __init__(self, aws_creds: Dict[str, Any], generate_sql_sys_prompt: str):
        """
        Args:
            aws_creds: AWS credentials.
            generate_sql_sys_prompt: System prompt containing stock database schema.
        """
        self.generate_sql_sys_prompt = generate_sql_sys_prompt
        if aws_creds is None or len(aws_creds.keys()) == 0:
            self.renew_sql_query_plugin()
        else:
            self.table_name = aws_creds["STOCK_DATA_TABLE_NAME"]
            db_host, db_username, db_pass, db_name = (
                aws_creds["MYSQL_DB_HOST"],
                aws_creds["MYSQL_DB_USER"],
                aws_creds["MYSQL_DB_PASS"],
                aws_creds["MYSQL_DB_NAME"],
            )
            self.sql_plugin = SQLQueryPlugin(db_host, db_username, db_pass, db_name)

    def renew_sql_query_plugin(self):
        aws_credential_provider = AWSCredentialsProvider()
        aws_creds = aws_credential_provider.get_credentials()
        self.table_name = aws_creds["STOCK_DATA_TABLE_NAME"]
        db_host, db_username, db_pass, db_name = (
            aws_creds["MYSQL_DB_HOST"],
            aws_creds["MYSQL_DB_USER"],
            aws_creds["MYSQL_DB_PASS"],
            aws_creds["MYSQL_DB_NAME"],
        )
        self.sql_plugin = SQLQueryPlugin(db_host, db_username, db_pass, db_name)

    def get_column_definitions(self) -> Dict[str, Any]:
        ret = {}
        if self.generate_sql_sys_prompt is None or len(self.generate_sql_sys_prompt.strip()) == 0:
            return ret
        schema_txt = self.generate_sql_sys_prompt.split("<Schema>")[-1].split("</Schema>")[0]
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

    async def execute(self, sql_query: str, has_retried: bool = False) -> Dict[str, Any]:
        # query the DB
        sql_data = self.sql_plugin.process_query(sql_query, is_update_query=False)
        self.sql_plugin.close_connection()

        if (
            sql_data is not None
            and "error_message" in sql_data.keys()
            and str(sql_data["error_message"]).endswith("Unable to Connect to DB.")
        ):
            self.renew_sql_query_plugin()
            sql_data = self.sql_plugin.process_query(sql_query, is_update_query=False)
            self.sql_plugin.close_connection()
        if sql_data is None:
            return {"error_message": "Returned None Data from DB SQL Query", "rds_data": [], "rds_columns": []}
        if "error_message" in sql_data.keys() and len(sql_data["error_message"].strip()) > 0:
            if str(sql_data["error_message"]).lower().startswith("unable to connect"):
                if not has_retried:
                    obj = FetchSQLData(aws_creds=None)
                    sql_data = await obj.execute(sql_query, has_retried=True)
            if sql_data is None:
                return {"error_message": "Returned None Data from DB SQL Query", "rds_data": [], "rds_columns": []}

            return sql_data

        # enrich
        sql_data["rds_column_definitions"] = []
        col_def_map = self.get_column_definitions()
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

        return sql_data

    # All properties must align with the corresponding tool in YAML
    @property
    def name(self) -> str:
        return "fetch_sql_data"

    @property
    def description(self) -> str:
        return "Runs a SQL query against the Barron's stock database, returning rows, column names, and column definitions."

    @property
    def type(self) -> str:
        return "function"

    @property
    def parameters(self) -> dict:
        return {
            "type": "object",
            "properties": {
                "sql_query": {"type": "string", "description": "SQL query to run against the stock data table"},
            },
            "required": ["sql_query"],
        }

    @property
    def asFunctionalTool(self) -> FunctionTool:
        return FunctionTool(name=self.name, description=self.description, func=self.execute)
