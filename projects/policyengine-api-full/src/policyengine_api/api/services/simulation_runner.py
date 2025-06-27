# simulation_runner.py
import os
import json
import requests
from google.cloud import workflows_v1, executions_v1
from google.cloud.workflows.executions_v1.types import Execution
from typing import Literal, Any

class SimulationRunner:
    def __init__(self):
        self.is_desktop = os.getenv("PE_MODE") == "desktop"
        if not self.is_desktop:
            self.project = "prod-api-v2-c4d5"
            self.location = "us-central1"
            self.workflow = "simulation-workflow"
            self.execution_client = executions_v1.ExecutionsClient()
            self.workflows_client = workflows_v1.WorkflowsClient()
        else:
            self.desktop_url = os.getenv(
                "SIMULATION_LOCAL_URL",
                "http://localhost:8081/simulate/economy/comparison"
            )

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

    def start_simulation(
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
            response = requests.post(self.desktop_url, json=payload)
            response.raise_for_status()
            return response.json()
        else:
            workflow_path = self.workflows_client.workflow_path(
                self.project, self.location, self.workflow
            )
            execution = self.execution_client.create_execution(
                parent=workflow_path,
                execution=Execution(argument=json.dumps(payload)),
            )
            return {"execution_id": execution.name}

    def get_simulation_result(self, execution_id: str) -> dict:
        if self.is_desktop:
            raise RuntimeError("Polling is not supported in desktop mode.")
        return json.loads(
            self.execution_client.get_execution(name=execution_id).result
        )
