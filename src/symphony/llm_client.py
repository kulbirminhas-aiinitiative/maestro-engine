"""
Symphony LLM Client

EPIC: MD-4123 - Symphony Real LLM Integration via claude_code_api_layer
Story: MD-4131 - Create SymphonyLLMClient for claude_code_api_layer routing

HTTP client that routes LLM requests through claude_code_api_layer (port 4001).
Handles authentication, request formatting, response parsing, and error handling.
"""

import os
import asyncio
import logging
import time
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from enum import Enum

import httpx

logger = logging.getLogger(__name__)


class LLMConnectionError(Exception):
    """API layer is unavailable"""
    pass


class LLMTimeoutError(Exception):
    """Request timed out"""
    pass


class LLMRateLimitError(Exception):
    """Rate limit exceeded"""
    pass


class LLMTokenLimitError(Exception):
    """Context or response exceeds token limits"""
    pass


class LLMResponseError(Exception):
    """Invalid or malformed response from LLM"""
    pass


@dataclass
class LLMResponse:
    """Structured response from LLM"""
    content: str
    tokens_input: int
    tokens_output: int
    model: str
    latency_ms: float

    @property
    def tokens_total(self) -> int:
        return self.tokens_input + self.tokens_output


class SymphonyLLMClient:
    """
    HTTP client for routing Symphony LLM requests through claude_code_api_layer.

    Features:
    - Async HTTP requests with configurable timeout
    - Automatic retry with exponential backoff
    - Structured error handling
    - Token usage tracking
    - Health check endpoint

    Usage:
        client = SymphonyLLMClient()
        response = await client.generate(
            prompt="Create user stories for login feature",
            system_prompt=SARAH_PRODUCT_OWNER_PROMPT,
            context={"project_brief": "E-commerce platform"}
        )
    """

    DEFAULT_API_URL = "http://localhost:4001"
    DEFAULT_MODEL = "claude-sonnet-4-20250514"
    DEFAULT_MAX_TOKENS = 4096
    DEFAULT_TIMEOUT = 120
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_RETRY_DELAY = 1.0

    def __init__(
        self,
        api_url: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        timeout: Optional[int] = None,
        max_retries: Optional[int] = None,
        retry_delay: Optional[float] = None,
    ):
        """
        Initialize the Symphony LLM Client.

        Args:
            api_url: claude_code_api_layer endpoint (default: http://localhost:4001)
            model: Claude model to use (default: claude-sonnet-4-20250514)
            max_tokens: Maximum tokens per response (default: 4096)
            timeout: Request timeout in seconds (default: 120)
            max_retries: Number of retry attempts (default: 3)
            retry_delay: Initial retry delay in seconds (default: 1.0)
        """
        self.api_url = api_url or os.getenv("CLAUDE_API_LAYER_URL", self.DEFAULT_API_URL)
        self.model = model or os.getenv("SYMPHONY_MODEL", self.DEFAULT_MODEL)
        self.max_tokens = max_tokens or int(os.getenv("SYMPHONY_MAX_TOKENS", self.DEFAULT_MAX_TOKENS))
        self.timeout = timeout or int(os.getenv("SYMPHONY_TIMEOUT", self.DEFAULT_TIMEOUT))
        self.max_retries = max_retries or int(os.getenv("SYMPHONY_MAX_RETRIES", self.DEFAULT_MAX_RETRIES))
        self.retry_delay = retry_delay or float(os.getenv("SYMPHONY_RETRY_DELAY", self.DEFAULT_RETRY_DELAY))

        # HTTP client configuration
        self._client: Optional[httpx.AsyncClient] = None

        # Metrics tracking
        self._total_tokens_used = 0
        self._total_requests = 0
        self._total_errors = 0

        logger.info(f"SymphonyLLMClient initialized: api_url={self.api_url}, model={self.model}")

    async def _get_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client"""
        if self._client is None or self._client.is_closed:
            base = self.api_url if self.api_url else self.DEFAULT_API_URL
            self._client = httpx.AsyncClient(
                base_url=base,
                timeout=httpx.Timeout(self.timeout, connect=10.0),
                headers={"Content-Type": "application/json"},
            )
        return self._client

    async def close(self):
        """Close the HTTP client"""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def health_check(self) -> Dict[str, Any]:
        """
        Check connectivity to claude_code_api_layer.

        Returns:
            Dict with status, api_layer_version, and latency_ms
        """
        start = time.perf_counter()
        try:
            client = await self._get_client()
            response = await client.get("/health")
            latency_ms = (time.perf_counter() - start) * 1000

            if response.status_code == 200:
                data = response.json()
                return {
                    "status": "healthy",
                    "api_layer_version": data.get("version", "unknown"),
                    "latency_ms": latency_ms,
                }
            else:
                return {
                    "status": "unhealthy",
                    "error": f"HTTP {response.status_code}",
                    "latency_ms": latency_ms,
                }
        except httpx.ConnectError:
            return {
                "status": "unhealthy",
                "error": "Connection refused",
                "latency_ms": (time.perf_counter() - start) * 1000,
            }
        except Exception as e:
            return {
                "status": "unhealthy",
                "error": str(e),
                "latency_ms": (time.perf_counter() - start) * 1000,
            }

    async def generate(
        self,
        prompt: str,
        system_prompt: str,
        context: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> LLMResponse:
        """
        Generate a response from the LLM via claude_code_api_layer.

        Args:
            prompt: User message/task to send to the LLM
            system_prompt: Persona system prompt
            context: Optional context dict with previous workflow outputs
            model: Optional model override
            max_tokens: Optional max tokens override

        Returns:
            LLMResponse with content, token usage, and latency

        Raises:
            LLMConnectionError: API layer unavailable
            LLMTimeoutError: Request timed out
            LLMRateLimitError: Rate limit exceeded
            LLMTokenLimitError: Token limit exceeded
            LLMResponseError: Invalid response
        """
        self._total_requests += 1

        # Build message with context
        user_message = prompt
        if context:
            context_str = self._format_context(context)
            user_message = f"{context_str}\n\n{prompt}"

        # Build full prompt with system prompt embedded (claude_code_api_layer format)
        full_prompt = f"""## System Instructions
{system_prompt}

## Task
{user_message}"""

        # Build request payload for /api/query endpoint
        payload = {
            "prompt": full_prompt,
            "output_format": "text",
            "timeout": self.timeout,
            "skip_permissions": True,
        }

        # Execute with retry
        last_error = None
        for attempt in range(self.max_retries):
            try:
                response = await self._execute_request(payload)
                return response
            except (LLMConnectionError, LLMTimeoutError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.retry_delay * (2 ** attempt)
                    logger.warning(f"LLM request failed (attempt {attempt + 1}), retrying in {delay}s: {e}")
                    await asyncio.sleep(delay)
                else:
                    self._total_errors += 1
                    raise
            except LLMRateLimitError:
                self._total_errors += 1
                raise
            except Exception as e:
                self._total_errors += 1
                raise LLMResponseError(f"Unexpected error: {e}") from e

        self._total_errors += 1
        if last_error is not None:
            raise last_error
        raise LLMConnectionError("All retry attempts failed")

    async def _execute_request(self, payload: Dict[str, Any]) -> LLMResponse:
        """Execute single LLM request via /api/query endpoint"""
        start = time.perf_counter()

        try:
            client = await self._get_client()
            response = await client.post("/api/query", json=payload)
            latency_ms = (time.perf_counter() - start) * 1000

            # Handle error responses
            if response.status_code == 429:
                raise LLMRateLimitError("Rate limit exceeded")
            elif response.status_code == 400:
                error_data = response.json()
                if "token" in str(error_data).lower():
                    raise LLMTokenLimitError(f"Token limit exceeded: {error_data}")
                raise LLMResponseError(f"Bad request: {error_data}")
            elif response.status_code >= 500:
                raise LLMConnectionError(f"Server error: HTTP {response.status_code}")
            elif response.status_code != 200:
                raise LLMResponseError(f"Unexpected status: HTTP {response.status_code}")

            # Parse response (claude_code_api_layer format)
            data = response.json()

            if not data.get("success", False):
                error_msg = data.get("error", "Unknown error from API layer")
                raise LLMResponseError(f"API layer error: {error_msg}")

            content = data.get("output", "")
            if not content:
                raise LLMResponseError("Empty output from API layer")

            # Token counts not available from claude_code_api_layer, estimate from content
            # Rough estimate: ~4 chars per token
            tokens_in_estimate = len(payload.get("prompt", "")) // 4
            tokens_out_estimate = len(content) // 4
            self._total_tokens_used += tokens_in_estimate + tokens_out_estimate

            return LLMResponse(
                content=content,
                tokens_input=tokens_in_estimate,
                tokens_output=tokens_out_estimate,
                model=self.model,
                latency_ms=latency_ms,
            )

        except httpx.ConnectError as e:
            raise LLMConnectionError(f"Failed to connect to {self.api_url}: {e}")
        except httpx.TimeoutException as e:
            raise LLMTimeoutError(f"Request timed out after {self.timeout}s: {e}")

    def _format_context(self, context: Dict[str, Any]) -> str:
        """Format context dict into prompt-friendly string"""
        parts = ["## Previous Workflow Context\n"]

        for key, value in context.items():
            if isinstance(value, list):
                parts.append(f"### {key.replace('_', ' ').title()}")
                for item in value:
                    if isinstance(item, dict):
                        parts.append(f"- {item}")
                    else:
                        parts.append(f"- {item}")
            elif isinstance(value, dict):
                parts.append(f"### {key.replace('_', ' ').title()}")
                for k, v in value.items():
                    parts.append(f"- {k}: {v}")
            else:
                parts.append(f"**{key.replace('_', ' ').title()}:** {value}")

        return "\n".join(parts)

    def _extract_content(self, response_data: Dict[str, Any]) -> str:
        """Extract text content from LLM response"""
        content_blocks = response_data.get("content", [])

        if not content_blocks:
            raise LLMResponseError("Empty content in LLM response")

        text_parts = []
        for block in content_blocks:
            if isinstance(block, dict) and block.get("type") == "text":
                text_parts.append(block.get("text", ""))
            elif isinstance(block, str):
                text_parts.append(block)

        if not text_parts:
            raise LLMResponseError("No text content in LLM response")

        return "\n".join(text_parts)

    def get_stats(self) -> Dict[str, Any]:
        """Get usage statistics"""
        return {
            "total_requests": self._total_requests,
            "total_errors": self._total_errors,
            "total_tokens_used": self._total_tokens_used,
            "error_rate": self._total_errors / max(self._total_requests, 1),
            "model": self.model,
            "api_url": self.api_url,
        }

    def reset_stats(self):
        """Reset usage statistics"""
        self._total_tokens_used = 0
        self._total_requests = 0
        self._total_errors = 0


# Singleton instance
_llm_client: Optional[SymphonyLLMClient] = None


def get_llm_client() -> SymphonyLLMClient:
    """Get or create the singleton LLM client"""
    global _llm_client
    if _llm_client is None:
        _llm_client = SymphonyLLMClient()
    return _llm_client


async def close_llm_client():
    """Close the singleton LLM client"""
    global _llm_client
    if _llm_client:
        await _llm_client.close()
        _llm_client = None
