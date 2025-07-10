import json
from typing import Dict, Any, Optional

from NewsAgents.infrastructure.llm.agent_manager import AgentManager
from NewsAgents.infrastructure import SQLQueryPlugin, is_valid_input
from NewsAgents.business.interfaces.workflow_interface import WorkflowInterface
from NewsAgents.services.aws_credentials import AWSCredentialsProvider

DB_COL_MAX_CHAR_LIMIT = 255

class BarronsUserFeedBackWorkflow(WorkflowInterface[str, str]):
    """
    A workflow that stores and fetches user feedback.
    """
    def __init__(self, agent_manager: AgentManager):
        """
        Initialize the User Feedback workflow.
        
        Args:
            agent_manager: Manager for LLM agent interactions
        """
        self.agent_manager = agent_manager
        self.aws_credential_provider = AWSCredentialsProvider()
        aws_creds = self.aws_credential_provider.get_credentials()
        self.table_name = "barrons_user_feedback_maf"
        db_host, db_username, db_pass, db_name = aws_creds["MYSQL_DB_HOST"], aws_creds["MYSQL_DB_USER"], aws_creds["MYSQL_DB_PASS"], aws_creds["MYSQL_DB_NAME"]
        self.sql_plugin = SQLQueryPlugin(db_host, db_username, db_pass, db_name)
        self.status = {"state": "idle"}
        self.create_feedback_table_if_not_exists()
    
    def create_feedback_table_if_not_exists(self) -> Dict[str, Any]:
        if self.sql_plugin is None:
            return {"error_message": "Unable to connect to Database"}
        feedback_table_creation_query = "CREATE TABLE IF NOT EXISTS "+self.table_name+" (id int NOT NULL AUTO_INCREMENT PRIMARY KEY, "
        feedback_table_creation_query += "message_id VARCHAR(64), user_email VARCHAR(50), session_id VARCHAR(64), "
        feedback_table_creation_query += "feedback_type BOOLEAN DEFAULT FALSE, feedback_comments VARCHAR("+str(DB_COL_MAX_CHAR_LIMIT)+"), "
        feedback_table_creation_query += "preset_options JSON, "
        feedback_table_creation_query += "last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP);"
        return self.sql_plugin.process_query(feedback_table_creation_query)
    
    def add_update_user_feedback(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ret = {}
        if query is None or len(query.strip()) == 0:
            ret["error_message"] = "Invalid Input Query"
            return ret
        message_id = parameters.get("message_id", "")
        session_id = parameters.get("session_id", "")
        for s in [message_id, session_id]:
            validation_str = is_valid_input(s)
            if len(validation_str.strip()) > 0:
                ret["error_message"] = validation_str
                return ret
        user_email = parameters.get("user_email", "")
        preset_options = parameters.get("preset_options", [])
        feedback_comments = parameters.get("feedback_comments", "")
        feedback_type = parameters.get("feedback_type", False)
        if user_email is None or len(user_email.strip()) == 0:
            user_email = "staging_env"
        if feedback_comments is not None and (len(feedback_comments) > DB_COL_MAX_CHAR_LIMIT):
            feedback_comments = feedback_comments[:DB_COL_MAX_CHAR_LIMIT]
        if user_email is not None and len(user_email) > 50:
            user_email = user_email[:50]
        if session_id is not None and len(session_id) > 64:
            session_id = session_id[:64]
        feedback_id = parameters.get("feedback_id", None)
        if feedback_id is None:
            feedback_query = "INSERT INTO "+self.table_name+" (message_id, user_email, session_id, feedback_comments, feedback_type, preset_options) VALUES (%s, %s, %s, %s, %s, %s);"
            ret = self.sql_plugin.process_query(feedback_query, input_values=(message_id, user_email, session_id, feedback_comments, feedback_type, json.dumps(preset_options)), is_update_query=True)
            if "updated_id" in ret.keys():
                ret["feedback_id"] = ret["updated_id"]
                del ret["updated_id"]
        else:
            feedback_query = "UPDATE barrons_user_feedback SET "
            feedback_query += "feedback_comments=%s, feedback_type=%s, preset_options=%s WHERE id=%s"
            feedback_query += "message_id=%s AND user_email=%s AND session_id=%s;"
            ret = self.sql_plugin.process_query(feedback_query, input_values=(feedback_comments, feedback_type, json.dumps(preset_options), feedback_id, message_id, user_email, session_id))
            ret["feedback_id"] = feedback_id
        em = ret.get("error_message", None)
        if em is None or len(em.strip()) == 0:
            ret["message_id"] = message_id
            ret["user_email"] = user_email
            ret["session_id"] = session_id
            ret["preset_options"] = preset_options
            ret["feedback_comments"] = feedback_comments
            ret["feedback_type"] = feedback_type
        return ret
    
    def fetch_user_feedback(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ret = {}
        if query is None or len(query.strip()) == 0:
            ret["error_message"] = "Invalid Input Query"
            return ret
        sql_query = "SELECT * FROM "+self.table_name+" where "
        query_args = []
        if "users" in parameters.keys() and isinstance(parameters["users"], list):
            sql_query += "user_email IN ("+", ".join(["%s"]*len(parameters["users"]))+")"
            query_args.extend(parameters["users"])
        else:
            sql_query += "user_email IS NOT NULL AND user_email != '' AND user_email != 'staging_env'"
        if "minDate" in parameters.keys():
            sql_query += " AND Date(last_updated) >= %s" #+str(filters["minDate"])
            query_args.append(parameters["minDate"])
        if "maxDate" in parameters.keys():
            sql_query += " AND Date(last_updated) < %s" #+str(filters["maxDate"])
            query_args.append(parameters["maxDate"])
        if "sessionIds" in parameters.keys() and isinstance(parameters["sessionIds"], list):
            sql_query += " AND session_id IN ("+", ".join(["%s"]*len(parameters["sessionIds"]))+")"
            query_args.extend(parameters["sessionIds"])
        if "feedback_type" in parameters.keys() and isinstance(parameters["feedback_type"], bool):
            sql_query += " AND feedback_type=%s" #+str(filters["feedback_type"])
            query_args.append(parameters["feedback_type"])
        sql_query += ";"
        return self.sql_plugin.process_query(sql_query, input_values=query_args, is_update_query=False)
    
    def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ret = {}
        if query is None or len(query.strip()) == 0:
            ret["error_message"] = "Invalid Input Query"
            return ret
        is_fetch_query = parameters.get("is_fetch_query", False)
        if not is_fetch_query:
            ret = self.add_update_user_feedback(query, parameters)
        else:
            ret = self.fetch_user_feedback(query, parameters)
        return ret

