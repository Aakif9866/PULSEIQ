"""Request IDs, context propagation, and tracing — docs/PHASES.md Phase 8
step 5. Every behavior below was verified broken (or absent) live before
the fix; these lock the fixes in.

The trace-tree test drives the REAL GroqProvider, analyst engine, and
tools — only the Groq SDK client at the very bottom is scripted — so the
spans asserted on are the ones production code actually creates.
"""
import json
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest
import structlog
from fastapi import APIRouter
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

from app.core import middleware, tracing
from app.core.concurrency import submit_in_context
from app.core.config import settings
from app.main import app
from app.services import deep_analysis_service

SALES_CSV = b"region,amount\neast,10\neast,30\nwest,5\n"


@pytest.fixture()
def spans():
    exporter = InMemorySpanExporter()
    tracing.configure_tracing(exporter)
    yield exporter
    tracing.reset_tracing()


@pytest.fixture(autouse=True)
def _clean_cache():
    yield
    deep_analysis_service._answer_cache.clear()


# ---- request ids ----


def test_a_well_formed_inbound_request_id_is_honored(client):
    resp = client.get("/", headers={"X-Request-ID": "fe-7f3a9c.01_x"})
    assert resp.headers["X-Request-ID"] == "fe-7f3a9c.01_x"


@pytest.mark.parametrize(
    "bad",
    [
        "has spaces in it",
        "x" * 129,
        "semi;colon",
        "",
    ],
)
def test_a_malformed_inbound_request_id_is_replaced_not_trusted(client, bad):
    resp = client.get("/", headers={"X-Request-ID": bad})
    returned = resp.headers["X-Request-ID"]
    assert returned != bad
    assert len(returned) == 36  # a fresh uuid4


def test_resolve_request_id_rejects_newline_log_injection():
    # Can't be sent through an HTTP client (it's an invalid header value
    # there too) — tested at the function that guards the log line.
    assert middleware._resolve_request_id("abc\nlevel=error fake=entry") != (
        "abc\nlevel=error fake=entry"
    )


def test_request_id_header_is_exposed_to_cross_origin_browser_js(client):
    resp = client.get(
        "/", headers={"Origin": settings.CORS_ORIGINS[0], "X-Request-ID": "abc"}
    )
    exposed = resp.headers.get("access-control-expose-headers", "")
    assert "X-Request-ID" in exposed


_boom_router = APIRouter()


@_boom_router.get("/__test_boom")
def _boom() -> None:
    raise RuntimeError("secret internal detail that must not leak")


app.include_router(_boom_router)


def test_an_unhandled_500_now_carries_the_request_id(client):
    resp = client.get("/__test_boom", headers={"X-Request-ID": "trace-me-1"})
    assert resp.status_code == 500
    assert resp.headers["X-Request-ID"] == "trace-me-1"
    body = resp.json()
    assert body["request_id"] == "trace-me-1"
    assert "secret internal detail" not in json.dumps(body)


def test_the_500_error_log_line_carries_the_request_id(client, monkeypatch):
    seen: list[dict] = []

    class _Recorder:
        def exception(self, event, **kw):
            seen.append({"event": event, **structlog.contextvars.get_contextvars(), **kw})

        def info(self, *a, **k):
            pass

    monkeypatch.setattr(middleware, "logger", _Recorder())
    client.get("/__test_boom", headers={"X-Request-ID": "trace-me-2"})

    failed = [e for e in seen if e["event"] == "request_failed"]
    assert failed and failed[0]["request_id"] == "trace-me-2"
    assert failed[0]["error_type"] == "RuntimeError"


# ---- context propagation into worker threads ----


def test_submit_in_context_carries_the_request_id_into_the_worker():
    structlog.contextvars.bind_contextvars(request_id="ctx-123")
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            plain = pool.submit(structlog.contextvars.get_contextvars).result()
            carried = submit_in_context(pool, structlog.contextvars.get_contextvars).result()
    finally:
        structlog.contextvars.clear_contextvars()
    assert plain == {}  # the gap this exists to close
    assert carried == {"request_id": "ctx-123"}


# ---- tracing ----


def test_tracing_is_a_no_op_when_not_configured():
    tracing.reset_tracing()
    with tracing.get_tracer().start_as_current_span("anything"):
        assert tracing.current_trace_id() is None


def _tool_call(id_, name, args):
    return SimpleNamespace(id=id_, function=SimpleNamespace(name=name, arguments=json.dumps(args)))


def _response(content=None, tool_calls=None):
    message = SimpleNamespace(content=content, tool_calls=tool_calls)
    usage = SimpleNamespace(
        prompt_tokens=100, completion_tokens=20, total_tokens=120, total_time=0.1
    )
    return SimpleNamespace(choices=[SimpleNamespace(message=message)], usage=usage)


def _script_groq(monkeypatch, responses):
    queue = list(responses)
    fake = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=lambda **_: queue.pop(0)))
    )
    monkeypatch.setattr("app.ai.groq_client.get_groq_client", lambda: fake)


def _signup(client, email):
    resp = client.post("/api/v1/auth/signup", json={"email": email, "password": "correct-horse-1"})
    return {"Authorization": f"Bearer {resp.json()['tokens']['access_token']}"}


def test_one_analyze_request_is_one_connected_trace(client, monkeypatch, spans):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    headers = _signup(client, "trace@pulseiq.dev")
    dataset_id = client.post(
        "/api/v1/datasets", headers=headers, files={"file": ("s.csv", SALES_CSV, "text/csv")}
    ).json()["id"]
    final = json.dumps(
        {"answer": "No missing values.", "findings": [], "needs_clarification": None}
    )
    _script_groq(
        monkeypatch,
        [
            _response(tool_calls=[_tool_call("1", "get_missing_values", {})]),
            _response(content=final),
        ],
    )
    spans.clear()  # only the analyze request's spans, not signup/upload

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze",
        headers={**headers, "X-Request-ID": "trace-req-9"},
        json={"question": "Any missing values?"},
    )
    assert resp.status_code == 200

    finished = {s.name: s for s in spans.get_finished_spans()}
    root = finished["POST /api/v1/datasets/{dataset_id}/analyze"]
    analyze = finished["analyze"]
    tool = finished["tool.get_missing_values"]
    llm_spans = [s for s in spans.get_finished_spans() if s.name == "llm.chat"]

    # One trace end to end: HTTP -> analyze -> {llm.chat x2, tool}.
    trace_ids = {s.context.trace_id for s in spans.get_finished_spans()}
    assert len(trace_ids) == 1
    assert analyze.parent.span_id == root.context.span_id
    assert tool.parent.span_id == analyze.context.span_id
    assert len(llm_spans) == 2
    assert all(s.parent.span_id == analyze.context.span_id for s in llm_spans)

    # The trace and the logs share the same request id.
    assert root.attributes["pulseiq.request_id"] == "trace-req-9"
    assert root.attributes["http.route"] == "/api/v1/datasets/{dataset_id}/analyze"
    assert root.attributes["http.response.status_code"] == 200
    # Token counts land on the LLM spans; message content never does.
    assert llm_spans[0].attributes["gen_ai.usage.input_tokens"] == 100
    assert all("Any missing values" not in json.dumps(dict(s.attributes)) for s in llm_spans)
    assert tool.attributes["pulseiq.tool.name"] == "get_missing_values"
    assert analyze.attributes["pulseiq.cache_hit"] is False


def test_a_failed_tool_call_marks_its_span_as_an_error(client, monkeypatch, spans):
    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    headers = _signup(client, "trace-toolerr@pulseiq.dev")
    dataset_id = client.post(
        "/api/v1/datasets", headers=headers, files={"file": ("s.csv", SALES_CSV, "text/csv")}
    ).json()["id"]
    final = json.dumps({"answer": "Couldn't.", "findings": [], "needs_clarification": None})
    _script_groq(
        monkeypatch,
        [
            _response(tool_calls=[_tool_call("1", "detect_outliers", {"column": "nope"})]),
            _response(content=final),
        ],
    )
    spans.clear()

    client.post(
        f"/api/v1/datasets/{dataset_id}/analyze", headers=headers, json={"question": "Outliers?"}
    )

    tool = next(s for s in spans.get_finished_spans() if s.name == "tool.detect_outliers")
    assert tool.status.status_code.name == "ERROR"


def test_provider_failure_on_the_first_call_is_a_degraded_200_not_a_400(client, monkeypatch):
    # BUG-017, reproduced over real HTTP exactly as found live: the Groq
    # SDK raises on the very first (tool-loop) call.
    class _RateLimited(Exception):
        pass

    def _always_429(**_):
        raise _RateLimited("Error code: 429 - rate limit reached")

    monkeypatch.setattr(settings, "AI_PROVIDER", "groq")
    monkeypatch.setattr("app.ai.providers.groq_provider.time.sleep", lambda _s: None)
    rate_limited_client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=_always_429))
    )
    monkeypatch.setattr("app.ai.groq_client.get_groq_client", lambda: rate_limited_client)
    headers = _signup(client, "bug017@pulseiq.dev")
    dataset_id = client.post(
        "/api/v1/datasets", headers=headers, files={"file": ("s.csv", SALES_CSV, "text/csv")}
    ).json()["id"]

    resp = client.post(
        f"/api/v1/datasets/{dataset_id}/analyze", headers=headers, json={"question": "Rows?"}
    )

    assert resp.status_code == 200
    assert resp.json()["status"] == "degraded"


def test_trace_id_is_bound_onto_log_lines_when_tracing_is_on(client, monkeypatch, spans):
    seen: list[dict] = []

    class _Recorder:
        def info(self, event, **kw):
            seen.append({"event": event, **structlog.contextvars.get_contextvars()})

        def exception(self, *a, **k):
            pass

    monkeypatch.setattr(middleware, "logger", _Recorder())
    client.get("/")

    completed = next(e for e in seen if e["event"] == "request_completed")
    root = next(s for s in spans.get_finished_spans() if s.name == "GET /")
    assert completed["trace_id"] == format(root.context.trace_id, "032x")
