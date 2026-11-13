import time
from types import SimpleNamespace

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from httpx import AsyncClient

from app import auth
from app.config import Settings, settings

REGION = "eu-central-1"
POOL = "eu-central-1_TestPool"
CLIENT_ID = "test-client-id"
ISSUER = f"https://cognito-idp.{REGION}.amazonaws.com/{POOL}"

KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
OTHER_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)


def make_token(*, key=KEY, **overrides) -> str:
    claims = {
        "sub": "user-1",
        "iss": ISSUER,
        "client_id": CLIENT_ID,
        "token_use": "access",
        "exp": int(time.time()) + 3600,
    }
    claims.update(overrides)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key, algorithm="RS256", headers={"kid": "k1"})


@pytest.fixture(autouse=True)
def cognito(monkeypatch: pytest.MonkeyPatch):
    """Turn login on and serve our own public key instead of calling Cognito."""
    monkeypatch.setattr(settings, "auth_disabled", False)
    monkeypatch.setattr(settings, "cognito_region", REGION)
    monkeypatch.setattr(settings, "cognito_user_pool_id", POOL)
    monkeypatch.setattr(settings, "cognito_app_client_id", CLIENT_ID)
    monkeypatch.setattr(settings, "cognito_domain", "")
    fake_jwks = SimpleNamespace(
        get_signing_key_from_jwt=lambda token: SimpleNamespace(key=KEY.public_key())
    )
    monkeypatch.setattr(auth, "_jwks_client", lambda: fake_jwks)


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


async def test_no_token_is_401(raw_client: AsyncClient):
    response = await raw_client.get("/api/me")
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


async def test_valid_token_creates_the_user_once(raw_client: AsyncClient):
    first = await raw_client.get("/api/me", headers=bearer(make_token()))
    second = await raw_client.get("/api/me", headers=bearer(make_token()))
    assert first.status_code == 200
    assert first.json()["id"] == second.json()["id"]


async def test_different_subs_are_different_users(raw_client: AsyncClient):
    a = await raw_client.get("/api/me", headers=bearer(make_token(sub="a")))
    b = await raw_client.get("/api/me", headers=bearer(make_token(sub="b")))
    assert a.json()["id"] != b.json()["id"]


@pytest.mark.parametrize(
    "overrides",
    [
        {"exp": int(time.time()) - 10},  # expired
        {"iss": "https://evil.example.com/pool"},  # wrong issuer
        {"client_id": "another-client"},  # token for another app client
        {"client_id": None},  # no client_id at all
        {"token_use": "id"},  # an ID token is not an access token
        {"sub": None},  # no subject
    ],
    ids=["expired", "wrong-issuer", "wrong-client", "no-client", "id-token", "no-sub"],
)
async def test_bad_claims_are_401(raw_client: AsyncClient, overrides: dict):
    response = await raw_client.get("/api/me", headers=bearer(make_token(**overrides)))
    assert response.status_code == 401


async def test_signature_from_another_key_is_401(raw_client: AsyncClient):
    response = await raw_client.get("/api/me", headers=bearer(make_token(key=OTHER_KEY)))
    assert response.status_code == 401


async def test_unsigned_token_is_401(raw_client: AsyncClient):
    # alg=none must never be accepted
    token = jwt.encode({"sub": "x", "iss": ISSUER}, key=None, algorithm="none")
    response = await raw_client.get("/api/me", headers=bearer(token))
    assert response.status_code == 401


async def test_garbage_token_is_401(raw_client: AsyncClient):
    response = await raw_client.get("/api/me", headers=bearer("not-a-token"))
    assert response.status_code == 401


async def test_jwks_outage_is_503(raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    def broken(_token):
        raise jwt.exceptions.PyJWKClientConnectionError("down")

    monkeypatch.setattr(
        auth, "_jwks_client", lambda: SimpleNamespace(get_signing_key_from_jwt=broken)
    )
    response = await raw_client.get("/api/me", headers=bearer(make_token()))
    assert response.status_code == 503


async def test_email_is_read_from_cognito_for_new_users(
    raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch
):
    async def fake_email(token: str) -> str:
        return "sara@example.com"

    monkeypatch.setattr(auth, "_fetch_email", fake_email)
    response = await raw_client.get("/api/me", headers=bearer(make_token(sub="sara")))
    assert response.json()["email"] == "sara@example.com"


async def test_auth_disabled_uses_the_dev_user(raw_client: AsyncClient, monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(settings, "auth_disabled", True)
    response = await raw_client.get("/api/me")
    assert response.status_code == 200
    assert response.json()["email"] == auth.DEV_EMAIL


async def test_user_is_not_duplicated_by_parallel_first_requests(raw_client: AsyncClient):
    import asyncio

    token = make_token(sub="racer")
    results = await asyncio.gather(*[raw_client.get("/api/me", headers=bearer(token)) for _ in range(5)])
    assert {r.status_code for r in results} == {200}
    assert len({r.json()["id"] for r in results}) == 1


def test_production_refuses_to_start_without_login():
    unsafe = Settings(environment="production", auth_disabled=True)
    with pytest.raises(RuntimeError, match="not allowed"):
        unsafe.check_auth_config()


def test_login_on_but_not_configured_refuses_to_start():
    incomplete = Settings(auth_disabled=False, cognito_region="", cognito_user_pool_id="")
    with pytest.raises(RuntimeError, match="COGNITO_REGION"):
        incomplete.check_auth_config()


def test_app_start_runs_the_config_check(monkeypatch: pytest.MonkeyPatch):
    from app.main import app

    monkeypatch.setattr(settings, "cognito_user_pool_id", "")
    with pytest.raises(RuntimeError):
        with TestClient(app):
            pass
