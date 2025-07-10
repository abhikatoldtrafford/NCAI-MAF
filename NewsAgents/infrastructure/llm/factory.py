import os
from typing import Dict, Any
from NewsAgents.application.models.model_configs import LLMModelTypes, LLMConfig
from NewsAgents.infrastructure.llm.llm_base import LLMModel
from NewsAgents.infrastructure.llm.llm_bedrock_anthropic import AnthropicBedrockModel
from NewsAgents.infrastructure.aws.secrets_manager import get_secret

class LLMFactory:
    """Factory for creating LLM instances."""
    
    @staticmethod
    def create_llm(provider: str, config: Dict[str, Any] = None) -> LLMModel:
        """
        Create an LLM instance based on the provider.
        
        Args:
            provider: The LLM provider (e.g., 'anthropic_bedrock', 'anthropic', 'openai', 'google')
            config: Configuration for the LLM
            
        Returns:
            An LLM instance
            
        Raises:
            ValueError: If the provider is not supported
        """
        config = config or {}
        # Extract common configuration
        project_name = config.get("project_name", "")
        session_id = config.get("session_id", None)
        user_id = config.get("user_id", None)

        # Get secrets from AWS Secrets Manager
        try:
            # Define the secret name based on environment or config
            secret_name = config.get("secret_name", "ncai/barrons-ticker/staging")
            region_name = config.get("aws_region", "us-east-1")
            
            # Get secrets
            secrets = get_secret(secret_name, region_name)
            
            # Extract credentials from secrets
            langfuse_public_key = secrets.get("LANGFUSE_PUBLIC_KEY_BARRONS_CHAT", "")
            langfuse_secret_key = secrets.get("LANGFUSE_SECRET_KEY_BARRONS_CHAT", "")
            langfuse_host = secrets.get("LANGFUSE_HOST", "")
            aws_access_key = secrets.get("AWS_ACCESS_KEY_ID")
            aws_secret_key = secrets.get("AWS_SECRET_ACCESS_KEY")
            
        except Exception as e:
            print(f"Error getting secrets: {str(e)}. Falling back to environment variables.")
            # Fallback to environment variables or config
            langfuse_public_key = config.get("langfuse_public_key", "")
            langfuse_secret_key = config.get("langfuse_secret_key", "")
            langfuse_host = config.get("langfuse_host", "")
            aws_access_key = None
            aws_secret_key = None
        
        # Fallback to environment variables if not found in secrets
        aws_access_key = aws_access_key or config.get("aws_access_key") or os.environ.get("AWS_ACCESS_KEY_ID")
        aws_secret_key = aws_secret_key or config.get("aws_secret_key") or os.environ.get("AWS_SECRET_ACCESS_KEY")
        aws_region = config.get("aws_region") or os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
        langfuse_public_key = langfuse_public_key or config.get("langfuse_public_key") or os.environ.get("LANGFUSE_PUBLIC_KEY_BARRONS_CHAT")
        langfuse_secret_key = langfuse_secret_key or config.get("langfuse_secret_key") or os.environ.get("LANGFUSE_SECRET_KEY_BARRONS_CHAT")
        langfuse_host = langfuse_host or config.get("langfuse_host") or os.environ.get("LANGFUSE_HOST")
        
        # Provider-specific initialization
        if provider.lower() == 'anthropic_bedrock':
            model_id = config.get("model_id", "us.anthropic.claude-3-5-sonnet-20241022-v2:0")
            
            # Create LLM config
            model_config = LLMConfig(
                model_type=LLMModelTypes.ANTHROPIC_BEDROCK,
                temperature=config.get("temperature", 0.7),
                max_tokens=config.get("max_tokens", 2048),
                top_p=config.get("top_p", 0.1),
                top_k=config.get("top_k", 250)
            )
            
            return AnthropicBedrockModel(
                project_name=project_name,
                langfuse_public_key=langfuse_public_key,
                langfuse_secret_key=langfuse_secret_key,
                langfuse_host=langfuse_host,
                aws_access_key=aws_access_key,
                aws_secret_key=aws_secret_key,
                aws_region=aws_region,
                model_configs=model_config,
                model_id=model_id,
                logging_session=session_id,
                user_id=user_id
            )
        elif provider.lower() == 'anthropic':
            # Uncomment when implementing AnthropicLLM
            # api_key = config.get("api_key")
            # model = config.get("model", "claude-3-5-sonnet-20241022-v2")
            # Return AnthropicLLM when implemented
            raise ValueError("AnthropicLLM not yet implemented")
        elif provider.lower() == 'openai':
            # Uncomment when implementing OpenAILLM
            # api_key = config.get("api_key")
            # model = config.get("model", "gpt-4o")
            # Return OpenAILLM when implemented
            raise ValueError("OpenAILLM not yet implemented")
        elif provider.lower() in ['google', 'gemini']:
            # Uncomment when implementing GoogleGeminiLLM
            # api_key = config.get("api_key")
            # model = config.get("model", "gemini-1.5-flash")
            # Return GoogleGeminiLLM when implemented
            raise ValueError("GoogleGeminiLLM not yet implemented")
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")