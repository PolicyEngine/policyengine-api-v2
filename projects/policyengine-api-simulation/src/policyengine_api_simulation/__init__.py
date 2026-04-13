from fastapi import FastAPI
from .internal_observability import create_router as create_internal_observability_router
from .simulation import create_router

"""
Application defined as routers completely indipendent of environment allowing it
to easily be run in whatever cloud provider container or desktop or test environment.
"""


def initialize(app: FastAPI):
    """
    attach all routes to the app and configure them to use the provided SQLModel engine
    and jwt settings.
    """
    app.include_router(create_router())
    app.include_router(create_internal_observability_router())
