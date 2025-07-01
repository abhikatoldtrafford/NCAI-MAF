from typing import Dict, Any, List, Optional, Callable, TypeVar, Generic

T = TypeVar('T')
R = TypeVar('R')

class Strategy(Generic[T, R]):
    """Base class for strategies."""
    
    def __init__(self, name: str, description: str, criteria: Callable[[T], bool], implementation: Callable[[T], R]):
        """
        Initialize the Strategy.
        
        Args:
            name: The name of the strategy
            description: The description of the strategy
            criteria: Function to determine if the strategy is applicable
            implementation: Function to execute the strategy
        """
        self.name = name
        self.description = description
        self.criteria = criteria
        self.implementation = implementation
    
    def is_applicable(self, input_data: T) -> bool:
        """
        Check if the strategy is applicable to the input data.
        
        Args:
            input_data: The input data
            
        Returns:
            True if the strategy is applicable, False otherwise
        """
        return self.criteria(input_data)
    
    def execute(self, input_data: T) -> R:
        """
        Execute the strategy.
        
        Args:
            input_data: The input data
            
        Returns:
            The result
        """
        return self.implementation(input_data)

class StrategySelector(Generic[T, R]):
    """Selector for strategies."""
    
    def __init__(self):
        """Initialize the StrategySelector."""
        self.strategies: List[Strategy[T, R]] = []
    
    def register_strategy(self, strategy: Strategy[T, R]) -> None:
        """
        Register a strategy.
        
        Args:
            strategy: The strategy to register
        """
        self.strategies.append(strategy)
    
    def select_strategy(self, input_data: T) -> Optional[Strategy[T, R]]:
        """
        Select a strategy for the input data.
        
        Args:
            input_data: The input data
            
        Returns:
            The selected strategy, or None if no strategy is applicable
        """
        for strategy in self.strategies:
            if strategy.is_applicable(input_data):
                return strategy
        
        return None
    
    def execute_strategy(self, input_data: T) -> Optional[R]:
        """
        Execute a strategy for the input data.
        
        Args:
            input_data: The input data
            
        Returns:
            The result of the strategy, or None if no strategy is applicable
        """
        strategy = self.select_strategy(input_data)
        
        if strategy:
            return strategy.execute(input_data)
        
        return None
