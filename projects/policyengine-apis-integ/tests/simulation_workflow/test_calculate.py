import pytest
from .simplified_workflow_client import SimplifiedWorkflowClient
from google.cloud.workflows.executions_v1.types import executions


@pytest.mark.requires_gcp
def test_calculate_default_model(client: SimplifiedWorkflowClient):
    execution = client.execute(
        argument={
            "country": "us",  # don't use uk. It will try to load extra stuff from huggingface
            "scope": "macro",
            "reform": {
                "gov.irs.credits.ctc.refundable.fully_refundable": {
                    "2023-01-01.2100-12-31": True
                }
            },
            "subsample": 200,  # reduce the number of households to speed things up.
            "data": "gs://policyengine-us-data/enhanced_cps_2024.h5",  # force the service to use google storage (policyengine.py defaults to huggingface)
        }
    )
    assert execution.state == executions.Execution.State.SUCCEEDED


@pytest.mark.requires_gcp
def test_calculate_specific_model(
    client: SimplifiedWorkflowClient, us_model_version: str
):
    execution = client.execute(
        argument={
            "country": "us",  # don't use uk. It will try to load extra stuff from huggingface
            "model_version": us_model_version,
            "scope": "macro",
            "reform": {
                "gov.irs.credits.ctc.refundable.fully_refundable": {
                    "2023-01-01.2100-12-31": True
                }
            },
            "subsample": 200,  # reduce the number of households to speed things up.
            "data": "gs://policyengine-us-data/enhanced_cps_2024.h5",  # force the service to use google storage (policyengine.py defaults to huggingface)
        }
    )
    assert execution.state == executions.Execution.State.SUCCEEDED
