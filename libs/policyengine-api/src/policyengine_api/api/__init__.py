from fastapi import FastAPI
from sqlalchemy import Engine

from policyengine_api.fastapi.auth.jwt_decoder import JWTDecoder
from policyengine_api.fastapi.database import create_session_dep
from .household import include_all_routers

"""
Application defined as routers completely indipendent of environment allowing it
to easily be run in whatever cloud provider container or desktop or test environment.
"""


def initialize(
    app: FastAPI, engine: Engine, jwt_issuer: str, jwt_audience: str
):
    """
    attach all routes to the app and configure them to use the provided SQLModel engine
    and jwt settings.
    """
    optional_auth = JWTDecoder(
        jwt_issuer, audience=jwt_audience, auto_error=False
    )
    auth = JWTDecoder(jwt_issuer, audience=jwt_audience, auto_error=True)
    include_all_routers(
        app,
        session_depedency=create_session_dep(engine),
        optional_auth=optional_auth,
        auth=auth,
    )
