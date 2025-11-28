"""
Unit Tests for GitHub Actions Client (MD-1790)

Tests the GitHubActionsClient for deployment workflow integration.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from src.services.github_actions_client import (
    GitHubActionsClient,
    GitHubActionsError,
    GitHubAuthError,
    GitHubRateLimitError,
    GitHubWorkflowError,
    WorkflowRun,
    WorkflowStatus,
    WorkflowConclusion,
    WorkflowJob,
)


class TestGitHubActionsClient:
    """Test suite for GitHubActionsClient."""

    @pytest.fixture
    def client(self):
        """Create a GitHubActionsClient instance for testing."""
        return GitHubActionsClient(
            token="test-token",
            repository="test-owner/test-repo"
        )

    @pytest.fixture
    def mock_workflow_run_data(self):
        """Sample workflow run data from GitHub API."""
        return {
            "id": 12345,
            "name": "Deploy to Production",
            "head_branch": "main",
            "head_sha": "abc123def456",
            "status": "completed",
            "conclusion": "success",
            "workflow_id": 100,
            "run_number": 42,
            "run_attempt": 1,
            "html_url": "https://github.com/test-owner/test-repo/actions/runs/12345",
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T10:05:00Z",
            "run_started_at": "2025-01-15T10:00:30Z",
            "event": "workflow_dispatch",
            "display_title": "Deploy v1.2.3",
        }

    # Initialization Tests
    def test_init_with_token(self, client):
        """Test client initialization with token."""
        assert client.token == "test-token"
        assert client.repository == "test-owner/test-repo"
        assert client.base_url == "https://api.github.com"

    def test_init_without_token_logs_warning(self):
        """Test that initialization without token logs a warning."""
        with patch('src.services.github_actions_client.logger') as mock_logger:
            client = GitHubActionsClient(token=None, repository="owner/repo")
            mock_logger.warning.assert_called()
            assert client.token is None

    def test_repo_url_property(self, client):
        """Test repository URL property."""
        assert client.repo_url == "https://api.github.com/repos/test-owner/test-repo"

    def test_headers_property(self, client):
        """Test headers property."""
        headers = client.headers
        assert headers["Authorization"] == "Bearer test-token"
        assert headers["Accept"] == "application/vnd.github+json"
        assert "X-GitHub-Api-Version" in headers

    # WorkflowRun Model Tests
    def test_workflow_run_from_api_response(self, mock_workflow_run_data):
        """Test WorkflowRun creation from API response."""
        run = WorkflowRun.from_api_response(mock_workflow_run_data)

        assert run.id == 12345
        assert run.name == "Deploy to Production"
        assert run.head_branch == "main"
        assert run.head_sha == "abc123def456"
        assert run.status == WorkflowStatus.COMPLETED
        assert run.conclusion == WorkflowConclusion.SUCCESS
        assert run.run_number == 42
        assert run.event == "workflow_dispatch"

    def test_workflow_run_is_complete(self, mock_workflow_run_data):
        """Test WorkflowRun completion check."""
        run = WorkflowRun.from_api_response(mock_workflow_run_data)
        assert run.is_complete() is True

        mock_workflow_run_data["status"] = "in_progress"
        run_in_progress = WorkflowRun.from_api_response(mock_workflow_run_data)
        assert run_in_progress.is_complete() is False

    def test_workflow_run_is_successful(self, mock_workflow_run_data):
        """Test WorkflowRun success check."""
        run = WorkflowRun.from_api_response(mock_workflow_run_data)
        assert run.is_successful() is True

        mock_workflow_run_data["conclusion"] = "failure"
        run_failed = WorkflowRun.from_api_response(mock_workflow_run_data)
        assert run_failed.is_successful() is False

    def test_workflow_run_is_failed(self, mock_workflow_run_data):
        """Test WorkflowRun failure check."""
        mock_workflow_run_data["conclusion"] = "failure"
        run = WorkflowRun.from_api_response(mock_workflow_run_data)
        assert run.is_failed() is True

        mock_workflow_run_data["conclusion"] = "success"
        run_success = WorkflowRun.from_api_response(mock_workflow_run_data)
        assert run_success.is_failed() is False

    # API Method Tests (Async)
    @pytest.mark.asyncio
    async def test_trigger_workflow(self, client, mock_workflow_run_data):
        """Test triggering a workflow dispatch."""
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            with patch.object(client, '_find_latest_run', new_callable=AsyncMock) as mock_find:
                mock_request.return_value = {}  # 204 No Content for dispatch
                mock_find.return_value = WorkflowRun.from_api_response(mock_workflow_run_data)

                run_id = await client.trigger_workflow(
                    workflow_id="deploy.yml",
                    ref="main",
                    inputs={"environment": "production"}
                )

                assert run_id == 12345
                mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_trigger_workflow_no_token_raises(self, ):
        """Test triggering workflow without token raises error."""
        client = GitHubActionsClient(token=None, repository="owner/repo")

        with pytest.raises(GitHubAuthError, match="GitHub token not configured"):
            await client.trigger_workflow("deploy.yml")

    @pytest.mark.asyncio
    async def test_get_workflow_run(self, client, mock_workflow_run_data):
        """Test getting a specific workflow run."""
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_workflow_run_data

            run = await client.get_workflow_run(12345)

            assert run.id == 12345
            assert run.name == "Deploy to Production"
            mock_request.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_workflow_jobs(self, client):
        """Test getting workflow jobs."""
        mock_jobs_response = {
            "total_count": 2,
            "jobs": [
                {
                    "id": 1001,
                    "name": "build",
                    "status": "completed",
                    "conclusion": "success",
                    "started_at": "2025-01-15T10:00:00Z",
                    "completed_at": "2025-01-15T10:02:00Z",
                    "steps": [{"name": "Checkout", "status": "completed"}]
                },
                {
                    "id": 1002,
                    "name": "deploy",
                    "status": "completed",
                    "conclusion": "success",
                    "started_at": "2025-01-15T10:02:00Z",
                    "completed_at": "2025-01-15T10:05:00Z",
                    "steps": [{"name": "Deploy", "status": "completed"}]
                }
            ]
        }

        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_jobs_response

            jobs = await client.get_workflow_jobs(12345)

            assert len(jobs) == 2
            assert jobs[0].name == "build"
            assert jobs[1].name == "deploy"

    @pytest.mark.asyncio
    async def test_get_workflow_logs(self, client):
        """Test retrieving workflow logs URL."""
        logs_url = await client.get_workflow_logs(12345)

        assert logs_url == "https://api.github.com/repos/test-owner/test-repo/actions/runs/12345/logs"

    @pytest.mark.asyncio
    async def test_cancel_workflow_run(self, client):
        """Test canceling a workflow run."""
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await client.cancel_workflow_run(12345)

            assert result is True
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert "cancel" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_cancel_workflow_run_failure(self, client):
        """Test canceling workflow when it fails."""
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = GitHubActionsError("Cannot cancel")

            result = await client.cancel_workflow_run(12345)

            assert result is False

    @pytest.mark.asyncio
    async def test_rerun_workflow(self, client):
        """Test re-running a workflow."""
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = {}

            result = await client.rerun_workflow(12345)

            assert result is True
            mock_request.assert_called_once()
            call_args = mock_request.call_args
            assert "rerun" in call_args[0][1]

    @pytest.mark.asyncio
    async def test_list_releases(self, client):
        """Test listing releases."""
        mock_releases = [
            {
                "tag_name": "v1.2.0",
                "name": "Release v1.2.0",
                "body": "Release notes",
                "prerelease": False,
                "published_at": "2025-01-15T10:00:00Z",
                "html_url": "https://github.com/test-owner/test-repo/releases/tag/v1.2.0",
                "target_commitish": "main"
            },
            {
                "tag_name": "v1.1.0",
                "name": "Release v1.1.0",
                "body": "Previous release",
                "prerelease": False,
                "published_at": "2025-01-10T10:00:00Z",
                "html_url": "https://github.com/test-owner/test-repo/releases/tag/v1.1.0",
                "target_commitish": "main"
            }
        ]

        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_releases

            releases = await client.list_releases(per_page=10)

            assert len(releases) == 2
            assert releases[0]["tag_name"] == "v1.2.0"
            assert releases[1]["tag_name"] == "v1.1.0"

    @pytest.mark.asyncio
    async def test_list_releases_exclude_prereleases(self, client):
        """Test listing releases excludes prereleases when specified."""
        mock_releases = [
            {"tag_name": "v1.2.0", "prerelease": False, "published_at": "2025-01-15T10:00:00Z"},
            {"tag_name": "v1.3.0-beta", "prerelease": True, "published_at": "2025-01-16T10:00:00Z"},
        ]

        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_releases

            releases = await client.list_releases(include_prereleases=False)

            # Should only return non-prerelease
            assert len(releases) == 1
            assert releases[0]["tag_name"] == "v1.2.0"

    @pytest.mark.asyncio
    async def test_list_tags(self, client):
        """Test listing tags."""
        mock_tags = [
            {"name": "v1.2.0", "commit": {"sha": "abc123", "url": "https://api.github.com/commits/abc123"}},
            {"name": "v1.1.0", "commit": {"sha": "def456", "url": "https://api.github.com/commits/def456"}},
        ]

        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.return_value = mock_tags

            tags = await client.list_tags()

            assert len(tags) == 2
            assert tags[0]["name"] == "v1.2.0"
            assert tags[0]["sha"] == "abc123"

    # Polling Tests
    @pytest.mark.asyncio
    async def test_poll_workflow_status_success(self, client, mock_workflow_run_data):
        """Test waiting for workflow completion - success case."""
        with patch.object(client, 'get_workflow_run', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = WorkflowRun.from_api_response(mock_workflow_run_data)

            run = await client.poll_workflow_status(12345, poll_interval=0.1, timeout=5)

            assert run.is_complete()
            assert run.is_successful()

    @pytest.mark.asyncio
    async def test_poll_workflow_status_with_callback(self, client, mock_workflow_run_data):
        """Test polling with callback function."""
        callback_calls = []

        async def callback(run):
            callback_calls.append(run)

        with patch.object(client, 'get_workflow_run', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = WorkflowRun.from_api_response(mock_workflow_run_data)

            run = await client.poll_workflow_status(
                12345,
                poll_interval=0.1,
                timeout=5,
                callback=callback
            )

            assert len(callback_calls) >= 1
            assert callback_calls[0].id == 12345

    @pytest.mark.asyncio
    async def test_poll_workflow_status_timeout(self, client, mock_workflow_run_data):
        """Test waiting for workflow completion - timeout case."""
        mock_workflow_run_data["status"] = "in_progress"
        mock_workflow_run_data["conclusion"] = None

        with patch.object(client, 'get_workflow_run', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = WorkflowRun.from_api_response(mock_workflow_run_data)

            with pytest.raises(asyncio.TimeoutError, match="did not complete"):
                await client.poll_workflow_status(12345, poll_interval=0.1, timeout=0.3)

    # Error Handling Tests - Testing error types by simulating via higher-level methods
    @pytest.mark.asyncio
    async def test_auth_error_handling(self, client):
        """Test handling of authentication errors via trigger_workflow."""
        # Test that auth errors are properly raised by the client
        client_no_token = GitHubActionsClient(token=None, repository="owner/repo")
        with pytest.raises(GitHubAuthError, match="GitHub token not configured"):
            await client_no_token.trigger_workflow("deploy.yml")

    @pytest.mark.asyncio
    async def test_workflow_error_propagation(self, client):
        """Test that workflow errors propagate correctly."""
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = GitHubWorkflowError("Workflow not found")

            with pytest.raises(GitHubWorkflowError, match="Workflow not found"):
                await client.get_workflow_run(99999)

    @pytest.mark.asyncio
    async def test_generic_actions_error_handling(self, client):
        """Test handling of generic GitHub Actions errors."""
        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            mock_request.side_effect = GitHubActionsError("API error 500")

            with pytest.raises(GitHubActionsError, match="API error"):
                await client.get_workflow_run(12345)


class TestWorkflowStatus:
    """Test suite for WorkflowStatus enum."""

    def test_status_values(self):
        """Test all status values are defined."""
        assert WorkflowStatus.QUEUED.value == "queued"
        assert WorkflowStatus.IN_PROGRESS.value == "in_progress"
        assert WorkflowStatus.COMPLETED.value == "completed"
        assert WorkflowStatus.WAITING.value == "waiting"
        assert WorkflowStatus.REQUESTED.value == "requested"
        assert WorkflowStatus.PENDING.value == "pending"

    def test_status_from_string(self):
        """Test creating status from string."""
        status = WorkflowStatus("completed")
        assert status == WorkflowStatus.COMPLETED

    def test_invalid_status(self):
        """Test handling of invalid status."""
        with pytest.raises(ValueError):
            WorkflowStatus("invalid_status")


class TestWorkflowConclusion:
    """Test suite for WorkflowConclusion enum."""

    def test_conclusion_values(self):
        """Test all conclusion values are defined."""
        assert WorkflowConclusion.SUCCESS.value == "success"
        assert WorkflowConclusion.FAILURE.value == "failure"
        assert WorkflowConclusion.CANCELLED.value == "cancelled"
        assert WorkflowConclusion.SKIPPED.value == "skipped"
        assert WorkflowConclusion.TIMED_OUT.value == "timed_out"


class TestWorkflowJob:
    """Test suite for WorkflowJob model."""

    def test_workflow_job_creation(self):
        """Test WorkflowJob dataclass creation."""
        job = WorkflowJob(
            id=1001,
            name="build",
            status="completed",
            conclusion="success",
            started_at=datetime(2025, 1, 15, 10, 0, 0),
            completed_at=datetime(2025, 1, 15, 10, 5, 0),
            steps=[{"name": "Checkout", "status": "completed"}]
        )

        assert job.id == 1001
        assert job.name == "build"
        assert job.status == "completed"
        assert job.conclusion == "success"
        assert len(job.steps) == 1


# Integration-style Tests (with mocked HTTP)
class TestGitHubActionsClientIntegration:
    """Integration-style tests with mocked HTTP responses."""

    @pytest.fixture
    def client(self):
        """Create client for integration tests."""
        return GitHubActionsClient(
            token="test-token",
            repository="maestro-ai/deployment-platform"
        )

    @pytest.mark.asyncio
    async def test_full_deployment_workflow(self, client):
        """Test a complete deployment workflow from trigger to completion."""
        triggered_run_data = {
            "id": 99999,
            "name": "Production Deploy",
            "head_branch": "main",
            "head_sha": "abc123",
            "status": "queued",
            "conclusion": None,
            "workflow_id": 1,
            "run_number": 100,
            "run_attempt": 1,
            "html_url": "https://github.com/maestro-ai/deployment-platform/actions/runs/99999",
            "created_at": "2025-01-15T10:00:00Z",
            "updated_at": "2025-01-15T10:00:00Z",
        }

        completed_run_data = triggered_run_data.copy()
        completed_run_data["status"] = "completed"
        completed_run_data["conclusion"] = "success"
        completed_run_data["updated_at"] = "2025-01-15T10:10:00Z"

        with patch.object(client, '_request', new_callable=AsyncMock) as mock_request:
            with patch.object(client, '_find_latest_run', new_callable=AsyncMock) as mock_find:
                mock_request.return_value = {}
                mock_find.return_value = WorkflowRun.from_api_response(triggered_run_data)

                # Step 1: Trigger deployment
                run_id = await client.trigger_workflow(
                    workflow_id="deploy-production.yml",
                    ref="main",
                    inputs={"environment": "production", "version": "v2.0.0"}
                )
                assert run_id == 99999

        # Step 2: Check completion
        with patch.object(client, 'get_workflow_run', new_callable=AsyncMock) as mock_get:
            mock_get.return_value = WorkflowRun.from_api_response(completed_run_data)

            final_run = await client.get_workflow_run(run_id)
            assert final_run.is_complete()
            assert final_run.is_successful()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
