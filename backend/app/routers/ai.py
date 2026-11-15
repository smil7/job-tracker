import io
import uuid
from datetime import UTC, date, datetime
from typing import Annotated

from docx import Document
from fastapi import APIRouter, Depends, HTTPException, Response, status
from openai import AsyncOpenAI
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUser
from app.db import get_session
from app.llm import service
from app.llm.client import get_llm
from app.models import Application, CoverLetter, Profile, ResumeReview, User
from app.routers.applications import _get_detail
from app.routers.profile import get_profile
from app.schemas import (
    ATSReview,
    CoverLetterGenerate,
    CoverLetterRead,
    CoverLetterUpdate,
    ResumeReviewRead,
)

router = APIRouter(prefix="/applications/{application_id}", tags=["ai"])

Session = Annotated[AsyncSession, Depends(get_session)]
LLM = Annotated[AsyncOpenAI, Depends(get_llm)]

DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


async def _inputs(
    session: AsyncSession, application_id: uuid.UUID, user: User
) -> tuple[Profile, Application]:
    """Load the profile and application, or 400 if either lacks what the model needs."""
    application = await _get_detail(session, application_id, user)
    profile = await get_profile(session, user)
    if not (application.job_description or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Add a job description first")
    if profile.resume_pdf is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Upload your resume in Profile first")
    return profile, application


def _review_read(row: ResumeReview) -> ResumeReviewRead:
    return ResumeReviewRead(
        id=row.id, created_at=row.created_at, review=ATSReview.model_validate(row.result)
    )


async def _letter(session: AsyncSession, application_id: uuid.UUID) -> CoverLetter | None:
    return await session.scalar(
        select(CoverLetter).where(CoverLetter.application_id == application_id)
    )


@router.post("/review", response_model=ResumeReviewRead, status_code=status.HTTP_201_CREATED)
async def run_review(application_id: uuid.UUID, session: Session, llm: LLM, user: CurrentUser):
    profile, application = await _inputs(session, application_id, user)
    try:
        review = await service.review_resume(llm, profile, application)
    except service.LLMError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    row = ResumeReview(
        application_id=application.id,
        score=review.overall_score,
        result=review.model_dump(),
    )
    session.add(row)
    await session.commit()
    await session.refresh(row)
    return _review_read(row)


@router.get("/review", response_model=ResumeReviewRead)
async def latest_review(application_id: uuid.UUID, session: Session, user: CurrentUser):
    await _get_detail(session, application_id, user)
    row = await session.scalar(
        select(ResumeReview)
        .where(ResumeReview.application_id == application_id)
        .order_by(ResumeReview.created_at.desc())
        .limit(1)
    )
    if row is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No review yet")
    return _review_read(row)


@router.post("/cover-letter", response_model=CoverLetterRead)
async def generate_letter(
    application_id: uuid.UUID,
    payload: CoverLetterGenerate,
    session: Session,
    llm: LLM,
    user: CurrentUser,
):
    profile, application = await _inputs(session, application_id, user)
    try:
        text = await service.generate_cover_letter(llm, profile, application, payload.instructions)
    except service.LLMError as exc:
        raise HTTPException(exc.status_code, exc.message) from exc
    letter = await _letter(session, application.id)
    if letter is None:
        letter = CoverLetter(application_id=application.id, content=text)
        session.add(letter)
    else:
        letter.content = text
        letter.generated_at = datetime.now(UTC)
    await session.commit()
    await session.refresh(letter)
    return letter


@router.get("/cover-letter", response_model=CoverLetterRead)
async def read_letter(application_id: uuid.UUID, session: Session, user: CurrentUser):
    await _get_detail(session, application_id, user)
    letter = await _letter(session, application_id)
    if letter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No cover letter yet")
    return letter


@router.put("/cover-letter", response_model=CoverLetterRead)
async def save_letter(
    application_id: uuid.UUID, payload: CoverLetterUpdate, session: Session, user: CurrentUser
):
    await _get_detail(session, application_id, user)
    letter = await _letter(session, application_id)
    if letter is None:
        letter = CoverLetter(application_id=application_id, content=payload.content)
        session.add(letter)
    else:
        letter.content = payload.content
    await session.commit()
    await session.refresh(letter)
    return letter


@router.get(
    "/cover-letter.docx",
    response_class=Response,
    responses={200: {"content": {DOCX_TYPE: {}}}},
)
async def download_letter(application_id: uuid.UUID, session: Session, user: CurrentUser):
    application = await _get_detail(session, application_id, user)
    letter = await _letter(session, application_id)
    if letter is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No cover letter yet")

    doc = Document()
    doc.add_paragraph(date.today().strftime("%d %B %Y"))
    for block in letter.content.split("\n\n"):
        if block.strip():
            doc.add_paragraph(block.strip())
    buffer = io.BytesIO()
    doc.save(buffer)

    company = "".join(c for c in application.company if c.isalnum() or c in " -_").strip()
    filename = f"Cover letter - {company or 'job'}.docx"
    return Response(
        buffer.getvalue(),
        media_type=DOCX_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
