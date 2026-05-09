from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from savvy.api.deps import SessionDep
from savvy.api.schemas.persons import PersonCreate, PersonOut, PersonUpdate
from savvy.config import get_settings
from savvy.storage.models import Person

router = APIRouter(prefix="/persons", tags=["persons"])


@router.post("", response_model=PersonOut, status_code=status.HTTP_201_CREATED)
async def create_person(payload: PersonCreate, session: SessionDep) -> Person:
    person = Person(
        tenant_id=get_settings().default_tenant_id,
        **payload.model_dump(),
    )
    session.add(person)
    await session.commit()
    await session.refresh(person)
    return person


@router.get("", response_model=list[PersonOut])
async def list_persons(
    session: SessionDep,
    limit: int = Query(default=50, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
) -> list[Person]:
    stmt = (
        select(Person)
        .where(Person.tenant_id == get_settings().default_tenant_id)
        .order_by(Person.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{person_id}", response_model=PersonOut)
async def get_person(person_id: UUID, session: SessionDep) -> Person:
    person = await session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    return person


@router.patch("/{person_id}", response_model=PersonOut)
async def update_person(
    person_id: UUID, payload: PersonUpdate, session: SessionDep
) -> Person:
    person = await session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(person, field, value)
    await session.commit()
    await session.refresh(person)
    return person


@router.delete("/{person_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_person(person_id: UUID, session: SessionDep) -> None:
    person = await session.get(Person, person_id)
    if person is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "person not found")
    await session.delete(person)
    await session.commit()
