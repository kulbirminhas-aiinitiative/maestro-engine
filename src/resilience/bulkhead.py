"""
Bulkhead Pattern implementation.

Part of ADR-006: Resilience Patterns

Limits concurrent requests to prevent resource exhaustion and isolate failures.
"""

import asyncio
import logging
from typing import Any, Callable, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


class Bulkhead:
    """
    Bulkhead pattern implementation using semaphore.

    Limits concurrent execution of operations to prevent resource exhaustion.

    Example:
        # Limit concurrent API calls to 3
        api_bulkhead = Bulkhead(max_concurrent=3)

        async def call_api():
            return await api_bulkhead.call(make_api_request)
    """

    def __init__(self, max_concurrent: int, name: str = "unnamed"):
        """
        Initialize bulkhead.

        Args:
            max_concurrent: Maximum number of concurrent operations
            name: Name for logging/metrics
        """
        self.max_concurrent = max_concurrent
        self.name = name
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
        self.total_executions = 0
        self.total_rejections = 0

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with concurrency limit.

        Args:
            func: Callable (async) to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from func

        Raises:
            Exception: Any exception from func
        """
        # Try to acquire semaphore (non-blocking check for metrics)
        if self.semaphore.locked() and self.active_count >= self.max_concurrent:
            self.total_rejections += 1
            logger.warning(
                f"Bulkhead '{self.name}' at capacity ({self.active_count}/{self.max_concurrent})",
                extra={
                    "bulkhead": self.name,
                    "active": self.active_count,
                    "max": self.max_concurrent,
                    "rejections": self.total_rejections,
                },
            )

        # Acquire semaphore (will wait if at capacity)
        async with self.semaphore:
            self.active_count += 1
            self.total_executions += 1

            logger.debug(
                f"Bulkhead '{self.name}' executing ({self.active_count}/{self.max_concurrent})",
                extra={
                    "bulkhead": self.name,
                    "active": self.active_count,
                    "max": self.max_concurrent,
                },
            )

            try:
                result = await func(*args, **kwargs)
                return result
            finally:
                self.active_count -= 1

    def get_metrics(self) -> dict:
        """Get bulkhead metrics."""
        return {
            "name": self.name,
            "max_concurrent": self.max_concurrent,
            "active_count": self.active_count,
            "total_executions": self.total_executions,
            "total_rejections": self.total_rejections,
            "available_slots": self.max_concurrent - self.active_count,
        }


class BulkheadFullError(Exception):
    """Raised when bulkhead is at capacity (for strict mode)."""

    pass


class StrictBulkhead(Bulkhead):
    """
    Bulkhead that rejects requests immediately when at capacity.

    Unlike regular Bulkhead which waits, this fails fast.
    """

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with concurrency limit, fail fast if at capacity.

        Raises:
            BulkheadFullError: If bulkhead is at capacity
        """
        # Try to acquire without waiting
        if not self.semaphore.locked():
            async with self.semaphore:
                self.active_count += 1
                self.total_executions += 1

                try:
                    result = await func(*args, **kwargs)
                    return result
                finally:
                    self.active_count -= 1
        else:
            self.total_rejections += 1
            raise BulkheadFullError(
                f"Bulkhead '{self.name}' at capacity "
                f"({self.active_count}/{self.max_concurrent})"
            )
