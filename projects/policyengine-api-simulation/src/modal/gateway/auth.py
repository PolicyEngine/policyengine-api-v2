"""Gateway authentication primitives.

The gateway is a public-facing ASGI app that routes simulation submission and
polling requests to versioned worker apps. Every write/mutation endpoint and
every read endpoint that exposes per-job state must require a valid bearer
token issued by the PolicyEngine identity provider. This module exposes a
FastAPI dependency (:func:`require_auth`) that callers attach with
``Depends(require_auth)``.

Configuration is read from the environment at import time so that Modal's
runtime container picks up the values injected via ``modal.Secret``:

- ``GATEWAY_AUTH_ISSUER`` - Auth0 issuer URL (must end with ``/``)
- ``GATEWAY_AUTH_AUDIENCE`` - Auth0 API identifier the gateway accepts

For local development and unit tests the dependency can be bypassed by
setting ``GATEWAY_AUTH_DISABLED=1``. Production deployments must leave this
unset; the gateway returns ``503`` to callers if it is started without the
issuer/audience configured.
"""

from __future__ import annotations

import logging
import os

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from policyengine_fastapi.auth import JWTDecoder

logger = logging.getLogger(__name__)


GATEWAY_AUTH_ISSUER_ENV = "GATEWAY_AUTH_ISSUER"
GATEWAY_AUTH_AUDIENCE_ENV = "GATEWAY_AUTH_AUDIENCE"
GATEWAY_AUTH_DISABLED_ENV = "GATEWAY_AUTH_DISABLED"


_bearer_scheme = HTTPBearer(auto_error=False)


def _auth_disabled() -> bool:
    return os.environ.get(GATEWAY_AUTH_DISABLED_ENV, "").lower() in {
        "1",
        "true",
        "yes",
    }


def _get_decoder() -> JWTDecoder:
    issuer = os.environ.get(GATEWAY_AUTH_ISSUER_ENV)
    audience = os.environ.get(GATEWAY_AUTH_AUDIENCE_ENV)
    if not issuer or not audience:
        raise RuntimeError(
            "Gateway auth misconfigured: set "
            f"{GATEWAY_AUTH_ISSUER_ENV} and {GATEWAY_AUTH_AUDIENCE_ENV} or "
            f"{GATEWAY_AUTH_DISABLED_ENV}=1 for local/test use."
        )
    return JWTDecoder(issuer=issuer, audience=audience, auto_error=True)


def require_auth(
    token: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> dict | None:
    """FastAPI dependency gating an endpoint behind a bearer JWT.

    Resolution rules:
    1. If ``GATEWAY_AUTH_DISABLED`` is truthy, accept the request without
       any token inspection so tests and local reruns don't need to wire
       fake JWT material.
    2. Otherwise, validate the bearer token via :class:`JWTDecoder`. A
       missing or invalid token produces a 403 (matching the underlying
       decoder's contract).

    If issuer/audience env configuration is missing the dependency returns
    503 so operators see a clear misconfiguration instead of silent bypass.
    """

    if _auth_disabled():
        return None

    try:
        decoder = _get_decoder()
    except RuntimeError as exc:
        logger.error("Gateway auth misconfigured: %s", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Gateway authentication is not configured.",
        )

    return decoder(token)
