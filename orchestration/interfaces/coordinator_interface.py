from abc import ABC, abstractmethod
from typing import Dict, Any, List, TypeVar, Generic

T = TypeVar('T')
R = TypeVar('R')

class CoordinatorInterface(Generic[T, R], ABC):
    """Interface for service coordinators."""
    
    @abstractmethod
    async def coordinate(self, input_data: T) -> R:
        """Coordinate services to process the input data."""
        pass
    
    @abstractmethod
    async def register_service(self, service_name: str, service: Any) -> bool:
        """Register a service with the coordinator."""
        pass
    
    @abstractmethod
    async def get_registered_services(self) -> List[str]:
        """Get a list of registered service names."""
        pass