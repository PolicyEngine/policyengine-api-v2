from fastapi import FastAPI
from sqlmodel import Field, Session, SQLModel, create_engine
import os
from dotenv import load_dotenv
from policyengine_api_prototype import (
    Job,
    get_local_database_engine,
    get_production_database_engine,
)
import time

load_dotenv()

if os.getenv("LOCAL_DATABASE"):
    engine = get_local_database_engine()
else:
    engine = get_production_database_engine()

app = FastAPI()


@app.get("/")
def read_root():
    return {"message": "Hello, World!"}


@app.post("/job")
def create_job(parameters: dict) -> Job:
    with Session(engine) as session:
        job = Job(parameters=parameters)
        session.add(job)
        session.commit()

        return job


@app.get("/job/{job_id}")
def read_job(job_id: int) -> Job:
    with Session(engine) as session:
        job = session.get(Job, job_id)
        return job
