from typing import Dict, Optional, Union, Any
import re
from agent_workflow.workflow_engine import (
    WorkflowManager,
    WorkflowInput,
    BaseProviderConfig,
    ProviderConfiguration,
    OpenAIProviderConfig,
    ModelSettings,
)
from agent_workflow.providers import OpenaiLLMObservabilityProvider
from NewsAgents.services.aws_credentials import AWSCredentialsProvider

class AgentManager:
    """
    Generic manager for LLM workflows.
    """

    def __init__(
        self,
        config: Optional[Dict] = None,
        default_workflow_file: Optional[str] = None,
        provider_config_name: str = "openai_gpt4",
        aws_creds: Dict[str, Any] = None
    ):
        self.config = config or {}
        self.provider = self.config.get("provider", "openai")
        self.provider_config_name = provider_config_name
        self.default_workflow_file = default_workflow_file
        if aws_creds is None:
            aws_credential_provider = AWSCredentialsProvider()
            aws_creds = aws_credential_provider.get_credentials()
        self.aws_creds = aws_creds


    def _setup_provider_config(self) -> ProviderConfiguration:
        cfgs: Dict[str, BaseProviderConfig] = {}
        if self.provider == "openai":
            # key = self.config.get("openai_api_key")
            key = self.aws_creds.get("OPENAI_API_KEY", "")
            if not key:
                raise Exception("Error: OPENAI_API_KEY must be set")
            cfgs[self.provider_config_name] = OpenAIProviderConfig(
                provider_type=self.provider,
                model="gpt-4o",
                api_key=key,
                model_settings=ModelSettings(temperature=0.7),
            )
        else:
            raise Exception(f"Unsupported provider: {self.provider}")
        return ProviderConfiguration(providers=cfgs)

    def _load_yaml_file(self, inputs: Optional[dict]) -> str:
        """
        Temporary YAML loader. Replace all occurrences of {{ key }} in a raw YAML file.
        (Since WorkflowInput is not filling in some fields - use this method for now).
        """
        with open(self.default_workflow_file, "r") as f:
            raw_yaml = f.read()

        if not inputs:
            return raw_yaml

        filled = raw_yaml
        for key, val in inputs.items():
            pattern = re.compile(r"^([ \t]*)\{\{\s*" + re.escape(key) + r"\s*\}\}", re.MULTILINE)

            def replacer(match: re.Match) -> str:
                indent = match.group(1) or ""
                if "\n" in val:
                    lines = val.splitlines(True)
                    indented = "".join(indent + "  " + line for line in lines)
                    return indented.rstrip("\n")
                else:
                    return indent + val

            filled = pattern.sub(replacer, filled)

        return filled

    async def run_workflow(
        self,
        user_prompt: str,
        provider_mapping: Optional[Dict[str, str]] = None,
        runtime_inputs: Optional[Dict[str, Any]] = None,
    ) -> Union[str, Dict]:
        """
        Execute an entire workflow.
        """
        # Configure
        inputs_dict = {} if not runtime_inputs else dict(runtime_inputs)
        # print("inputs_dict", inputs_dict)
        print("default_workflow_file", self.default_workflow_file)
        source_file = self._load_yaml_file(inputs_dict)
        # print("source_file", source_file)
        print("Loaded Source file yaml")
        provider_cfg = self._setup_provider_config()
        print("Got cfg")
        wf_input = WorkflowInput(
            user_query=user_prompt,
            workflow={"inputs": inputs_dict},
            provider_config=provider_cfg,
            provider_mapping=provider_mapping,
        )

        # print("wf_input", wf_input)
        # Execute
        wm = WorkflowManager(
            engine_type=self.provider,
            provider_config=provider_cfg,
            llm_observability_provider=[OpenaiLLMObservabilityProvider()],
        )
        print("wm", wm)
        wf = await wm.initialize_workflow(source_file, provider_mapping)
        print("wf", wf)
        exec_result = await wm.execute(wf, wf_input)
        print("exec_result", exec_result)
        final = {out.agent: out.output for out in exec_result.agent_outputs}
        print("final", final)

        return final
