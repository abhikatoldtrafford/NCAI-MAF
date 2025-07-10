import json
import boto3.session
from typing import Dict, Any, Optional, List
from NewsAgents.services.aws_credentials import AWSCredentialsProvider
from NewsAgents.infrastructure.data.plugins.plugin_interface import DataPluginInterface

def _to_ddb_attr(value: Any) -> Dict[str, Any]:
    if isinstance(value, str):
        return {"S": value}
    if isinstance(value, bool):
        return {"BOOL": value}
    if isinstance(value, (int, float)):
        return {"N": str(value)}
    if isinstance(value, list) and all(isinstance(x, str) for x in value):
        return {"SS": value}
    # Fallback – store any other structure as JSON string
    return {"S": json.dumps(value)}

def _from_ddb_attr(attr: Dict[str, Any]) -> Any:
    if "S" in attr:
        return attr["S"]
    if "N" in attr:
        n = attr["N"]
        return int(n) if n.isdigit() else float(n)
    if "BOOL" in attr:
        return attr["BOOL"]
    if "SS" in attr:
        return attr["SS"]
    if "M" in attr and isinstance(attr["M"], dict):
        tmp = {}
        for k, v in attr["M"].items():
            if isinstance(v, dict):
                tmp[k] = _from_ddb_attr(v)
            else:
                tmp[k] = v
        return tmp
    return attr

class DynamoDBPlugin(DataPluginInterface):
    def __init__(self, aws_creds: Dict[str, Any]):
        if aws_creds is None or len(aws_creds.keys()) == 0:
            aws_credential_provider = AWSCredentialsProvider()
            aws_creds = aws_credential_provider.get_credentials()
        aws_access_key_id = aws_creds.get("AWS_ACCESS_KEY_ID")
        aws_secret_access_key = aws_creds.get("AWS_SECRET_ACCESS_KEY", "")
        aws_region = aws_creds.get("AWS_REGION_NAME", "")
        if self.validate_query(aws_access_key_id) and self.validate_query(aws_secret_access_key) and self.validate_query(aws_region):
            self.dynamodb = boto3.session.Session().client(
                service_name='dynamodb',
                region_name=aws_region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )
        else:
            self.dynamodb = boto3.session.Session().client("dynamodb")

    def process_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ret = {}
        if parameters is None:
            parameters = {}
        print("Dynamo DB Plugin, Got Query as : ", query)
        print("Dynamo DB Plugin, Got Parameters as : ", parameters)
        is_insert_query = parameters.get("store_data", False)
        is_update_query = parameters.get("update_data", False)
        is_fetch_query = parameters.get("fetch_data", False)
        is_delete_query = parameters.get("delete_data", False)
        if is_insert_query:
            ret = self.store_data(query, parameters)
        elif is_update_query:
            ret = self.update_data(parameters)
        elif is_fetch_query:
            ret = self.fetch_data(query, parameters)
        elif is_delete_query:
            ret = self.delete_data(query, parameters)
        else:
            ret["error_message"] = "Query Type not provided."
        print("Dynamo DB Plugin, Returning data: ", ret)
        return ret

    def store_data(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Store a text item with metadata and its embedding vector in DynamoDB.
        :param item_id: Unique identifier for the item
        :param text: The text to store
        :param metadata: A dict of metadata fields (e.g., {"category": "news", "author": "Alice", "date": datetime.now()})
        """
        ret = {}
        if parameters is None:
            ret["error_message"] = "Invalid Input Details"
            return ret
        if query is None:
            query = ""
        table_name = parameters.get("table_name", None)
        if table_name is None or len(table_name.strip()) == 0:
            ret["error_message"] = "Invalid Table Name Provided"
            return ret
        put_item = parameters.get("put_item", {})
        if put_item is None or not isinstance(put_item, dict) or len(put_item.keys()) == 0:
            ret["error_message"] = "Invalid put_item details as : "+str(put_item)
            return ret
        try:
            self.dynamodb.put_item(TableName=table_name, Item=put_item)
        except Exception as e:
            ret = {"error_message": "Got error while storing data as "+str(e)}
        return ret
    
    def delete_data(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        ret = {}
        if parameters is None:
            ret["error_message"] = "Invalid Search Criteria"
            return ret
        table_name = parameters.get("table_name", None)
        if table_name is None or len(table_name.strip()) == 0:
            ret["error_message"] = "Invalid Table Name Provided"
            return ret
        try:
            item_id = parameters.get("item_id", None)
            if self.validate_query(item_id):
                self.delete_item(table_name, item_id)
            else:
                delete_data = self.fetch_data(query, parameters)
                if delete_data is not None and "data" in delete_data.keys() and isinstance(delete_data["data"], list):
                    primary_key_name = parameters.get("primary_key_name", None)
                    use_pk = self.validate_query(primary_key_name)
                    for d_item in delete_data["data"]:
                        if d_item is None or not isinstance(d_item, dict):
                            continue
                        item_id = d_item.get("item_id", None)
                        if item_id is None or len(item_id.strip()) == 0:
                            continue
                        if use_pk:
                            self.delete_item(table_name, item_id, primary_key_name, d_item.get(primary_key_name, None))
                        else:
                            self.delete_item(table_name, item_id)
        except Exception as e:
            ret["error_message"] = "Unable to delete data due to : "+str(e)
        return ret
    
    def delete_item(self, table_name: str, item_id: str, primary_key_name: Optional[str] = None, primary_key_val: Optional[str] = None) -> Dict[str, Any]:
        ret = {}
        try:
            if self.validate_query(primary_key_name) and self.validate_query(primary_key_val):
                self.dynamodb.delete_item(TableName=table_name, Key={primary_key_name: _to_ddb_attr(primary_key_val), "item_id": _to_ddb_attr(item_id)})
            else:
                self.dynamodb.delete_item(TableName=table_name, Key={"item_id": _to_ddb_attr(item_id)})
        except Exception as e:
            ret["error_message"] = "Unable to delete data due to : "+str(e)
        return ret

    def fetch_data(self, query: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        if query is None or len(query.strip()) == 0:
            ret = self.fetch_by_metadata(parameters)
        else:
            ret = self.search_with_text_and_metadata(query, parameters)
        return ret
    
    def update_data(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        ret = {}
        if parameters is None:
            ret["error_message"] = "Invalid Search Criteria"
            return ret
        primary_key_name, primary_key_val, common_kwargs, values, conditions, sort_key_name, sort_key_val = self.get_expression_attributes_kwargs(parameters, "updates", None, None)
        if primary_key_val is None:
            ret["error_message"] = "Key Conditions not specified"
            return ret
        if len(values) == 0 or len(conditions) == 0:
            ret["error_message"] = "Nothing to Update"
            return ret
        common_kwargs["UpdateExpression"] = "SET " + ", ".join(conditions)
        pk_sk_val = {primary_key_name: _to_ddb_attr(primary_key_val)}
        if sort_key_val is not None:
            pk_sk_val[sort_key_name] = _to_ddb_attr(sort_key_val)
        resp = self.dynamodb.update_item(
            Key = pk_sk_val,
            ReturnValues='UPDATED_NEW',
            **{k: v for k, v in common_kwargs.items()}
        )
        ret["data"] = resp.get("Items", [])
        ret["last_evaluated_key"] = resp.get("LastEvaluatedKey")
        return ret
    
    def fill_common_kwargs(self, parameters: Dict[str, Any], common_kwargs: Dict[str, Any]) -> Dict[str, Any]:
        if common_kwargs is None:
            common_kwargs = {}
        table_name = parameters.get("table_name", None)
        if table_name is not None and isinstance(table_name, str) and len(table_name.strip()) > 0:
            common_kwargs["TableName"] = table_name
        limit = parameters.get("limit", None)
        if limit is not None:
            common_kwargs["Limit"] = limit
        last_evaluated_key = parameters.get("last_evaluated_key", None)
        if last_evaluated_key is not None:
            common_kwargs["ExclusiveStartKey"] = last_evaluated_key
        index_name = parameters.get("index_name", None)
        if index_name is not None and isinstance(index_name, str) and len(index_name.strip()) > 0:
            common_kwargs["IndexName"] = index_name
        return common_kwargs
    
    def get_expression_attributes_kwargs(self, parameters: Dict[str, Any], condition_key_name: str, ip_values: Optional[Dict[str, Any]] = None, ip_conditions: Optional[List[str]] = None):
        primary_key_name = parameters.get("primary_key_name", None)
        primary_key_val = None
        sort_key_name = parameters.get("sort_key_name", None)
        sort_key_val = None
        common_kwargs = self.fill_common_kwargs(parameters, common_kwargs=None)
        filter_conditions = parameters.get(condition_key_name, None)
        if filter_conditions is None or not isinstance(filter_conditions, dict) or len(filter_conditions.keys()) == 0:
            return primary_key_name, primary_key_val, common_kwargs, values, conditions, sort_key_name, sort_key_val
        filter_conditions = {k: v for k,v in parameters.get(condition_key_name, None).items()}
        if primary_key_name is not None and primary_key_name in filter_conditions.keys():
            primary_key_val = filter_conditions.get(primary_key_name)
            del filter_conditions[primary_key_name]
        if sort_key_name is not None and sort_key_name in filter_conditions.keys():
            sort_key_val = filter_conditions.get(sort_key_name)
            del filter_conditions[sort_key_name]
        names: Dict[str, str] = {}
        values = {}
        if ip_values is None and isinstance(ip_values, dict):
            for ik1, iv1 in ip_values.items():
                values[ik1] = iv1
        conditions = []
        if ip_conditions is not None and isinstance(ip_conditions, list):
            conditions.extend(ip_conditions)
        for i, (k, v) in enumerate(filter_conditions.items(), start=1):
            alias_name = f"#m{i}"
            alias_value = f":v{i}"
            names[alias_name] = k
            values[alias_value] = _to_ddb_attr(v)
            conditions.append(f"{alias_name} = {alias_value}")
        metadata_conditions = parameters.get("metadata", None)
        if metadata_conditions is not None and isinstance(metadata_conditions, dict) and len(metadata_conditions.keys()) > 0:
            if primary_key_name is not None and primary_key_name in filter_conditions.keys():
                if primary_key_val is None or len(primary_key_val.strip()) == 0:
                    primary_key_val = metadata_conditions.get(primary_key_name)
                del metadata_conditions[primary_key_name]
            for i, (k, v) in enumerate(metadata_conditions.items(), start=1):
                alias_name = f"metadata.#m{i}"
                alias_value = f":v{i}"
                names[alias_name] = k
                values[alias_value] = _to_ddb_attr(v)
                conditions.append(f"{alias_name} = {alias_value}")
        if len(values) > 0:
            common_kwargs["ExpressionAttributeValues"] = values
        if len(names) > 0:
            common_kwargs["ExpressionAttributeNames"] = names
        return primary_key_name, primary_key_val, common_kwargs, values, conditions, sort_key_name, sort_key_val

    def fetch_by_metadata(self, parameters: Dict[str, Any], ip_values: Optional[Dict[str, Any]] = None, ip_conditions: Optional[List[str]] = None, fetched_data: Optional[List] = None) -> Dict[str, Any]:
        ret = {}
        if parameters is None:
            ret["error_message"] = "Invalid Search Criteria"
            return ret
        table_name = parameters.get("table_name", None)
        if table_name is None or len(table_name.strip()) == 0:
            ret["error_message"] = "Invalid Table Name Provided"
            return ret
        filter_conditions = parameters.get("filters", None)
        if filter_conditions is None or not isinstance(filter_conditions, dict) or len(filter_conditions.keys()) == 0:
            ret["error_message"] = "No search Criteria Provided."
            return ret
        primary_key_name, primary_key_val, common_kwargs, values, conditions, sort_key_name, sort_key_val = self.get_expression_attributes_kwargs(parameters, "filters", ip_values, ip_conditions)
        filter_expression = " AND ".join(conditions)
        if len(filter_expression) > 0:
            common_kwargs["FilterExpression"] = filter_expression
        sort_ascending = parameters.get("sort_ascending", False)
        kce = f"{primary_key_name} = :pkval"
        kce_vals = {":pkval": _to_ddb_attr(primary_key_val)}
        if sort_key_val is not None:
            kce = " AND " + f"{sort_key_name} = :skval"
            kce_vals[":skval"] = _to_ddb_attr(sort_key_val)
        if primary_key_val is not None:
            if len(values) > 0:
                resp = self.dynamodb.query(
                    KeyConditionExpression= kce,
                    ExpressionAttributeValues={**values, **kce_vals},
                    ScanIndexForward=sort_ascending,
                    **{k: v for k, v in common_kwargs.items() if k != "FilterExpression" and k!= "ExpressionAttributeValues"}
                    | {"FilterExpression": filter_expression},
                )
            else:
                resp = self.dynamodb.query(
                    KeyConditionExpression=kce,
                    ExpressionAttributeValues={**kce_vals},
                    ScanIndexForward=sort_ascending,
                    **{k: v for k, v in common_kwargs.items() if k != "FilterExpression" and k!= "ExpressionAttributeValues"}
                )
        else:
            common_kwargs["ScanIndexForward"] = sort_ascending
            resp = self.dynamodb.scan(**common_kwargs)
        ret["last_evaluated_key"] = resp.get("LastEvaluatedKey")
        if fetched_data is None:
            fetched_data = []
        this_data = resp.get("Items", [])
        fetched_data.extend(this_data)
        ret["data"] = fetched_data
        if ret["last_evaluated_key"] is not None:
            search_further = len(fetched_data) == 0
            if not search_further:
                limit = parameters.get("limit", None)
                search_further = limit is not None and len(fetched_data) < limit
            if search_further:
                parameters["last_evaluated_key"] = ret["last_evaluated_key"]
                print("Searching again with last_evaluated_key as : ", ret["last_evaluated_key"])
                return self.fetch_by_metadata(parameters, ip_values=ip_values, ip_conditions=ip_conditions, fetched_data=fetched_data)
        return ret

    def search_with_text_and_metadata(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if query is None or len(query.strip()) == 0:
            return self.fetch_by_metadata(parameters)
        search_query_field_name = parameters.get("search_query_field_name", None)
        if search_query_field_name is None or len(search_query_field_name.strip()) ==0:
            return self.fetch_by_metadata(parameters)
        values: Dict[str, Any] = {":t": _to_ddb_attr(query)}
        conditions: List[str] = [f"contains({search_query_field_name}, :t)"]
        return self.fetch_by_metadata(parameters, ip_values=values, ip_conditions=conditions)

    def validate_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        if query is None or len(query.strip()) == 0:
            return False
        return True
    
    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "store_data": "Inserts Data into DynamoDB",
            "update_data": "Updates an Existing data in DynamoDB",
            "fetch_data": "Fetches data from DynamoDB based on only filters or text search and filters",
            "delete_data": "Deletes data from DynamoDB"
        }

