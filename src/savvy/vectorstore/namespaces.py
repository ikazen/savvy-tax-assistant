"""VectorStore namespace 규약.

검색 인덱스의 격리 단위. 같은 namespace 안에서만 유사도 비교됨.

- TAX_LAW    : 세법 청크 (LawChunk.id ↔ vector_embeddings.id 매핑)
- CASE_LAW   : 판례 청크 (CaseChunk.id ↔ vector_embeddings.id 매핑)
- client_history(entity_id) : 사업체별 외부 커뮤니케이션 히스토리
                              (ClientCommunicationChunk.id ↔ vector_embeddings.id 매핑)
"""

from __future__ import annotations

import uuid

TAX_LAW = "tax_law"
CASE_LAW = "case_law"


def client_history(entity_id: uuid.UUID | str) -> str:
    """사업체(Entity) 단위로 격리되는 고객 커뮤니케이션 namespace."""
    return f"client_history:{entity_id}"
