import uuid
from datetime import date, datetime
from enum import StrEnum

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, LargeBinary, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db import Base


class ApplicationStatus(StrEnum):
    WISHLIST = "wishlist"
    APPLIED = "applied"
    ASSESSMENT = "assessment"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class JobType(StrEnum):
    GRADUATE_PROGRAM = "graduate_program"
    JUNIOR = "junior"
    INTERNSHIP = "internship"
    OTHER = "other"


def _pg_enum(enum_cls: type[StrEnum], name: str) -> Enum:
    # Store the lowercase values (not the member names) in Postgres
    return Enum(enum_cls, name=name, values_callable=lambda e: [m.value for m in e])


status_enum = _pg_enum(ApplicationStatus, "application_status")
job_type_enum = _pg_enum(JobType, "job_type")


class Application(Base):
    __tablename__ = "applications"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    company: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(200))
    job_url: Mapped[str | None] = mapped_column(String(2000))
    location: Mapped[str | None] = mapped_column(String(200))
    job_type: Mapped[JobType | None] = mapped_column(job_type_enum)
    source: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[ApplicationStatus] = mapped_column(
        status_enum, default=ApplicationStatus.APPLIED, index=True
    )
    applied_at: Mapped[date | None] = mapped_column(Date, index=True)
    deadline: Mapped[date | None] = mapped_column(Date)
    salary: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)
    job_description: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    events: Mapped[list["StatusEvent"]] = relationship(
        back_populates="application",
        cascade="all, delete-orphan",
        passive_deletes=True,
        order_by="StatusEvent.occurred_at.desc()",
    )
    reviews: Mapped[list["ResumeReview"]] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )
    cover_letter: Mapped["CoverLetter | None"] = relationship(
        cascade="all, delete-orphan", passive_deletes=True
    )


class StatusEvent(Base):
    """A timeline entry: a status change (to_status set) or a plain note."""

    __tablename__ = "status_events"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    from_status: Mapped[ApplicationStatus | None] = mapped_column(status_enum)
    to_status: Mapped[ApplicationStatus | None] = mapped_column(status_enum)
    note: Mapped[str | None] = mapped_column(Text)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    application: Mapped[Application] = relationship(back_populates="events")


class Profile(Base):
    """Single-row table: the resume and background used by the AI features."""

    __tablename__ = "profile"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    resume_pdf: Mapped[bytes | None] = mapped_column(LargeBinary)
    resume_filename: Mapped[str | None] = mapped_column(String(255))
    about_me: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ResumeReview(Base):
    __tablename__ = "resume_reviews"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), index=True
    )
    score: Mapped[int] = mapped_column(Integer)
    result: Mapped[dict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class CoverLetter(Base):
    __tablename__ = "cover_letters"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    application_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("applications.id", ondelete="CASCADE"), unique=True
    )
    content: Mapped[str] = mapped_column(Text)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
