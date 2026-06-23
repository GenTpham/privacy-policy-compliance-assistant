"""
backend/app/core/telemetry.py
Arize Phoenix tracing — instruments the openai SDK automatically.
Call setup_tracing() once at FastAPI startup.

All opentelemetry imports are deferred inside setup_tracing() so the module
can be imported in environments where opentelemetry is not installed (e.g., test).
"""


def setup_tracing(app=None, endpoint: str = "http://phoenix:4317") -> None:
    """
    Instrument the openai SDK and FastAPI via OpenTelemetry.
    Every embeddings.create() and chat.completions.create() call is traced automatically.
    Call once at FastAPI startup — not per-request.

    All imports are deferred — module is safe to import without opentelemetry installed.

    Args:
        app: The FastAPI application instance to instrument.
        endpoint: OTLP/gRPC collector endpoint. Pass settings.phoenix_collector_endpoint
                  so the value is configurable via PHOENIX_COLLECTOR_ENDPOINT env var.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from openinference.instrumentation.openai import OpenAIInstrumentor
        exporter = OTLPSpanExporter(endpoint=endpoint)
        provider = TracerProvider()
        provider.add_span_processor(BatchSpanProcessor(exporter))
        trace.set_tracer_provider(provider)
        OpenAIInstrumentor().instrument()
        if app:
            from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
            FastAPIInstrumentor.instrument_app(app)
        print(f"[telemetry] Tracing enabled — exporting to {endpoint}")
    except ImportError:
        # opentelemetry / openinference not installed — tracing disabled
        print("[telemetry] opentelemetry not installed — tracing disabled")
    except Exception as exc:
        # Phoenix may not be running in local dev — log and continue
        print(f"[telemetry] Failed to enable tracing: {exc} — continuing without tracing")
