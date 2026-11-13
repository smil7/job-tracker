import uuid
from collections import defaultdict
from datetime import date, timedelta

from fastapi import APIRouter
from sqlalchemy import func, select

from app.auth import CurrentUser
from app.models import Application, ApplicationStatus, StatusEvent, User
from app.routers.applications import Session
from app.schemas import Stats

router = APIRouter(prefix="/stats", tags=["stats"])

S = ApplicationStatus
ACTIVE = {S.APPLIED, S.ASSESSMENT, S.INTERVIEW}
# Reaching any of these means the company got back to you
RESPONDED = {S.ASSESSMENT, S.INTERVIEW, S.OFFER, S.REJECTED}
INTERVIEWED = {S.INTERVIEW, S.OFFER}

# Pipeline order; the two closed stages share the last rank
RANK = {S.WISHLIST: 0, S.APPLIED: 1, S.ASSESSMENT: 2, S.INTERVIEW: 3, S.OFFER: 4, S.REJECTED: 5, S.WITHDRAWN: 5}


async def _stages_reached(session: Session, user: User) -> dict[uuid.UUID, set[ApplicationStatus]]:
    """Stages each application has genuinely reached, replayed from its history.

    Moving forward keeps earlier stages (interviewed then rejected still counts as an
    interview). Moving backward is treated as undoing a mistake, so stages beyond the
    new one are dropped (Applied -> Assessment -> Applied no longer counts as a response).
    """
    rows = await session.execute(
        select(StatusEvent.application_id, StatusEvent.from_status, StatusEvent.to_status)
        .join(Application, Application.id == StatusEvent.application_id)
        .where(StatusEvent.to_status.is_not(None), Application.user_id == user.id)
        .order_by(StatusEvent.application_id, StatusEvent.occurred_at)
    )
    reached: dict[uuid.UUID, set[ApplicationStatus]] = defaultdict(set)
    for app_id, from_status, to_status in rows.all():
        stages = reached[app_id]
        if from_status is not None and RANK[to_status] < RANK[from_status]:
            stages -= {s for s in stages if RANK[s] > RANK[to_status]}
        stages.add(to_status)
    return reached


@router.get("", response_model=Stats)
async def get_stats(session: Session, user: CurrentUser):
    rows = await session.execute(
        select(Application.status, func.count())
        .where(Application.user_id == user.id)
        .group_by(Application.status)
    )
    by_status = {s: 0 for s in ApplicationStatus}
    by_status.update({s: n for s, n in rows.all()})

    total_applied = sum(n for s, n in by_status.items() if s != S.WISHLIST)
    reached = (await _stages_reached(session, user)).values()
    responded = sum(1 for stages in reached if stages & RESPONDED)
    week_ago = date.today() - timedelta(days=7)
    applied_this_week = await session.scalar(
        select(func.count()).where(
            Application.user_id == user.id,
            Application.applied_at >= week_ago,
            Application.status != S.WISHLIST,
        )
    )

    return Stats(
        total_applied=total_applied,
        active=sum(by_status[s] for s in ACTIVE),
        interviews=sum(1 for stages in reached if stages & INTERVIEWED),
        offers=by_status[S.OFFER],
        applied_this_week=applied_this_week,
        response_rate=round(responded / total_applied, 3) if total_applied else 0.0,
        by_status=by_status,
    )
