from fastapi import FastAPI
from .simulation import create_router

def include_all_routers(app:FastAPI):
    app.include_router(create_router())

def initialize(app:FastAPI):
    include_all_routers(app)