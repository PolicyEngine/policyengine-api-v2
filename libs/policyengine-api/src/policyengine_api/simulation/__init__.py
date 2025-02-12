from fastapi import FastAPI
from policyengine_fastapi.auth.jwt_decoder import JWTDecoder
from .router import create_simulation_router
from policyengine_fastapi.database import SessionGeneratorFactory


def include_simulation_routers(
    app: FastAPI,
    session_depedency: SessionGeneratorFactory,
    optional_auth: JWTDecoder,
    auth: JWTDecoder,
):
    app.include_router(
        create_simulation_router(
            session_dependency=session_depedency,
            optional_auth=optional_auth,
            auth=auth,
        )
    )
