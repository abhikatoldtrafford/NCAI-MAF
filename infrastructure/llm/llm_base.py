import abc
import warnings
from langfuse.callback import CallbackHandler

from typing import Optional

class LLMModel(abc.ABC):
    
    def __init__(self, project_name: str, langfuse_public_key: str, langfuse_secret_key: str, langfuse_host: str, logging_session: Optional[str]=None, user_id: Optional[str] = None, trace_name: str = None) -> None:
        super().__init__()
        self.langfuse_handler = None
        if langfuse_public_key and langfuse_secret_key and langfuse_host:
            self.langfuse_handler = CallbackHandler(
                public_key=langfuse_public_key,
                secret_key=langfuse_secret_key,
                host=langfuse_host,
                session_id=logging_session,
                user_id=user_id,
                metadata= None if project_name is None or len(project_name.strip()) == 0 else {"project_name": project_name},
                trace_name= None if trace_name is None or len(trace_name.strip()) == 0 else trace_name
            )
        else:
            warnings.warn("Skipping logging, Langfuse keys not found")
    
    """
    Abstract base class for all LLM (Large Language Model) models.
    """

    @abc.abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, parser) -> str:
        """
        Generate text based on the given prompt.

        Args:
            system_prompt (str): The input prompt for text generation.
            user_prompt (str): The input prompt for text generation.
        Returns:
            str: The generated text.
        """
        pass