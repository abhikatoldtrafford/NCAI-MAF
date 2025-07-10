from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional, Tuple


class ConversationStorageInterface(ABC):
    """Interface for conversation storage implementations."""

    @abstractmethod
    def create_conversation(self, conversation_id: str, metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Create a new conversation.

        Args:
            conversation_id: The conversation ID
            metadata: Optional metadata

        Returns:
            The created conversation
        """
        pass

    @abstractmethod
    def get_conversations_for_user(self, user_id: str, page: int, limit: int) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Get conversations by user.

        Args:
            user_id:
            page:
            limit:

        Return (total_count, [{conversation_id, created_at, last_updated, metadata}])
        """
        pass

    @abstractmethod
    def search_conversations(self, user_id: str, query: str, page: int, limit: int) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Search user conversation.

        Args:
            user_id:
            page:
            limit:

        Return (total_count, [{conversation_id, created_at, snippet}])
        """
        pass

    @abstractmethod
    def add_message(self, conversation_id: str, message: Dict[str, Any]) -> bool:
        """
        Add a message to a conversation.

        Args:
            conversation_id: The conversation ID
            message: The message to add

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def get_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: The conversation ID
            limit: Optional limit on number of messages

        Returns:
            List of messages
        """
        pass

    @abstractmethod
    def update_metadata(self, conversation_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update metadata for a conversation.

        Args:
            conversation_id: The conversation ID
            metadata: The metadata to update

        Returns:
            True if successful, False otherwise
        """
        pass

    @abstractmethod
    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            True if deleted, False if not found
        """
        pass

    @abstractmethod
    def cleanup_expired(self, max_age_minutes: int) -> int:
        """
        Clean up expired conversations.

        Args:
            max_age_minutes: Maximum age in minutes

        Returns:
            Number of conversations deleted
        """
        pass
