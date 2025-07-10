import os
import boto3
import json
from botocore.exceptions import ClientError
from typing import Dict, Any

def get_secret(secret_name: str, region_name: str = "us-east-1") -> Dict[str, Any]:
    """
    Retrieve a secret from AWS Secrets Manager.
    
    Args:
        secret_name: The name of the secret to retrieve
        region_name: The AWS region where the secret is stored
        
    Returns:
        The secret value as a dictionary
        
    Raises:
        ClientError: If there's an error retrieving the secret
    """
    # Create a Secrets Manager client
    session = boto3.session.Session()
    aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
    aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
    if aws_access_key_id is not None and len(aws_access_key_id.strip()) > 0 and aws_secret_access_key is not None and len(aws_secret_access_key.strip()) > 0:
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name,
            aws_access_key_id=aws_access_key_id,
            aws_secret_access_key=aws_secret_access_key
        )
    else:
        client = session.client(
            service_name='secretsmanager',
            region_name=region_name
        )
    
    try:
        # Get the secret value
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        # For a list of exceptions thrown, see
        # https://docs.aws.amazon.com/secretsmanager/latest/apireference/API_GetSecretValue.html
        raise e
    
    # Parse the secret value
    secret_string = get_secret_value_response['SecretString']
    
    # If the secret is a JSON string, parse it into a dictionary
    try:
        return json.loads(secret_string)
    except json.JSONDecodeError:
        # If it's not JSON, return it as a dictionary with a single key
        return {"secret": secret_string}