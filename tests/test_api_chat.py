from __future__ import annotations

from collections.abc import AsyncIterator, Sequence
from uuid import UUID, uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.api.app import create_app
from savvy.api.routers.chat import DEFAULT_SYSTEM_PROMPT
from savvy.config import get_settings
from savvy.llm.base import ChatResponse, Message, Role, ToolDefinition
from savvy.storage.models import ChatMessage, ChatSession, MessageRole
from tests.conftest import requires_db

pytestmark = requires_db


class FakeLLM:
    """테스트용 LLM. 호출 인자 기록 + 미리 지정한 응답 반환."""

    def __init__(self, response: str = "테스트 응답") -> None:
        self._response = response
        self.calls: list[list[Message]] = []
        self.fail: Exception | None = None

    @property
    def model_id(self) -> str:
        return "fake-model"

    async def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        self.calls.append(list(messages))
        if self.fail is not None:
            raise self.fail
        return ChatResponse(
            content=self._response,
            tool_calls=[],
            finish_reason="stop",
            raw={"prompt_eval_count": 42, "eval_count": 17},
        )


@pytest.fixture
def fake_llm() -> FakeLLM:
    return FakeLLM()


@pytest_asyncio.fixture
async def client(
    session_factory: async_sessionmaker[AsyncSession],
    fake_llm: FakeLLM,
) -> AsyncIterator[AsyncClient]:
    app = create_app()
    app.state.session_factory = session_factory
    app.state.settings = get_settings()
    app.state.llm = fake_llm
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as c:
        yield c


@pytest_asyncio.fixture(autouse=True)
async def _cleanup(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[None]:
    yield
    async with session_factory() as s:
        await s.execute(delete(ChatMessage))
        await s.execute(delete(ChatSession))
        await s.commit()


async def _create_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> UUID:
    async with session_factory() as s:
        chat = ChatSession(tenant_id="default")
        s.add(chat)
        await s.commit()
        await s.refresh(chat)
        return chat.id


async def test_chat_persists_user_and_assistant_messages(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    fake_llm: FakeLLM,
) -> None:
    sid = await _create_session(session_factory)

    resp = await client.post(
        f"/api/v1/chat-sessions/{sid}/chat",
        json={"content": "법인세 절세 알려줘"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["role"] == "assistant"
    assert body["content"] == "테스트 응답"
    assert body["model_id"] == "fake-model"
    assert body["token_usage"] == {"prompt": 42, "completion": 17}

    # DB에는 user + assistant 두 행이 남아야 함
    async with session_factory() as s:
        rows = (
            await s.execute(
                select(ChatMessage).where(ChatMessage.session_id == sid)
                .order_by(ChatMessage.created_at)
            )
        ).scalars().all()
    assert [r.role for r in rows] == [MessageRole.USER, MessageRole.ASSISTANT]
    assert rows[0].content == "법인세 절세 알려줘"


async def test_chat_sends_system_prompt_and_history(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    fake_llm: FakeLLM,
) -> None:
    sid = await _create_session(session_factory)

    await client.post(
        f"/api/v1/chat-sessions/{sid}/chat", json={"content": "첫 질문"}
    )
    await client.post(
        f"/api/v1/chat-sessions/{sid}/chat", json={"content": "두번째 질문"}
    )

    # 두번째 호출 인자: system + user1 + assistant1 + user2
    last_call = fake_llm.calls[-1]
    assert last_call[0].role == Role.SYSTEM
    assert last_call[0].content == DEFAULT_SYSTEM_PROMPT
    assert [m.role for m in last_call[1:]] == [
        Role.USER,
        Role.ASSISTANT,
        Role.USER,
    ]
    assert last_call[1].content == "첫 질문"
    assert last_call[-1].content == "두번째 질문"


async def test_chat_unknown_session_returns_404(client: AsyncClient) -> None:
    resp = await client.post(
        f"/api/v1/chat-sessions/{uuid4()}/chat",
        json={"content": "안녕"},
    )
    assert resp.status_code == 404


async def test_chat_llm_failure_preserves_user_msg_and_returns_502(
    client: AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    fake_llm: FakeLLM,
) -> None:
    sid = await _create_session(session_factory)
    fake_llm.fail = RuntimeError("LLM 다운")

    resp = await client.post(
        f"/api/v1/chat-sessions/{sid}/chat",
        json={"content": "안녕"},
    )
    assert resp.status_code == 502

    # user 메시지만 남아 있어야 함 (assistant 저장 안 됨)
    async with session_factory() as s:
        rows = (
            await s.execute(
                select(ChatMessage).where(ChatMessage.session_id == sid)
            )
        ).scalars().all()
    assert len(rows) == 1
    assert rows[0].role == MessageRole.USER
    assert rows[0].content == "안녕"
