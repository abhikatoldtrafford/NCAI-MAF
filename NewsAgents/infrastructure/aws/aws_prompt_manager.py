import os
from typing import Optional, Tuple
import boto3
from NewsAgents.application.services.prompt_service import BasePromptManager


class AWSPromptManager(BasePromptManager):
    def __init__(self, region: str = "us-east-1"):
        aws_access_key_id = os.getenv("AWS_ACCESS_KEY_ID", "")
        aws_secret_access_key = os.getenv("AWS_SECRET_ACCESS_KEY", "")
        if aws_access_key_id is not None and len(aws_access_key_id.strip()) > 0 and aws_secret_access_key is not None and len(aws_secret_access_key.strip()) > 0:
            self.client = boto3.client(
                service_name='bedrock-agent',
                region_name=region,
                aws_access_key_id=aws_access_key_id,
                aws_secret_access_key=aws_secret_access_key
            )
        else:
            self.client = boto3.client("bedrock-agent", region_name=region)

    def _fetch_prompt(self, prompt_id: str, prompt_version: Optional[str] = None) -> str:
        params = {"promptIdentifier": prompt_id}
        if prompt_version:
            params["promptVersion"] = prompt_version

        response = self.client.get_prompt(**params)
        variants = response.get("variants", [])
        if not variants:
            raise ValueError(f"No prompt variants found for prompt: {prompt_id}")

        template_conf = variants[0].get("templateConfiguration", {})
        text_conf = template_conf.get("text", {})
        text = text_conf.get("text")
        if text is None:
            raise KeyError("Prompt text not found in the expected response structure.")

        return text

    def get_prompt(self, prompt_id: str, prompt_version: str = None) -> str:
        return self._fetch_prompt(prompt_id, prompt_version)

    def get_prompts(
        self,
        sys_prompt_id: str,
        sys_prompt_version: str,
        user_prompt_id: str,
        user_prompt_version: str,
    ) -> Tuple[str, str]:
        system_text = self.get_prompt(sys_prompt_id, sys_prompt_version)
        user_text = self.get_prompt(user_prompt_id, user_prompt_version)
        return system_text, user_text
