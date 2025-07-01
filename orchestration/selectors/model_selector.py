from typing import Dict, Any, Optional
from src.infrastructure.llm.llm_base import LLMBase  # there would be an infra layer where the LLMs will come from
from src.infrastructure.llm.factory import LLMFactory # there would be an infra layer where the LLMs will come from

class ModelSelector:
    """Selector for LLM models."""
    
    def __init__(self, default_provider: str = "anthropic", default_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the ModelSelector.
        
        Args:
            default_provider: The default LLM provider
            default_config: The default LLM configuration
        """
        self.default_provider = default_provider
        self.default_config = default_config or {}
        self.models = {}
    
    def get_model(self, model_type: Optional[str] = None, config: Optional[Dict[str, Any]] = None) -> LLMBase:
        """
        Get an LLM model instance.
        
        Args:
            model_type: The model type (provider)
            config: The model configuration
            
        Returns:
            An LLM model instance
        """
        # Use default provider if not specified
        provider = model_type or self.default_provider
        
        # Combine default config with provided config
        combined_config = {**self.default_config}
        if config:
            combined_config.update(config)
        
        # Check if model already exists
        model_key = f"{provider}:{json.dumps(combined_config, sort_keys=True)}"
        if model_key in self.models:
            return self.models[model_key]
        
        # Create a new model
        model = LLMFactory.create_llm(provider, combined_config)
        
        # Cache the model
        self.models[model_key] = model
        
        return model