"""
Fallback Pattern implementation.

Part of ADR-006: Resilience Patterns

Provides degraded service when primary function fails.
"""

import logging
from typing import Callable, Optional, TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def with_fallback(
    primary: Callable[..., T],
    fallback: Callable[..., T],
    *args,
    fallback_exceptions: tuple = (Exception,),
    **kwargs,
) -> T:
    """
    Execute primary function, use fallback if it fails.

    Args:
        primary: Primary function to try
        fallback: Fallback function to use if primary fails
        *args: Arguments for both functions
        fallback_exceptions: Exceptions that trigger fallback
        **kwargs: Keyword arguments for both functions

    Returns:
        Result from primary or fallback

    Example:
        async def get_from_service():
            return await api_client.get_data()

        async def get_from_cache():
            return cached_data

        data = await with_fallback(
            primary=get_from_service,
            fallback=get_from_cache,
            fallback_exceptions=(httpx.HTTPError,)
        )
    """
    try:
        result = await primary(*args, **kwargs)
        return result

    except fallback_exceptions as e:
        logger.warning(
            f"Primary function {primary.__name__} failed, using fallback {fallback.__name__}",
            extra={
                "primary": primary.__name__,
                "fallback": fallback.__name__,
                "error": str(e),
                "error_type": type(e).__name__,
            },
        )

        result = await fallback(*args, **kwargs)
        return result


class FallbackChain:
    """
    Chain multiple fallbacks in order.

    Example:
        chain = FallbackChain()
        chain.add(get_from_primary_db)
        chain.add(get_from_replica_db)
        chain.add(get_from_cache)
        chain.add(get_default_value)

        data = await chain.execute()
    """

    def __init__(self):
        self.functions = []

    def add(self, func: Callable, fallback_exceptions: tuple = (Exception,)):
        """Add function to fallback chain."""
        self.functions.append((func, fallback_exceptions))
        return self

    async def execute(self, *args, **kwargs) -> Optional[T]:
        """
        Execute chain, trying each function until one succeeds.

        Returns:
            Result from first successful function, or None if all fail
        """
        last_exception = None

        for i, (func, exceptions) in enumerate(self.functions):
            try:
                result = await func(*args, **kwargs)
                if i > 0:
                    logger.info(
                        f"Fallback chain succeeded at level {i} ({func.__name__})",
                        extra={"level": i, "function": func.__name__},
                    )
                return result

            except exceptions as e:
                last_exception = e
                logger.warning(
                    f"Fallback chain level {i} ({func.__name__}) failed: {e}",
                    extra={
                        "level": i,
                        "function": func.__name__,
                        "error": str(e),
                        "remaining": len(self.functions) - i - 1,
                    },
                )
                continue

        logger.error(
            f"Fallback chain exhausted ({len(self.functions)} attempts)",
            extra={"attempts": len(self.functions)},
        )

        if last_exception:
            raise last_exception

        return None
