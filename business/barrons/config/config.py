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
        "llm": {
            "provider": "anthropic_bedrock",
            "model_id": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
            "temperature": 0.7,
            "max_tokens": 2048,
        },
        "observability": {"type": "langfuse", "enabled": True},
        "workflows": {
            "default": "direct_query",
            "data_query_patterns": [
                r"(?:find|search|get|query|select|fetch)",
                r"(?:data|information|records)",
                r"(?:database|table|source)",
            ],
        },
    }

    # Environment-specific overrides
    if environment == "production":
        config["llm"]["temperature"] = 0.5  # More deterministic in production

    elif environment == "development":
        config["llm"]["max_tokens"] = 4096  # More tokens for testing
        config["observability"]["enabled"] = False  # Disable observability in development

    # Override with environment variables if present
    if os.environ.get("BARRONS_MODEL_ID"):
        config["llm"]["model_id"] = os.environ.get("BARRONS_MODEL_ID")

    if os.environ.get("BARRONS_TEMPERATURE"):
        config["llm"]["temperature"] = float(os.environ.get("BARRONS_TEMPERATURE"))

    if os.environ.get("BARRONS_MAX_TOKENS"):
        config["llm"]["max_tokens"] = int(os.environ.get("BARRONS_MAX_TOKENS"))

    return config
