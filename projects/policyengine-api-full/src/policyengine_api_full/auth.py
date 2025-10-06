"""
Supabase authentication utilities for FastAPI.
"""

from typing import Optional
from fastapi import HTTPException, Header, status
import jwt
import os

# Supabase JWT secret from environment
# For local development, this is the default Supabase secret
SUPABASE_JWT_SECRET = os.getenv(
    "SUPABASE_JWT_SECRET",
    "super-secret-jwt-token-with-at-least-32-characters-long"
)

SUPABASE_JWT_ALGORITHM = "HS256"


def verify_token(authorization: Optional[str] = Header(None)) -> Optional[str]:
    """
    Verify Supabase JWT token from Authorization header.

    Args:
        authorization: Authorization header value (Bearer token)

    Returns:
        User ID from the token payload, or None if no token provided

    Raises:
        HTTPException: If token is invalid or expired
    """
    if not authorization:
        return None

    try:
        # Extract token from "Bearer <token>" format
        scheme, token = authorization.split()
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid authentication scheme. Expected Bearer token.",
            )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Authorization header format. Expected 'Bearer <token>'.",
        )

    try:
        # Verify and decode JWT
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=[SUPABASE_JWT_ALGORITHM],
        )

        # Extract user ID from payload
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token payload missing 'sub' claim.",
            )

        return user_id

    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Could not validate credentials: {str(e)}",
        )


def get_current_user_id(authorization: Optional[str] = Header(None)) -> str:
    """
    Get current authenticated user ID. Returns 'anonymous' if not authenticated.

    Args:
        authorization: Authorization header value (Bearer token)

    Returns:
        User ID from token, or 'anonymous' if no valid token
    """
    user_id = verify_token(authorization)
    return user_id if user_id else "anonymous"
