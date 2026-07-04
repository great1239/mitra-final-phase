from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any

from fastapi import FastAPI

from .config import RuntimeSettings


try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
        OTLPSpanExporter,
    )
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    _OTEL_AVAILABLE = True
except Exception:  # pragma: no cover - exercised when optional deps absent.
    trace = None
    OTLPSpanExporter = None
    FastAPIInstrumentor = None
    Resource = None
    TracerProvider = None
    BatchSpanProcessor = None
    _OTEL_AVAILABLE = False


def configure_opentelemetry(
    app: FastAPI,
    settings: RuntimeSettings,
) -> dict[str, Any]:
    """Install FastAPI OpenTelemetry instrumentation when configured."""

    status = {
        "enabled": settings.otel_enabled,
        "available": _OTEL_AVAILABLE,
        "service_name": settings.otel_service_name,
        "otlp_endpoint": settings.otel_exporter_otlp_endpoint,
        "instrumented": False,
    }
    if not settings.otel_enabled or not _OTEL_AVAILABLE:
        app.state.opentelemetry = status
        return status

    resource = Resource.create(
        {
            "service.name": settings.otel_service_name,
            "deployment.environment": settings.deployment_environment,
        }
    )
    provider = TracerProvider(resource=resource)
    if settings.otel_exporter_otlp_endpoint:
        exporter = OTLPSpanExporter(
            endpoint=settings.otel_exporter_otlp_endpoint
        )
        provider.add_span_processor(BatchSpanProcessor(exporter))
        status["exporter"] = "otlp-http"
    else:
        status["exporter"] = "none-configured"

    trace.set_tracer_provider(provider)
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=provider,
        excluded_urls="/health,/ready,/metrics",
    )
    status["instrumented"] = True
    app.state.opentelemetry = status
    return status


@contextmanager
def runtime_span(name: str, **attributes: Any) -> Iterator[None]:
    """Create an OpenTelemetry span if tracing is installed."""

    if not _OTEL_AVAILABLE:
        yield
        return
    tracer = trace.get_tracer("mitra_companion.runtime")
    with tracer.start_as_current_span(name) as span:
        for key, value in attributes.items():
            if value is None:
                continue
            if isinstance(value, str | bool | int | float):
                span.set_attribute(key, value)
        yield
