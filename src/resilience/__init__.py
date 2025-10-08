"""
Resilience patterns for MAESTRO Engine.

Part of ADR-006: Resilience Patterns

This module provides fault tolerance mechanisms:
- Circuit Breaker: Stop calling failing services
- Retry with Exponential Backoff: Automatically retry failed requests
- Timeout: Prevent requests from hanging
- Bulkhead: Limit concurrent requests to prevent resource exhaustion
- Fallback: Provide degraded service when primary fails

Usage:
    from src.resilience import CircuitBreaker, retry_with_backoff, timeout, Bulkhead

Example:
    circuit = CircuitBreaker(failure_threshold=5)
    result = await circuit.call(my_service_call, arg1, arg2)
"""

from .bulkhead import Bulkhead
from .circuit_breaker import CircuitBreaker, CircuitBreakerOpenError, CircuitState
from .fallback import with_fallback
from .retry import retry_with_backoff
from .timeout import TimeoutError, timeout

__all__ = [
    "CircuitBreaker",
    "CircuitState",
    "CircuitBreakerOpenError",
    "retry_with_backoff",
    "timeout",
    "TimeoutError",
    "Bulkhead",
    "with_fallback",
]
