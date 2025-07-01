from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Union

class DataPluginInterface(ABC):
    """Interface for data layer plugins."""
    
    @abstractmethod
    def process_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Process a query and return results.
        
        Args:
            query: The query string to process
            parameters: Additional parameters for query processing
            
        Returns:
            Dictionary containing the query results and metadata
        """
        pass
    
    @abstractmethod
    def validate_query(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> bool:
        """
        Validate if a query can be processed by this plugin.
        
        Args:
            query: The query string to validate
            parameters: Additional parameters for validation
            
        Returns:
            True if the query is valid for this plugin, False otherwise
        """
        pass
    
    @abstractmethod
    def get_capabilities(self) -> Dict[str, Any]:
        """
        Get the capabilities of this plugin.
        
        Returns:
            Dictionary containing plugin capabilities and metadata
        """
        pass