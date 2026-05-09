from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select

from savvy.api.deps import LLMDep, SessionDep
from savvy.api.schemas.chat import ChatMessageOut, ChatRequest
from savvy.llm.base import Message, Role
from savvy.storage.models import ChatMessage, ChatSession, MessageRole

router = APIRouter(tags=["chat"])

DEFAULT_SYSTEM_PROMPT = (
    "너는 한국 세무사를 돕는 AI 어시스턴트야. "
    "세무사가 업무 중에 묻는 질문에 정확하고 간결하게 답해야 해.\n"
    "- 세법 관련 답변에는 근거 법령(법명·조항)을 가능하면 명시해.\n"
    "- 불확실한 부분은 추측하지 말고 그렇다고 말해.\n"
    "- 한국어로 답해."
)


def _extract_token_usage(raw: Any) -> dict[str, Any] | None:
    """Ollama 응답의 prompt_eval_count/eval_count를 표준화. 없으면 None."""
    if not isinstance(raw, dict):
        return None
    usage: dict[str, Any] = {}
    if (p := raw.get("prompt_eval_count")) is not None:
        usage["prompt"] = p
    if (c := raw.get("eval_count")) is not None:
        usage["completion"] = c
    return usage or None


def _to_llm_message(m: ChatMessage) -> Message:
    return Message(role=Role(m.role.value), content=m.content)


@router.post(
    "/chat-sessions/{session_id}/chat",
    response_model=ChatMessageOut,
    status_code=status.HTTP_201_CREATED,
)
async def chat(
    session_id: UUID,
    payload: ChatRequest,
    session: SessionDep,
    llm: LLMDep,
) -> ChatMessage:
    if await session.get(ChatSession, session_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "chat session not found")

    # 사용자 메시지를 먼저 영속화 — LLM 실패해도 사용자 입력은 보존됨.
    user_msg = ChatMessage(
        session_id=session_id, role=MessageRole.USER, content=payload.content
    )
    session.add(user_msg)
    await session.commit()

    history_stmt = (
        select(ChatMessage)
        .where(ChatMessage.session_id == session_id)
        .order_by(ChatMessage.created_at.asc())
    )
    history = list((await session.execute(history_stmt)).scalars().all())

    llm_messages = [
        Message(role=Role.SYSTEM, content=DEFAULT_SYSTEM_PROMPT),
        *[_to_llm_message(m) for m in history],
    ]

    try:
        resp = await llm.chat(llm_messages)
    except Exception as e:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"LLM call failed: {e}"
        ) from e

    assistant_msg = ChatMessage(
        session_id=session_id,
        role=MessageRole.ASSISTANT,
        content=resp.content,
        model_id=llm.model_id,
        token_usage=_extract_token_usage(resp.raw),
    )
    session.add(assistant_msg)
    await session.commit()
    await session.refresh(assistant_msg)
    return assistant_msg
