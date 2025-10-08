"""
Circuit Breaker Pattern implementation.

Part of ADR-006: Resilience Patterns

Prevents cascading failures by stopping calls to failing services.

States:
- CLOSED: Normal operation, requests pass through
- OPEN: Service is failing, requests fail fast
- HALF_OPEN: Testing if service recovered
"""

import logging
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, block requests
    HALF_OPEN = "half_open"  # Testing if recovered


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open."""

    pass


class CircuitBreaker:
    """
    Circuit breaker implementation.

    Example:
        circuit = CircuitBreaker(failure_threshold=5, timeout=60)

        async def call_service():
            return await my_service.get_data()

        try:
            result = await circuit.call(call_service)
        except CircuitBreakerOpenError:
            # Use fallback or fail gracefully
            result = get_cached_data()
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout: int = 60,
        name: str = "unnamed",
    ):
        """
        Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            success_threshold: Number of successes to close circuit from half-open
            timeout: Seconds to wait before trying half-open from open
            name: Name for logging/metrics
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout = timeout
        self.name = name

        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.state = CircuitState.CLOSED

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Callable (sync or async) to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: Any exception from func
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                logger.info(f"Circuit breaker '{self.name}' attempting reset (HALF_OPEN)")
                self.state = CircuitState.HALF_OPEN
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker '{self.name}' is OPEN - service unavailable"
                )

        try:
            # Call the function
            result = await func(*args, **kwargs) if hasattr(func, "__call__") else func
            self._on_success()
            return result

        except Exception as e:
            self._on_failure()
            logger.error(
                f"Circuit breaker '{self.name}' recorded failure: {e}",
                extra={"state": self.state.value, "failure_count": self.failure_count},
            )
            raise

    def _on_success(self):
        """Handle successful request."""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            logger.info(
                f"Circuit breaker '{self.name}' success in HALF_OPEN "
                f"({self.success_count}/{self.success_threshold})"
            )

            if self.success_count >= self.success_threshold:
                logger.info(f"Circuit breaker '{self.name}' transitioning to CLOSED")
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def _on_failure(self):
        """Handle failed request."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()

        if self.state == CircuitState.HALF_OPEN:
            # Immediately reopen on failure in half-open
            logger.warning(f"Circuit breaker '{self.name}' failed in HALF_OPEN - reopening")
            self.state = CircuitState.OPEN
            self.success_count = 0

        elif self.failure_count >= self.failure_threshold:
            logger.error(
                f"Circuit breaker '{self.name}' threshold reached "
                f"({self.failure_count} failures) - opening circuit"
            )
            self.state = CircuitState.OPEN

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to test recovery."""
        if not self.last_failure_time:
            return True

        elapsed = (datetime.now() - self.last_failure_time).total_seconds()
        return elapsed > self.timeout

    def reset(self):
        """Manually reset circuit breaker to CLOSED state."""
        logger.info(f"Circuit breaker '{self.name}' manually reset")
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None

    def get_state(self) -> CircuitState:
        """Get current circuit state."""
        return self.state

    def get_metrics(self) -> dict:
        """Get circuit breaker metrics."""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure_time": (
                self.last_failure_time.isoformat() if self.last_failure_time else None
            ),
        }
