from typing import Dict, Any, Optional
from business.interfaces.workflow_interface import WorkflowInterface
from infrastructure.llm.agent_manager import AgentManager
from infrastructure.llm.llm_base import LLMModel

class DirectQueryWorkflow(WorkflowInterface[str, str]):
    """
    A simple workflow that passes a prompt directly to the LLM and returns the response.
    """
    
    def __init__(self, agent_manager: AgentManager, llm: LLMModel):
        """
        Initialize the direct query workflow.
        
        Args:
            agent_manager: Manager for LLM agent interactions
        """
        self.agent_manager = agent_manager
        self.llm = llm
        self.status = {"state": "idle"}
    
    def execute(self, prompt: str, system_prompt: Optional[str] = None) -> str:
        """
        Execute the direct query workflow.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt
            
        Returns:
            The generated response
        """
        self.status = {"state": "processing"}
        
        try:
            # Create context with system prompt if provided
            context = {}
            if system_prompt:
                context['system_prompt'] = system_prompt
            
            # Generate response using the agent manager
            response = self.agent_manager.generate_response(self.llm, prompt, context)
            
            self.status = {"state": "completed"}
            return response
            
        except Exception as e:
            self.status = {"state": "failed", "error": str(e)}
            return f"Error processing prompt: {str(e)}"
    
    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the workflow.
        
        Returns:
            The workflow status
        """
        return self.status