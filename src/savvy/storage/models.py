from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.sql import text as sql_text

from savvy.config import get_settings


class Base(DeclarativeBase):
    pass


# pgvector 컬럼은 차원이 스키마에 박히므로 설정 시점에 결정.
# 임베딩 모델을 다른 차원으로 교체하려면 마이그레이션 필요.
_DIM = get_settings().embed_dimension


# ---- enum types ----

class ClientKind(StrEnum):
    CORP = "corp"
    INDIVIDUAL = "individual"


class MessageRole(StrEnum):
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"
    SYSTEM = "system"


class CommChannel(StrEnum):
    KAKAO = "kakao"
    PHONE = "phone"
    EMAIL = "email"
    MEETING = "meeting"
    NOTE = "note"


class CommDirection(StrEnum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"
    NOTE = "note"


def _enum_col(enum_cls: type[StrEnum], name: str) -> Enum:
    """ENUM은 VARCHAR + CHECK constraint로 저장. native PG ENUM 안 씀.

    Why: native ENUM은 ALTER TYPE을 별도 마이그레이션해야 추가 가능. CHECK는 컬럼 정의에
    포함되어 create_all로 멱등 관리되고, 값 추가는 모델 수정 + 컬럼 ALTER만으로 충분.
    """
    return Enum(
        enum_cls,
        name=name,
        native_enum=False,
        values_callable=lambda e: [v.value for v in e],
    )


# ---- vector store ----

class VectorEmbedding(Base):
    __tablename__ = "vector_embeddings"

    namespace: Mapped[str] = mapped_column(String, primary_key=True)
    id: Mapped[str] = mapped_column(String, primary_key=True)
    vector: Mapped[list[float]] = mapped_column(Vector(_DIM), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default="{}"
    )
    model_id: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


# ---- user domain ----

class Person(Base):
    """자연인 (사장님 등). 한 명이 여러 entity의 owner일 수 있음."""

    __tablename__ = "persons"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(Text, nullable=True)
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_persons_tenant_name", "tenant_id", "name"),
    )


class Entity(Base):
    """수임 단위 (법인/개인사업자). 세무사가 관리하는 사업체."""

    __tablename__ = "entities"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    kind: Mapped[ClientKind] = mapped_column(
        _enum_col(ClientKind, "client_kind"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    owner_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("persons.id", ondelete="SET NULL"),
        nullable=True,
    )
    memo: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index("idx_entities_tenant_kind", "tenant_id", "kind"),
        Index("idx_entities_owner", "owner_person_id"),
        # external_id 가 null이 아닐 때만 unique (사업자번호 중복 방지).
        Index(
            "uq_entities_tenant_external",
            "tenant_id",
            "external_id",
            unique=True,
            postgresql_where=sql_text("external_id IS NOT NULL"),
        ),
    )


class ChatSession(Base):
    """세무사 ↔ 챗봇 대화 세션. LLM 컨텍스트 유지 단위."""

    __tablename__ = "chat_sessions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=True,
    )
    title: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    __table_args__ = (
        Index(
            "idx_chat_sessions_tenant_entity_updated",
            "tenant_id",
            "entity_id",
            "updated_at",
        ),
    )


class ChatMessage(Base):
    __tablename__ = "chat_messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    session_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("chat_sessions.id", ondelete="CASCADE"),
        nullable=False,
    )
    role: Mapped[MessageRole] = mapped_column(
        _enum_col(MessageRole, "message_role"), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[list[dict[str, Any]]] = mapped_column(
        JSONB, nullable=False, default=list, server_default="[]"
    )
    tool_call_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    model_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    token_usage: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_chat_messages_session_created", "session_id", "created_at"),
    )


class ClientCommunication(Base):
    """세무사 ↔ 실제 고객의 카톡/전화/메일 등 외부 채널 커뮤니케이션 (RAG 인풋)."""

    __tablename__ = "client_communications"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    tenant_id: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("entities.id", ondelete="CASCADE"),
        nullable=False,
    )
    channel: Mapped[CommChannel] = mapped_column(
        _enum_col(CommChannel, "comm_channel"), nullable=False
    )
    direction: Mapped[CommDirection] = mapped_column(
        _enum_col(CommDirection, "comm_direction"), nullable=False
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_metadata: Mapped[dict[str, Any] | None] = mapped_column(
        JSONB, nullable=True
    )
    source_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index(
            "idx_client_comm_tenant_entity_occurred",
            "tenant_id",
            "entity_id",
            "occurred_at",
        ),
        # 외부 채널 메시지 중복 입력 방지 (source_id 있을 때만).
        Index(
            "uq_client_comm_source",
            "tenant_id",
            "channel",
            "source_id",
            unique=True,
            postgresql_where=sql_text("source_id IS NOT NULL"),
        ),
    )


class ClientCommunicationChunk(Base):
    """ClientCommunication을 임베딩 단위로 청킹한 결과."""

    __tablename__ = "client_communication_chunks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    communication_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_communications.id", ondelete="CASCADE"),
        nullable=False,
    )
    text: Mapped[str] = mapped_column(Text, nullable=False)
    chunk_idx: Mapped[int] = mapped_column(Integer, nullable=False)
    token_count: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("idx_client_comm_chunks_comm_idx", "communication_id", "chunk_idx"),
    )
