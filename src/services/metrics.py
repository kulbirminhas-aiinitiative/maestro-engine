"""Prometheus metrics for Maestro Engine

Comprehensive metrics tracking for SDLC workflow orchestration and persona execution.
"""

import time
from functools import wraps
from typing import Callable

from fastapi import Response
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Gauge, Histogram, generate_latest

# ============================================================================
# Workflow Metrics
# ============================================================================

workflows_total = Counter(
    "maestro_workflows_total",
    "Total workflows executed",
    ["status", "type"],  # status: success/failed, type: sdlc/custom
)

active_workflows = Gauge("maestro_active_workflows", "Number of currently active workflows")

workflow_duration_seconds = Histogram(
    "maestro_workflow_duration_seconds",
    "Workflow execution duration in seconds",
    ["type"],
    buckets=(10, 30, 60, 120, 300, 600, 1800, 3600),
)

workflow_steps_total = Counter(
    "maestro_workflow_steps_total", "Total workflow steps executed", ["persona", "status"]
)

workflow_steps_duration_seconds = Histogram(
    "maestro_workflow_steps_duration_seconds",
    "Workflow step duration in seconds",
    ["persona"],
    buckets=(5, 10, 30, 60, 120, 300),
)

# ============================================================================
# Persona Metrics
# ============================================================================

persona_invocations_total = Counter(
    "maestro_persona_invocations_total", "Total persona invocations", ["persona"]
)

persona_duration_seconds = Histogram(
    "maestro_persona_duration_seconds",
    "Persona execution duration in seconds",
    ["persona"],
    buckets=(10, 30, 60, 120, 300, 600),
)

persona_errors_total = Counter(
    "maestro_persona_errors_total", "Total persona execution errors", ["persona", "error_type"]
)

# ============================================================================
# Document Generation Metrics
# ============================================================================

documents_generated_total = Counter(
    "maestro_documents_generated_total", "Total documents generated", ["type", "persona"]
)

document_generation_duration_seconds = Histogram(
    "maestro_document_generation_duration_seconds",
    "Document generation duration in seconds",
    ["type"],
)

document_size_bytes = Histogram(
    "maestro_document_size_bytes",
    "Generated document size in bytes",
    ["type"],
    buckets=(1024, 10240, 102400, 1024000, 10240000),
)

# ============================================================================
# Service Integration Metrics
# ============================================================================

external_service_calls_total = Counter(
    "maestro_external_service_calls_total", "Total external service calls", ["service", "status"]
)

external_service_duration_seconds = Histogram(
    "maestro_external_service_duration_seconds",
    "External service call duration in seconds",
    ["service"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0),
)

rag_queries_total = Counter("maestro_rag_queries_total", "Total RAG service queries", ["status"])

template_retrievals_total = Counter(
    "maestro_template_retrievals_total", "Total template retrievals", ["status"]
)

# ============================================================================
# Queue Metrics
# ============================================================================

workflow_queue_depth = Gauge("maestro_workflow_queue_depth", "Current workflow queue depth")

workflow_queue_wait_seconds = Histogram(
    "maestro_workflow_queue_wait_seconds",
    "Workflow queue wait time in seconds",
    buckets=(1, 5, 10, 30, 60, 300),
)

# ============================================================================
# Error Metrics
# ============================================================================

errors_total = Counter("maestro_errors_total", "Total errors", ["type", "component"])

retries_total = Counter("maestro_retries_total", "Total operation retries", ["operation"])

# ============================================================================
# Helper Functions
# ============================================================================


def metrics_endpoint() -> Response:
    """Prometheus metrics endpoint"""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


def track_workflow(workflow_type: str):
    """Context manager to track workflow execution"""

    class WorkflowTracker:
        def __init__(self, workflow_type: str):
            self.workflow_type = workflow_type
            self.start_time = None

        def __enter__(self):
            self.start_time = time.time()
            active_workflows.inc()
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            duration = time.time() - self.start_time
            active_workflows.dec()

            status = "failed" if exc_type else "success"
            workflows_total.labels(status=status, type=self.workflow_type).inc()

            workflow_duration_seconds.labels(type=self.workflow_type).observe(duration)

    return WorkflowTracker(workflow_type)


def track_persona(persona_name: str):
    """Decorator to track persona execution"""

    def decorator(func: Callable):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            persona_invocations_total.labels(persona=persona_name).inc()

            try:
                result = await func(*args, **kwargs)
                workflow_steps_total.labels(persona=persona_name, status="success").inc()
                return result
            except Exception as e:
                persona_errors_total.labels(persona=persona_name, error_type=type(e).__name__).inc()
                workflow_steps_total.labels(persona=persona_name, status="failed").inc()
                raise
            finally:
                duration = time.time() - start_time
                persona_duration_seconds.labels(persona=persona_name).observe(duration)
                workflow_steps_duration_seconds.labels(persona=persona_name).observe(duration)

        return wrapper

    return decorator


# ============================================================================
# Metric Recording Functions
# ============================================================================


def record_document_generation(doc_type: str, persona: str, size: int, duration: float):
    """Record document generation metrics"""
    documents_generated_total.labels(type=doc_type, persona=persona).inc()
    document_generation_duration_seconds.labels(type=doc_type).observe(duration)
    document_size_bytes.labels(type=doc_type).observe(size)


def record_external_service_call(service: str, status: str, duration: float):
    """Record external service call"""
    external_service_calls_total.labels(service=service, status=status).inc()
    external_service_duration_seconds.labels(service=service).observe(duration)


def record_error(error_type: str, component: str):
    """Record error occurrence"""
    errors_total.labels(type=error_type, component=component).inc()


def setup_metrics():
    """Initialize metrics on startup"""
    active_workflows.set(0)
    workflow_queue_depth.set(0)
    print("✅ Prometheus metrics initialized for Maestro Engine")
