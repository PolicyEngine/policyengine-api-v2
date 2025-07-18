import os
import json
import uuid
import asyncio
import httpx

from typing import Literal, Any
from google.cloud import workflows_v1
from google.cloud.workflows import executions_v1
from google.cloud.workflows.executions_v1.types import Execution
from google.protobuf.json_format import MessageToDict
from policyengine_api_full.settings import get_settings, Environment

class SimulationRunner:
    def __init__(self):
        # self.is_desktop = os.getenv("PE_MODE") == "desktop"
        settings = get_settings()
        self.is_desktop = settings.environment == Environment.DESKTOP
        print(f"SKLOGS ENVIRONMENT: {get_settings().environment}")

        if not self.is_desktop:
            self.project = "prod-api-v2-c4d5"
            self.location = "us-central1"
            self.workflow = "simulation-workflow"
            self.execution_client = executions_v1.ExecutionsClient()
            self.workflows_client = workflows_v1.WorkflowsClient()
        else:
            self.desktop_url = os.getenv(
                "SIMULATION_LOCAL_URL",
                "http://localhost:8081/simulate/economy/comparison",
            )
            self._simulations: dict[str, dict] = {}
            self._lock = asyncio.Lock()  # To protect self._simulations

    def _build_payload(
        self,
        country_id: str,
        reform: dict,
        baseline: dict,
        region: str,
        dataset: str,
        time_period: str,
        scope: Literal["macro", "household"] = "macro",
        model_version: str | None = None,
        data_version: str | None = None,
    ) -> dict[str, Any]:
        return {
            "country": country_id,
            "scope": scope,
            "reform": reform,
            "baseline": baseline,
            "time_period": time_period,
            "region": region,
            "data": dataset,
            "model_version": model_version,
            "data_version": data_version,
        }

    async def start_simulation(
        self,
        country_id: str,
        reform: dict,
        baseline: dict,
        region: str,
        dataset: str,
        time_period: str,
        scope: Literal["macro", "household"] = "macro",
        model_version: str | None = None,
        data_version: str | None = None,
    ) -> dict:
        payload = self._build_payload(
            country_id,
            reform,
            baseline,
            region,
            dataset,
            time_period,
            scope,
            model_version,
            data_version,
        )

        if self.is_desktop:
            async with httpx.AsyncClient() as client:
                response = await client.post(self.desktop_url, json=payload)
                response.raise_for_status()
                result = response.json()

            execution_id = f"desktop-{uuid.uuid4()}"
            async with self._lock:
                self._simulations[execution_id] = {
                    "status": "SUCCEEDED",
                    "result": result,
                    "error": None,
                }
            return {"execution_id": execution_id}

        else:
            # Use asyncio.to_thread for blocking I/O
            def create_execution():
                workflow_path = self.workflows_client.workflow_path(
                    self.project, self.location, self.workflow
                )
                return self.execution_client.create_execution(
                    parent=workflow_path,
                    execution=Execution(argument=json.dumps(payload)),
                )

            execution = await asyncio.to_thread(create_execution)
            return {"execution_id": execution.name}

    async def get_simulation_result(self, execution_id: str) -> dict:
        if self.is_desktop:
            print("SKLOGS: in desktop mode")
            async with self._lock:
                if execution_id not in self._simulations:
                    raise ValueError(f"Unknown execution ID: {execution_id}")
                simulation = self._simulations[execution_id]

            return {
                "execution_id": execution_id,
                "status": simulation["status"],
                "result": simulation["result"],
                "error": simulation["error"],
            }

        else:
            print("SKLOGS: in prod mode")

            def get_execution():
                return self.execution_client.get_execution(name=execution_id)

            execution = await asyncio.to_thread(get_execution)
            status = execution.state.name

            response = {
                "execution_id": execution_id,
                "status": status,
            }

            if status == "SUCCEEDED":
                response["result"] = json.loads(execution.result or "{}")
                response["error"] = None
            elif status == "FAILED":
                try:
                    error_dict = MessageToDict(execution.error)
                    response["error"] = error_dict.get("message", str(execution.error))
                except Exception:
                    response["error"] = str(execution.error)
                response["result"] = None
            else:
                response["result"] = None
                response["error"] = None

            return response
