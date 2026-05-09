from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from savvy.storage.models import MessageRole


class ChatSessionBase(BaseModel):
    entity_id: UUID | None = None
    title: str | None = None


class ChatSessionCreate(ChatSessionBase):
    pass


class ChatSessionUpdate(BaseModel):
    entity_id: UUID | None = None
    title: str | None = None


class ChatSessionOut(ChatSessionBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    created_at: datetime
    updated_at: datetime


class ChatRequest(BaseModel):
    """단일 사용자 turn 입력. Phase 4 에이전트 도입 전이라 텍스트 메시지만."""

    content: str


class ChatMessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    session_id: UUID
    role: MessageRole
    content: str
    tool_calls: list[dict[str, Any]]
    tool_call_id: str | None
    model_id: str | None
    token_usage: dict[str, Any] | None
    created_at: datetime
