import uuid
import asyncio
from typing import Dict, Any, Optional, List, Callable, Awaitable
from datetime import datetime
import json
from NewsAgents.business.interfaces.business_logic_interface import BusinessLogicInterface
from NewsAgents.infrastructure.llm.agent_manager import AgentManager
from NewsAgents.infrastructure.data.data_manager import DataManager
from NewsAgents.infrastructure.data.plugins.Dynamo_DB_plugin import DynamoDBPlugin
from NewsAgents.infrastructure.conversation.dynamodb_conversation_storage import DynamoDBConversationStorage


class EnhancedOrchestrator:
    """Enhanced orchestrator with streaming and conversation support."""

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
        # workflow_file = self.config.get("workflow_file")

        # Initialize other managers
        # self.agent_manager = AgentManager(config=self.config, default_workflow_file=workflow_file, aws_creds=self.business_logic.aws_creds)
        self.agent_manager = AgentManager(self.config.get("llm", {}))
        self.data_manager = DataManager()
        self.data_manager.register_custom_plugin("dynamodb", DynamoDBPlugin(aws_creds=self.business_logic.aws_creds))
        # Add conversation store
        # self.conversation_store = ConversationStore(
        #     max_age_minutes=self.config.get("conversation_max_age_minutes", 60),
        #     max_conversations=self.config.get("max_conversations", 1000)
        # )
        self.conversation_store = DynamoDBConversationStorage(self.data_manager.plugin_manager, self.business_logic.aws_creds)

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

        # Active streaming requests
        self.streaming_requests = {}

    async def process_prompt_with_streaming(
        self,
        prompt: dict,
        parameters: Dict[str, Any] = {},
        callback: Optional[Callable[[Dict[str, Any]], Awaitable[None]]] = None,
    ) -> Dict[str, Any]:
        """
        Process a prompt with streaming support.

        Args:
            prompt: The user prompt metadata or raw prompt object
            parameters: Additional parameters for processing
            callback: Optional callback function for streaming results

        Returns:
            Dictionary containing the response and request ID
        """
        # Add streaming support
        is_streaming = parameters.get("stream", False)

        # Put user ID into metadata
        user_id = parameters.get("user_id")
        conversation_id = parameters.get("conversation_id")
        if not conversation_id:
            conversation_id = str(uuid.uuid4())
            parameters["conversation_id"] = conversation_id

        # Extract prompt text and system prompt
        user_prompt_text, system_prompt_text = self._extract_prompts(prompt, parameters)

        # Add user message to conversation
        # self.conversation_store.add_message(conversation_id=conversation_id, role="user", content=user_prompt_text)

        # Enhance prompt with conversation history if applicable

        #This needs to be done with LLM Observability tool, as the conversation store is for UI and very different from LLM conversation History.
        
        if parameters.get("include_conversation_history", True):
            limit = parameters.get("history_limit", 10)
            llm_conv = self.conversation_store.fetch_llm_conversations(user_id, conversation_id, limit=limit)
            parameters["history"] = llm_conv.get("history", None)

        # Generate request ID
        request_id = str(uuid.uuid4())
        # If using streaming, set up the streaming context
        if is_streaming and callback:
            self.streaming_requests[request_id] = {
                "status": "processing",
                "started_at": datetime.now().isoformat(),
                "updates": [],
                "callback": callback,
            }

        # Set up observability and tracking
        self._setup_request_tracking(request_id, user_prompt_text, parameters)
        store_conv = parameters.get("store_conv", True) and user_id is not None and isinstance(user_id, str) and len(user_id.strip())>0
        try:
            # Determine workflows to execute
            workflow_info = self._determine_workflows(user_prompt_text, parameters)
            workflow_id = workflow_info["primary"]
            # Update request with workflow info
            self.requests[request_id]["workflow"] = workflow_id
            conversation_created = False
            async for result in self._execute_workflow(workflow_id=workflow_id, request_id=request_id, user_prompt=user_prompt_text, system_prompt=system_prompt_text, parameters=parameters):
                if store_conv:
                    if not conversation_created:
                        self.conversation_store.create_conversation(user_id, conversation_id, user_prompt_text)
                        user_params = {
                            "user_id": user_id,
                            "conversation_id": conversation_id,
                            "conversation_title": user_prompt_text,
                            "request_id": request_id,
                            "session_id": parameters.get("session_id", ""),
                        }
                        tmp_data = {"role": "user", "content": user_prompt_text, "name": "User", "type": "text", "message_id": request_id}
                        try:
                            self.conversation_store.add_llm_message(user_id=user_id, conversation_id=conversation_id, data=tmp_data)
                            user_question_params = {**user_params}
                            user_question_params["query_type"] = "user_question"
                            self.conversation_store.add_message(user_prompt_text, user_question_params)
                        except Exception as e:
                            print("Got error in dynamo db as, For query_type: user_question : "+str(e))
                        conversation_created = True
                    response = result
                    if "response" in result.keys():
                        response = result["response"]
                    if isinstance(response, dict):
                        for query_type, rd in response.items():
                            if query_type == "follow_up_questions":
                                continue
                            if not isinstance(rd, dict):
                                continue
                            this_result_params = {**user_params}
                            this_result_params["query_type"] = query_type
                            this_data = {**rd}
                            tmp_data = {"role": "assistant", "name": "Assistant"}
                            if "message_id" in this_data.keys():
                                tmp_data["message_id"] = this_data["message_id"]
                            for param_key in ["message_id", "rds_data", "rds_columns", "rds_column_definitions"]:
                                if param_key in this_data.keys():
                                    this_result_params[param_key] = this_data[param_key]
                                    del this_data[param_key]
                            try:
                                self.conversation_store.add_message(json.dumps(this_data), this_result_params)
                                tmp_data["content"] = this_data
                                tmp_data["type"] = "text" if query_type != "stock_data" else "data_frame"
                                self.conversation_store.add_llm_message(user_id=user_id, conversation_id=conversation_id, data=tmp_data)
                            except Exception as e:
                                print("Got error in dynamo db as, For query_type: "+query_type+" : "+str(e))
                # Update result with conversation_id
                if isinstance(result, dict):
                    result["conversation_id"] = conversation_id
                # Update request status
                self.requests[request_id]["status"] = "completed"
                if is_streaming:
                    yield (json.dumps(result) + "\n").encode("utf-8")
                    await asyncio.sleep(1)
                else:
                    yield result
        except Exception as e:
            # Log the error and update request status
            error_message = str(e)
            print(f"Error processing prompt: {error_message}")

            # Update request status
            self.requests[request_id]["status"] = "failed"
            self.requests[request_id]["error"] = error_message

            result = {
                "response": f"Error processing prompt: {error_message}",
                "request_id": request_id,
                "conversation_id": conversation_id,
                "error": error_message,
            }
            if is_streaming:
                yield json.dumps(result)
            else:
                yield result

    async def _execute_parallel_workflows_streaming(
        self,
        request_id: str,
        user_prompt: str,
        system_prompt: str,
        workflow_info: Dict[str, Any],
        parameters: Dict[str, Any],
        conversation_id: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> Dict[str, Any]:
        """
        Execute multiple workflows in parallel with streaming updates.

        Args:
            request_id: The request ID
            user_prompt: The user prompt text
            system_prompt: The system prompt text
            workflow_info: Dictionary with workflow information
            parameters: Additional parameters
            conversation_id: The conversation ID
            callback: Callback function for streaming updates

        Returns:
            Dictionary with final results
        """
        # Get workflows to execute
        workflows = [workflow_info["primary"]]
        if workflow_info.get("parallel"):
            workflows.extend(workflow_info["parallel"])

        # Create tasks for all workflows
        tasks = []
        for workflow_id in workflows:
            task = asyncio.create_task(
                self._execute_workflow_with_streaming(
                    workflow_id=workflow_id,
                    user_prompt=user_prompt,
                    system_prompt=system_prompt,
                    parameters=parameters,
                    request_id=request_id,
                    callback=callback,
                )
            )
            tasks.append(task)

        # Wait for all workflows to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Prepare final response
        final_result = {
            "request_id": request_id,
            "conversation_id": conversation_id,
            "status": "completed",
            "workflows": {},
            "response": "",  # Will be filled with primary workflow response
        }

        # Process results
        for i, result in enumerate(results):
            workflow_id = workflows[i]

            # Handle successful result
            if not isinstance(result, Exception) and isinstance(result, dict):
                final_result["workflows"][workflow_id] = result

                # Use primary workflow response as main response
                if workflow_id == workflow_info["primary"]:
                    final_result["response"] = result.get("response", "")

                    # Add to conversation history
                    self.conversation_store.add_message(
                        conversation_id=conversation_id,
                        role="assistant",
                        content=str(result.get("response", "")),
                        metadata={"workflow_id": workflow_id},
                    )

            # Handle error
            else:
                error_msg = str(result) if isinstance(result, Exception) else "Unknown error"
                final_result["workflows"][workflow_id] = {"status": "failed", "error": error_msg}

        # Update request status
        self.requests[request_id]["status"] = "completed"

        # Send final update
        if callback:
            await callback({"event": "complete", "request_id": request_id, "result": final_result})

        return final_result

    async def _execute_workflow_with_streaming(
        self,
        workflow_id: str,
        user_prompt: str,
        system_prompt: str,
        parameters: Dict[str, Any],
        request_id: str,
        callback: Callable[[Dict[str, Any]], Awaitable[None]],
    ) -> Dict[str, Any]:
        """
        Execute a single workflow with streaming updates.

        Args:
            workflow_id: The workflow ID
            user_prompt: The user prompt text
            system_prompt: The system prompt text
            parameters: Additional parameters
            request_id: The request ID
            callback: Callback function for streaming updates

        Returns:
            Dictionary with workflow results
        """
        try:
            # Send started event
            await callback({"event": "workflow_started", "request_id": request_id, "workflow_id": workflow_id})

            # Get workflow instance
            # workflow = self.business_logic.get_workflow(workflow_id, parameters)
            result = None
            async for r in self._execute_workflow(workflow_id=workflow_id, user_prompt=user_prompt, system_prompt=system_prompt, parameters=parameters):
                result = r

            # Execute workflow
            # result = await self._execute_workflow(
            #     workflow_id=workflow_id, user_prompt=user_prompt, system_prompt=system_prompt, parameters=parameters
            # )

            # Send completed event
            await callback(
                {"event": "workflow_completed", "request_id": request_id, "workflow_id": workflow_id, "result": result}
            )

            return result

        except Exception as e:
            error_message = str(e)
            print(f"Error executing workflow {workflow_id}: {error_message}")

            # Send error event
            await callback(
                {"event": "workflow_error", "request_id": request_id, "workflow_id": workflow_id, "error": error_message}
            )

            raise e

    def add_metada_to_workflow_response(self, response, workflow_id: str, request_id: str):
        processed_response = self.business_logic.process_response(response)

        # Format result
        result = {"response": processed_response, "workflow": workflow_id, "request_id": request_id}

        # Include additional fields if available
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

    async def _execute_workflow(
        self, workflow_id: str, request_id: str, user_prompt: str, system_prompt: str, parameters: Dict[str, Any]
    ):
        """
        Execute a single workflow.

        Args:
            workflow_id: The workflow ID
            user_prompt: The user prompt text
            system_prompt: The system prompt text
            parameters: Additional parameters

        Returns:
            Dictionary with workflow results
        """
        # Get workflow instance
        workflow = self.business_logic.get_workflow(workflow_id, parameters)
        # Execute workflow based on type
        if workflow_id == "news_query" or workflow_id == "master_news_query":
            # These workflows use async execute method
            response = await workflow.execute(user_prompt, parameters)
        elif workflow_id == "direct_query":
            # Check if workflow is async
            if hasattr(workflow.execute, "__await__") or asyncio.iscoroutinefunction(workflow.execute):
                response = await workflow.execute(user_prompt, system_prompt)
            else:
                response = workflow.execute(user_prompt, system_prompt)
        elif workflow_id == "master_chat_query":
            async for response in workflow.execute(user_prompt, parameters):
                result = self.add_metada_to_workflow_response(response, workflow_id, request_id)
                # You can modify or enrich the item here
                yield result
        else:
            # For other workflows, check if they're async
            if hasattr(workflow.execute, "__await__") or asyncio.iscoroutinefunction(workflow.execute):
                response = await workflow.execute(user_prompt, parameters)
            else:
                response = workflow.execute(user_prompt, parameters)
        if workflow_id != "master_chat_query":
            # Process response
            result = self.add_metada_to_workflow_response(response, workflow_id, request_id)
            yield result

    def _extract_prompts(self, prompt: dict, parameters: Dict[str, Any]) -> tuple:
        """
        Extract user and system prompts from request.

        Args:
            prompt: The prompt dictionary
            parameters: Request parameters

        Returns:
            Tuple of (user_prompt_text, system_prompt_text)
        """
        user_prompt_text = None
        system_prompt_text = None

        # Check if this is a raw prompt
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

            # Get the prompt service from business logic (it creates or returns the already configured one)
            prompt_service = self.business_logic.get_prompt_service()
            system_prompt_text, user_prompt_text = prompt_service.get_prompts(
                sys_prompt_id=sys_prompt_id,
                sys_prompt_version=sys_prompt_version,
                user_prompt_id=user_prompt_id,
                user_prompt_version=user_prompt_version,
            )

        return user_prompt_text, system_prompt_text

    def _determine_workflows(self, user_prompt: str, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine which workflows to run.

        Args:
            user_prompt: The user prompt text
            parameters: Additional parameters

        Returns:
            Dictionary with workflow information
        """
        # Check if business logic has workflow mapping capability
        if hasattr(self.business_logic, "get_workflow_map"):
            return self.business_logic.get_workflow_map(user_prompt, parameters)

        # Fall back to basic workflow determination
        primary_workflow = self.business_logic.determine_workflow(user_prompt, parameters)

        return {"primary": primary_workflow, "parallel": []}

    def _setup_request_tracking(self, request_id: str, user_prompt_text: str, parameters: Dict[str, Any]) -> None:
        """
        Set up request tracking and observability.

        Args:
            request_id: The request ID
            user_prompt_text: The user prompt text
            parameters: Additional parameters
        """
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
                "conversation_id": parameters.get("conversation_id"),
            }

            # Get handler from business logic
            observability_handler = self.business_logic.get_observability_handler(
                observability_type=observability_type, config=observability_context
            )

            # Add handler to parameters if created successfully
            if observability_handler:
                parameters["observability_handler"] = observability_handler

        # Track request
        self.requests[request_id] = {
            "prompt": user_prompt_text,
            "parameters": parameters,
            "status": "processing",
            "conversation_id": parameters.get("conversation_id"),
            "started_at": datetime.now().isoformat(),
        }

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

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: The conversation ID

        Returns:
            The conversation or None if not found
        """
        return self.conversation_store.get_conversations_for_user(conversation_id)

    def get_conversation_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: The conversation ID
            limit: Optional limit on number of messages to return

        Returns:
            List of messages or empty list if conversation not found
        """
        return self.conversation_store.get_messages(conversation_id, limit)

    def search_chat_history(self, user_id: str, search_query: Optional[str] = None, conversation_id: Optional[str] = None, limit: Optional[int] = None, last_evaluated_key = None) -> Dict[str, Any]:
        if search_query is not None:
            ret = self.conversation_store.search_conversations(user_id, search_query, conversation_id, limit, last_evaluated_key)
        else:
            ret = self.conversation_store.get_conversations_for_user(user_id, conversation_id, limit, last_evaluated_key)
        return ret
    
    def fetch_key_terms_explanation(self) -> list:
        workflow = self.business_logic.get_workflow("stock_db_query", parameters={})
        col_def_map = workflow.get_column_definitions(None)
        ret = []
        for cn, cd in col_def_map.items():
            tmp = {"column_name": cn, "column_def": cd}
            ret.append(tmp)
        return ret
