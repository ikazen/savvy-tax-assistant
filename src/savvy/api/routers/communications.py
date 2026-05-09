from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from savvy.api.deps import SessionDep
from savvy.api.schemas.communications import (
    ClientCommunicationCreate,
    ClientCommunicationOut,
)
from savvy.config import get_settings
from savvy.storage.models import ClientCommunication, CommChannel, CommDirection, Entity

router = APIRouter(tags=["communications"])


@router.post(
    "/entities/{entity_id}/communications",
    response_model=ClientCommunicationOut,
    status_code=status.HTTP_201_CREATED,
)
async def record_communication(
    entity_id: UUID,
    payload: ClientCommunicationCreate,
    session: SessionDep,
) -> ClientCommunication:
    if await session.get(Entity, entity_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entity not found")

    comm = ClientCommunication(
        tenant_id=get_settings().default_tenant_id,
        entity_id=entity_id,
        **payload.model_dump(),
    )
    session.add(comm)
    try:
        await session.commit()
    except IntegrityError as e:
        await session.rollback()
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            "duplicate source_id for this (tenant, channel)",
        ) from e
    await session.refresh(comm)
    return comm


@router.get(
    "/entities/{entity_id}/communications",
    response_model=list[ClientCommunicationOut],
)
async def list_communications(
    entity_id: UUID,
    session: SessionDep,
    channel: CommChannel | None = None,
    direction: CommDirection | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> list[ClientCommunication]:
    if await session.get(Entity, entity_id) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "entity not found")

    stmt = select(ClientCommunication).where(
        ClientCommunication.tenant_id == get_settings().default_tenant_id,
        ClientCommunication.entity_id == entity_id,
    )
    if channel is not None:
        stmt = stmt.where(ClientCommunication.channel == channel)
    if direction is not None:
        stmt = stmt.where(ClientCommunication.direction == direction)
    stmt = (
        stmt.order_by(ClientCommunication.occurred_at.desc())
        .limit(limit)
        .offset(offset)
    )
    return list((await session.execute(stmt)).scalars().all())


@router.get(
    "/communications/{communication_id}", response_model=ClientCommunicationOut
)
async def get_communication(
    communication_id: UUID, session: SessionDep
) -> ClientCommunication:
    comm = await session.get(ClientCommunication, communication_id)
    if comm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "communication not found")
    return comm


@router.delete(
    "/communications/{communication_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_communication(
    communication_id: UUID, session: SessionDep
) -> None:
    comm = await session.get(ClientCommunication, communication_id)
    if comm is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "communication not found")
    await session.delete(comm)
    await session.commit()
