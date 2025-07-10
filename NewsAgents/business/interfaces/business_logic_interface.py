from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

class BusinessLogicInterface(ABC):
    """Interface for business logic implementations."""
    
    @abstractmethod
    def determine_workflow(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """
        Determine which workflow to use based on the prompt and parameters.
        
        Args:
            prompt: The user prompt
            parameters: Additional parameters
            
        Returns:
            The workflow ID to use
        """
        pass
    
    @abstractmethod
    def get_workflow(self, workflow_id: str, parameters: Dict[str, Any]) -> Any:
        """
        Get a workflow instance by ID.
        
        Args:
            workflow_id: The workflow ID
            
        Returns:
            The workflow instance
        """
        pass
    
    @abstractmethod
    def process_response(self, response: Any) -> Any:
        """
        Process a response from a workflow.
        
        Args:
            response: The raw response from a workflow
            
        Returns:
            The processed response
        """
        pass
    
    @abstractmethod
    def get_credentials(self, use_secrets_manager: bool = True, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get credentials from various sources.
        
        Args:
            use_secrets_manager: Whether to try a secrets manager
            config: Additional configuration parameters
            
        Returns:
            Dictionary with resolved credentials
        """
        pass
    
    @abstractmethod
    def get_observability_handler(self, observability_type: str, config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create an observability handler based on the specified type.
        
        Args:
            observability_type: Type of observability handler to create
            config: Configuration for the handler
            
        Returns:
            Observability handler or None if creation fails
        """
        pass
    
    @abstractmethod
    def configure_agent_manager(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Configure the agent manager with credentials.
        
        Args:
            config: Configuration parameters
            
        Returns:
            True if successful, False otherwise
        """
        pass
    
    @abstractmethod
    def configure_data_manager(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Configure the data manager with data sources.
        
        Args:
            config: Configuration parameters
            
        Returns:
            True if successful, False otherwise
        """
        pass