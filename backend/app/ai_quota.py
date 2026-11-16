"""A daily limit on AI requests for each user.

Each AI request costs real money (OpenRouter). Without a limit, one user (or one stolen login)
could spend all the credit. The count is kept in Postgres, so it works with many API tasks.
"""

import logging
from datetime import UTC, date, datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import AIUsage, User

logger = logging.getLogger(__name__)


def _today() -> date:
    return datetime.now(UTC).date()


def _seconds_until_reset() -> int:
    now = datetime.now(UTC)
    midnight = datetime.combine(now.date() + timedelta(days=1), datetime.min.time(), tzinfo=UTC)
    return max(1, int((midnight - now).total_seconds()))


async def reserve_ai_request(session: AsyncSession, user: User) -> None:
    """Count one AI request for today. Raise 429 if the user is at the limit.

    Call this after the checks that can fail (missing resume, unknown id) and before the model
    call. The request counts when it starts, also if the model call fails later.
    """
    limit = settings.ai_daily_limit
    reserved = False
    if limit > 0:
        # One SQL statement: add 1 only if the count is below the limit. The database does the
        # check and the add together, so two requests at the same time cannot both pass.
        statement = (
            insert(AIUsage)
            .values(user_id=user.id, day=_today(), count=1)
            .on_conflict_do_update(
                index_elements=[AIUsage.user_id, AIUsage.day],
                set_={"count": AIUsage.count + 1},
                where=AIUsage.count < limit,
            )
            .returning(AIUsage.count)
        )
        reserved = await session.scalar(statement) is not None
        await session.commit()  # keep the count even if the request fails later

    if not reserved:
        logger.warning("AI daily limit reached", extra={"limit": limit})
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS,
            f"Daily AI limit reached ({limit} requests per day). It resets at 00:00 UTC.",
            headers={"Retry-After": str(_seconds_until_reset())},
        )
