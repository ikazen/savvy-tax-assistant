from __future__ import annotations

import uuid
from collections.abc import Sequence
from typing import Any, cast

import httpx

from savvy.llm.base import (
    ChatResponse,
    Message,
    ToolCall,
    ToolDefinition,
)


class OllamaLLM:
    """Ollama LLM provider — works for both local Ollama and Ollama Cloud.

    Local:  base_url="http://localhost:11434", api_key=None
    Cloud:  base_url="https://ollama.com",     api_key="<key>"
    """

    def __init__(
        self,
        model: str,
        base_url: str = "http://localhost:11434",
        api_key: str | None = None,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url.rstrip("/")
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport

    @property
    def model_id(self) -> str:
        return self._model

    async def chat(
        self,
        messages: Sequence[Message],
        tools: Sequence[ToolDefinition] | None = None,
        temperature: float = 0.0,
        max_tokens: int | None = None,
    ) -> ChatResponse:
        payload: dict[str, Any] = {
            "model": self._model,
            "messages": [self._serialize_message(m) for m in messages],
            "stream": False,
            "options": {"temperature": temperature},
        }
        if max_tokens is not None:
            payload["options"]["num_predict"] = max_tokens
        if tools:
            payload["tools"] = [self._serialize_tool(t) for t in tools]

        data = await self._post("/api/chat", payload)
        return self._parse_chat_response(data)

    async def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
        ) as client:
            resp = await client.post(path, json=payload, headers=headers)
            resp.raise_for_status()
            return cast(dict[str, Any], resp.json())

    @staticmethod
    def _serialize_message(m: Message) -> dict[str, Any]:
        out: dict[str, Any] = {"role": m.role.value, "content": m.content}
        if m.tool_calls:
            out["tool_calls"] = [
                {
                    "function": {
                        "name": tc.name,
                        "arguments": tc.arguments,
                    }
                }
                for tc in m.tool_calls
            ]
        return out

    @staticmethod
    def _serialize_tool(t: ToolDefinition) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": t.name,
                "description": t.description,
                "parameters": t.parameters,
            },
        }

    @staticmethod
    def _parse_chat_response(data: dict[str, Any]) -> ChatResponse:
        message = data.get("message", {}) or {}
        raw_calls = message.get("tool_calls") or []
        tool_calls = [
            ToolCall(
                id=str(uuid.uuid4()),
                name=tc["function"]["name"],
                arguments=tc["function"].get("arguments") or {},
            )
            for tc in raw_calls
        ]
        return ChatResponse(
            content=message.get("content") or "",
            tool_calls=tool_calls,
            finish_reason=data.get("done_reason") or "stop",
            raw=data,
        )
