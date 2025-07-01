from pydantic import BaseModel
from typing import Dict, Any, Optional, Union, List


class PromptRequest(BaseModel):
    prompt: Union[str, Dict[str, Any]]
    parameters: Dict[str, Any] = {}
    conversation_id: Optional[str] = None
    stream: bool = False


class PromptResponse(BaseModel):
    response: Union[str, Dict[str, Any]]
    request_id: str
    conversation_id: Optional[str] = None
    workflow: Optional[str] = None
    status: Optional[str] = None
    error: Optional[str] = None
    data: Optional[Dict[str, Any]] = None


class ConversationMessage(BaseModel):
    role: str
    content: str
    timestamp: str
    metadata: Optional[Dict[str, Any]] = None


class ConversationResponse(BaseModel):
    conversation_id: str
    messages: List[ConversationMessage]
    created_at: str
    last_updated: str
