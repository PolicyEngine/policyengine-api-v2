from fastapi import FastAPI

from .middleware import Middleware
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor


class FastAPIEnhancedInstrumenter:
    """
    Enhances the default FastAPIInstrumentor to generate per operation
    metrics instead of global for the whole api.
    """

    def instrument(self, app: FastAPI):
        FastAPIInstrumentor.instrument_app(app)
        middleware = Middleware(app)
        app.middleware("http")(middleware)
