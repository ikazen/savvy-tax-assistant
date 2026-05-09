from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from savvy.api.deps import SessionDep
from savvy.api.schemas.chat import (
    ChatMessageOut,
    ChatSessionCreate,
    ChatSessionOut,
    ChatSessionUpdate,
)
from savvy.config import get_settings
from savvy.storage.models import ChatMessage, ChatSession, Entity

router = APIRouter(prefix="/chat-sessions", tags=["chat"])


async def _ensure_entity_exists(entity_id: UUID, session: SessionDep) -> None:
    if await session.get(Entity, entity_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, f"entity {entity_id} not found")


@router.post("", response_model=ChatSessionOut, status_code=status.HTTP_201_CREATED)
async def create_chat_session(
    payload: ChatSessionCreate, session: SessionDep
) -> ChatSession:
    if payload.entity_id is not None:
        await _ensure_entity_exists(payload.entity_id, session)
    chat = ChatSession(
        tenant_id=get_settings().default_tenant_id,
        **payload.model_dump(),
    )
    session.add(chat)
    await session.commit()
    await session.refresh(chat)
    return chat


@router.get("", response_model=list[ChatSessionOut])
async def list_chat_sessions(
    session: SessionDep,
    entity_id: UUID | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[ChatSession]:
    stmt = select(ChatSession).where(
        ChatSession.tenant_id == get_settings().default_tenant_id
    )
    if entity_id is not None:
        stmt = stmt.where(ChatSession.entity_id == entity_id)
    stmt = stmt.order_by(ChatSession.updated_at.desc()).limit(limit).offset(offset)
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{session_id}", response_model=ChatSessionOut)
async def get_chat_session(session_id: UUID, session: SessionDep) -> ChatSession:
    chat = await session.get(ChatSession, session_id)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "chat session not found")
    return chat


@router.patch("/{session_id}", response_model=ChatSessionOut)
async def update_chat_session(
    session_id: UUID, payload: ChatSessionUpdate, session: SessionDep
) -> ChatSession:
    chat = await session.get(ChatSession, session_id)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "chat session not found")
    updates = payload.model_dump(exclude_unset=True)
    if "entity_id" in updates and updates["entity_id"] is not None:
        await _ensure_entity_exists(updates["entity_id"], session)
    for field, value in updates.items():
        setattr(chat, field, value)
    await session.commit()
    await session.refresh(chat)
    return chat


@router.delete("/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_chat_session(session_id: UUID, session: SessionDep) -> None:
    chat = await session.get(ChatSession, session_id)
    if chat is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "chat session not found")
    await session.delete(chat)
    await session.commit()


@router.get("/{session_id}/messages", response_model=list[ChatMessageOut])
async def list_chat_messages(
    session_id: UUID,
    session: SessionDep,
    limit: int = Query(default=100, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
) -> list[ChatMessage]:
    if await session.get(ChatSession, session_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "chat session not found")
    stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())
