from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
import uuid


class ConversationStore:
    """
    Manages conversation state and history for threaded conversations.
    """

    def __init__(self, max_age_minutes: int = 60, max_conversations: int = 1000):
        """
        Initialize the conversation store.

        Args:
            max_age_minutes: Maximum age of conversations in minutes before cleanup
            max_conversations: Maximum number of conversations to store
        """
        self.conversations = {}
        self.max_age_minutes = max_age_minutes
        self.max_conversations = max_conversations
        self.last_cleanup = datetime.now()

    def create_conversation(self, conversation_id: Optional[str] = None) -> str:
        """
        Create a new conversation or reset an existing one.

        Args:
            conversation_id: Optional ID for the conversation

        Returns:
            The conversation ID
        """
        # Generate ID if not provided
        if not conversation_id:
            conversation_id = str(uuid.uuid4())

        # Create conversation structure
        self.conversations[conversation_id] = {
            "created_at": datetime.now(),
            "last_updated": datetime.now(),
            "messages": [],
            "metadata": {},
        }

        # Run cleanup if needed
        self._maybe_cleanup()

        return conversation_id

    def add_message(self, conversation_id: str, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> int:
        """
        Add a message to a conversation.

        Args:
            conversation_id: The conversation ID
            role: The role of the message sender (user/assistant)
            content: The message content
            metadata: Optional message metadata

        Returns:
            The index of the new message
        """
        # Create conversation if it doesn't exist
        if conversation_id not in self.conversations:
            self.create_conversation(conversation_id)

        # Add message
        message = {"role": role, "content": content, "timestamp": datetime.now().isoformat(), "metadata": metadata or {}}

        conv = self.conversations[conversation_id]
        conv["messages"].append(message)
        conv["last_updated"] = datetime.now()

        # Return index of new message
        return len(conv["messages"]) - 1

    def get_conversation(self, conversation_id: str) -> Optional[Dict[str, Any]]:
        """
        Get a conversation by ID.

        Args:
            conversation_id: The conversation ID

        Returns:
            The conversation or None if not found
        """
        return self.conversations.get(conversation_id)

    def get_messages(self, conversation_id: str, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Get messages from a conversation.

        Args:
            conversation_id: The conversation ID
            limit: Optional limit on number of messages to return (most recent)

        Returns:
            List of messages or empty list if conversation not found
        """
        conversation = self.get_conversation(conversation_id)
        if not conversation:
            return []

        messages = conversation["messages"]
        if limit and len(messages) > limit:
            return messages[-limit:]
        return messages

    def get_conversations_for_user(self, user_id: str, page: int, limit: int) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Get conversations by user.

        Args:
            user_id:
            page:
            limit:

        Return (total_count, [{conversation_id, created_at, last_updated, metadata}])
        """
        all_convs = []
        for cid, conv in self.conversations.items():
            if conv["metadata"].get("user_id") == user_id:
                all_convs.append(
                    {
                        "conversation_id": cid,
                        "created_at": conv["created_at"].isoformat(),
                        "last_updated": conv["last_updated"].isoformat(),
                        "metadata": conv["metadata"],
                    }
                )
        all_convs.sort(key=lambda x: x["last_updated"], reverse=True)
        total = len(all_convs)
        start = (page - 1) * limit
        return total, all_convs[start : start + limit]

    def search_conversations(self, user_id: str, query: str, page: int, limit: int) -> Tuple[int, List[Dict[str, Any]]]:
        """
        Search user conversation.

        Args:
            user_id:
            page:
            limit:

        Return (total_count, [{conversation_id, created_at, snippet}])
        """
        matches = []
        q = query.lower()
        for cid, conv in self.conversations.items():
            if conv["metadata"].get("user_id") != user_id:
                continue
            for m in conv["messages"]:
                if m["role"] == "user" and q in m["content"].lower():
                    text = m["content"]
                    idx = text.lower().index(q)
                    start = max(0, idx - 30)
                    end = min(len(text), idx + len(query) + 30)
                    snippet = text[start:end].strip()
                    matches.append({"conversation_id": cid, "created_at": conv["created_at"].isoformat(), "snippet": snippet})
                    break
        matches.sort(key=lambda x: x["created_at"], reverse=True)
        total = len(matches)
        start = (page - 1) * limit
        return total, matches[start : start + limit]

    def format_for_prompt(self, conversation_id: str, limit: Optional[int] = None) -> str:
        """
        Format conversation history for inclusion in a prompt.

        Args:
            conversation_id: The conversation ID
            limit: Optional limit on number of messages to include

        Returns:
            Formatted conversation history
        """
        messages = self.get_messages(conversation_id, limit)
        if not messages:
            return ""

        # Format as a string
        formatted = "Previous conversation:\n\n"
        for msg in messages:
            role = "User" if msg["role"].lower() == "user" else "Assistant"
            formatted += f"{role}: {msg['content']}\n\n"

        return formatted

    def update_metadata(self, conversation_id: str, metadata: Dict[str, Any]) -> bool:
        """
        Update metadata for a conversation.

        Args:
            conversation_id: The conversation ID
            metadata: Metadata to update

        Returns:
            True if successful, False if conversation not found
        """
        if conversation_id not in self.conversations:
            return False

        # Update metadata
        self.conversations[conversation_id]["metadata"].update(metadata)
        self.conversations[conversation_id]["last_updated"] = datetime.now()

        return True

    def delete_conversation(self, conversation_id: str) -> bool:
        """
        Delete a conversation.

        Args:
            conversation_id: The conversation ID

        Returns:
            True if deleted, False if not found
        """
        if conversation_id in self.conversations:
            del self.conversations[conversation_id]
            return True
        return False

    def _maybe_cleanup(self) -> None:
        """
        Run cleanup if needed to remove old conversations.
        """
        # Only run cleanup occasionally
        now = datetime.now()
        if (now - self.last_cleanup).total_seconds() < 60:
            return

        self.last_cleanup = now
        cutoff = now - timedelta(minutes=self.max_age_minutes)

        # Remove old conversations
        to_remove = []
        for conv_id, conv in self.conversations.items():
            if conv["last_updated"] < cutoff:
                to_remove.append(conv_id)

        for conv_id in to_remove:
            del self.conversations[conv_id]

        # If still too many conversations, remove oldest
        if len(self.conversations) > self.max_conversations:
            sorted_convs = sorted(self.conversations.items(), key=lambda x: x[1]["last_updated"])
            to_remove = sorted_convs[: len(self.conversations) - self.max_conversations]
            for conv_id, _ in to_remove:
                del self.conversations[conv_id]
