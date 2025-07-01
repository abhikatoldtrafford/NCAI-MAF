from typing import Dict, Any, List, Optional, TypeVar, Generic
from src.orchestration.interfaces.coordinator_interface import CoordinatorInterface

T = TypeVar('T')
R = TypeVar('R')

class ServiceCoordinator(CoordinatorInterface[T, R], Generic[T, R]):
    """Base coordinator for services."""
    
    def __init__(self):
        """Initialize the ServiceCoordinator."""
        self.services = {}
    
    async def coordinate(self, input_data: T) -> R:
        """
        Coordinate services to process the input data.
        
        Args:
            input_data: The input data
            
        Returns:
            The result
            
        Raises:
            NotImplementedError: This method must be implemented by subclasses
        """
        raise NotImplementedError("This method must be implemented by subclasses")
    
    async def register_service(self, service_name: str, service: Any) -> bool:
        """
        Register a service with the coordinator.
        
        Args:
            service_name: The name of the service
            service: The service instance
            
        Returns:
            True if registered successfully, False otherwise
        """
        if service_name in self.services:
            return False
        
        self.services[service_name] = service
        return True
    
    async def get_registered_services(self) -> List[str]:
        """
        Get a list of registered service names.
        
        Returns:
            A list of service names
        """
        return list(self.services.keys())