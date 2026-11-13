from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db import get_session
from app.models import User
from app.schemas import UserRead

router = APIRouter(prefix="/me", tags=["me"])


@router.get("", response_model=UserRead)
async def read_me(user: CurrentUser):
    return user


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def delete_me(user: CurrentUser, session: Annotated[AsyncSession, Depends(get_session)]):
    """Delete the user and all of their data. The database cascades to every child row."""
    await session.execute(delete(User).where(User.id == user.id))
    await session.commit()
