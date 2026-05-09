from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from savvy.storage.models import ClientKind


class EntityBase(BaseModel):
    kind: ClientKind
    name: str
    external_id: str | None = None
    owner_person_id: UUID | None = None
    memo: str | None = None


class EntityCreate(EntityBase):
    pass


class EntityUpdate(BaseModel):
    """전부 optional. exclude_unset으로 보낸 필드만 갱신."""

    kind: ClientKind | None = None
    name: str | None = None
    external_id: str | None = None
    owner_person_id: UUID | None = None
    memo: str | None = None


class EntityOut(EntityBase):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    tenant_id: str
    created_at: datetime
    updated_at: datetime
