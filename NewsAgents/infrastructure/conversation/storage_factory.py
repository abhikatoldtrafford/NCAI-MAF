from typing import Dict, Any, Optional
from NewsAgents.infrastructure.conversation.storage_interface import ConversationStorageInterface
from NewsAgents.infrastructure.data.plugin_manager import PluginManager


def create_storage(config: Dict[str, Any], plugin_manager: PluginManager) -> Optional[ConversationStorageInterface]:
    """
    Create a conversation storage implementation based on configuration.

    Args:
        config: Configuration dictionary
        plugin_manager: The plugin manager

    Returns:
        Storage implementation or None for in-memory
    """
    storage_type = config.get("conversation_storage", {}).get("type")

    if not storage_type or storage_type == "memory":
        # Use in-memory storage (None)
        return None

    elif storage_type == "dynamodb":
        # Use DynamoDB storage
        from NewsAgents.infrastructure.conversation.dynamodb_conversation_storage import DynamoDBConversationStorage

        # Get table names from config
        storage_config = config.get("conversation_storage", {})

        return DynamoDBConversationStorage(
            plugin_manager=plugin_manager, aws_creds=storage_config
        )

    # Add support for other storage types here

    else:
        raise ValueError(f"Unsupported storage type: {storage_type}")
