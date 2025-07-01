from typing import Dict, Any, Optional
from business.interfaces.workflow_interface import WorkflowInterface
from application.services.prompt_service import PromptService
from infrastructure.llm.agent_manager import AgentManager
from infrastructure.data.data_manager import DataManager
from infrastructure.llm.llm_base import LLMModel


class DataQueryWorkflow(WorkflowInterface[str, Dict[str, Any]]):
    """
    A workflow that processes data queries with LLM assistance.
    """

    def __init__(self, agent_manager: AgentManager, data_manager: DataManager, prompt_service: PromptService, llm: LLMModel):
        """
        Initialize the data query workflow.

        Args:
            agent_manager: Manager for LLM agent interactions
            data_manager: Manager for data operations
        """
        self.agent_manager = agent_manager
        self.prompt_service = prompt_service
        self.data_manager = data_manager
        self.llm = llm
        self.status = {"state": "idle"}

    def execute(self, query: str, parameters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Execute the data query workflow.

        Args:
            query: The query string
            parameters: Optional parameters for execution

        Returns:
            The workflow result
        """
        self.status = {"state": "processing"}
        parameters = parameters or {}

        try:
            # Step 1: Use LLM to understand and format the query if needed
            if parameters.get("enhance_query", False):
                # Format system prompt for query understanding
                system_prompt = self.prompt_service.manager.get_prompt(prompt_id="55NYPYO244", prompt_version="1")

                # Get enhanced query from LLM
                enhanced_query = self.agent_manager.generate_response(self.llm, query, {"system_prompt": system_prompt})

                # Log the query enhancement
                self.status["enhanced_query"] = enhanced_query

                # Use the enhanced query
                processed_query = enhanced_query
            else:
                processed_query = query

            # Step 2: Execute the query using the data manager
            query_result = self.data_manager.get_data(
                processed_query, source=parameters.get("data_source", "default"), parameters=parameters
            )

            # Step 3: Use LLM to summarize or explain the results if needed
            if parameters.get("explain_results", False) and query_result["status"] == "success":
                # Format system prompt for result explanation
                system_prompt = self.prompt_service.manager.get_prompt(prompt_id="BYOP6UJ1GF", prompt_version="1")

                # Create a prompt with the results
                result_prompt = f"Please explain these query results:\n{query_result['data']}"

                # Get explanation from LLM
                explanation = self.agent_manager.generate_response(self.llm, result_prompt, {"system_prompt": system_prompt})

                # Add explanation to results
                query_result["explanation"] = explanation

            self.status = {"state": "completed"}
            return query_result

        except Exception as e:
            self.status = {"state": "failed", "error": str(e)}
            return {"status": "error", "message": f"Error in data query workflow: {str(e)}", "query": query}

    def get_status(self) -> Dict[str, Any]:
        """
        Get the current status of the workflow.

        Returns:
            The workflow status
        """
        return self.status
