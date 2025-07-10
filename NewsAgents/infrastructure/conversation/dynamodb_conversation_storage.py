from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from NewsAgents.infrastructure.conversation.storage_interface import ConversationStorageInterface
from NewsAgents.infrastructure.data.plugin_manager import PluginManager
from NewsAgents.infrastructure.data.plugins.Dynamo_DB_plugin import _to_ddb_attr, _from_ddb_attr
import boto3
import json


class DynamoDBConversationStorage(ConversationStorageInterface):
    """
    DynamoDB implementation of conversation storage.
    """

    def __init__(self, plugin_manager: PluginManager, aws_creds: Dict[str, Any]):
        """
        Initialize the DynamoDB conversation storage.

        Args:
            plugin_manager: The plugin manager
            conversation_table: Name of the conversations table
            message_table: Name of the messages table
        """
        self.plugin_manager = plugin_manager
        if aws_creds is None:
            aws_creds = {}
        self.conversation_table = aws_creds.get("dynamo_db_conversation_table_name", None)
        self.conversation_table_index = aws_creds.get("dynamo_db_conversation_table_index_name", None)
        self.user_message_table = aws_creds.get("dynamo_db_user_message_table_name", None)
        self.user_message_table_index = aws_creds.get("dynamo_db_user_message_table_indexname", None)
        self.llm_message_table = aws_creds.get("dynamo_db_llm_message_table_name", None)
        self.llm_message_table_index = aws_creds.get("dynamo_db_llm_message_table_indexname", None)
        self.generic_keys = ["last_updated", "ttl", "created_at"]

        if not plugin_manager.get_plugin("dynamodb"):
            raise ValueError("DynamoDB plugin not registered in plugin manager")
    
    def create_item_id(self, parameters: Dict[str, Any]) -> str:
        ret = ""
        if parameters is None:
            return ret
        for k in ["conversation_id", "session_id", "request_id", "message_id"]:
            v = parameters.get(k, "")
            if self.is_valid_query(v):
                ret += v
        return ret
    
    def is_valid_query(self, query: str) -> bool:
        if query is None or len(query.strip()) == 0:
            return False
        return True
    
    def _execute_query(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a DynamoDB operation using the plugin.

        Args:
            operation: The operation type
            parameters: Operation parameters

        Returns:
            Operation result
        """
        return self.plugin_manager.execute_query(query, parameters)
    
    def get_conversation_details(self, user_id: str, conversation_id: str) -> List[Dict[str, Any]]:
        ret = []
        if user_id is None or len(user_id.strip()) == 0:
            return ret
        if conversation_id is None or len(conversation_id.strip()) == 0:
            return ret
        params = {
            "fetch_data": True,
            "primary_key_name": "user_id",
            "table_name": self.conversation_table,
            "index_name": self.conversation_table_index,
            "filters": {"user_id": user_id, "conversation_id": conversation_id},
            "plugin": "dynamodb"
        }
        result = self._execute_query(None, params)
        if result.get("error_message") or not result.get("data"):
            return ret
        data = self.normalize_conversation_messages(result.get("data"))
        return data
    
    def convert_messages_to_conversation(self, user_id: str, data, ignore_single_messages: bool = False) -> Dict[str, Any]:
        user_id_conversation_map = {}
        if data is None or len(data) == 0:
            return user_id_conversation_map
        for d in data:
            user_id = user_id
            if "user_id" in d.keys():
                user_id = d["user_id"]
                del d["user_id"]
            if user_id not in user_id_conversation_map.keys():
                user_id_conversation_map[user_id] = {}
            conversation_id = "conversation-id-NA"
            if "conversation_id" in d.keys():
                conversation_id = d["conversation_id"]
                del d["conversation_id"]
            if conversation_id not in user_id_conversation_map[user_id].keys():
                user_id_conversation_map[user_id][conversation_id] = []
            if "search_data" in d.keys():
                del d["search_data"]
            for d_key in ["query_data", "rds_data", "rds_column_definitions"]:
                if d_key in d.keys() and isinstance(d[d_key], str):
                    try:
                        d[d_key] = json.loads(str(d[d_key]))
                    except (json.JSONDecodeError, ValueError):
                        pass
            user_id_conversation_map[user_id][conversation_id].append(d)
        all_users = []
        for u in user_id_conversation_map.keys():
            this_u = {"user_id": u}
            all_conversations = []
            for c in user_id_conversation_map[u].keys():
                this_conv = {"conversation_id": c}
                for m in user_id_conversation_map[u][c]:
                    for cd_key in ["conversation_title", "created_at", "last_updated"]:
                        if cd_key not in this_conv.keys():
                            cd_val = m.get(cd_key, None)
                            if cd_val is not None:
                                this_conv[cd_key] = cd_val
                                del m[cd_key]
                if "conversation_title" not in this_conv.keys():
                    all_conv_details = self.get_conversation_details(u, c)
                    for c1 in all_conv_details:
                        c1_uid = c1.get("user_id", None)
                        if c1_uid is None or not isinstance(c1_uid, str) or len(c1_uid.strip()) == 0 or c1_uid != u:
                            continue
                        c1_cid = c1.get("conversation_id", None)
                        if c1_cid is None or not isinstance(c1_cid, str) or len(c1_cid.strip()) == 0 or c1_cid != c:
                            continue
                        for k1, v1 in c1.items():
                            if k1 in ["user_id", "conversation_id"]:
                                continue
                            this_conv[k1] = v1
                this_conv["messages"] = []
                for m in user_id_conversation_map[u][c]:
                    if len(list(m.keys() - set(self.generic_keys))) > 0:
                        this_conv["messages"].append(m)
                if ignore_single_messages and len(this_conv["messages"]) < 2:
                    continue
                all_conversations.append(this_conv)
            this_u["conversations"] = all_conversations
            all_users.append(this_u)
        return {"users": all_users}
    
    def normalize_conversation_messages(self, data, sort_ascending: bool = False) -> List:
        all_items = []
        if data is None or len(data) == 0:
            return all_items
        for ai in data:
            if ai is None or not isinstance(ai, dict):
                continue
            tmp = {}
            for k2, v2 in ai.items():
                tmp[k2] = _from_ddb_attr(v2)
            if "created_at" in tmp.keys():
                tmp["created_at"] = datetime.fromisoformat(tmp["created_at"])
            if "last_updated" in tmp.keys():
                tmp["last_updated"] = datetime.fromtimestamp(tmp["last_updated"])
            all_items.append(tmp)
        all_items = sorted(all_items, key=lambda item: item["last_updated"], reverse= not sort_ascending)
        return all_items
    
    def fetch_llm_conversations(self, user_id: str, conversation_id: str, limit: Optional[int] = None, last_evaluated_key = None) -> List[Dict[str, Any]]:
        if not self.is_valid_query(user_id):
            return {"error_message": "Invalid User Id provided for fetching conversation."}
        if not self.is_valid_query(conversation_id):
            return {"error_message": "Invalid Conversation Id provided for fetching conversation."}
        params = {
            "fetch_data": True,
            "primary_key_name": "user_id",
            "table_name": self.llm_message_table,
            "index_name": self.llm_message_table_index,
            "plugin": "dynamodb"
        }
        if conversation_id is None or len(conversation_id.strip()) == 0:
            params["filters"] = {"user_id": user_id}
        else:
            params["filters"] = {"user_id": user_id, "conversation_id": conversation_id}
        if limit is not None:
            params["limit"] = limit
        if last_evaluated_key is not None:
            params["last_evaluated_key"] = last_evaluated_key
        result = self._execute_query(None, params)
        if result.get("error_message") or not result.get("data"):
            return result
        ret = self.convert_messages_to_conversation(user_id, self.normalize_conversation_messages(result.get("data"), sort_ascending=True))
        history = []
        for u in ret["users"]:
            if u["user_id"] != user_id:
                continue
            for c in u["conversations"]:
                if c["conversation_id"] != conversation_id:
                    continue
                for m in c["messages"]:
                    tmp_h = {**m}
                    for k in ["created_at", "last_updated", "ttl", "item_id"]:
                        try:
                            del tmp_h[k]
                        except KeyError:
                            pass
                    history.append(tmp_h)
        ret["history"] = history
        ret["last_evaluated_key"] = None
        if "last_evaluated_key" in result.keys():
            ret["last_evaluated_key"] = result["last_evaluated_key"]
        return ret
    
    def get_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        return self.get_conversations_for_user("test-user", conversation_id, limit)

    def get_conversations_for_user(self, user_id: str, conversation_id: str, limit: Optional[int] = None, last_evaluated_key = None) -> List[Dict[str, Any]]:
        if not self.is_valid_query(user_id):
            return {"error_message": "Invalid User Id provided for fetching conversation."}
        params = {
            "fetch_data": True,
            "primary_key_name": "user_id",
            "plugin": "dynamodb"
        }
        only_conversations = False
        if conversation_id is None or len(conversation_id.strip()) == 0:
            params["table_name"] = self.conversation_table
            params["index_name"] = self.conversation_table_index
            params["filters"] = {"user_id": user_id}
            only_conversations = True
        else:
            params["table_name"] = self.user_message_table
            params["index_name"] = self.user_message_table_index
            params["filters"] = {"user_id": user_id, "conversation_id": conversation_id}
        if limit is not None:
            params["limit"] = limit
        if last_evaluated_key is not None:
            params["last_evaluated_key"] = last_evaluated_key
        result = self._execute_query(None, params)
        if result.get("error_message") or not result.get("data"):
            return result
        ret = self.convert_messages_to_conversation(user_id, self.normalize_conversation_messages(result.get("data"), sort_ascending=False), ignore_single_messages=not only_conversations)
        ret["last_evaluated_key"] = None
        if "last_evaluated_key" in result.keys():
            ret["last_evaluated_key"] = result["last_evaluated_key"]
        return ret
    
    def search_conversations(self, user_id: str, search_query: str, conversation_id: str, limit: Optional[int] = None, last_evaluated_key = None) -> List[Dict[str, Any]]:
        if not self.is_valid_query(user_id):
            return {"error_message": "Invalid User Id provided for searching conversation."}
        if not self.is_valid_query(search_query):
            return {"error_message": "Invalid Search Query provided for searching conversation."}
        if len(search_query.strip()) < 3:
            return {"error_message": "Search Query too Small to search anything."}
        params = {
            "fetch_data": True,
            "primary_key_name": "user_id",
            "table_name": self.user_message_table,
            "index_name": self.user_message_table_index,
            "filters": {"user_id": user_id},
            "search_query_field_name": "search_data",
            "plugin": "dynamodb"
        }
        if conversation_id is not None:
            params["filters"]["conversation_id"] = conversation_id
        if limit is not None:
            params["limit"] = limit
        if last_evaluated_key is not None:
            params["last_evaluated_key"] = last_evaluated_key
        result = self._execute_query(search_query.lower(), params)
        if result.get("error_message") or not result.get("data"):
            return result
        ret = self.convert_messages_to_conversation(user_id, self.normalize_conversation_messages(result.get("data"), sort_ascending=False))
        ret["last_evaluated_key"] = None
        if "last_evaluated_key" in result.keys():
            ret["last_evaluated_key"] = result["last_evaluated_key"]
        return ret
    
    def create_conversation(self, user_id: str, conversation_id: str, conversation_title: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.is_valid_query(user_id):
            return {"error_message": "Invalid User Id provided for fetching conversation."}
        if not self.is_valid_query(conversation_id):
            return {"error_message": "Invalid Conversation Id provided for fetching conversation."}
        if not self.is_valid_query(conversation_title):
            return {"error_message": "Invalid Conversation Title provided for fetching conversation."}
        params = {
            "fetch_data": True,
            "primary_key_name": "user_id",
            "table_name": self.conversation_table,
            "index_name": self.conversation_table_index,
            "filters": {"user_id": user_id, "conversation_id": conversation_id},
            "plugin": "dynamodb"
        }
        result = self._execute_query(None, params)
        del params["fetch_data"]
        del params["filters"]
        del params["index_name"]
        if result.get("error_message") or not result.get("data"):
            #Create New Conversation
            now = datetime.now()
            if metadata is None:
                metadata = {}
            put_item = {
                "user_id": _to_ddb_attr(user_id),
                "conversation_id": _to_ddb_attr(conversation_id),
                "conversation_title": _to_ddb_attr(conversation_title),
                "created_at": _to_ddb_attr(now.isoformat()),
                "last_updated": _to_ddb_attr(int(now.timestamp())), #used for sorting
                "ttl": _to_ddb_attr(int((now + timedelta(days=30)).timestamp())) # 30-day TTL
            }
            if metadata is not None and len(metadata.keys()) > 0:
                put_item["metadata"] = {"M": {k: _to_ddb_attr(v) for k, v in metadata.items()}}
            params["put_item"] = put_item
            params["store_data"] = True
            result = self._execute_query(None, params)
            if result.get("error_message", None):
                raise Exception(f"Failed to create conversation: {result.get('error_message')}")
            return result
        else:
            #Update last_updated column
            params["update_data"] = True
            params["sort_key_name"] = "conversation_id"
            params["updates"] = {"user_id": user_id, "conversation_id": conversation_id, "last_updated": int(datetime.now().timestamp())}
            result = self._execute_query(None, params)
            if result.get("error_message", None):
                raise Exception(f"Failed to Update conversation: {result.get('error_message')}")
            return result
        
    def add_message(self, data: str, parameters: Optional[Dict[str, Any]] = None):
        if not self.is_valid_query(data):
            return {"error_message": "Invalid data Provided for adding message to the conversation."}
        if parameters is None or len(parameters.keys()) == 0:
            return {"error_message": "Invalid Details Provided for adding message to the conversation."}
        user_id = parameters.get("user_id", "")
        if not self.is_valid_query(user_id):
            return {"error_message": "Invalid User ID Provided for adding message to the conversation."}
        conversation_id = parameters.get("conversation_id", "")
        if not self.is_valid_query(conversation_id):
            return {"error_message": "Invalid Conversation ID Provided for adding message to the conversation."}
        now = datetime.now()
        put_item = {
            "user_id": _to_ddb_attr(user_id),
            "item_id": _to_ddb_attr(self.create_item_id(parameters)),
            "conversation_id": _to_ddb_attr(conversation_id),
            "query_data": _to_ddb_attr(data),
            "search_data": _to_ddb_attr(str(data).lower()),
            "created_at": _to_ddb_attr(now.isoformat()),
            "last_updated": _to_ddb_attr(int(now.timestamp())), #used for sorting
            "ttl": _to_ddb_attr(int((now + timedelta(days=30)).timestamp())) # 30-day TTL
        }
        session_id = parameters.get("session_id", "")
        if session_id is not None and isinstance(session_id, str) and len(session_id.strip()) > 0:
            put_item["session_id"] = _to_ddb_attr(session_id)
        request_id = parameters.get("request_id", "")
        if request_id is not None and isinstance(request_id, str) and len(request_id.strip()) > 0:
            put_item["request_id"] = _to_ddb_attr(request_id)
        query_type = parameters.get("query_type", "")
        if query_type is not None and isinstance(query_type, str) and len(query_type.strip()) > 0:
            put_item["query_type"] = _to_ddb_attr(query_type)
        message_id = parameters.get("message_id", "")
        if message_id is not None and isinstance(message_id, str) and len(message_id.strip()) > 0:
            put_item["message_id"] = _to_ddb_attr(message_id)
        metadata = parameters.get("metadata", {})
        if metadata is not None and len(metadata.keys()) > 0:
            put_item["metadata"] = {"M": {k: _to_ddb_attr(v) for k, v in metadata.items()}}
        if "rds_data" in parameters.keys():
            put_item["rds_data"] = _to_ddb_attr(parameters.get("rds_data", {}))
        if "rds_columns" in parameters.keys():
            put_item["rds_columns"] = _to_ddb_attr(parameters.get("rds_columns", {}))
        if "rds_column_definitions" in parameters.keys():
            put_item["rds_column_definitions"] = _to_ddb_attr(parameters.get("rds_column_definitions", {}))
        result = self._execute_query(None, {
            "store_data": True,
            "table_name": self.user_message_table,
            "put_item": put_item,
            "plugin": "dynamodb"
        })
        if result.get("error_message", None):
            raise Exception(f"Failed to add Message to the conversation: {result.get('error_message')}")
        return result
    
    def add_llm_message(self, user_id: str, conversation_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        if not self.is_valid_query(user_id):
            return {"error_message": "Invalid User Id provided for fetching conversation."}
        if not self.is_valid_query(conversation_id):
            return {"error_message": "Invalid Conversation Id provided for fetching conversation."}
        if data is None or len(data.keys()) == 0:
            return {"error_message": "Invalid Data provided for fetching conversation."}
        now = datetime.now()
        item_id = conversation_id
        put_item = {
            "user_id": _to_ddb_attr(user_id),
            "conversation_id": _to_ddb_attr(conversation_id),
            "created_at": _to_ddb_attr(now.isoformat()),
            "last_updated": _to_ddb_attr(int(now.timestamp())), #used for sorting
            "ttl": _to_ddb_attr(int((now + timedelta(days=30)).timestamp())) # 30-day TTL
        }
        if data is not None and isinstance(data, dict):
            for k,v in data.items():
                if v is not None:
                    put_item[k] = _to_ddb_attr(v)
                if k in ["message_id", "role"] and isinstance(v, str) and len(v.strip()) > 0:
                    item_id += v
            put_item["item_id"] = _to_ddb_attr(item_id)
        result = self._execute_query(None, {
            "store_data": True,
            "table_name": self.llm_message_table,
            "put_item": put_item,
            "plugin": "dynamodb"
        })
        if result.get("error_message", None):
            raise Exception(f"Failed to add LLM Message conversation: {result.get('error_message')}")
        return result

    def delete_conversation(self, user_id: str, conversation_id: str) -> bool:
        """
        Delete a conversation and its messages from DynamoDB.

        Args:
            conversation_id: The conversation ID

        Returns:
            True if deleted, False if not found
        """
        # Delete conversation
        result = self._execute_query(None, {
            "delete_data": True,
            "primary_key_name": "user_id",
            "table_name": self.user_message_table,
            "key": {"user_id": user_id, "conversation_id": conversation_id},
            "plugin": "dynamodb"
        })
        if result.get("error_message"):
            return False
        result = self._execute_query(None, {
            "delete_data": True,
            "primary_key_name": "user_id",
            "table_name": self.conversation_table,
            "key": {"user_id": user_id, "conversation_id": conversation_id},
            "plugin": "dynamodb"
        })
        if result.get("error_message"):
            return False
        result = self._execute_query(None, {
            "delete_data": True,
            "primary_key_name": "user_id",
            "table_name": self.llm_message_table,
            "key": {"user_id": user_id, "conversation_id": conversation_id},
            "plugin": "dynamodb"
        })
        if result.get("error_message"):
            return False
        return result

    def cleanup_expired(self, max_age_minutes: int) -> int:
        """
        Clean up expired conversations based on last_updated timestamp.

        Args:
            max_age_minutes: Maximum age in minutes

        Returns:
            Number of conversations deleted
        """
        cutoff = datetime.now() - timedelta(minutes=max_age_minutes)
        cutoff_str = cutoff.isoformat()

        # Scan for expired conversations
        result = self._execute_query(
            "scan",
            {
                "table_name": self.conversation_table,
                "FilterExpression": "last_updated < :cutoff",
                "ExpressionAttributeValues": {":cutoff": cutoff_str},
                "plugin": "dynamodb",
            },
        )

        if result.get("error"):
            return 0

        expired = result.get("items", [])
        deleted_count = 0

        # Delete each expired conversation
        for conversation in expired:
            if "conversation_id" in conversation:
                success = self.delete_conversation(conversation["conversation_id"])
                if success:
                    deleted_count += 1

        return deleted_count
    
    def update_metadata(self, conversation_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update metadata for a conversation in DynamoDB.
        
        Args:
            conversation_id: The conversation ID
            metadata: The metadata to update
            
        Returns:
            True if successful, False otherwise
        """
        result = self._execute_query("update_item", {
            "table_name": self.conversation_table,
            "key": {"conversation_id": conversation_id},
            "update_expression": "SET metadata = :metadata, last_updated = :timestamp",
            "expression_attribute_values": {
                ":metadata": json.dumps(metadata),
                ":timestamp": datetime.now().isoformat()
            },
            "plugin": "dynamodb"
        })
        return not bool(result.get("error"))

# @Shashi we can use this script to create the tables
def create_tables(region_name, table_prefix="", aws_access_key_id=None, aws_secret_access_key=None):
    """
    Create DynamoDB tables for conversation storage.

    Args:
        region_name: AWS region
        table_prefix: Prefix for table names
        aws_access_key_id: AWS access key ID
        aws_secret_access_key: AWS secret access key
    """
    # Create session
    session_kwargs = {"region_name": region_name}
    if aws_access_key_id and aws_secret_access_key:
        session_kwargs.update({"aws_access_key_id": aws_access_key_id, "aws_secret_access_key": aws_secret_access_key})

    session = boto3.Session(**session_kwargs)
    dynamodb = session.client("dynamodb")

    # Create conversations table
    conversations_table = f"{table_prefix}conversations"
    try:
        dynamodb.create_table(
            TableName=conversations_table,
            KeySchema=[{"AttributeName": "conversation_id", "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": "conversation_id", "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
        )
        print(f"Creating table {conversations_table}...")
        dynamodb.get_waiter("table_exists").wait(TableName=conversations_table)
        print(f"Table {conversations_table} created successfully")
    except dynamodb.exceptions.ResourceInUseException:
        print(f"Table {conversations_table} already exists")

    # Create messages table
    messages_table = f"{table_prefix}messages"
    try:
        dynamodb.create_table(
            TableName=messages_table,
            KeySchema=[
                {"AttributeName": "message_id", "KeyType": "HASH"},
                {"AttributeName": "conversation_id", "KeyType": "RANGE"},
            ],
            AttributeDefinitions=[
                {"AttributeName": "message_id", "AttributeType": "S"},
                {"AttributeName": "conversation_id", "AttributeType": "S"},
            ],
            BillingMode="PAY_PER_REQUEST",
            TimeToLiveSpecification={"Enabled": True, "AttributeName": "ttl"},
        )
        print(f"Creating table {messages_table}...")
        dynamodb.get_waiter("table_exists").wait(TableName=messages_table)
        print(f"Table {messages_table} created successfully")

        # Create GSI for retrieving messages by conversation_id
        dynamodb.update_table(
            TableName=messages_table,
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "conversation_id-timestamp-index",
                    "KeySchema": [
                        {"AttributeName": "conversation_id", "KeyType": "HASH"},
                        {"AttributeName": "timestamp", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                }
            ],
            AttributeDefinitions=[
                {"AttributeName": "conversation_id", "AttributeType": "S"},
                {"AttributeName": "timestamp", "AttributeType": "S"},
            ],
        )
        print(f"Added GSI to {messages_table}")

        dynamodb.update_table(
            TableName=conversations_table,
            AttributeDefinitions=[
                {"AttributeName": "conversation_id", "AttributeType": "S"},
                {"AttributeName": "user_id", "AttributeType": "S"},
                {"AttributeName": "last_updated", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexUpdates=[
                {
                    "Create": {
                        "IndexName": "user_id-last_updated-index",
                        "KeySchema": [
                            {"AttributeName": "user_id", "KeyType": "HASH"},
                            {"AttributeName": "last_updated", "KeyType": "RANGE"},
                        ],
                        "Projection": {"ProjectionType": "ALL"},
                        "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                    }
                }
            ],
        )
        print(f"Added GSI to {conversations_table}")

        # Create GSI for retrieving sessions by user_id

    except dynamodb.exceptions.ResourceInUseException:
        print(f"Table {messages_table} already exists")
