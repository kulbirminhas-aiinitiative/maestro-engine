#!/usr/bin/env python3
"""
CircuitBreaker - Agent Failure Resilience

Gracefully handles agent failures without cascading.

MD-2102: [DDE-6] Implement circuit breaker for agent failures

Features:
- CLOSED/OPEN/HALF_OPEN state machine
- Configurable failure threshold and reset timeout
- Automatic recovery
- Metrics and monitoring
"""

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, Generic, List, Optional, TypeVar
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional Prometheus metrics
try:
    from prometheus_client import Counter, Gauge, Histogram
    PROMETHEUS_AVAILABLE = True

    CIRCUIT_STATE = Gauge(
        "dde_circuit_breaker_state",
        "Circuit breaker state (0=closed, 1=open, 2=half_open)",
        ["circuit_id"]
    )
    CIRCUIT_TRIPS = Counter(
        "dde_circuit_breaker_trips_total",
        "Total circuit breaker trips",
        ["circuit_id"]
    )
    CIRCUIT_CALLS = Counter(
        "dde_circuit_breaker_calls_total",
        "Total calls through circuit breaker",
        ["circuit_id", "result"]
    )
    FALLBACK_INVOCATIONS = Counter(
        "dde_circuit_breaker_fallback_total",
        "Total fallback invocations",
        ["circuit_id"]
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    CIRCUIT_STATE = None
    CIRCUIT_TRIPS = None
    CIRCUIT_CALLS = None
    FALLBACK_INVOCATIONS = None


T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Blocking calls
    HALF_OPEN = "half_open"  # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """Configuration for circuit breaker."""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 3          # Successes to close from half-open
    reset_timeout_seconds: float = 60   # Seconds before trying again
    half_open_max_calls: int = 3        # Max calls in half-open state
    excluded_exceptions: tuple = ()     # Exceptions that don't count as failures


@dataclass
class CircuitBreakerStats:
    """Statistics for circuit breaker."""
    circuit_id: str
    state: CircuitState
    failure_count: int
    success_count: int
    consecutive_failures: int
    consecutive_successes: int
    total_calls: int
    total_failures: int
    total_successes: int
    last_failure_time: Optional[datetime]
    last_success_time: Optional[datetime]
    last_state_change: datetime
    trip_count: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "circuit_id": self.circuit_id,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "consecutive_failures": self.consecutive_failures,
            "consecutive_successes": self.consecutive_successes,
            "total_calls": self.total_calls,
            "total_failures": self.total_failures,
            "total_successes": self.total_successes,
            "last_failure_time": self.last_failure_time.isoformat() if self.last_failure_time else None,
            "last_success_time": self.last_success_time.isoformat() if self.last_success_time else None,
            "last_state_change": self.last_state_change.isoformat(),
            "trip_count": self.trip_count,
        }


class CircuitBreakerError(Exception):
    """Exception raised when circuit is open."""

    def __init__(self, message: str, circuit_id: str, retry_after: Optional[float] = None):
        super().__init__(message)
        self.circuit_id = circuit_id
        self.retry_after = retry_after


class CircuitBreaker(Generic[T]):
    """
    Circuit breaker pattern for agent calls.

    State transitions:
    - CLOSED -> OPEN: when failures >= threshold
    - OPEN -> HALF_OPEN: when timeout elapsed
    - HALF_OPEN -> CLOSED: on success
    - HALF_OPEN -> OPEN: on failure
    """

    def __init__(
        self,
        circuit_id: Optional[str] = None,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable[..., T]] = None,
        on_state_change: Optional[Callable[[CircuitState, CircuitState], None]] = None,
    ):
        self.circuit_id = circuit_id or f"circuit_{uuid4().hex[:8]}"
        self.config = config or CircuitBreakerConfig()
        self._fallback = fallback
        self._on_state_change = on_state_change

        self._state = CircuitState.CLOSED
        self._lock = threading.RLock()

        # Counters
        self._failure_count = 0
        self._success_count = 0
        self._consecutive_failures = 0
        self._consecutive_successes = 0
        self._total_calls = 0
        self._total_failures = 0
        self._total_successes = 0
        self._half_open_calls = 0
        self._trip_count = 0

        # Timestamps
        self._last_failure_time: Optional[datetime] = None
        self._last_success_time: Optional[datetime] = None
        self._last_state_change = datetime.utcnow()
        self._opened_at: Optional[datetime] = None

        logger.info(f"CircuitBreaker {self.circuit_id} initialized (threshold: {self.config.failure_threshold})")

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        with self._lock:
            self._check_state_timeout()
            return self._state

    def _check_state_timeout(self) -> None:
        """Check if state should transition due to timeout."""
        if self._state == CircuitState.OPEN and self._opened_at:
            elapsed = (datetime.utcnow() - self._opened_at).total_seconds()
            if elapsed >= self.config.reset_timeout_seconds:
                self._transition_to(CircuitState.HALF_OPEN)

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new state."""
        old_state = self._state
        if old_state == new_state:
            return

        self._state = new_state
        self._last_state_change = datetime.utcnow()

        if new_state == CircuitState.OPEN:
            self._opened_at = datetime.utcnow()
            self._trip_count += 1
            if PROMETHEUS_AVAILABLE and CIRCUIT_TRIPS:
                CIRCUIT_TRIPS.labels(circuit_id=self.circuit_id).inc()
        elif new_state == CircuitState.HALF_OPEN:
            self._half_open_calls = 0
        elif new_state == CircuitState.CLOSED:
            self._failure_count = 0
            self._consecutive_failures = 0
            self._opened_at = None

        # Update metrics
        if PROMETHEUS_AVAILABLE and CIRCUIT_STATE:
            state_value = {"closed": 0, "open": 1, "half_open": 2}[new_state.value]
            CIRCUIT_STATE.labels(circuit_id=self.circuit_id).set(state_value)

        # Callback
        if self._on_state_change:
            try:
                self._on_state_change(old_state, new_state)
            except Exception as e:
                logger.error(f"State change callback error: {e}")

        logger.info(f"CircuitBreaker {self.circuit_id}: {old_state.value} -> {new_state.value}")

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        Execute a function through the circuit breaker.

        Raises CircuitBreakerError if circuit is open.
        """
        with self._lock:
            self._total_calls += 1
            self._check_state_timeout()

            # Check if call is allowed
            if self._state == CircuitState.OPEN:
                if self._fallback:
                    if PROMETHEUS_AVAILABLE and FALLBACK_INVOCATIONS:
                        FALLBACK_INVOCATIONS.labels(circuit_id=self.circuit_id).inc()
                    return self._fallback(*args, **kwargs)

                retry_after = None
                if self._opened_at:
                    elapsed = (datetime.utcnow() - self._opened_at).total_seconds()
                    retry_after = max(0, self.config.reset_timeout_seconds - elapsed)

                raise CircuitBreakerError(
                    f"Circuit {self.circuit_id} is OPEN",
                    self.circuit_id,
                    retry_after,
                )

            if self._state == CircuitState.HALF_OPEN:
                self._half_open_calls += 1
                if self._half_open_calls > self.config.half_open_max_calls:
                    self._transition_to(CircuitState.OPEN)
                    raise CircuitBreakerError(
                        f"Circuit {self.circuit_id} exceeded half-open call limit",
                        self.circuit_id,
                    )

        # Execute the function
        try:
            result = func(*args, **kwargs)
            self.record_success()
            return result
        except Exception as e:
            if not isinstance(e, self.config.excluded_exceptions):
                self.record_failure(e)
            raise

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            self._success_count += 1
            self._total_successes += 1
            self._consecutive_successes += 1
            self._consecutive_failures = 0
            self._last_success_time = datetime.utcnow()

            if PROMETHEUS_AVAILABLE and CIRCUIT_CALLS:
                CIRCUIT_CALLS.labels(circuit_id=self.circuit_id, result="success").inc()

            if self._state == CircuitState.HALF_OPEN:
                if self._consecutive_successes >= self.config.success_threshold:
                    self._transition_to(CircuitState.CLOSED)

    def record_failure(self, error: Optional[Exception] = None) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._total_failures += 1
            self._consecutive_failures += 1
            self._consecutive_successes = 0
            self._last_failure_time = datetime.utcnow()

            if PROMETHEUS_AVAILABLE and CIRCUIT_CALLS:
                CIRCUIT_CALLS.labels(circuit_id=self.circuit_id, result="failure").inc()

            if error:
                logger.debug(f"CircuitBreaker {self.circuit_id} recorded failure: {error}")

            if self._state == CircuitState.CLOSED:
                if self._consecutive_failures >= self.config.failure_threshold:
                    self._transition_to(CircuitState.OPEN)
            elif self._state == CircuitState.HALF_OPEN:
                self._transition_to(CircuitState.OPEN)

    def is_available(self) -> bool:
        """Check if the circuit allows calls."""
        with self._lock:
            self._check_state_timeout()
            return self._state != CircuitState.OPEN

    def reset(self) -> None:
        """Reset the circuit breaker to CLOSED state."""
        with self._lock:
            self._transition_to(CircuitState.CLOSED)
            self._failure_count = 0
            self._success_count = 0
            self._consecutive_failures = 0
            self._consecutive_successes = 0

    def force_open(self) -> None:
        """Force the circuit to OPEN state."""
        with self._lock:
            self._transition_to(CircuitState.OPEN)

    def get_stats(self) -> CircuitBreakerStats:
        """Get current statistics."""
        with self._lock:
            self._check_state_timeout()
            return CircuitBreakerStats(
                circuit_id=self.circuit_id,
                state=self._state,
                failure_count=self._failure_count,
                success_count=self._success_count,
                consecutive_failures=self._consecutive_failures,
                consecutive_successes=self._consecutive_successes,
                total_calls=self._total_calls,
                total_failures=self._total_failures,
                total_successes=self._total_successes,
                last_failure_time=self._last_failure_time,
                last_success_time=self._last_success_time,
                last_state_change=self._last_state_change,
                trip_count=self._trip_count,
            )

    def time_until_retry(self) -> Optional[float]:
        """Get seconds until circuit might allow calls again."""
        with self._lock:
            if self._state != CircuitState.OPEN or not self._opened_at:
                return 0

            elapsed = (datetime.utcnow() - self._opened_at).total_seconds()
            remaining = self.config.reset_timeout_seconds - elapsed
            return max(0, remaining)

    def __enter__(self) -> "CircuitBreaker":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        if exc_type is not None:
            if not isinstance(exc_val, self.config.excluded_exceptions):
                self.record_failure(exc_val)
        else:
            self.record_success()
        return False


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.
    """

    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = threading.Lock()

    def get_or_create(
        self,
        circuit_id: str,
        config: Optional[CircuitBreakerConfig] = None,
        fallback: Optional[Callable] = None,
    ) -> CircuitBreaker:
        """Get existing circuit breaker or create a new one."""
        with self._lock:
            if circuit_id not in self._breakers:
                self._breakers[circuit_id] = CircuitBreaker(
                    circuit_id=circuit_id,
                    config=config,
                    fallback=fallback,
                )
            return self._breakers[circuit_id]

    def get(self, circuit_id: str) -> Optional[CircuitBreaker]:
        """Get circuit breaker by ID."""
        return self._breakers.get(circuit_id)

    def list_circuits(self) -> List[str]:
        """List all circuit IDs."""
        return list(self._breakers.keys())

    def get_all_stats(self) -> Dict[str, CircuitBreakerStats]:
        """Get stats for all circuit breakers."""
        return {
            circuit_id: breaker.get_stats()
            for circuit_id, breaker in self._breakers.items()
        }

    def reset_all(self) -> None:
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()

    def remove(self, circuit_id: str) -> bool:
        """Remove a circuit breaker."""
        with self._lock:
            if circuit_id in self._breakers:
                del self._breakers[circuit_id]
                return True
            return False


# Decorator for easy use
def circuit_breaker(
    circuit_id: Optional[str] = None,
    failure_threshold: int = 5,
    reset_timeout_seconds: float = 60,
    fallback: Optional[Callable] = None,
):
    """
    Decorator to wrap a function with a circuit breaker.

    Usage:
        @circuit_breaker(circuit_id="my_service", failure_threshold=3)
        def call_service():
            ...
    """
    config = CircuitBreakerConfig(
        failure_threshold=failure_threshold,
        reset_timeout_seconds=reset_timeout_seconds,
    )

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        cid = circuit_id or f"{func.__module__}.{func.__name__}"
        breaker = CircuitBreaker(circuit_id=cid, config=config, fallback=fallback)

        def wrapper(*args, **kwargs) -> T:
            return breaker.call(func, *args, **kwargs)

        wrapper._circuit_breaker = breaker
        wrapper.__name__ = func.__name__
        wrapper.__doc__ = func.__doc__

        return wrapper

    return decorator


# Global registry instance
_global_registry = CircuitBreakerRegistry()


def get_circuit(circuit_id: str) -> Optional[CircuitBreaker]:
    """Get a circuit breaker from the global registry."""
    return _global_registry.get(circuit_id)


def get_or_create_circuit(
    circuit_id: str,
    config: Optional[CircuitBreakerConfig] = None,
) -> CircuitBreaker:
    """Get or create a circuit breaker in the global registry."""
    return _global_registry.get_or_create(circuit_id, config)
