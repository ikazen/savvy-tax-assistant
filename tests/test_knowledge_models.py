"""지식베이스 ORM 모델 스키마 검증.

검증 대상:
- Law / LawVersion: prev_version_id 체인, (law_id, effective_date) UNIQUE
- LawChunk: article/paragraph nullable, FK CASCADE
- Case: (court, case_number) UNIQUE
- CaseChunk: FK CASCADE
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from datetime import date

import pytest
import pytest_asyncio
from sqlalchemy import delete, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from savvy.storage.models import (
    Case,
    CaseChunk,
    Law,
    LawChunk,
    LawVersion,
)
from tests.conftest import requires_db

pytestmark = requires_db


@pytest_asyncio.fixture
async def db_session(
    session_factory: async_sessionmaker[AsyncSession],
) -> AsyncIterator[AsyncSession]:
    async with session_factory() as s:
        yield s
    async with session_factory() as s:
        await s.execute(delete(LawChunk))
        await s.execute(delete(LawVersion))
        await s.execute(delete(Law))
        await s.execute(delete(CaseChunk))
        await s.execute(delete(Case))
        await s.commit()


async def test_law_versions_chain_via_prev_version_id(
    db_session: AsyncSession,
) -> None:
    law = Law(name="법인세법", category="세법")
    db_session.add(law)
    await db_session.flush()

    v1 = LawVersion(
        law_id=law.id, effective_date=date(2024, 1, 1), text="2024년 시행본"
    )
    db_session.add(v1)
    await db_session.flush()

    v2 = LawVersion(
        law_id=law.id,
        effective_date=date(2025, 1, 1),
        text="2025년 시행본",
        prev_version_id=v1.id,
    )
    db_session.add(v2)
    await db_session.commit()

    loaded_v2 = (
        await db_session.execute(select(LawVersion).where(LawVersion.id == v2.id))
    ).scalar_one()
    assert loaded_v2.prev_version_id == v1.id


async def test_law_versions_unique_law_id_effective_date(
    db_session: AsyncSession,
) -> None:
    law = Law(name="소득세법")
    db_session.add(law)
    await db_session.flush()

    db_session.add(
        LawVersion(law_id=law.id, effective_date=date(2025, 1, 1), text="ver1")
    )
    await db_session.commit()

    db_session.add(
        LawVersion(law_id=law.id, effective_date=date(2025, 1, 1), text="ver2")
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_law_chunks_with_article_paragraph(db_session: AsyncSession) -> None:
    law = Law(name="부가가치세법")
    db_session.add(law)
    await db_session.flush()
    version = LawVersion(
        law_id=law.id, effective_date=date(2025, 1, 1), text="전문..."
    )
    db_session.add(version)
    await db_session.flush()

    db_session.add_all(
        [
            LawChunk(
                law_version_id=version.id,
                article_no="13",
                paragraph_no="1",
                text="제13조 ① ...",
                chunk_idx=0,
            ),
            LawChunk(
                law_version_id=version.id,
                article_no="13",
                paragraph_no="2",
                text="제13조 ② ...",
                chunk_idx=1,
            ),
            # article/paragraph 모두 null인 토큰 윈도우 청크도 허용
            LawChunk(
                law_version_id=version.id,
                text="비정형 텍스트 청크...",
                chunk_idx=2,
            ),
        ]
    )
    await db_session.commit()

    chunks = (
        await db_session.execute(
            select(LawChunk)
            .where(LawChunk.law_version_id == version.id)
            .order_by(LawChunk.chunk_idx)
        )
    ).scalars().all()
    assert len(chunks) == 3
    assert chunks[2].article_no is None and chunks[2].paragraph_no is None


async def test_case_unique_court_case_number(db_session: AsyncSession) -> None:
    db_session.add(
        Case(
            case_number="2024다12345",
            court="대법원",
            decided_at=date(2024, 6, 1),
            text="판례 본문...",
        )
    )
    await db_session.commit()

    db_session.add(
        Case(
            case_number="2024다12345",
            court="대법원",
            decided_at=date(2024, 6, 1),
            text="중복",
        )
    )
    with pytest.raises(IntegrityError):
        await db_session.commit()


async def test_case_chunks_cascade(db_session: AsyncSession) -> None:
    case = Case(
        case_number="2025두9999",
        court="조세심판원",
        decided_at=date(2025, 3, 1),
        text="결정문...",
    )
    db_session.add(case)
    await db_session.flush()

    db_session.add_all(
        [
            CaseChunk(case_id=case.id, text="c1", chunk_idx=0),
            CaseChunk(case_id=case.id, text="c2", chunk_idx=1),
        ]
    )
    await db_session.commit()

    await db_session.execute(delete(Case).where(Case.id == case.id))
    await db_session.commit()

    remaining = (
        await db_session.execute(
            select(CaseChunk).where(CaseChunk.case_id == case.id)
        )
    ).scalars().all()
    assert remaining == []
