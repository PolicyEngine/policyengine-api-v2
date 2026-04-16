"""
Pydantic models for the Gateway API.
"""

from typing import Any, ClassVar, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from src.modal.telemetry import TelemetryEnvelope


def _move_internal_telemetry_alias(value):
    if not isinstance(value, dict):
        return value
    if "telemetry" in value or "_telemetry" not in value:
        return value

    normalized = dict(value)
    normalized["telemetry"] = normalized.pop("_telemetry")
    return normalized


class GatewayRequestBase(BaseModel):
    """Base request model that preserves internal telemetry aliasing."""

    country: str
    version: Optional[str] = None
    telemetry: TelemetryEnvelope | None = None

    model_config = ConfigDict(
        extra="allow",
        populate_by_name=True,
    )  # Pass through all other fields

    @model_validator(mode="before")
    @classmethod
    def move_internal_telemetry_alias(cls, value):
        return _move_internal_telemetry_alias(value)


class SimulationRequest(GatewayRequestBase):
    """Request model for simulation submission."""


class PolicyEngineBundle(BaseModel):
    """Resolved runtime provenance returned by the gateway."""

    model_version: str
    policyengine_version: Optional[str] = None
    data_version: Optional[str] = None
    dataset: Optional[str] = None


class JobSubmitResponse(BaseModel):
    """Response model for job submission."""

    job_id: str
    status: str
    poll_url: str
    country: str
    version: str
    resolved_app_name: str
    policyengine_bundle: PolicyEngineBundle
    run_id: Optional[str] = None


class JobStatusResponse(BaseModel):
    """Response model for job status polling."""

    status: str
    result: Optional[dict] = None
    error: Optional[str] = None
    resolved_app_name: Optional[str] = None
    policyengine_bundle: Optional[PolicyEngineBundle] = None
    run_id: Optional[str] = None


class BudgetWindowBatchRequest(GatewayRequestBase):
    """Request model for budget-window batch submission."""

    MAX_YEARS: ClassVar[int] = 75
    MAX_END_YEAR: ClassVar[int] = 2099
    MAX_PARALLEL: ClassVar[int] = 3

    region: str
    start_year: str
    window_size: int = Field(ge=1, le=MAX_YEARS)
    max_parallel: int = Field(default=MAX_PARALLEL, ge=1, le=MAX_PARALLEL)
    target: Literal["general"] = "general"

    @field_validator("start_year")
    @classmethod
    def validate_start_year(cls, value: str) -> str:
        try:
            return str(int(value))
        except (TypeError, ValueError) as exc:
            raise ValueError("start_year must be an integer year") from exc

    @model_validator(mode="after")
    def validate_end_year(self) -> "BudgetWindowBatchRequest":
        end_year = int(self.start_year) + self.window_size - 1
        if end_year > self.MAX_END_YEAR:
            raise ValueError(
                f"budget-window end_year must be {self.MAX_END_YEAR} or earlier"
            )
        return self


class BudgetWindowAnnualImpact(BaseModel):
    """Annual budget-window impact row."""

    year: str
    taxRevenueImpact: float
    federalTaxRevenueImpact: float
    stateTaxRevenueImpact: float
    benefitSpendingImpact: float
    budgetaryImpact: float


class BudgetWindowTotals(BaseModel):
    """Aggregate totals for a completed budget-window response."""

    year: Literal["Total"] = "Total"
    taxRevenueImpact: float
    federalTaxRevenueImpact: float
    stateTaxRevenueImpact: float
    benefitSpendingImpact: float
    budgetaryImpact: float


class BudgetWindowResult(BaseModel):
    """Completed budget-window output."""

    kind: Literal["budgetWindow"] = "budgetWindow"
    startYear: str
    endYear: str
    windowSize: int
    annualImpacts: list[BudgetWindowAnnualImpact] = Field(default_factory=list)
    totals: BudgetWindowTotals


class BatchChildJobStatus(BaseModel):
    """Per-year child simulation job tracking."""

    job_id: str
    status: str
    error: Optional[str] = None


class BudgetWindowBatchSubmitResponse(BaseModel):
    """Response model for budget-window batch submission."""

    batch_job_id: str
    status: str
    poll_url: str
    country: str
    version: str
    resolved_app_name: str
    policyengine_bundle: PolicyEngineBundle
    run_id: Optional[str] = None


class BudgetWindowBatchStatusResponse(BaseModel):
    """Response model for budget-window batch polling."""

    status: str
    progress: Optional[int] = None
    completed_years: list[str] = Field(default_factory=list)
    running_years: list[str] = Field(default_factory=list)
    queued_years: list[str] = Field(default_factory=list)
    failed_years: list[str] = Field(default_factory=list)
    child_jobs: dict[str, BatchChildJobStatus] = Field(default_factory=dict)
    result: Optional[BudgetWindowResult] = None
    error: Optional[str] = None
    resolved_app_name: Optional[str] = None
    policyengine_bundle: Optional[PolicyEngineBundle] = None
    run_id: Optional[str] = None


class BudgetWindowBatchState(BaseModel):
    """Internal state persisted for a budget-window parent batch job."""

    batch_job_id: str
    status: str
    country: str
    region: str
    version: str
    target: Literal["general"] = "general"
    resolved_app_name: str
    policyengine_bundle: PolicyEngineBundle
    start_year: str
    window_size: int
    max_parallel: int
    request_payload: dict[str, Any] = Field(default_factory=dict)
    years: list[str] = Field(default_factory=list)
    queued_years: list[str] = Field(default_factory=list)
    running_years: list[str] = Field(default_factory=list)
    completed_years: list[str] = Field(default_factory=list)
    failed_years: list[str] = Field(default_factory=list)
    child_jobs: dict[str, BatchChildJobStatus] = Field(default_factory=dict)
    partial_annual_impacts: dict[str, BudgetWindowAnnualImpact] = Field(
        default_factory=dict
    )
    result: Optional[BudgetWindowResult] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str
    run_id: Optional[str] = None


class PingRequest(BaseModel):
    """Request model for ping endpoint."""

    value: int


class PingResponse(BaseModel):
    """Response model for ping endpoint."""

    incremented: int
