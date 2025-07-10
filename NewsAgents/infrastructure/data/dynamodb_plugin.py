import boto3
from typing import Dict, Any
from NewsAgents.infrastructure.data.plugins.plugin_interface import DataPluginInterface


class DynamoDBPlugin(DataPluginInterface):
    """
    A DataPluginInterface implementation that routes storage calls
    (put_item, get_item, query, scan, update_item, delete_item) to boto3.
    """

    def __init__(self, region_name: str, aws_access_key_id: str = None, aws_secret_access_key: str = None):
        session_kwargs = {"region_name": region_name}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update({"aws_access_key_id": aws_access_key_id, "aws_secret_access_key": aws_secret_access_key})
        session = boto3.Session(**session_kwargs)
        self.client = session.client("dynamodb")

    def validate_query(self, query: str, parameters: Dict[str, Any]) -> bool:
        # We only handle calls where parameters["plugin"] == "dynamodb"
        return parameters.get("plugin") == "dynamodb"

    def process_query(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        table = parameters.get("table_name")
        if query == "put_item":
            return self.client.put_item(TableName=table, Item=parameters["item"])
        elif query == "get_item":
            return self.client.get_item(TableName=table, Key=parameters["key"])
        elif query == "query":
            return self.client.query(**{k: v for k, v in parameters.items() if k != "plugin"})
        elif query == "scan":
            return self.client.scan(**{k: v for k, v in parameters.items() if k != "plugin"})
        elif query == "update_item":
            return self.client.update_item(**{k: v for k, v in parameters.items() if k != "plugin"})
        elif query == "delete_item":
            return self.client.delete_item(**{k: v for k, v in parameters.items() if k != "plugin"})
        else:
            raise ValueError(f"Unsupported DynamoDB operation: {query}")

    def get_capabilities(self) -> Dict[str, Any]:
        return {"description": "DynamoDB storage plugin"}
