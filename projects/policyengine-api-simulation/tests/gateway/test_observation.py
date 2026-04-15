from src.modal.gateway.models import SimulationRequest
from src.modal.gateway.observation import GatewayObservation


class RecordingSpan:
    def __init__(self, traceparent: str | None = None):
        self.traceparent = traceparent

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return None

    def get_traceparent(self) -> str | None:
        return self.traceparent


class RecordingObservability:
    def __init__(self):
        self.events = []
        self.counters = []
        self.histograms = []
        self.spans = []

    def emit_lifecycle_event(self, payload):
        self.events.append(payload)

    def emit_counter(self, name, value=1, attributes=None):
        self.counters.append(
            {"name": name, "value": value, "attributes": dict(attributes or {})}
        )

    def emit_histogram(self, name, value, attributes=None):
        self.histograms.append(
            {"name": name, "value": value, "attributes": dict(attributes or {})}
        )

    def span(self, name, attributes=None, parent_traceparent=None):
        self.spans.append(
            {
                "name": name,
                "attributes": dict(attributes or {}),
                "parent_traceparent": parent_traceparent,
            }
        )
        return RecordingSpan("00-11111111111111111111111111111111-2222222222222222-01")


def test_gateway_observation__request_span_updates_traceparent():
    request = SimulationRequest.model_validate(
        {
            "country": "us",
            "scope": "macro",
            "reform": {},
            "_telemetry": {
                "run_id": "run-123",
                "process_id": "proc-123",
            },
        }
    )
    observability = RecordingObservability()

    observation = GatewayObservation.from_request(observability, request)

    with observation.request_span("gateway.submit_simulation"):
        pass

    assert observation.telemetry is not None
    assert (
        observation.telemetry["traceparent"]
        == "00-11111111111111111111111111111111-2222222222222222-01"
    )
    assert observability.spans[0]["attributes"]["country"] == "us"
    assert observability.spans[0]["attributes"]["run_id"] == "run-123"


def test_gateway_observation__call_stage_records_success_and_detail_updates():
    observability = RecordingObservability()
    observation = GatewayObservation(
        observability,
        service="policyengine-simulation-gateway",
        telemetry={
            "run_id": "run-123",
            "country": "us",
            "simulation_kind": "national",
            "traceparent": "00-parenttraceparent-1111111111111111-01",
        },
        country="us",
    )

    result = observation.call_stage(
        "gateway.version_resolved",
        lambda: ("policyengine-simulation-us1-2-3-uk2-3-4", "1.2.3"),
        details={"requested_version": None},
        on_success=lambda outcome, details: details.update(
            {
                "modal_app_name": outcome[0],
                "version": outcome[1],
            }
        ),
    )

    assert result == ("policyengine-simulation-us1-2-3-uk2-3-4", "1.2.3")
    assert observability.spans[0]["name"] == "gateway.version_resolved"
    assert (
        observability.spans[0]["parent_traceparent"]
        == "00-parenttraceparent-1111111111111111-01"
    )
    assert observability.events[0]["stage"] == "gateway.version_resolved"
    assert observability.events[0]["status"] == "ok"
    assert observability.events[0]["details"] == {
        "requested_version": None,
        "modal_app_name": "policyengine-simulation-us1-2-3-uk2-3-4",
        "version": "1.2.3",
    }
