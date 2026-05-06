from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any, Protocol, runtime_checkable


@dataclass
class VectorRecord:
    id: str
    vector: list[float]
    payload: dict[str, Any] = field(default_factory=dict)


@dataclass
class SearchHit:
    id: str
    score: float
    payload: dict[str, Any]


@runtime_checkable
class VectorStore(Protocol):
    async def upsert(
        self,
        namespace: str,
        records: Sequence[VectorRecord],
    ) -> None: ...

    async def search(
        self,
        namespace: str,
        query_vector: list[float],
        k: int = 10,
        filter: dict[str, Any] | None = None,
    ) -> list[SearchHit]: ...

    async def delete(
        self,
        namespace: str,
        ids: Sequence[str],
    ) -> None: ...
