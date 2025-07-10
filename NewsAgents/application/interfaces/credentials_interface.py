from abc import ABC, abstractmethod
from typing import Dict, Any

class CredentialsInterface(ABC):
    """Interface for credential providers."""
    
    @abstractmethod
    def get_credentials(self, context: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Get credentials from the provider.
        
        Args:
            context: Context information for credential retrieval
            
        Returns:
            Dictionary with resolved credentials
        """
        pass
    
    @abstractmethod
    def update_context(self, context: Dict[str, Any]) -> None:
        """
        Update the context for credential retrieval.
        
        Args:
            context: New context information
        """
        pass