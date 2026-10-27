import uuid
from datetime import date
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db import get_session
from app.models import Application, ApplicationStatus, StatusEvent
from app.schemas import (
    ApplicationCreate,
    ApplicationDetail,
    ApplicationRead,
    ApplicationUpdate,
    EventCreate,
    EventRead,
)

router = APIRouter(prefix="/applications", tags=["applications"])

Session = Annotated[AsyncSession, Depends(get_session)]

SORTS = {
    "updated": Application.updated_at.desc(),
    "applied": Application.applied_at.desc().nulls_last(),
    "applied_asc": Application.applied_at.asc().nulls_last(),
    "company": Application.company.asc(),
    "deadline": Application.deadline.asc().nulls_last(),
}


async def _get_detail(session: AsyncSession, application_id: uuid.UUID) -> Application:
    result = await session.execute(
        select(Application)
        .where(Application.id == application_id)
        .options(selectinload(Application.events))
        .execution_options(populate_existing=True)
    )
    application = result.scalar_one_or_none()
    if application is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Application not found")
    return application


def _fill_applied_date(application: Application) -> None:
    # Anything past the wishlist has been applied to; default the date to today
    if application.status != ApplicationStatus.WISHLIST and application.applied_at is None:
        application.applied_at = date.today()


@router.get("", response_model=list[ApplicationRead])
async def list_applications(
    session: Session,
    status_filter: Annotated[list[ApplicationStatus] | None, Query(alias="status")] = None,
    q: str | None = None,
    sort: Literal["updated", "applied", "applied_asc", "company", "deadline"] = "updated",
):
    stmt = select(Application).order_by(SORTS[sort])
    if status_filter:
        stmt = stmt.where(Application.status.in_(status_filter))
    if q:
        pattern = f"%{q}%"
        stmt = stmt.where(
            or_(
                Application.company.ilike(pattern),
                Application.role.ilike(pattern),
                Application.location.ilike(pattern),
            )
        )
    return (await session.scalars(stmt)).all()


@router.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
async def create_application(payload: ApplicationCreate, session: Session):
    application = Application(**payload.model_dump())
    _fill_applied_date(application)
    application.events = [StatusEvent(to_status=application.status, note="Added")]
    session.add(application)
    await session.commit()
    return await _get_detail(session, application.id)


@router.get("/{application_id}", response_model=ApplicationDetail)
async def get_application(application_id: uuid.UUID, session: Session):
    return await _get_detail(session, application_id)


@router.patch("/{application_id}", response_model=ApplicationDetail)
async def update_application(
    application_id: uuid.UUID, payload: ApplicationUpdate, session: Session
):
    application = await _get_detail(session, application_id)
    changes = payload.model_dump(exclude_unset=True)
    new_status = changes.pop("status", None)

    for field, value in changes.items():
        if field in ("company", "role") and value is None:
            continue  # required columns can't be cleared
        setattr(application, field, value)

    if new_status is not None and new_status != application.status:
        application.events.append(
            StatusEvent(from_status=application.status, to_status=new_status)
        )
        application.status = new_status
        _fill_applied_date(application)

    await session.commit()
    return await _get_detail(session, application_id)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(application_id: uuid.UUID, session: Session):
    application = await _get_detail(session, application_id)
    await session.delete(application)
    await session.commit()


@router.post(
    "/{application_id}/events", response_model=EventRead, status_code=status.HTTP_201_CREATED
)
async def add_event(application_id: uuid.UUID, payload: EventCreate, session: Session):
    application = await _get_detail(session, application_id)
    event = StatusEvent(application_id=application.id, note=payload.note)
    if payload.occurred_at is not None:
        event.occurred_at = payload.occurred_at
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event
