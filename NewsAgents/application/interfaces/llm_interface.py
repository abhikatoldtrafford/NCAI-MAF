from typing import Dict, Any, Optional, AsyncGenerator
from abc import ABC, abstractmethod

class LLMInterface(ABC):
    """Interface for LLM interactions."""
    
    @abstractmethod
    async def generate(self, 
                 system_prompt: str, 
                 user_prompt: str,
                 model_parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Generate text based on the given prompts.
        
        Args:
            system_prompt: The system prompt
            user_prompt: The user prompt
            model_parameters: Optional parameters for the model
            
        Returns:
            Generated text and metadata
        """
        pass
    
    @abstractmethod
    async def stream_generate(self, 
                       system_prompt: str, 
                       user_prompt: str,
                       model_parameters: Optional[Dict[str, Any]] = None) -> AsyncGenerator[str, None]:
        """
        Stream generated text based on the given prompts.
        
        Args:
            system_prompt: The system prompt
            user_prompt: The user prompt
            model_parameters: Optional parameters for the model
            
        Yields:
            Generated text chunks
        """
        pass