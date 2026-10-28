"""Langfuse tracing (OpenTelemetry under the hood). A no-op unless LANGFUSE_PUBLIC_KEY and
LANGFUSE_SECRET_KEY are set, so tests and keyless runs never touch the network."""
import os
from contextlib import contextmanager

from opentelemetry import trace as otel

from . import config  # noqa: F401  (loads backend/.env)

ENV = os.getenv("LANGFUSE_TRACING_ENVIRONMENT", "local")
ENABLED = bool(os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY"))
lf = None
if ENABLED:
    from langfuse import Langfuse

    lf = Langfuse(environment=ENV)


class _Noop:
    trace_id = None

    def update(self, **_):
        return self


@contextmanager
def span(name, as_type="span", root=False, **kw):
    """root=True starts a trace (ask, extract). Child spans are only recorded inside a trace,
    so evals and other direct calls to search/generate stay untraced."""
    if lf is None or not (root or otel.get_current_span().get_span_context().is_valid):
        yield _Noop()
        return
    if root:
        from langfuse import propagate_attributes

        with propagate_attributes(trace_name=name, tags=[ENV]), \
                lf.start_as_current_observation(name=name, as_type=as_type, **kw) as obs:
            yield obs
    else:
        with lf.start_as_current_observation(name=name, as_type=as_type, **kw) as obs:
            yield obs


def score(trace_id, name, value, comment=None):
    if lf is not None and trace_id:
        lf.create_score(trace_id=trace_id, name=name, value=value, data_type="NUMERIC", comment=comment)


def flush():
    if lf is not None:
        lf.flush()
