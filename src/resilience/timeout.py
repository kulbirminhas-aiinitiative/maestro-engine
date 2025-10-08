"""
Timeout Pattern implementation.

Part of ADR-006: Resilience Patterns

Prevent operations from hanging forever by enforcing timeouts.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

logger = logging.getLogger(__name__)


class TimeoutError(Exception):
    """Raised when operation exceeds timeout."""

    pass


@asynccontextmanager
async def timeout(seconds: float, operation: str = "operation") -> AsyncIterator[None]:
    """
    Context manager for timeout enforcement.

    Args:
        seconds: Timeout in seconds
        operation: Description of operation for error message

    Raises:
        TimeoutError: If operation exceeds timeout

    Example:
        async with timeout(30.0, "API call"):
            result = await slow_api_call()
    """
    try:
        async with asyncio.timeout(seconds):
            yield

    except asyncio.TimeoutError:
        error_msg = f"{operation} exceeded {seconds}s timeout"
        logger.error(error_msg, extra={"timeout": seconds, "operation": operation})
        raise TimeoutError(error_msg)


async def with_timeout(coro, seconds: float, operation: str = "operation"):
    """
    Execute coroutine with timeout.

    Args:
        coro: Coroutine to execute
        seconds: Timeout in seconds
        operation: Description for error message

    Returns:
        Result from coroutine

    Raises:
        TimeoutError: If coroutine exceeds timeout

    Example:
        result = await with_timeout(
            slow_api_call(),
            seconds=30.0,
            operation="fetch template"
        )
    """
    try:
        return await asyncio.wait_for(coro, timeout=seconds)
    except asyncio.TimeoutError:
        error_msg = f"{operation} exceeded {seconds}s timeout"
        logger.error(error_msg, extra={"timeout": seconds, "operation": operation})
        raise TimeoutError(error_msg)
