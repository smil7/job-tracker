import io
from types import SimpleNamespace

import pytest
from docx import Document
from httpx import AsyncClient

from app.llm.client import get_llm
from app.main import app
from app.schemas import ATSReview

PDF = b"%PDF-1.4\n%fake resume\n"
DOCX_TYPE = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"

REVIEW = ATSReview.model_validate(
    {
        "overall_score": 72,
        "summary": "Solid match with a few gaps.",
        "keywords": {"matched": ["Python", "SQL"], "missing": ["Kubernetes"]},
        "section_scores": {"skills": 80, "experience": 70, "education": 90, "formatting": 60},
        "formatting_issues": ["Two-column layout"],
        "strengths": ["Relevant internship"],
        "gaps": ["No container experience"],
        "suggested_edits": [
            {"section": "Skills", "current": "Python", "suggestion": "Python (FastAPI)", "reason": "Match"}
        ],
    }
)
LETTER = "Dear Acme team,\n\nI would love to join as a Graduate Engineer.\n\nBest regards"


class FakeLLM:
    """Stands in for AsyncOpenAI: returns a canned review or letter depending on the request."""

    def __init__(self):
        self.finish_reason = "stop"
        self.review_json = REVIEW.model_dump_json()
        self.calls: list[dict] = []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.calls.append(kwargs)
        content = self.review_json if "response_format" in kwargs else LETTER
        message = SimpleNamespace(content=content, refusal=None)
        return SimpleNamespace(choices=[SimpleNamespace(message=message, finish_reason=self.finish_reason)])


@pytest.fixture
async def llm(client: AsyncClient):
    fake = FakeLLM()
    app.dependency_overrides[get_llm] = lambda: fake
    return fake


async def make_application(client: AsyncClient, job_description: str | None = "Python, SQL, Kubernetes") -> str:
    response = await client.post(
        "/api/applications",
        json={"company": "Acme", "role": "Graduate Engineer", "job_description": job_description},
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


async def upload_resume(client: AsyncClient, content: bytes = PDF, filename: str = "cv.pdf"):
    return await client.put("/api/profile/resume", files={"file": (filename, content, "application/pdf")})


async def test_profile_defaults_and_update(client: AsyncClient):
    profile = (await client.get("/api/profile")).json()
    assert profile["has_resume"] is False
    assert profile["about_me"] is None

    updated = await client.put("/api/profile", json={"about_me": "CS grad who likes data"})
    assert updated.json()["about_me"] == "CS grad who likes data"
    assert (await client.get("/api/profile")).json()["about_me"] == "CS grad who likes data"


async def test_resume_upload_and_download(client: AsyncClient):
    response = await upload_resume(client)
    assert response.status_code == 200
    assert response.json()["has_resume"] is True
    assert response.json()["resume_filename"] == "cv.pdf"

    download = await client.get("/api/profile/resume")
    assert download.status_code == 200
    assert download.headers["content-type"] == "application/pdf"
    assert download.content == PDF


async def test_resume_download_without_upload(client: AsyncClient):
    assert (await client.get("/api/profile/resume")).status_code == 404


async def test_resume_rejects_non_pdf(client: AsyncClient):
    response = await upload_resume(client, b"just some text", "cv.txt")
    assert response.status_code == 400


async def test_resume_rejects_oversized(client: AsyncClient):
    response = await upload_resume(client, PDF + b"0" * (5 * 1024 * 1024))
    assert response.status_code == 413


async def test_ai_requires_resume_and_job_description(client: AsyncClient, llm: FakeLLM):
    with_jd = await make_application(client)
    without_jd = await make_application(client, job_description=None)

    # No resume yet
    assert (await client.post(f"/api/applications/{with_jd}/review")).status_code == 400
    assert (await client.post(f"/api/applications/{with_jd}/cover-letter", json={})).status_code == 400

    # Resume but no job description
    await upload_resume(client)
    assert (await client.post(f"/api/applications/{without_jd}/review")).status_code == 400
    assert (await client.post(f"/api/applications/{without_jd}/cover-letter", json={})).status_code == 400
    assert llm.calls == []


async def test_review_is_stored_and_latest_returned(client: AsyncClient, llm: FakeLLM):
    app_id = await make_application(client)
    await upload_resume(client)
    assert (await client.get(f"/api/applications/{app_id}/review")).status_code == 404

    response = await client.post(f"/api/applications/{app_id}/review")
    assert response.status_code == 201
    assert response.json()["review"]["overall_score"] == 72
    assert response.json()["review"]["keywords"]["missing"] == ["Kubernetes"]

    latest = await client.get(f"/api/applications/{app_id}/review")
    assert latest.status_code == 200
    assert latest.json()["review"]["summary"] == "Solid match with a few gaps."

    # The job description reaches the model inside its untrusted-data tags
    text = llm.calls[0]["messages"][1]["content"][1]["text"]
    assert "<job_description>\nPython, SQL, Kubernetes\n</job_description>" in text


async def test_refusal_maps_to_502(client: AsyncClient, llm: FakeLLM):
    app_id = await make_application(client)
    await upload_resume(client)
    llm.finish_reason = "content_filter"
    assert (await client.post(f"/api/applications/{app_id}/review")).status_code == 502
    assert (await client.post(f"/api/applications/{app_id}/cover-letter", json={})).status_code == 502
    assert (await client.get(f"/api/applications/{app_id}/review")).status_code == 404


async def test_cover_letter_generate_edit_and_docx(client: AsyncClient, llm: FakeLLM):
    app_id = await make_application(client)
    await upload_resume(client)
    assert (await client.get(f"/api/applications/{app_id}/cover-letter")).status_code == 404

    generated = await client.post(
        f"/api/applications/{app_id}/cover-letter", json={"instructions": "under 300 words"}
    )
    assert generated.status_code == 200
    assert generated.json()["content"] == LETTER
    assert "under 300 words" in llm.calls[0]["messages"][1]["content"][1]["text"]

    saved = await client.put(f"/api/applications/{app_id}/cover-letter", json={"content": "Edited letter"})
    assert saved.json()["content"] == "Edited letter"
    assert (await client.get(f"/api/applications/{app_id}/cover-letter")).json()["content"] == "Edited letter"

    # Regenerating replaces the single stored letter
    regenerated = await client.post(f"/api/applications/{app_id}/cover-letter", json={})
    assert regenerated.json()["content"] == LETTER

    await client.put(f"/api/applications/{app_id}/cover-letter", json={"content": "First\n\nSecond"})
    docx = await client.get(f"/api/applications/{app_id}/cover-letter.docx")
    assert docx.status_code == 200
    assert docx.headers["content-type"] == DOCX_TYPE
    assert "Cover letter - Acme.docx" in docx.headers["content-disposition"]
    paragraphs = [p.text for p in Document(io.BytesIO(docx.content)).paragraphs]
    assert paragraphs[1:] == ["First", "Second"]


async def test_docx_without_letter(client: AsyncClient):
    app_id = await make_application(client)
    assert (await client.get(f"/api/applications/{app_id}/cover-letter.docx")).status_code == 404


async def test_delete_application_cascades(client: AsyncClient, llm: FakeLLM):
    app_id = await make_application(client)
    await upload_resume(client)
    await client.post(f"/api/applications/{app_id}/review")
    await client.post(f"/api/applications/{app_id}/cover-letter", json={})

    assert (await client.delete(f"/api/applications/{app_id}")).status_code == 204
    assert (await client.get(f"/api/applications/{app_id}/review")).status_code == 404
    assert (await client.get(f"/api/applications/{app_id}/cover-letter")).status_code == 404


async def test_review_retries_once_on_bad_json(client: AsyncClient, llm: FakeLLM):
    app_id = await make_application(client)
    await upload_resume(client)
    llm.review_json = "not json"
    assert (await client.post(f"/api/applications/{app_id}/review")).status_code == 502
    assert len(llm.calls) == 2

    llm.review_json = "```json\n" + REVIEW.model_dump_json() + "\n```"
    assert (await client.post(f"/api/applications/{app_id}/review")).status_code == 201
