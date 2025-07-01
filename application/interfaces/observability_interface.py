from abc import ABC, abstractmethod
from typing import Dict, Any

class ObservabilityInterface(ABC):
    """Interface for observability implementations."""
    
    @abstractmethod
    def create_handler(self, context: Dict[str, Any] = None) -> Any:
        """
        Create an observability handler.
        
        Args:
            context: Context information for the handler
            
        Returns:
            A handler object for the specific observability implementation
        """
        pass
    
    @abstractmethod
    def log_event(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> None:
        """
        Log an event.
        
        Args:
            event_type: Type of event
            data: Event data
            context: Additional context
        """
        pass
    
    @abstractmethod
    def start_trace(self, name: str, context: Dict[str, Any] = None) -> Any:
        """
        Start a trace.
        
        Args:
            name: Trace name
            context: Additional context
            
        Returns:
            A trace object
        """
        pass
    
    @abstractmethod
    def end_trace(self, trace: Any, status: str = "success", context: Dict[str, Any] = None) -> None:
        """
        End a trace.
        
        Args:
            trace: The trace object
            status: Trace status
            context: Additional context
        """
        pass