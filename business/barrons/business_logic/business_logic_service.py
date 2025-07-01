import os
import re
from typing import Dict, Any, Optional
from business.interfaces.business_logic_interface import BusinessLogicInterface
from business.barrons.workflows.direct_query_workflow import DirectQueryWorkflow
from infrastructure.llm.agent_manager import AgentManager
from infrastructure.data.data_manager import DataManager
from application.services.prompt_service import PromptService
from infrastructure.aws.secrets_manager import get_secret
from business.barrons.workflows.news_query_execution import NewsQueryWorkflow
from business.barrons.workflows.Stock_Data_Explainer_workflow import StockDataExplainerWorkflow
from business.barrons.workflows.Stock_DB_Query_workflow import StockDBQueryWorkflow
from business.barrons.workflows.barrons_user_feedback_workflow import BarronsUserFeedBackWorkflow
from business.barrons.workflows.master_chat_workflow import MasterChatWorkflow


class BusinessLogicManager(BusinessLogicInterface):
    """Barrons implementation of business logic operations."""

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        """
        Initialize business logic components.

        Args:
            config: Optional configuration dictionary
        """
        # Store configuration
        self.config = config or {}

        # We'll initialize workflows on-demand
        self.workflows = {}
        self.agent_manager = None
        self.data_manager = None
        self.prompt_service = None

        # Secret cache to avoid repeated calls to Secrets Manager
        self.secrets_cache = {}

        # Observability handler cache
        self.observability_handlers = {}

        # Patterns for recognizing query types (can be overridden by config)
        self.data_query_patterns = self.config.get("workflows", {}).get(
            "data_query_patterns",
            [r"(?:find|search|get|query|select|fetch)", r"(?:data|information|records)", r"(?:database|table|source)"],
        )

    def set_agent_manager(self, agent_manager: AgentManager):
        """
        Set the agent manager to use for workflow creation.

        Args:
            agent_manager: The agent manager instance
        """
        self.agent_manager = agent_manager

    def set_data_manager(self, data_manager: DataManager):
        """
        Set the data manager to use for workflow creation.

        Args:
            data_manager: The data manager instance
        """
        self.data_manager = data_manager

    def get_prompt_service(self) -> PromptService:
        """
        Returns the active PromptService. If none is set, it creates one
        based on configuration, so the orchestrator stays decoupled from any specific prompt manager.
        """
        if not self.prompt_service:
            # Choose prompt manager based on configuration (default: AWS for now as it's the only one we have)
            prompt_manager_type = self.config.get("prompt_manager_type", "aws")

            if prompt_manager_type == "aws":
                from infrastructure.aws.aws_prompt_manager import AWSPromptManager

                aws_region = self.config.get("aws_region", "us-east-1")
                prompt_manager = AWSPromptManager(region=aws_region)

            # Optionally use a different prompt manager
            # elif prompt_manager_type == "other":
            #     from infrastructure.llm.custom_prompt_manager import OtherPromptManager
            #     prompt_manager = OtherPromptManager(self.config.get("custom_config", {}))

            else:
                raise ValueError(f"Unknown prompt manager type: {prompt_manager_type}")

            # Create the generic PromptService with the chosen prompt manager
            self.prompt_service = PromptService(manager=prompt_manager)

        return self.prompt_service

    def determine_workflow(self, prompt: str, parameters: Dict[str, Any]) -> str:
        """
        Determine which workflow to use based on the prompt and parameters.

        Args:
            prompt: The user prompt
            parameters: Additional parameters

        Returns:
            The workflow ID to use
        """
        # Check if workflow is explicitly specified
        if "workflow" in parameters:
            return parameters["workflow"]

        # Check for data query patterns
        prompt_lower = prompt.lower()
        if any(re.search(pattern, prompt_lower) for pattern in self.data_query_patterns):
            # return "data_query"
            pass
        if prompt_lower == "user-feedback":
            return "barrons_user_feedback"

        # Use default workflow from config or fallback to direct_query
        # return self.config.get("workflows", {}).get("default", "direct_query")
        return "master_chat_query"
    
    def get_workflow(self, workflow_id: str, parameters: Dict[str, Any]) -> Any:
        """
        Get a workflow instance by ID.

        Args:
            workflow_id: The workflow ID

        Returns:
            The workflow instance
        """
        # Create workflow if it doesn't exist
        llm = self.agent_manager.generate_custom_config_llm({"session_id": parameters.get("session_id", None), "user_id": parameters.get("user_id", None)})
        if workflow_id not in self.workflows:
            if workflow_id == "direct_query":
                if not self.agent_manager:
                    raise ValueError("Agent manager not set")
                self.workflows[workflow_id] = DirectQueryWorkflow(self.agent_manager, llm)
            elif workflow_id == "news_query":
                if not self.agent_manager or not self.data_manager:
                    raise ValueError("Agent manager or data manager not set")
                self.workflows[workflow_id] = NewsQueryWorkflow(self.agent_manager, self.get_prompt_service(), llm)
            elif workflow_id == "stock_chat":
                if not self.agent_manager or not self.data_manager:
                    raise ValueError("Agent manager or data manager not set")
                self.workflows[workflow_id] = StockDataExplainerWorkflow(self.agent_manager, self.get_prompt_service(), llm)
            elif workflow_id == "stock_db_query":
                if not self.agent_manager or not self.data_manager:
                    raise ValueError("Agent manager or data manager not set")
                self.workflows[workflow_id] = StockDBQueryWorkflow(self.agent_manager, self.get_prompt_service(), llm)
            elif workflow_id == "barrons_user_feedback":
                if not self.agent_manager or not self.data_manager:
                    raise ValueError("Agent manager or data manager not set")
                self.workflows[workflow_id] = BarronsUserFeedBackWorkflow(self.agent_manager)
            elif workflow_id == "master_chat_query":
                if not self.agent_manager or not self.data_manager:
                    raise ValueError("Agent manager or data manager not set")
                self.workflows[workflow_id] = MasterChatWorkflow(self.agent_manager, self.get_prompt_service(), llm)
            else:
                raise ValueError(f"Unknown workflow ID: {workflow_id}")

        return self.workflows[workflow_id]

    def process_response(self, response: Any) -> Any:
        """
        Process the response from a workflow.

        Args:
            response: The raw workflow response

        Returns:
            The processed response
        """
        # Enable formatting if needed (as per https://github.com/newscorp-ghfb/NCAI-MAF/pull/45/)
        # from business.barrons.business_logic.format_response import jsonify_output
        # return jsonify_output(response)
        return response

    def get_credentials(self, use_secrets_manager: bool = True, config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Get credentials from various sources.

        Args:
            use_secrets_manager: Whether to try AWS Secrets Manager
            config: Additional configuration parameters

        Returns:
            Dictionary with resolved credentials
        """
        config = config or {}
        credentials = {}

        # Try to get from AWS Secrets Manager if requested
        if use_secrets_manager:
            # Get secret name and region
            secret_name = config.get("secret_name", "ncai/barrons-ticker/staging")
            region_name = config.get("aws_region", "us-east-1")

            # Check if we have cached secrets
            cache_key = f"{secret_name}:{region_name}"
            if cache_key in self.secrets_cache:
                secrets = self.secrets_cache[cache_key]
            else:
                # Try to get from Secrets Manager
                try:
                    secrets = get_secret(secret_name, region_name)
                    # Cache the secrets
                    self.secrets_cache[cache_key] = secrets
                except Exception as e:
                    print(f"Error getting secrets: {str(e)}. Will use environment variables.")
                    secrets = {}

            # Extract credentials from secrets
            credentials.update(
                {
                    "langfuse_public_key": secrets.get("LANGFUSE_PUBLIC_KEY", ""),
                    "langfuse_secret_key": secrets.get("LANGFUSE_SECRET_KEY", ""),
                    "langfuse_host": secrets.get("LANGFUSE_HOST", ""),
                    "aws_access_key": secrets.get("AWS_ACCESS_KEY_ID"),
                    "aws_secret_key": secrets.get("AWS_SECRET_ACCESS_KEY"),
                }
            )

        # Add explicit config values (overriding secrets)
        for key in [
            "langfuse_public_key",
            "langfuse_secret_key",
            "langfuse_host",
            "aws_access_key",
            "aws_secret_key",
            "aws_region",
        ]:
            if key in config and config[key]:
                credentials[key] = config[key]

        # Fall back to environment variables for any missing values
        env_mapping = {
            "langfuse_public_key": "LANGFUSE_PUBLIC_KEY_BARRONS_CHAT",
            "langfuse_secret_key": "LANGFUSE_SECRET_KEY_BARRONS_CHAT",
            "langfuse_host": "LANGFUSE_HOST",
            "aws_access_key": "AWS_ACCESS_KEY_ID",
            "aws_secret_key": "AWS_SECRET_ACCESS_KEY",
            "aws_region": "AWS_DEFAULT_REGION",
        }

        for key, env_var in env_mapping.items():
            if key not in credentials or not credentials[key]:
                env_value = os.environ.get(env_var)
                if env_value:
                    credentials[key] = env_value

        # Ensure aws_region has a default
        if "aws_region" not in credentials or not credentials["aws_region"]:
            credentials["aws_region"] = "us-east-1"

        # Include other config values for model settings
        for key in ["project_name", "model_id", "temperature", "max_tokens", "top_p", "top_k"]:
            if key in config:
                credentials[key] = config[key]

        return credentials

    def get_observability_handler(self, observability_type: str = "langfuse", config: Optional[Dict[str, Any]] = None) -> Any:
        """
        Create an observability handler based on the specified type.

        Args:
            observability_type: Type of observability handler to create
            config: Configuration for the handler

        Returns:
            Observability handler or None if creation fails
        """
        config = config or {}

        # Check if handler is cached and use if available
        cache_key = f"{observability_type}:{config.get('session_id', '')}"
        if cache_key in self.observability_handlers:
            return self.observability_handlers[cache_key]

        # Create handler based on type
        handler = None
        if observability_type == "langfuse":
            handler = self._create_langfuse_handler(config)
        # Add other observability types here as needed
        else:
            print(f"Unsupported observability type: {observability_type}")
            return None

        # Cache the handler if created successfully
        if handler:
            self.observability_handlers[cache_key] = handler

        return handler

    def _create_langfuse_handler(self, config: Dict[str, Any]) -> Any:
        """
        Create a Langfuse handler for observability.

        Args:
            config: Configuration for the handler

        Returns:
            Langfuse handler or None if creation fails
        """
        try:
            # Get credentials for Langfuse
            credentials = self.get_credentials(config=config)

            # Check if we have the required credentials
            langfuse_public_key = credentials.get("langfuse_public_key")
            langfuse_secret_key = credentials.get("langfuse_secret_key")
            langfuse_host = credentials.get("langfuse_host")

            if not (langfuse_public_key and langfuse_secret_key and langfuse_host):
                print("Skipping Langfuse logging, credentials not found")
                return None

            # Import Langfuse here to avoid dependency issues
            from langfuse.callback import CallbackHandler

            # Get context information
            project_name = config.get("project_name", credentials.get("project_name", ""))
            session_id = config.get("session_id")
            user_id = config.get("user_id")
            trace_name = config.get("trace_name")

            # Create metadata if project name exists
            metadata = None
            if project_name and len(project_name.strip()) > 0:
                metadata = {"project_name": project_name}

            # Create handler
            handler = CallbackHandler(
                public_key=langfuse_public_key,
                secret_key=langfuse_secret_key,
                host=langfuse_host,
                session_id=session_id,
                user_id=user_id,
                metadata=metadata,
                trace_name=trace_name if trace_name and len(trace_name.strip()) > 0 else None,
            )

            return handler

        except Exception as e:
            print(f"Error creating Langfuse handler: {str(e)}")
            return None

    def configure_agent_manager(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Configure the agent manager with credentials.

        Args:
            config: Configuration parameters

        Returns:
            True if successful, False otherwise
        """
        if not self.agent_manager:
            return False

        try:
            # Get resolved credentials
            credentials = self.get_credentials(config=config)

            # Update agent manager config with credentials
            self.agent_manager.config.update(credentials)

            # Recreate the LLM with new credentials
            # provider = self.agent_manager.config.get("provider", "anthropic_bedrock")
            # self.agent_manager.llm = self.agent_manager._create_llm(provider, credentials)

            return True

        except Exception as e:
            print(f"Error configuring agent manager: {str(e)}")
            return False

    def configure_data_manager(self, config: Optional[Dict[str, Any]] = None) -> bool:
        """
        Configure the data manager with data sources.

        Args:
            config: Configuration parameters

        Returns:
            True if successful, False otherwise
        """
        if not self.data_manager:
            return False

        try:
            config = config or {}

            # Register data sources if provided
            data_sources = config.get("data_sources", {})
            for source_id, source_config in data_sources.items():
                self.data_manager.register_data_source(source_id, source_config)

            return True

        except Exception as e:
            print(f"Error configuring data manager: {str(e)}")
            return False
