from typing import Dict, Any, List, Optional
from enum import Enum

class AgentType(Enum):
    """Types of agents."""
    STOCK_ANALYZER = "stock_analyzer"
    NEWS_ANALYZER = "news_analyzer"
    MARKET_TREND_ANALYZER = "market_trend_analyzer"
    INTENT_CLASSIFIER = "intent_classifier"
    COMPARISON_ANALYZER = "comparison_analyzer"
    CUSTOM = "custom"

class Agent:
    """Base class for agent configuration."""
    
    def __init__(
        self, 
        agent_type: AgentType, 
        name: str, 
        description: str, 
        capabilities: List[str],
        parameters: Dict[str, Any] = None
    ):
        """
        Initialize the Agent.
        
        Args:
            agent_type: The type of agent
            name: The name of the agent
            description: A description of the agent
            capabilities: A list of agent capabilities
            parameters: Additional parameters for the agent
        """
        self.agent_type = agent_type
        self.name = name
        self.description = description
        self.capabilities = capabilities
        self.parameters = parameters or {}
    
    def to_dict(self) -> Dict[str, Any]:
        """
        Convert the agent to a dictionary.
        
        Returns:
            A dictionary representation of the agent
        """
        return {
            "agent_type": self.agent_type.value,
            "name": self.name,
            "description": self.description,
            "capabilities": self.capabilities,
            "parameters": self.parameters
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Agent':
        """
        Create an agent from a dictionary.
        
        Args:
            data: A dictionary containing agent data
            
        Returns:
            An Agent instance
        """
        return cls(
            agent_type=AgentType(data["agent_type"]),
            name=data["name"],
            description=data["description"],
            capabilities=data["capabilities"],
            parameters=data.get("parameters", {})
        )

class AgentSelector:
    """Selector for agents."""
    
    def __init__(self):
        """Initialize the AgentSelector."""
        self.agents = {}
    
    def register_agent(self, agent: Agent) -> None:
        """
        Register an agent.
        
        Args:
            agent: The agent to register
        """
        self.agents[agent.name] = agent
    
    def get_agent(self, name: str) -> Optional[Agent]:
        """
        Get an agent by name.
        
        Args:
            name: The name of the agent
            
        Returns:
            The agent if found, None otherwise
        """
        return self.agents.get(name)
        
    def select_agent_for_capabilities(self, required_capabilities: List[str]) -> Optional[Agent]:
        """
        Select an agent based on required capabilities.
        
        Args:
            required_capabilities: List of required capabilities
            
        Returns:
            The agent with the most matching capabilities, or None if no suitable agent is found
        """
        # TODO Define capabilities of multi-agentic workflow
        pass
    
    def get_all_agents(self) -> List[Agent]:
        """
        Get all registered agents.
        
        Returns:
            A list of all agents
        """
        return list(self.agents.values())
    
    def get_agents_by_type(self, agent_type: AgentType) -> List[Agent]:
        """
        Get all agents of a given type.
        
        Args:
            agent_type: The type of agents to retrieve
            
        Returns:
            A list of agents of the given type
        """
        return [agent for agent in self.agents.values() if agent.agent_type == agent_type]
