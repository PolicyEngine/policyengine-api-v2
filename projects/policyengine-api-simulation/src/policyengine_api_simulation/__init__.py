from fastapi import FastAPI
from .simulation import create_router
import os

"""
Application defined as routers completely indipendent of environment allowing it
to easily be run in whatever cloud provider container or desktop or test environment.
"""


def initialize(app: FastAPI):
    """
    attach all routes to the app and configure them to use the provided SQLModel engine
    and jwt settings.
    """
    # Ensure anonymous user exists for development
    from policyengine.database import Database
    db_url = os.environ.get("DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres")
    database = Database(url=db_url)
    database.ensure_anonymous_user()

    app.include_router(create_router())
