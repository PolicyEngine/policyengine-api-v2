import flask
import functions_framework
from pydantic import BaseModel
from policyengine import Simulation
import os
from sqlmodel import Field, Session, SQLModel, create_engine
from policyengine_api_prototype import Job
from dotenv import load_dotenv
from policyengine_api_prototype import (
    Job,
    get_local_database_engine,
    get_production_database_engine,
)

load_dotenv()

if os.getenv("LOCAL_DATABASE"):
    engine = get_local_database_engine()
else:
    engine = get_production_database_engine()


def execute_job(parameters: dict):
    simulation = Simulation(parameters)
    result = simulation.calculate().model_dump()
    return result


def execute_job_from_id(job_id: int):
    with Session(engine) as session:
        job = session.get(Job, job_id)
        job.result = execute_job(job.parameters)
        session.add(job)
        session.commit()


@functions_framework.http
def main(request: flask.Request) -> dict:
    # Get job_id from query parameter
    job_id = int(request.args.get("job_id"))

    execute_job_from_id(job_id)

    return {"message": "Job executed"}
