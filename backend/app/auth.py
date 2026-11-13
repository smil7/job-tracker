"""Login: check the Cognito token on each request and find the user it belongs to.

Cognito signs an access token with a private key. We hold only the public keys (the JWKS), so
we can check a token but cannot make one. No password or secret is stored in this API.
"""

import asyncio
import logging
from functools import lru_cache
from typing import Annotated

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient
from jwt.exceptions import PyJWKClientConnectionError
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db import get_session
from app.models import User

logger = logging.getLogger(__name__)

# auto_error=False: we return our own 401, and the OpenAPI page still shows the "Authorize" box
bearer = HTTPBearer(auto_error=False)

# The one user that exists when AUTH_DISABLED=true (local development only)
DEV_SUB = "dev-user"
DEV_EMAIL = "dev@localhost"


@lru_cache
def _jwks_client() -> PyJWKClient:
    # Downloads the public keys once, then keeps them for an hour
    url = f"{settings.cognito_issuer}/.well-known/jwks.json"
    return PyJWKClient(url, cache_keys=True, lifespan=3600)


def verify_access_token(token: str) -> dict:
    """Return the claims of a valid Cognito access token. Raise a jwt error if it is not valid.

    This function does blocking network work on a cache miss, so call it with asyncio.to_thread.
    """
    signing_key = _jwks_client().get_signing_key_from_jwt(token)
    claims = jwt.decode(
        token,
        signing_key.key,
        algorithms=["RS256"],  # only the algorithm Cognito uses; never trust the token header
        issuer=settings.cognito_issuer,
        options={"require": ["exp", "iss", "sub"], "verify_aud": False},
    )
    # Access tokens have no `aud`. They carry `client_id` instead. ID tokens must not be accepted.
    if claims.get("token_use") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    if claims.get("client_id") != settings.cognito_app_client_id:
        raise jwt.InvalidTokenError("Token was issued for another app client")
    return claims


async def _fetch_email(token: str) -> str | None:
    """Ask Cognito for the user's email. Access tokens do not contain it. Never raises."""
    if not settings.cognito_domain:
        return None
    try:
        async with httpx.AsyncClient(timeout=5) as http:
            response = await http.get(
                f"https://{settings.cognito_domain}/oauth2/userInfo",
                headers={"Authorization": f"Bearer {token}"},
            )
        response.raise_for_status()
        return response.json().get("email")
    except (httpx.HTTPError, ValueError):
        logger.warning("Could not read the email of a new user from Cognito")
        return None


async def _find(session: AsyncSession, sub: str) -> User | None:
    return await session.scalar(select(User).where(User.cognito_sub == sub))


async def get_or_create_user(session: AsyncSession, sub: str, email: str | None = None) -> User:
    user = await _find(session, sub)
    if user is not None:
        return user
    # ON CONFLICT DO NOTHING: two first requests at the same time must not crash on the unique key
    await session.execute(
        insert(User).values(cognito_sub=sub, email=email).on_conflict_do_nothing(index_elements=["cognito_sub"])
    )
    await session.commit()
    logger.info("Created a user")
    user = await _find(session, sub)
    assert user is not None
    return user


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(status.HTTP_401_UNAUTHORIZED, detail, headers={"WWW-Authenticate": "Bearer"})


async def current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Annotated[AsyncSession, Depends(get_session)],
) -> User:
    """The logged-in user. Add this to a route to make the route private."""
    if settings.auth_disabled:
        return await get_or_create_user(session, DEV_SUB, DEV_EMAIL)

    if credentials is None:
        raise _unauthorized("Not logged in")
    token = credentials.credentials
    try:
        claims = await asyncio.to_thread(verify_access_token, token)
    except PyJWKClientConnectionError as exc:
        # Cognito is not reachable. This is not the fault of the user, so do not say 401.
        logger.error("Could not download the Cognito public keys")
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "Login service unavailable") from exc
    except jwt.PyJWTError as exc:
        logger.warning("Rejected a token: %s", exc)
        raise _unauthorized("Invalid or expired token") from exc

    sub = claims["sub"]
    user = await _find(session, sub)
    if user is None:
        user = await get_or_create_user(session, sub, await _fetch_email(token))
    return user


CurrentUser = Annotated[User, Depends(current_user)]
