from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from savvy.storage.models import CommChannel, CommDirection


class ClientCommunicationCreate(BaseModel):
    """외부 채널 메시지/녹음/메모를 기록.

    source_id는 dedup 키. 같은 (tenant, channel, source_id) 중복은 409로 거부됨.
    """

    channel: CommChannel
    direction: CommDirection
    occurred_at: datetime
    content: str
    source_metadata: dict[str, Any] | None = None
    source_id: str | None = None


class ClientCommunicationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    entity_id: UUID
    channel: CommChannel
    direction: CommDirection
    occurred_at: datetime
    content: str
    source_metadata: dict[str, Any] | None
    source_id: str | None
    created_at: datetime
