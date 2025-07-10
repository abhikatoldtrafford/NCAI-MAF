from abc import ABC, abstractmethod
from typing import Optional, Tuple


class BasePromptManager(ABC):
    @abstractmethod
    def get_prompt(self, prompt_id: str, prompt_version: Optional[str] = None) -> str:
        """
        Retrieve a single prompt text for the given prompt ID and version.
        """
        pass

    @abstractmethod
    def get_prompts(
        self,
        sys_prompt_id: str,
        sys_prompt_version: Optional[str],
        user_prompt_id: str,
        user_prompt_version: Optional[str],
    ) -> Tuple[str, str]:
        """
        Retrieve both system and user prompt texts.
        """
        pass


class PromptService:
    """
    A generic prompt service.
    """

    def __init__(self, manager: BasePromptManager):
        self.manager = manager

    def get_prompt(
        self,
        prompt_id: str,
        prompt_version: str,
    ) -> Tuple[str, str]:
        return self.manager.get_prompt(prompt_id, prompt_version)

    def get_prompts(
        self,
        sys_prompt_id: str,
        sys_prompt_version: str,
        user_prompt_id: str,
        user_prompt_version: str,
    ) -> Tuple[str, str]:
        return self.manager.get_prompts(sys_prompt_id, sys_prompt_version, user_prompt_id, user_prompt_version)
