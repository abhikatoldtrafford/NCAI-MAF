"""
Configuration settings for Barron's implementation.
"""

import os
from typing import Dict, Any

def get_config(environment: str = "staging") -> Dict[str, Any]:
    """
    Get configuration settings for the specified environment.

    Args:
        environment: Environment name (staging, production)

    Returns:
        Dictionary containing configuration settings
    """
    # Base configuration
    config = {
        "business_name": "barrons",
        "credentials": {"secret_name": f"ncai/barrons-ticker/{environment}", "project_name": "barrons-stock-screener"},
        "llm": {},
        "observability": {"type": "langfuse", "enabled": True},
        "workflows": {
            "default": "direct_query",
            "data_query_patterns": [
                r"(?:find|search|get|query|select|fetch)",
                r"(?:data|information|records)",
                r"(?:database|table|source)",
            ],
        },
        # Add DynamoDB configuration
        "dynamodb": {
            "region": "us-east-1",
            "table_prefix": f"barrons-{environment}-",
            # AWS credentials are retrieved from environment or IAM role
            # Optionally include explicit credentials:
            # "aws_access_key_id": "",
            # "aws_secret_access_key": ""
        },
        # Add conversation storage configuration
        "conversation_storage": {
            "type": "dynamodb",  # Use "memory" for in-memory storage
            "conversation_table": "conversations",
            "message_table": "messages",
            # Additional storage-specific options can go here
        },
        "conversation_max_age_minutes": 60,  # Conversations expire after 60 minutes
        "max_conversations": 1000  # Maximum in-memory conversations (for memory storage)
    }

    # Environment-specific overrides
    if environment == "production":
        config["llm"]["temperature"] = 0.5  # More deterministic in production
    
    elif environment == "development":
        config["llm"]["max_tokens"] = 4096  # More tokens for testing
        config["observability"]["enabled"] = False  # Disable observability in development
        config["conversation_storage"]["type"] = "memory"  # Use in-memory storage for development

    # Override with environment variables if present
    if os.environ.get("BARRONS_MODEL_ID"):
        config["llm"]["model_id"] = os.environ.get("BARRONS_MODEL_ID")

    if os.environ.get("BARRONS_TEMPERATURE"):
        config["llm"]["temperature"] = float(os.environ.get("BARRONS_TEMPERATURE"))

    if os.environ.get("BARRONS_MAX_TOKENS"):
        config["llm"]["max_tokens"] = int(os.environ.get("BARRONS_MAX_TOKENS"))

    # Add DynamoDB override options
    if os.environ.get("DYNAMODB_REGION"):
        config["dynamodb"]["region"] = os.environ.get("DYNAMODB_REGION")

    if os.environ.get("DYNAMODB_TABLE_PREFIX"):
        config["dynamodb"]["table_prefix"] = os.environ.get("DYNAMODB_TABLE_PREFIX")

    # Add conversation storage override options
    if os.environ.get("CONVERSATION_STORAGE_TYPE"):
        config["conversation_storage"]["type"] = os.environ.get("CONVERSATION_STORAGE_TYPE")

    return config
