# policyengine-api-simulation

PolicyEngine Simulation API service.

## Observability

The service currently runs two observability backends in parallel:

- `policyengine-observability` emits structured request, operation, error,
  and runtime timing logs.
- Logfire remains enabled as the legacy platform for existing dashboards and
  alerting while we evaluate replacing it with another observability platform.

New instrumentation should be added through `policyengine-observability`; the
Logfire path is retained for continuity during that evaluation.

For `policyengine-observability`, this service intentionally forces:

- `log_destinations=("stdout",)`
- `otel_enabled=False`
- `google_cloud_project=None`

Cloud Logging and OTel export are therefore disabled until the target GCP
project is ready. The package does not currently provide memory-usage
measurements, so memory is not emitted.

Modal captures container output and exposes it through the app logs UI and
CLI. Useful `policyengine-observability` checks after deploying:

```bash
modal app logs policyengine-simulation-gateway --tail 100
modal app logs policyengine-simulation-gateway --tail 100 --search policyengine.observability
modal app logs policyengine-simulation-py<version> --tail 100 --search run_simulation
modal app dashboard policyengine-simulation-gateway
```

If using Modal source filters, include both `stdout` and `stderr`. The
observability destination is named `stdout`, but its current Python logging
handler writes through the standard stream handler.

Logfire continues to use the `policyengine-logfire` Modal secret. Worker
functions and the gateway configure Logfire only when `LOGFIRE_TOKEN` is
present.
