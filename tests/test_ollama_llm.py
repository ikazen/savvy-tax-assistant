from __future__ import annotations

import json
from typing import Any

import httpx
import pytest

from savvy.llm import Message, Role, ToolDefinition
from savvy.llm.ollama import OllamaLLM


def _make_handler(
    response_json: dict[str, Any],
    captured: dict[str, Any],
):
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["method"] = request.method
        captured["headers"] = dict(request.headers)
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=response_json)

    return handler


@pytest.mark.asyncio
async def test_chat_basic_message_payload():
    captured: dict[str, Any] = {}
    response = {
        "message": {"role": "assistant", "content": "안녕하세요"},
        "done": True,
        "done_reason": "stop",
    }
    transport = httpx.MockTransport(_make_handler(response, captured))

    llm = OllamaLLM(
        model="qwen2.5:14b",
        base_url="http://localhost:11434",
        transport=transport,
    )

    result = await llm.chat([Message(role=Role.USER, content="hi")])

    assert result.content == "안녕하세요"
    assert result.tool_calls == []
    assert result.finish_reason == "stop"
    assert captured["url"] == "http://localhost:11434/api/chat"
    assert captured["body"]["model"] == "qwen2.5:14b"
    assert captured["body"]["messages"] == [{"role": "user", "content": "hi"}]
    assert captured["body"]["stream"] is False
    assert captured["body"]["options"]["temperature"] == 0.0
    # API key 없으면 Authorization 헤더 미전송
    assert "authorization" not in {k.lower() for k in captured["headers"]}


@pytest.mark.asyncio
async def test_chat_includes_authorization_header_when_api_key_set():
    captured: dict[str, Any] = {}
    response = {"message": {"content": "ok"}, "done_reason": "stop"}
    transport = httpx.MockTransport(_make_handler(response, captured))

    llm = OllamaLLM(
        model="gpt-oss:120b",
        base_url="https://ollama.com",
        api_key="sk-test-123",
        transport=transport,
    )

    await llm.chat([Message(role=Role.USER, content="hi")])

    assert captured["headers"]["authorization"] == "Bearer sk-test-123"
    assert captured["url"] == "https://ollama.com/api/chat"


@pytest.mark.asyncio
async def test_chat_serializes_tools_and_parses_tool_calls():
    captured: dict[str, Any] = {}
    response = {
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "search_tax_law", "arguments": {"q": "부가세"}}}
            ],
        },
        "done_reason": "stop",
    }
    transport = httpx.MockTransport(_make_handler(response, captured))

    llm = OllamaLLM(model="qwen2.5:14b", transport=transport)

    tool = ToolDefinition(
        name="search_tax_law",
        description="세법 검색",
        parameters={"type": "object", "properties": {"q": {"type": "string"}}},
    )
    result = await llm.chat([Message(role=Role.USER, content="부가세")], tools=[tool])

    assert captured["body"]["tools"][0]["function"]["name"] == "search_tax_law"
    assert len(result.tool_calls) == 1
    assert result.tool_calls[0].name == "search_tax_law"
    assert result.tool_calls[0].arguments == {"q": "부가세"}
    assert result.tool_calls[0].id  # 자동 생성된 ID


@pytest.mark.asyncio
async def test_chat_passes_max_tokens_as_num_predict():
    captured: dict[str, Any] = {}
    response = {"message": {"content": "ok"}, "done_reason": "stop"}
    transport = httpx.MockTransport(_make_handler(response, captured))

    llm = OllamaLLM(model="x", transport=transport)
    await llm.chat([Message(role=Role.USER, content="hi")], max_tokens=128)

    assert captured["body"]["options"]["num_predict"] == 128


@pytest.mark.asyncio
async def test_chat_serializes_assistant_tool_calls_in_history():
    """이전 turn의 어시스턴트 tool_calls 메시지가 직렬화되어 다시 보내지는지 검증."""
    from savvy.llm import ToolCall

    captured: dict[str, Any] = {}
    response = {"message": {"content": "done"}, "done_reason": "stop"}
    transport = httpx.MockTransport(_make_handler(response, captured))

    llm = OllamaLLM(model="x", transport=transport)
    history = [
        Message(role=Role.USER, content="검색해줘"),
        Message(
            role=Role.ASSISTANT,
            content="",
            tool_calls=[ToolCall(id="abc", name="search", arguments={"q": "x"})],
        ),
        Message(role=Role.TOOL, content="결과: ..."),
    ]
    await llm.chat(history)

    assistant_msg = captured["body"]["messages"][1]
    assert assistant_msg["tool_calls"][0]["function"]["name"] == "search"
    assert assistant_msg["tool_calls"][0]["function"]["arguments"] == {"q": "x"}
