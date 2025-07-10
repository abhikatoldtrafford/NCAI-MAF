import warnings
from typing import Dict, Any
from langfuse.callback import CallbackHandler
from NewsAgents.application.interfaces.observability_interface import ObservabilityInterface

class LangfuseObservability(ObservabilityInterface):
    """Langfuse implementation of observability."""
    
    def __init__(self, credentials_provider):
        """
        Initialize the Langfuse observability.
        
        Args:
            credentials_provider: Provider for Langfuse credentials
        """
        self.credentials_provider = credentials_provider
        self.active_traces = {}
    
    def create_handler(self, context: Dict[str, Any] = None) -> Any:
        """
        Create a Langfuse callback handler.
        
        Args:
            context: Context information for the handler
            
        Returns:
            A Langfuse callback handler or None if credentials are missing
        """
        context = context or {}
        credentials = self.credentials_provider.get_credentials(context)
        
        public_key = credentials.get("langfuse_public_key")
        secret_key = credentials.get("langfuse_secret_key")
        host = credentials.get("langfuse_host")
        
        if not (public_key and secret_key and host):
            warnings.warn("Skipping Langfuse logging, credentials not found")
            return None
            
        # Extract Langfuse-specific context
        project_name = context.get("project_name") or credentials.get("project_name", "")
        session_id = context.get("session_id")
        user_id = context.get("user_id") 
        trace_name = context.get("trace_name")
        
        # Create metadata if project name exists
        metadata = None
        if project_name and len(project_name.strip()) > 0:
            metadata = {"project_name": project_name}
            
        # Create and return handler
        try:
            handler = CallbackHandler(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
                session_id=session_id,
                user_id=user_id,
                metadata=metadata,
                trace_name=trace_name if trace_name and len(trace_name.strip()) > 0 else None
            )
            return handler
        except Exception as e:
            warnings.warn(f"Error creating Langfuse handler: {str(e)}")
            return None
    
    def log_event(self, event_type: str, data: Dict[str, Any], context: Dict[str, Any] = None) -> None:
        """
        Log an event to Langfuse.
        
        Args:
            event_type: Type of event
            data: Event data
            context: Additional context
        """
        # Langfuse doesn't directly support standalone events outside of traces
        # You would typically use this within an active trace
        pass
    
    def start_trace(self, name: str, context: Dict[str, Any] = None) -> Any:
        """
        Start a Langfuse trace.
        
        Args:
            name: Trace name
            context: Additional context
            
        Returns:
            A trace object or None if handler creation fails
        """
        context = context or {}
        context["trace_name"] = name
        
        handler = self.create_handler(context)
        if handler:
            # In a real implementation, you would create a trace here
            # For Langfuse, traces are created implicitly
            trace_id = name  # Using name as a simple trace ID for demo
            self.active_traces[trace_id] = {
                "handler": handler,
                "context": context
            }
            return trace_id
        
        return None
    
    def end_trace(self, trace: Any, status: str = "success", context: Dict[str, Any] = None) -> None:
        """
        End a Langfuse trace.
        
        Args:
            trace: The trace object or ID
            status: Trace status
            context: Additional context
        """
        # In a real implementation, you might mark the trace as completed
        if trace in self.active_traces:
            del self.active_traces[trace]