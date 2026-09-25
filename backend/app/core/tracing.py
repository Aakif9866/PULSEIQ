"""Optional distributed tracing — docs/PHASES.md Phase 8 step 5.

Off by default: with OTEL_EXPORTER_OTLP_ENDPOINT unset, get_tracer()
returns OpenTelemetry's no-op tracer, spans are non-recording, and
nothing is exported. Set it and every request becomes a trace: an HTTP
span (RequestLoggingMiddleware) containing an `analyze` span, containing
one span per LLM call and per tool call — the same request_id on the
root span as on every log line.

OpenTelemetry over LangSmith: OTLP is vendor-neutral, so the same
configuration exports to Jaeger, Grafana Tempo, Honeycomb, or LangSmith's
own OTLP endpoint; the LangSmith SDK is LangChain-oriented, and this
project doesn't use LangChain.

Deliberately holds its own TracerProvider rather than installing one as
OpenTelemetry's process-global provider: the global can only be set once
per process ("Overriding of current TracerProvider is not allowed"),
which would make it impossible for tests to swap in an in-memory
exporter. Span *parenting* still works across modules either way —
that goes through OpenTelemetry's context (contextvars), not the
provider.
"""
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor, SpanExporter

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_INSTRUMENTATION_NAME = "pulseiq"

_provider: trace.TracerProvider = trace.NoOpTracerProvider()


def _parse_headers(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    headers = {}
    for pair in raw.split(","):
        key, sep, value = pair.partition("=")
        if sep and key.strip():
            headers[key.strip()] = value.strip()
    return headers


def configure_tracing(exporter: SpanExporter | None = None) -> bool:
    """Returns whether tracing ended up enabled. `exporter` is for tests
    (an InMemorySpanExporter, exported synchronously so a test can assert
    on spans immediately); in the app it's built from Settings and
    exported in batches off the request path."""
    global _provider
    synchronous = exporter is not None
    if exporter is None:
        endpoint = settings.OTEL_EXPORTER_OTLP_ENDPOINT
        if not endpoint:
            _provider = trace.NoOpTracerProvider()
            return False
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        exporter = OTLPSpanExporter(
            endpoint=f"{endpoint.rstrip('/')}/v1/traces",
            headers=_parse_headers(settings.OTEL_EXPORTER_OTLP_HEADERS),
        )
        # Endpoint host only — never the headers (they can carry an API key).
        logger.info("tracing_enabled", endpoint=endpoint, service=settings.OTEL_SERVICE_NAME)

    provider = TracerProvider(
        resource=Resource.create({SERVICE_NAME: settings.OTEL_SERVICE_NAME})
    )
    processor = SimpleSpanProcessor(exporter) if synchronous else BatchSpanProcessor(exporter)
    provider.add_span_processor(processor)
    _provider = provider
    return True


def reset_tracing() -> None:
    """Test-only: flush and go back to the no-op provider."""
    global _provider
    if isinstance(_provider, TracerProvider):
        _provider.shutdown()
    _provider = trace.NoOpTracerProvider()


def force_flush() -> None:
    if isinstance(_provider, TracerProvider):
        _provider.force_flush()


def get_tracer() -> trace.Tracer:
    return _provider.get_tracer(_INSTRUMENTATION_NAME)


def current_trace_id() -> str | None:
    """The active trace id as 32 hex chars, or None when there's no
    recording span (tracing off) — used to put trace_id on log lines so a
    log search and a trace lookup find the same request."""
    span_context = trace.get_current_span().get_span_context()
    if not span_context.is_valid:
        return None
    return format(span_context.trace_id, "032x")
