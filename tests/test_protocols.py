from savvy.embedding import EmbeddingProvider
from savvy.llm import (
    ChatResponse,
    LLMProvider,
    Message,
    Role,
    ToolCall,
    ToolDefinition,
)
from savvy.vectorstore import SearchHit, VectorRecord, VectorStore


class _FakeLLM:
    @property
    def model_id(self) -> str:
        return "fake"

    async def chat(self, messages, tools=None, temperature=0.0, max_tokens=None):
        return ChatResponse(content="ok", tool_calls=[], finish_reason="stop")


class _FakeEmbedding:
    @property
    def model_id(self) -> str:
        return "fake"

    @property
    def dimension(self) -> int:
        return 3

    async def embed(self, texts):
        return [[0.0, 0.0, 0.0] for _ in texts]


class _FakeVectorStore:
    async def upsert(self, namespace, records):
        return None

    async def search(self, namespace, query_vector, k=10, filter=None):
        return []

    async def delete(self, namespace, ids):
        return None


def test_llm_protocol_conformance():
    assert isinstance(_FakeLLM(), LLMProvider)


def test_embedding_protocol_conformance():
    assert isinstance(_FakeEmbedding(), EmbeddingProvider)


def test_vectorstore_protocol_conformance():
    assert isinstance(_FakeVectorStore(), VectorStore)


def test_message_dataclass():
    m = Message(role=Role.USER, content="hi")
    assert m.role is Role.USER
    assert m.tool_calls == []


def test_tool_definition():
    t = ToolDefinition(name="x", description="d", parameters={"type": "object"})
    assert t.name == "x"


def test_vector_record_default_payload():
    r = VectorRecord(id="a", vector=[0.1, 0.2])
    assert r.payload == {}


def test_search_hit_shape():
    h = SearchHit(id="a", score=0.9, payload={"x": 1})
    assert h.score == 0.9


def test_tool_call_round_trip():
    tc = ToolCall(id="1", name="search", arguments={"q": "test"})
    assert tc.arguments["q"] == "test"
