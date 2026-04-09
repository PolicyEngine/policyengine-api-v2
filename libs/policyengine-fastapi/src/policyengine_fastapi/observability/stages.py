from enum import Enum


class SimulationStage(str, Enum):
    REQUEST_ACCEPTED = "request.accepted"
    REQUEST_VALIDATED = "request.validated"
    JOB_SETUP = "job.setup"
    JOB_SUBMITTED = "job.submitted"
    GATEWAY_RECEIVED = "gateway.received"
    GATEWAY_VERSION_RESOLVED = "gateway.version_resolved"
    GATEWAY_SPAWNED = "gateway.spawned"
    WORKER_STARTED = "worker.started"
    WORKER_CREDENTIALS_READY = "worker.credentials.ready"
    WORKER_OPTIONS_VALIDATED = "worker.options.validated"
    WORKER_SIMULATION_CONSTRUCTED = "worker.simulation.constructed"
    WORKER_COMPARISON_CALCULATED = "worker.comparison.calculated"
    WORKER_TRACER_EXPORTED = "worker.tracer.exported"
    WORKER_RESULT_SERIALIZED = "worker.result.serialized"
    WORKER_COMPLETED = "worker.completed"
    RESULT_POLLED = "result.polled"
    RESULT_RETURNED = "result.returned"
    RESULT_FAILED = "result.failed"


class TracerCaptureMode(str, Enum):
    DISABLED = "disabled"
    FAILURES = "failures"
    THRESHOLD = "threshold"
    SAMPLED = "sampled"
    ALWAYS = "always"
