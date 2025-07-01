from abc import ABC, abstractmethod
from typing import Dict, Any, Generic, TypeVar

T_in = TypeVar('T_in')
T_out = TypeVar('T_out')

class WorkflowInterface(Generic[T_in, T_out]):
    """Interface for workflow definitions."""
    
    @abstractmethod
    async def execute(self, input_data: T_in) -> T_out:
        """
        Execute the workflow.
        
        Args:
            input_data: The input data for the workflow
            
        Returns:
            The workflow result
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    @abstractmethod
    async def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the workflow.
        
        Returns:
            The workflow status
        """
        raise NotImplementedError("Subclasses must implement this method")
    
    @abstractmethod
    async def cancel(self) -> bool:
        """Cancel the workflow execution."""
        pass
    
