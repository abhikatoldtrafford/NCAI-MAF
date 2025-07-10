"""
NewsAgents application module.
"""

__version__ = "0.1.0"

from NewsAgents.application.services.prompt_service import PromptService, BasePromptManager

__all__ = [
    # Application services
    "PromptService",
    "BasePromptManager",
]