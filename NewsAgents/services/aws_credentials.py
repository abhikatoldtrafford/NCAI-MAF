import os
from typing import Dict, Any, Optional
from NewsAgents.application.interfaces.credentials_interface import CredentialsInterface
from NewsAgents.infrastructure.aws import get_secret

class AWSCredentialsProvider(CredentialsInterface):
    """AWS implementation of credentials provider using Secrets Manager."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the AWS credentials provider.
        
        Args:
            config: Initial configuration
        """
        self.config = config or {}
        self.secrets_cache = {}

    def get_credentials(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get credentials from AWS Secrets Manager and environment variables.
        
        Args:
            context: Context information for credential retrieval
            
        Returns:
            Dictionary with resolved credentials
        """
        context = context or {}
        credentials = {}
        
        # Merge context with config
        merged_config = {**self.config, **context}
        
        # Determine if we should use Secrets Manager
        use_secrets_manager = merged_config.get("use_secrets_manager", True)
        
        # Try to get from AWS Secrets Manager if requested
        if use_secrets_manager:
            # Get secret name and region
            secret_name = merged_config.get("secret_name", "ncai/barrons-ticker/staging")
            region_name = merged_config.get("aws_region", "us-east-1")
            
            # Check if we have cached secrets
            cache_key = f"{secret_name}:{region_name}"
            if cache_key in self.secrets_cache:
                secrets = self.secrets_cache[cache_key]
            else:
                # Try to get from Secrets Manager
                try:
                    secrets = get_secret(secret_name, region_name)
                    # Cache the secrets
                    self.secrets_cache[cache_key] = secrets
                except Exception as e:
                    print(f"Error getting secrets: {str(e)}. Will use environment variables.")
                    secrets = {}
            
            # Extract credentials from secrets
            credentials.update({
                "langfuse_public_key": secrets.get("LANGFUSE_PUBLIC_KEY_BARRONS_CHAT", ""),
                "langfuse_secret_key": secrets.get("LANGFUSE_SECRET_KEY_BARRONS_CHAT", ""),
                "langfuse_host": secrets.get("LANGFUSE_HOST", ""),
                "aws_access_key": secrets.get("AWS_ACCESS_KEY_ID"),
                "aws_secret_key": secrets.get("AWS_SECRET_ACCESS_KEY"),
                "MYSQL_DB_HOST": secrets.get("MYSQL_DB_HOST"),
                "MYSQL_DB_NAME": secrets.get("MYSQL_DB_NAME"),
                "STOCK_DATA_TABLE_NAME": secrets.get("STOCK_DATA_TABLE_NAME"),
                "SDL_URL": secrets.get("SDL_URL"),
                "OKTA_SDL_AUTH_ISSUER": secrets.get("OKTA_SDL_AUTH_ISSUER"),
                "OKTA_SDL_AUTH_CLIENT_SECRET": secrets.get("OKTA_SDL_AUTH_CLIENT_SECRET"),
                "OKTA_SDL_AUTH_CLIENT_ID": secrets.get("OKTA_SDL_AUTH_CLIENT_ID"),
                "RDS_SECRET_NAME": secrets.get("RDS_SECRET_NAME", ""),
                "FACTIVA_CLIENTID": secrets.get("FACTIVA_CLIENTID", ""),
                "FACTIVA_USERNAME": secrets.get("FACTIVA_USERNAME", ""),
                "FACTIVA_PASSWORD": secrets.get("FACTIVA_PASSWORD", ""),
                "DYNAMO_DB_TABLE_NAME": secrets.get("DYNAMO_DB_TABLE_NAME", ""),
                "DYNAMO_DB_TABLE_INDEX_NAME": secrets.get("DYNAMO_DB_TABLE_INDEX_NAME", "")
            })
            
            for sn, sv in secrets.items():
                credentials[sn] = sv
            mysql_user_pass = self.fetch_mysql_username_pass(credentials.get("RDS_SECRET_NAME", ""), region_name)
            credentials.update({
                "MYSQL_DB_USER": mysql_user_pass.get("username", ""),
                "MYSQL_DB_PASS": mysql_user_pass.get("password", "")
            })
        
        # Layer 2: Add explicit config values from merged config (overriding secrets)
        for key in ["langfuse_public_key", "langfuse_secret_key", "langfuse_host", 
                    "aws_access_key", "aws_secret_key", "aws_region"]:
            if key in merged_config and merged_config[key]:
                credentials[key] = merged_config[key]
        
        # Layer 3: Fall back to environment variables for any missing values
        env_mapping = {
            "langfuse_public_key": "LANGFUSE_PUBLIC_KEY_BARRONS_CHAT",
            "langfuse_secret_key": "LANGFUSE_SECRET_KEY_BARRONS_CHAT",
            "langfuse_host": "LANGFUSE_HOST",
            "aws_access_key": "AWS_ACCESS_KEY_ID",
            "aws_secret_key": "AWS_SECRET_ACCESS_KEY",
            "aws_region": "AWS_DEFAULT_REGION",
            "openai_api_key": "OPENAI_API_KEY",
        }
        
        for key, env_var in env_mapping.items():
            if key not in credentials or not credentials[key]:
                env_value = os.environ.get(env_var)
                if env_value:
                    credentials[key] = env_value
        
        # Ensure aws_region has a default
        if "aws_region" not in credentials or not credentials["aws_region"]:
            credentials["aws_region"] = "us-east-1"
            
        # Include other config values for model settings
        for key in ["project_name", "model_id", "temperature", "max_tokens", "top_p", "top_k"]:
            if key in merged_config:
                credentials[key] = merged_config[key]

        return credentials
    
    def fetch_mysql_username_pass(self, secret_name: str, region_name: str = "us-east-1") -> Dict[str, Any]:
        if secret_name is None or len(secret_name.strip()) == 0:
            secret_name = os.getenv("RDS_SECRET_NAME", "")
        try:
            secrets = get_secret(secret_name, region_name)
            # Cache the secrets
            cache_key = f"{secret_name}:{region_name}"
            self.secrets_cache[cache_key] = secrets
        except Exception as e:
            print(f"Error getting secrets: {str(e)}. Will use environment variables.")
            secrets = {}
        return secrets

    def update_context(self, context: Dict[str, Any]) -> None:
        """
        Update the context for credential retrieval.
        
        Args:
            context: New context information
        """
        self.config.update(context)
        # Clear cache if secret details might have changed
        if "secret_name" in context or "aws_region" in context:
            self.secrets_cache = {}