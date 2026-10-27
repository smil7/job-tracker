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
