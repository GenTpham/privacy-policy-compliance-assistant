"""
backend/app/core/telemetry.py
Arize Phoenix tracing — instruments the openai SDK automatically.
Call setup_tracing() once at FastAPI startup.
"""
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter


def setup_tracing(endpoint: str = "http://phoenix:4317") -> None:
    """
    Instrument the openai SDK via OpenTelemetry.
    Every embeddings.create() and chat.completions.create() call is traced automatically.
    Call once at FastAPI startup — not per-request.
    """
    try:
        from openinference.instrumentation.openai import OpenAIInstrumentor
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        OpenAIInstrumentor().instrument()
        print(f"[telemetry] Tracing enabled — exporting to {endpoint}")
    except ImportError:
        # openinference-instrumentation-openai not installed — tracing disabled
        print("[telemetry] openinference not installed — tracing disabled")
    except Exception as exc:
        # Phoenix may not be running in local dev — log and continue
        print(f"[telemetry] Failed to enable tracing: {exc} — continuing without tracing")
