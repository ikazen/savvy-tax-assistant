from __future__ import annotations

from datetime import datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, String, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from savvy.config import get_settings


class Base(DeclarativeBase):
    pass


# pgvector 컬럼은 차원이 스키마에 박히므로 설정 시점에 결정.
# 임베딩 모델을 다른 차원으로 교체하려면 마이그레이션 필요.
_DIM = get_settings().embed_dimension


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
