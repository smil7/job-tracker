import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field

from app.models import ApplicationStatus, JobType


class ApplicationFields(BaseModel):
    job_url: str | None = Field(default=None, max_length=2000)
    location: str | None = Field(default=None, max_length=200)
    job_type: JobType | None = None
    source: str | None = Field(default=None, max_length=100)
    applied_at: date | None = None
    deadline: date | None = None
    salary: str | None = Field(default=None, max_length=100)
    notes: str | None = None
    job_description: str | None = None


class ApplicationCreate(ApplicationFields):
    company: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1, max_length=200)
    status: ApplicationStatus = ApplicationStatus.APPLIED


class ApplicationUpdate(ApplicationFields):
    company: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1, max_length=200)
    status: ApplicationStatus | None = None


class ApplicationRead(ApplicationFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    company: str
    role: str
    status: ApplicationStatus
    created_at: datetime
    updated_at: datetime


class EventCreate(BaseModel):
    note: str = Field(min_length=1)
    occurred_at: datetime | None = None


class EventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    from_status: ApplicationStatus | None
    to_status: ApplicationStatus | None
    note: str | None
    occurred_at: datetime


class ApplicationDetail(ApplicationRead):
    events: list[EventRead]


class Stats(BaseModel):
    total_applied: int
    active: int
    interviews: int
    offers: int
    applied_this_week: int
    response_rate: float
    by_status: dict[ApplicationStatus, int]


class ProfileRead(BaseModel):
    about_me: str | None
    resume_filename: str | None
    has_resume: bool
    updated_at: datetime | None


class ProfileUpdate(BaseModel):
    about_me: str | None = None


class KeywordMatch(BaseModel):
    matched: list[str]
    missing: list[str]


class SectionScores(BaseModel):
    skills: int = Field(ge=0, le=100)
    experience: int = Field(ge=0, le=100)
    education: int = Field(ge=0, le=100)
    formatting: int = Field(ge=0, le=100)


class SuggestedEdit(BaseModel):
    section: str
    current: str
    suggestion: str
    reason: str


class ATSReview(BaseModel):
    """Structured output the model fills in; also the stored review payload."""

    overall_score: int = Field(ge=0, le=100)
    summary: str
    keywords: KeywordMatch
    section_scores: SectionScores
    formatting_issues: list[str]
    strengths: list[str]
    gaps: list[str]
    suggested_edits: list[SuggestedEdit]


class ResumeReviewRead(BaseModel):
    id: uuid.UUID
    created_at: datetime
    review: ATSReview


class CoverLetterGenerate(BaseModel):
    instructions: str | None = Field(default=None, max_length=1000)


class CoverLetterUpdate(BaseModel):
    content: str


class CoverLetterRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    content: str
    generated_at: datetime
    updated_at: datetime
