from fastapi import FastAPI
from opentelemetry.sdk.resources import (
    SERVICE_NAME,
    SERVICE_INSTANCE_ID,
    Resource,
)

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
)

from opentelemetry import metrics
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import (
    PeriodicExportingMetricReader,
    ConsoleMetricExporter,
)

import logging

from .middleware import Middleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from .gcp import GCPLoggingInstrumentor, export_ot_to_gcp

log = logging.getLogger(__name__)

# Configure opentelemetry
# 1. to include python logs and
# 2. export to console (for demo purposes)


def export_ot_to_console(resource: Resource):
    """
    configure opentelemetry to dump messages to console for debugging on desktop
    """
    traceProvider = TracerProvider(resource=resource)
    processor = BatchSpanProcessor(ConsoleSpanExporter())
    traceProvider.add_span_processor(processor)
    trace.set_tracer_provider(traceProvider)

    reader = PeriodicExportingMetricReader(ConsoleMetricExporter())
    meterProvider = MeterProvider(resource=resource, metric_readers=[reader])
    metrics.set_meter_provider(meterProvider)


class FastAPIEnhancedInstrumenter:
    """
    Enhances the default FastAPIInstrumentor to generate per operation
    metrics instead of global for the whole api.
    """

    def instrument(self, app: FastAPI):
        FastAPIInstrumentor.instrument_app(app)
        middleware = Middleware(app)
        app.middleware("http")(middleware)
