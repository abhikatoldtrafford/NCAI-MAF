import re
import pymysql
import sqlparse
from typing import Dict, Any, Optional, Union

from NewsAgents.infrastructure.data.plugins.plugin_interface import DataPluginInterface


def is_valid_sql(query) -> bool:
    try:
        # Parse the query
        parsed = sqlparse.parse(query)
        # Check if it's empty or invalid
        if not parsed:
            return False
        # Ensure it contains valid tokens
        for statement in parsed:
            if not statement.tokens:
                return False
        return True
    except Exception:
        # If an error occurs, it's not valid SQL
        return False

def is_malicious_input(user_input):
    # Patterns for SQL injection detection
    sql_patterns = [
        r"(\bor\b|\band\b)[\s]*(\d+=[\d\w])",  # OR 1=1 or AND conditions
        r"(union select|select.*from)",         # UNION SELECT or SELECT queries
        r"(--|#)",                              # SQL comment indicators
        r"('|\"|;)",                            # Suspicious single/double quotes or semicolon
        r"(?i)(insert|update|delete|drop|alter|create|exec|execute|shutdown|xp_cmdshell|sp_|declare)"  # Dangerous SQL keywords
    ]

    # Patterns for XSS detection
    xss_patterns = [
        r"<[^>]+>",                              # HTML tags
        r"(?i)(script|onload|onerror|alert|document\.cookie|eval|javascript:)"  # Suspicious XSS keywords
    ]

    # Combine all patterns
    MALICIOUS_PATTERNS = sql_patterns + xss_patterns
    for pattern in MALICIOUS_PATTERNS:
        if re.search(pattern, user_input, re.IGNORECASE):
            return True
    return False

def is_valid_input(input_str: str) -> str:
    if input_str is None or len(input_str.strip()) == 0:
        return "Empty String"
    # if is_valid_sql(input_str):
        # return "Malicious Input detected as \""+str(input_str)+"\""
    # if is_malicious_input(input_str):
    #     return "Malicious Input detected as \""+str(input_str)+"\""
    return ""

class SQLQueryPlugin(DataPluginInterface):
    def __init__(self, host: str, user: str, db_pwd: str, db_name: str):
        self.host = host
        self.user = user
        self.db_pwd = db_pwd
        self.db_name = db_name
        self.connection = None
    
    def get_connection(self):
        if self.connection is not None:
            if not self.connection.open:
                self.connection.ping(reconnect=True)
            return self.connection
        try:
            self.connection = pymysql.connect(host=self.host, user=self.user, password=self.db_pwd, db=self.db_name)
        except Exception as e:
            print("Unable to connect to database due to : "+str(e))
            return None
        return self.connection
    
    def close_connection(self):
        if self.connection is not None and self.connection.open:
            self.connection.close()
    
    def process_query(self, query: str, is_update_query: bool = True, input_values: Union[list, tuple, dict] = None, retry_count: int = 0) -> Dict[str, Any]:
        ret = {}
        if query is None or len(query.strip()) == 0:
            ret["error_message"] = "Empty or None SQL Query provided as input"
            return ret
        if not is_valid_sql(query):
            ret["error_message"] = "Invalid SQL Query provided as input"
            return ret
        con = self.get_connection()
        if con is None:
            print("Unable to connect to database.")
            ret["error_message"] = "Internal Server Error. Unable to Connect to DB."
            return ret
        cursor = con.cursor()
        try:
            cursor.execute(query, args=input_values)
            if is_update_query:
                con.commit()
                ret["updated_id"] = cursor.lastrowid
            else:
                data = cursor.fetchall()
                column_names = [description[0] for description in cursor.description]
                ret["rds_data"] = [list(d) for d in data]
                ret["rds_columns"] = column_names
        except Exception as e:
            if retry_count > 3:
                print("Maximum Retry count reached")
                ret["error_message"] = "Got Error while executing query as : "+str(e)
                return ret
            if "doesn't exist" not in str(e):
                ret = self.process_query(query, is_update_query=is_update_query, input_values=input_values, retry_count=retry_count+1)
        finally:
            cursor.close()
        return ret
    
    def validate_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        return is_valid_sql(query)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "name": "SQL Query Plugin",
            "description": "Plugin for processing SQL queries",
            "capabilities": ["Execute SQL Queries"]
        }

