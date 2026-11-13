from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db import get_session
from app.models import Profile, User
from app.schemas import ProfileRead, ProfileUpdate

router = APIRouter(prefix="/profile", tags=["profile"])

Session = Annotated[AsyncSession, Depends(get_session)]

MAX_RESUME_BYTES = 5 * 1024 * 1024


async def get_profile(session: AsyncSession, user: User) -> Profile:
    """The profile of the user, created empty on first use."""
    profile = await session.get(Profile, user.id)
    if profile is None:
        profile = Profile(user_id=user.id)
        session.add(profile)
        await session.commit()
        await session.refresh(profile)
    return profile


def _read(profile: Profile) -> ProfileRead:
    return ProfileRead(
        about_me=profile.about_me,
        resume_filename=profile.resume_filename,
        has_resume=profile.resume_pdf is not None,
        updated_at=profile.updated_at,
    )


@router.get("", response_model=ProfileRead)
async def read_profile(session: Session, user: CurrentUser):
    return _read(await get_profile(session, user))


@router.put("", response_model=ProfileRead)
async def update_profile(payload: ProfileUpdate, session: Session, user: CurrentUser):
    profile = await get_profile(session, user)
    profile.about_me = payload.about_me
    await session.commit()
    await session.refresh(profile)
    return _read(profile)


@router.put("/resume", response_model=ProfileRead)
async def upload_resume(file: UploadFile, session: Session, user: CurrentUser):
    # Read one byte past the cap so oversized files are rejected without loading them all
    data = await file.read(MAX_RESUME_BYTES + 1)
    if len(data) > MAX_RESUME_BYTES:
        raise HTTPException(status.HTTP_413_CONTENT_TOO_LARGE, "Resume must be 5 MB or less")
    if not data.startswith(b"%PDF"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Resume must be a PDF file")
    profile = await get_profile(session, user)
    profile.resume_pdf = data
    profile.resume_filename = file.filename or "resume.pdf"
    await session.commit()
    await session.refresh(profile)
    return _read(profile)


@router.get(
    "/resume",
    response_class=Response,
    responses={200: {"content": {"application/pdf": {}}}},
)
async def download_resume(session: Session, user: CurrentUser):
    profile = await get_profile(session, user)
    if profile.resume_pdf is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No resume uploaded")
    return Response(
        profile.resume_pdf,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{profile.resume_filename}"'},
    )
