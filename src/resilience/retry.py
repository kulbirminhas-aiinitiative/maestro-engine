"""
Retry with Exponential Backoff pattern.

Part of ADR-006: Resilience Patterns

Automatically retry failed requests with increasing delays between attempts.
"""

import asyncio
import logging
from typing import Callable, Tuple, Type, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def retry_with_backoff(
    func: Callable[..., T],
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
    on_retry: Callable[[int, Exception], None] = None,
) -> T:
    """
    Retry function with exponential backoff.

    Args:
        func: Async function to retry
        max_retries: Maximum number of retry attempts (0 = no retries)
        initial_delay: Initial delay in seconds between retries
        backoff_factor: Multiplier for delay after each retry
        max_delay: Maximum delay between retries in seconds
        retryable_exceptions: Tuple of exception types to retry on
        on_retry: Optional callback(attempt, exception) called on each retry

    Returns:
        Result from func

    Raises:
        Exception: The last exception if all retries exhausted

    Example:
        async def fetch_data():
            response = await client.get("/data")
            return response.json()

        data = await retry_with_backoff(
            fetch_data,
            max_retries=3,
            initial_delay=1.0,
            retryable_exceptions=(httpx.HTTPError, httpx.TimeoutException)
        )
    """
    delay = initial_delay
    last_exception = None

    for attempt in range(max_retries + 1):
        try:
            # Call the function
            result = await func()
            return result

        except retryable_exceptions as e:
            last_exception = e

            # Don't retry on last attempt
            if attempt >= max_retries:
                logger.error(
                    f"Max retries ({max_retries}) exceeded for {func.__name__}",
                    extra={
                        "function": func.__name__,
                        "attempts": attempt + 1,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    },
                )
                raise

            # Calculate wait time with exponential backoff
            wait_time = min(delay, max_delay)

            logger.warning(
                f"Retry {attempt + 1}/{max_retries} for {func.__name__} after {wait_time:.1f}s",
                extra={
                    "function": func.__name__,
                    "attempt": attempt + 1,
                    "max_retries": max_retries,
                    "wait_time": wait_time,
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
            )

            # Call retry callback if provided
            if on_retry:
                on_retry(attempt + 1, e)

            # Wait before retry
            await asyncio.sleep(wait_time)

            # Increase delay for next attempt
            delay *= backoff_factor

    # This should never be reached, but just in case
    if last_exception:
        raise last_exception


def retry(
    max_retries: int = 3,
    initial_delay: float = 1.0,
    backoff_factor: float = 2.0,
    max_delay: float = 60.0,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
):
    """
    Decorator for automatic retry with exponential backoff.

    Example:
        @retry(max_retries=3, initial_delay=1.0)
        async def fetch_data():
            response = await client.get("/data")
            return response.json()
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        async def wrapper(*args, **kwargs) -> T:
            async def call_func():
                return await func(*args, **kwargs)

            return await retry_with_backoff(
                call_func,
                max_retries=max_retries,
                initial_delay=initial_delay,
                backoff_factor=backoff_factor,
                max_delay=max_delay,
                retryable_exceptions=retryable_exceptions,
            )

        return wrapper

    return decorator
