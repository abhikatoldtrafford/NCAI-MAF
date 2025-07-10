import uuid
import asyncio
from typing import Dict, Any, Optional
from NewsAgents.business.interfaces.business_logic_interface import BusinessLogicInterface
from NewsAgents.infrastructure.llm.agent_manager import AgentManager
from NewsAgents.infrastructure.data.data_manager import DataManager


class Orchestrator:
    """Main orchestrator for coordinating services and workflows."""

    def __init__(self, business_logic: BusinessLogicInterface, config: Optional[Dict[str, Any]] = None):
        """
        Initialize the orchestrator.

        Args:
            business_logic: Business logic implementation
            config: Configuration for the orchestrator and its components
        """
        self.config = config or {}

        # Set business logic
        self.business_logic = business_logic

        # Initialize other managers
        self.agent_manager = AgentManager(self.config.get("llm", {}))
        self.data_manager = DataManager()

        # Set dependencies in business logic
        if hasattr(self.business_logic, "set_agent_manager"):
            self.business_logic.set_agent_manager(self.agent_manager)

        if hasattr(self.business_logic, "set_data_manager"):
            self.business_logic.set_data_manager(self.data_manager)

        # Configure agent manager with credentials from business logic
        self.business_logic.configure_agent_manager(self.config.get("credentials", {}))

        # Configure data manager with data sources from business logic
        self.business_logic.configure_data_manager(self.config)

        # Request tracking
        self.requests = {}

    async def process_prompt(self, prompt: dict, parameters: Dict[str, Any] = {}) -> Dict[str, Any]:
        """
        Process a prompt through the orchestration pipeline.

        Args:
            prompt: The user prompt metadata (ID + version) or raw prompt object
            parameters: Additional parameters for processing

        Returns:
            Dictionary containing the response and request ID
        """
        # Handle raw prompt format
        user_prompt_text = None
        system_prompt_text = None

        # Generate a unique request ID
        request_id = str(uuid.uuid4())

        # Check if this is a raw prompt (created by the API endpoint)
        if prompt.get("id") == "raw_prompt" and "text" in prompt:
            user_prompt_text = prompt["text"]

            # Check for raw system prompt
            system_prompt = parameters.get("system_prompt", {})
            if isinstance(system_prompt, dict) and system_prompt.get("id") == "raw_system_prompt" and "text" in system_prompt:
                system_prompt_text = system_prompt["text"]
            else:
                # Default system prompt if none provided
                system_prompt_text = "You are a helpful assistant."
        else:
            # Handle regular prompt format with prompt service
            # Validate and extract user prompt info
            if "id" not in prompt:
                raise ValueError("User prompt must contain an 'id'.")
            user_prompt_id = prompt["id"]
            user_prompt_version = prompt.get("version")

            # Validate and extract system prompt info
            system_prompt = parameters.get("system_prompt")
            if not system_prompt or "id" not in system_prompt:
                raise ValueError("System prompt must contain an 'id'.")
            sys_prompt_id = system_prompt["id"]
            sys_prompt_version = system_prompt.get("version")

            if not self.business_logic.prompt_service:
                raise ValueError("Prompt service not set in business logic.")

            # Fetch prompts via the injected prompt service
            prompt_service = self.business_logic.get_prompt_service()
            if not prompt_service:
                raise ValueError("Prompt service not set in business logic.")

            system_prompt_text, user_prompt_text = prompt_service.get_prompts(
                sys_prompt_id=sys_prompt_id,
                sys_prompt_version=sys_prompt_version,
                user_prompt_id=user_prompt_id,
                user_prompt_version=user_prompt_version,
            )

        # Create observability handler if needed
        observability_handler = None
        if parameters.get("use_observability", True):
            # Get observability type from parameters or default to langfuse
            observability_type = parameters.get("observability_type", "langfuse")

            # Create context for observability
            observability_context = {
                "session_id": request_id,
                "user_id": parameters.get("user_id"),
                "trace_name": f"query_{request_id}",
            }

            # Get handler from business logic
            observability_handler = self.business_logic.get_observability_handler(
                observability_type=observability_type, config=observability_context
            )

            # Add handler to parameters if created successfully
            if observability_handler:
                parameters["observability_handler"] = observability_handler

        # Track request
        self.requests[request_id] = {"prompt": user_prompt_text, "parameters": parameters, "status": "processing"}

        try:
            # Step 1: Determine which workflow to use
            workflow_id = self.business_logic.determine_workflow(user_prompt_text, parameters)

            # Update request with workflow info
            self.requests[request_id]["workflow"] = workflow_id

            try:
                # Step 2: Get the workflow instance
                workflow = self.business_logic.get_workflow(workflow_id, parameters)

                # Step 3: Execute the workflow with the prompt
                # Check if the workflow's execute method is async
                if hasattr(workflow.execute, "__await__") or asyncio.iscoroutinefunction(workflow.execute):
                    response = await workflow.execute(user_prompt_text, parameters)
                else:
                    response = workflow.execute(user_prompt_text, parameters)

                # Step 4: Post-process the response if needed
                processed_response = self.business_logic.process_response(response)

                # Update request status
                self.requests[request_id]["status"] = "completed"

                # Format the final response
                result = {"response": processed_response, "request_id": request_id, "workflow": workflow_id}

                # If the response was a dictionary, include some of its fields
                if isinstance(processed_response, dict):
                    # Include status if available
                    if "status" in processed_response:
                        result["status"] = processed_response["status"]

                    # If response had its own response field, use that as the main response
                    if "response" in processed_response:
                        result["response"] = processed_response["response"]
                    elif "data" in processed_response:
                        # Include data field for API responses
                        result["data"] = processed_response["data"]

                return result

            except Exception as workflow_error:
                # Handle workflow execution errors
                error_message = str(workflow_error)
                print(f"Workflow execution error: {error_message}")

                # Update request status
                self.requests[request_id]["status"] = "failed"
                self.requests[request_id]["error"] = error_message

                return {
                    "response": f"Error processing prompt: {error_message}",
                    "request_id": request_id,
                    "workflow": workflow_id,
                    "error": error_message,
                }

        except Exception as e:
            # Log the error and update request status
            error_message = str(e)
            print(f"Error processing prompt: {error_message}")

            # Update request status
            self.requests[request_id]["status"] = "failed"
            self.requests[request_id]["error"] = error_message

            return {"response": f"Error processing prompt: {error_message}", "request_id": request_id, "error": error_message}

    def get_request_status(self, request_id: str) -> Dict[str, Any]:
        """
        Get the status of a request.

        Args:
            request_id: The request ID

        Returns:
            Request status information
        """
        if request_id in self.requests:
            return self.requests[request_id]
        else:
            return {"status": "not_found"}
