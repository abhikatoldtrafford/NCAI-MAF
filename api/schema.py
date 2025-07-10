from pydantic import BaseModel
from typing import Dict, Any, Optional, Union, List


class PromptRequest(BaseModel):
    prompt: Union[str, Dict[str, Any]]
    parameters: Dict[str, Any] = {}
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None
    stream: bool = False

class HistorySearchRequest(BaseModel):
    user_id: str = None
    search_query: Optional[str] = None
    conversation_id: Optional[str] = None
    limit: Optional[int] = None
    last_evaluated_key: Optional[Any] = None

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


class PaginationMeta(BaseModel):
    total: int
    page: int
    limit: int


class ChatSessionSummary(BaseModel):
    session_id: str
    title: str
    timestamp: str
    details_url: str


class ChatSearchItem(ChatSessionSummary):
    snippet: str


class ChatHistoryResponse(BaseModel):
    data: List[ChatSessionSummary]
    pagination: PaginationMeta


class ChatSearchResponse(BaseModel):
    data: List[ChatSearchItem]
    pagination: PaginationMeta
