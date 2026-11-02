import base64
from typing import Any

from openai import APIConnectionError, APIStatusError, AsyncOpenAI, RateLimitError
from pydantic import ValidationError

from app.config import settings
from app.llm.prompts import ATS_REVIEWER, COVER_LETTER_WRITER
from app.models import Application, Profile
from app.schemas import ATSReview


class LLMError(Exception):
    """A failed model call, carrying the HTTP status the API should return."""

    def __init__(self, status_code: int, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.message = message


def _messages(
    system: str, profile: Profile, application: Application, task: str
) -> list[dict[str, Any]]:
    assert profile.resume_pdf is not None
    pdf = base64.standard_b64encode(profile.resume_pdf).decode()
    return [
        {"role": "system", "content": system},
        {
            "role": "user",
            "content": [
                {
                    "type": "file",
                    "file": {
                        "filename": profile.resume_filename or "resume.pdf",
                        "file_data": f"data:application/pdf;base64,{pdf}",
                    },
                },
                {
                    "type": "text",
                    "text": (
                        f"<about_me>\n{profile.about_me or '(none provided)'}\n</about_me>\n\n"
                        f"Company: {application.company}\nRole: {application.role}\n"
                        f"Location: {application.location or 'not given'}\n\n"
                        f"<job_description>\n{application.job_description}\n</job_description>\n\n"
                        f"{task}"
                    ),
                },
            ],
        },
    ]


def _wrap(exc: Exception) -> LLMError:
    if isinstance(exc, RateLimitError):
        return LLMError(503, "The AI service is rate limited. Try again in a minute.")
    if isinstance(exc, APIConnectionError):
        return LLMError(503, "Could not reach the AI service.")
    if isinstance(exc, APIStatusError):
        if exc.status_code in (401, 403):
            return LLMError(502, "The OpenRouter API key is missing or invalid (check backend/.env).")
        if exc.status_code == 402:
            return LLMError(502, "Your OpenRouter credits have run out.")
    return LLMError(502, "The AI service returned an error.")


async def _complete(llm: AsyncOpenAI, messages: list[dict[str, Any]], **extra: Any) -> str:
    """One chat completion; returns the text or raises LLMError."""
    try:
        response = await llm.chat.completions.create(
            model=settings.llm_model, messages=messages, max_tokens=16000, **extra
        )
    except (APIStatusError, APIConnectionError) as exc:
        raise _wrap(exc) from exc
    choice = response.choices[0]
    if choice.finish_reason == "content_filter" or getattr(choice.message, "refusal", None):
        raise LLMError(502, "The model declined to process this request.")
    if choice.finish_reason == "length":
        raise LLMError(502, "The response was cut off before it finished. Try again.")
    return (choice.message.content or "").strip()


async def review_resume(llm: AsyncOpenAI, profile: Profile, application: Application) -> ATSReview:
    messages = _messages(
        ATS_REVIEWER, profile, application, "Review this resume against the job description."
    )
    response_format = {
        "type": "json_schema",
        "json_schema": {"name": "ats_review", "schema": ATSReview.model_json_schema()},
    }
    # Models differ in how well they follow a JSON schema, so allow one retry
    for attempt in range(2):
        text = await _complete(llm, messages, response_format=response_format)
        try:
            return ATSReview.model_validate_json(_strip_fences(text))
        except ValidationError:
            if attempt == 1:
                raise LLMError(502, "The model returned an unreadable review. Try again.") from None
    raise AssertionError("unreachable")


def _strip_fences(text: str) -> str:
    """Some models wrap JSON in a markdown code fence despite the schema."""
    if text.startswith("```"):
        text = text.split("\n", 1)[-1].removesuffix("```")
    return text.strip()


async def generate_cover_letter(
    llm: AsyncOpenAI,
    profile: Profile,
    application: Application,
    instructions: str | None,
) -> str:
    task = "Write the cover letter."
    if instructions:
        task += f"\n\nExtra instructions from the candidate: {instructions}"
    text = await _complete(llm, _messages(COVER_LETTER_WRITER, profile, application, task))
    if not text:
        raise LLMError(502, "The model returned an empty letter. Try again.")
    return text
