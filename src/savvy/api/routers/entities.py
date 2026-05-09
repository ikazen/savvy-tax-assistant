from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select

from savvy.api.deps import SessionDep
from savvy.api.schemas.entities import EntityCreate, EntityOut, EntityUpdate
from savvy.config import get_settings
from savvy.storage.models import Entity

router = APIRouter(prefix="/entities", tags=["entities"])


@router.post("", response_model=EntityOut, status_code=status.HTTP_201_CREATED)
async def create_entity(payload: EntityCreate, session: SessionDep) -> Entity:
    entity = Entity(
        tenant_id=get_settings().default_tenant_id,
        **payload.model_dump(),
    )
    session.add(entity)
    await session.commit()
    await session.refresh(entity)
    return entity


@router.get("", response_model=list[EntityOut])
async def list_entities(
    session: SessionDep,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[Entity]:
    stmt = (
        select(Entity)
        .where(Entity.tenant_id == get_settings().default_tenant_id)
        .order_by(Entity.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get("/{entity_id}", response_model=EntityOut)
async def get_entity(entity_id: UUID, session: SessionDep) -> Entity:
    entity = await session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entity not found")
    return entity


@router.patch("/{entity_id}", response_model=EntityOut)
async def update_entity(
    entity_id: UUID, payload: EntityUpdate, session: SessionDep
) -> Entity:
    entity = await session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entity not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(entity, field, value)
    await session.commit()
    await session.refresh(entity)
    return entity


@router.delete("/{entity_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_entity(entity_id: UUID, session: SessionDep) -> None:
    entity = await session.get(Entity, entity_id)
    if entity is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entity not found")
    await session.delete(entity)
    await session.commit()
