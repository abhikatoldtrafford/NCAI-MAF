import os
import sys
import copy
sys.path.append(os.getcwd())
from typing import Dict, Any, Optional
from NewsAgents.infrastructure.llm.llm_base import LLMModel
# from application.models.model_configs import LLMConfig, LLMModelTypes
# from infrastructure.llm.llm_bedrock_anthropic import AnthropicBedrockModel
# from infrastructure.aws.secrets_manager import get_secret
from NewsAgents.infrastructure.llm.factory import LLMFactory

class AgentManager:
    """Manager for LLM agent interactions."""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the agent manager.
        
        Args:
            config: Configuration for the LLM agent
        """
        self.config = config or {}
        
        # Use the factory to create the LLM instance
        # provider = self.config.get("provider", "anthropic_bedrock")
        # self.llm = self._create_llm(provider, self.config)
    
    def _create_llm(self, provider: str, config: Dict[str, Any]) -> LLMModel:
        """
        Create an LLM instance using the factory.
        
        Args:
            provider: The LLM provider
            config: Configuration including credentials
            
        Returns:
            An LLM instance
        """
        return LLMFactory.create_llm(provider, config)
    
    def generate_custom_config_llm(self, updated_configs: Dict[str, Any]) -> LLMModel:
        llm_configs = copy.deepcopy(self.config)
        if updated_configs is None:
            updated_configs = {}
        llm_configs.update(updated_configs)
        provider = llm_configs.get("provider", "anthropic_bedrock")
        return self._create_llm(provider, llm_configs)
    
    def generate_response(self, llm: LLMModel, prompt: str, context: Optional[Dict[str, Any]] = None) -> str:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The user prompt
            context: Optional context parameters
            
        Returns:
            The generated response text
        """

        # Extract parameters from context
        params = context or {}
        
        # Get system prompt or use default
        system_prompt = params.get('system_prompt')
        
        # Get parser if provided
        parser = params.get('parser')
        try:
            # Generate response using the LLM
            response = llm.generate(
                system_prompt=system_prompt,
                user_prompt=prompt,
                parser=parser
            )

            # Handle different response types from LangChain
            if hasattr(response, 'content'):
                # If it's an AIMessage or similar LangChain object
                return response.content
            elif isinstance(response, dict) and 'content' in response:
                # If it's a dictionary with content
                return response['content']
            elif isinstance(response, str):
                # If it's already a string
                return response
            else:
                # Last resort - convert to string
                return response
            
        except Exception as e:
            # Handle errors
            print(f"Error generating response: {str(e)}")
            return f"Error generating response: {str(e)}"
    
    def format_prompt(self, prompt: str, data: Any = None) -> str:
        """
        Format the prompt for the LLM.
        
        Args:
            prompt: The user prompt
            data: Optional data to include in the context
            
        Returns:
            Formatted prompt string
        """
        if data:
            # Add data context to the prompt
            return f"{prompt}\n\nContext: {str(data)}"
        return prompt