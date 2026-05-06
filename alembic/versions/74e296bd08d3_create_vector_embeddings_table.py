"""create vector_embeddings table

Revision ID: 74e296bd08d3
Revises:
Create Date: 2026-05-07 02:41:45.246718

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

from alembic import op
from savvy.config import get_settings

revision: str = "74e296bd08d3"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    dim = get_settings().embed_dimension

    op.create_table(
        "vector_embeddings",
        sa.Column("namespace", sa.String(), nullable=False),
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("vector", Vector(dim), nullable=False),
        sa.Column(
            "payload",
            sa.dialects.postgresql.JSONB(),
            nullable=False,
            server_default="{}",
        ),
        sa.Column("model_id", sa.String(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("namespace", "id"),
    )

    op.create_index(
        "idx_vector_embeddings_namespace",
        "vector_embeddings",
        ["namespace"],
    )

    op.create_index(
        "idx_vector_embeddings_hnsw",
        "vector_embeddings",
        ["vector"],
        postgresql_using="hnsw",
        postgresql_ops={"vector": "vector_cosine_ops"},
    )


def downgrade() -> None:
    op.drop_index("idx_vector_embeddings_hnsw", table_name="vector_embeddings")
    op.drop_index("idx_vector_embeddings_namespace", table_name="vector_embeddings")
    op.drop_table("vector_embeddings")
