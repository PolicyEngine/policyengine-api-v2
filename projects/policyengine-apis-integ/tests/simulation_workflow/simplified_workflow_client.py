import json
from typing import Any

from google.cloud import workflows_v1
from google.cloud.workflows import executions_v1

from google.cloud.workflows.executions_v1.types import executions


class SimplifiedWorkflowClient:
    def __init__(self, project_id: str, location: str, workflow_id: str):
        self.execution_client = executions_v1.ExecutionsClient()
        self.workflows_client = workflows_v1.WorkflowsClient()
        self.project_id = project_id
        self.location = location
        self.workflow_id = workflow_id

    def execute(self, argument: Any) -> executions.Execution:
        parent = self.workflows_client.workflow_path(
            self.project_id, self.location, self.workflow_id
        )
        response = self.execution_client.create_execution(
            parent=parent,
            execution=executions.Execution(argument=json.dumps(argument)),
        )

        execution_finished = False
        while True:
            execution = self.execution_client.get_execution(
                request={"name": response.name}
            )
            execution_finished = execution.state != executions.Execution.State.ACTIVE
            if execution_finished:
                return execution
