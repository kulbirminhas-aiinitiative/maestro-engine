"""
Tests for Symphony LLM Client

EPIC: MD-4123 - Symphony Real LLM Integration via claude_code_api_layer
Story: MD-4136 - Create comprehensive test suite for LLM integration
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, patch, MagicMock
import httpx

import sys
sys.path.insert(0, '/home/ec2-user/projects/maestro-platform/maestro-engine/src')

from symphony.llm_client import (
    SymphonyLLMClient,
    LLMResponse,
    LLMConnectionError,
    LLMTimeoutError,
    LLMRateLimitError,
    LLMTokenLimitError,
    LLMResponseError,
    get_llm_client,
)


class TestSymphonyLLMClient:
    """Test suite for SymphonyLLMClient"""

    @pytest.fixture
    def client(self):
        """Create a test client"""
        return SymphonyLLMClient(
            api_url="http://test-api:4001",
            model="claude-sonnet-4-20250514",
            timeout=30,
            max_retries=2,
        )

    @pytest.fixture
    def mock_response(self):
        """Create a mock successful response"""
        return {
            "content": [
                {"type": "text", "text": "Test response content"}
            ],
            "usage": {
                "input_tokens": 100,
                "output_tokens": 200
            }
        }

    def test_client_initialization(self, client):
        """Test client initializes with correct parameters"""
        assert client.api_url == "http://test-api:4001"
        assert client.model == "claude-sonnet-4-20250514"
        assert client.timeout == 30
        assert client.max_retries == 2

    def test_client_default_values(self):
        """Test client uses defaults when not specified"""
        client = SymphonyLLMClient()
        assert client.api_url == "http://localhost:4001"
        assert client.max_tokens == 4096
        assert client.retry_delay == 1.0

    @pytest.mark.asyncio
    async def test_health_check_success(self, client):
        """Test health check with healthy API"""
        with patch.object(client, '_get_client') as mock_get:
            mock_http = AsyncMock()
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"version": "1.0.0"}
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_get.return_value = mock_http

            result = await client.health_check()

            assert result["status"] == "healthy"
            assert result["api_layer_version"] == "1.0.0"
            assert "latency_ms" in result

    @pytest.mark.asyncio
    async def test_health_check_connection_error(self, client):
        """Test health check when API is down"""
        with patch.object(client, '_get_client') as mock_get:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(side_effect=httpx.ConnectError("Connection refused"))
            mock_get.return_value = mock_http

            result = await client.health_check()

            assert result["status"] == "unhealthy"
            assert "Connection refused" in result["error"]

    @pytest.mark.asyncio
    async def test_generate_success(self, client, mock_response):
        """Test successful LLM generation"""
        with patch.object(client, '_execute_request') as mock_exec:
            mock_exec.return_value = LLMResponse(
                content="Test response content",
                tokens_input=100,
                tokens_output=200,
                model="claude-sonnet-4-20250514",
                latency_ms=500.0,
            )

            response = await client.generate(
                prompt="Test prompt",
                system_prompt="You are a helpful assistant",
            )

            assert response.content == "Test response content"
            assert response.tokens_input == 100
            assert response.tokens_output == 200
            assert response.tokens_total == 300

    @pytest.mark.asyncio
    async def test_generate_with_context(self, client):
        """Test generation with context"""
        with patch.object(client, '_execute_request') as mock_exec:
            mock_exec.return_value = LLMResponse(
                content="Response with context",
                tokens_input=150,
                tokens_output=250,
                model="claude-sonnet-4-20250514",
                latency_ms=600.0,
            )

            context = {"project_brief": "Build an e-commerce app"}
            response = await client.generate(
                prompt="Create user stories",
                system_prompt="You are a product owner",
                context=context,
            )

            assert response.content == "Response with context"
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_retry_on_connection_error(self, client):
        """Test retry behavior on connection error"""
        call_count = 0

        async def mock_request(payload):
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise LLMConnectionError("Connection failed")
            return LLMResponse(
                content="Success after retry",
                tokens_input=100,
                tokens_output=200,
                model="claude-sonnet-4-20250514",
                latency_ms=500.0,
            )

        with patch.object(client, '_execute_request', side_effect=mock_request):
            with patch('asyncio.sleep', new_callable=AsyncMock):
                response = await client.generate(
                    prompt="Test",
                    system_prompt="System",
                )

            assert response.content == "Success after retry"
            assert call_count == 2

    @pytest.mark.asyncio
    async def test_generate_max_retries_exceeded(self, client):
        """Test failure after max retries"""
        with patch.object(client, '_execute_request') as mock_exec:
            mock_exec.side_effect = LLMConnectionError("Always fails")

            with patch('asyncio.sleep', new_callable=AsyncMock):
                with pytest.raises(LLMConnectionError):
                    await client.generate(
                        prompt="Test",
                        system_prompt="System",
                    )

            # Should have tried max_retries times
            assert mock_exec.call_count == client.max_retries

    def test_format_context(self, client):
        """Test context formatting"""
        context = {
            "project_brief": "E-commerce platform",
            "user_stories": [
                {"title": "Login", "priority": "High"},
                {"title": "Checkout", "priority": "Medium"},
            ],
        }

        formatted = client._format_context(context)

        assert "Previous Workflow Context" in formatted
        assert "E-commerce platform" in formatted
        assert "User Stories" in formatted

    def test_extract_content_text_blocks(self, client):
        """Test content extraction from text blocks"""
        response_data = {
            "content": [
                {"type": "text", "text": "First part"},
                {"type": "text", "text": "Second part"},
            ]
        }

        content = client._extract_content(response_data)

        assert "First part" in content
        assert "Second part" in content

    def test_extract_content_empty_raises(self, client):
        """Test empty content raises error"""
        response_data = {"content": []}

        with pytest.raises(LLMResponseError):
            client._extract_content(response_data)

    def test_get_stats(self, client):
        """Test statistics retrieval"""
        stats = client.get_stats()

        assert "total_requests" in stats
        assert "total_errors" in stats
        assert "total_tokens_used" in stats
        assert "error_rate" in stats

    def test_reset_stats(self, client):
        """Test statistics reset"""
        client._total_requests = 10
        client._total_errors = 2
        client._total_tokens_used = 5000

        client.reset_stats()

        assert client._total_requests == 0
        assert client._total_errors == 0
        assert client._total_tokens_used == 0


class TestLLMClientSingleton:
    """Test singleton pattern for LLM client"""

    def test_get_llm_client_singleton(self):
        """Test that get_llm_client returns same instance"""
        # Reset singleton
        import symphony.llm_client as module
        module._llm_client = None

        client1 = get_llm_client()
        client2 = get_llm_client()

        assert client1 is client2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
