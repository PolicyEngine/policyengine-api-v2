print("Starting job...")

from pydantic import BaseModel
from policyengine import Simulation
import os
from sqlmodel import Field, Session
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


execute_job_from_id(int(os.getenv("JOB_ID")))
