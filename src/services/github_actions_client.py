#!/usr/bin/env python3
"""
GitHub Actions Client
Epic: MD-1790 [Platform] Unified Deployment Management GUI

Client for interacting with GitHub Actions API to:
- Trigger workflow_dispatch events
- Poll workflow run status
- Retrieve workflow logs
- Cancel running workflows

Implements AC-4: One-click deploy from versions
"""

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

import aiohttp

logger = logging.getLogger("github_actions_client")


class WorkflowStatus(str, Enum):
    """GitHub Actions workflow run status."""
    QUEUED = "queued"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    WAITING = "waiting"
    REQUESTED = "requested"
    PENDING = "pending"


class WorkflowConclusion(str, Enum):
    """GitHub Actions workflow run conclusion."""
    SUCCESS = "success"
    FAILURE = "failure"
    CANCELLED = "cancelled"
    SKIPPED = "skipped"
    TIMED_OUT = "timed_out"
    ACTION_REQUIRED = "action_required"
    NEUTRAL = "neutral"
    STALE = "stale"


@dataclass
class WorkflowRun:
    """Represents a GitHub Actions workflow run."""
    id: int
    name: str
    status: WorkflowStatus
    conclusion: Optional[WorkflowConclusion]
    run_number: int
    html_url: str
    created_at: datetime
    updated_at: datetime
    run_started_at: Optional[datetime] = None
    head_sha: Optional[str] = None
    head_branch: Optional[str] = None
    event: Optional[str] = None
    display_title: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_api_response(cls, data: Dict[str, Any]) -> "WorkflowRun":
        """Create WorkflowRun from GitHub API response."""
        return cls(
            id=data["id"],
            name=data.get("name", "Unknown"),
            status=WorkflowStatus(data["status"]),
            conclusion=WorkflowConclusion(data["conclusion"]) if data.get("conclusion") else None,
            run_number=data["run_number"],
            html_url=data["html_url"],
            created_at=datetime.fromisoformat(data["created_at"].replace("Z", "+00:00")),
            updated_at=datetime.fromisoformat(data["updated_at"].replace("Z", "+00:00")),
            run_started_at=datetime.fromisoformat(data["run_started_at"].replace("Z", "+00:00")) if data.get("run_started_at") else None,
            head_sha=data.get("head_sha"),
            head_branch=data.get("head_branch"),
            event=data.get("event"),
            display_title=data.get("display_title"),
            metadata=data,
        )

    def is_complete(self) -> bool:
        """Check if the workflow run is complete."""
        return self.status == WorkflowStatus.COMPLETED

    def is_successful(self) -> bool:
        """Check if the workflow run completed successfully."""
        return self.is_complete() and self.conclusion == WorkflowConclusion.SUCCESS

    def is_failed(self) -> bool:
        """Check if the workflow run failed."""
        return self.is_complete() and self.conclusion in [
            WorkflowConclusion.FAILURE,
            WorkflowConclusion.TIMED_OUT,
            WorkflowConclusion.CANCELLED,
        ]


@dataclass
class WorkflowJob:
    """Represents a job within a workflow run."""
    id: int
    name: str
    status: str
    conclusion: Optional[str]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    steps: List[Dict[str, Any]] = field(default_factory=list)


class GitHubActionsError(Exception):
    """Base exception for GitHub Actions client errors."""
    pass


class GitHubAuthError(GitHubActionsError):
    """Authentication error."""
    pass


class GitHubRateLimitError(GitHubActionsError):
    """Rate limit exceeded."""
    pass


class GitHubWorkflowError(GitHubActionsError):
    """Workflow operation error."""
    pass


class GitHubActionsClient:
    """
    Client for GitHub Actions API integration.

    Uses workflow_dispatch to trigger deployments and monitors
    workflow run status for the deployment dashboard.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        repository: Optional[str] = None,
        base_url: str = "https://api.github.com",
        timeout: int = 30,
        max_retries: int = 3,
    ):
        """
        Initialize GitHub Actions client.

        Args:
            token: GitHub Personal Access Token (or set GITHUB_TOKEN env var)
            repository: Repository in format "owner/repo"
            base_url: GitHub API base URL
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts for failed requests
        """
        self.token = token or os.environ.get("GITHUB_TOKEN")
        self.repository = repository or os.environ.get("GITHUB_REPOSITORY", "fifth9/maestro-platform")
        self.base_url = base_url.rstrip("/")
        self.timeout = aiohttp.ClientTimeout(total=timeout)
        self.max_retries = max_retries
        self._session: Optional[aiohttp.ClientSession] = None

        if not self.token:
            logger.warning("GitHub token not configured. API calls will fail.")

    @property
    def repo_url(self) -> str:
        """Get the repository API URL."""
        return f"{self.base_url}/repos/{self.repository}"

    @property
    def headers(self) -> Dict[str, str]:
        """Get request headers."""
        return {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
        }

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create an aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=self.timeout,
                headers=self.headers,
            )
        return self._session

    async def close(self) -> None:
        """Close the client session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Make an API request with retry logic.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional arguments for aiohttp request

        Returns:
            Response JSON or empty dict for 204 responses

        Raises:
            GitHubAuthError: On authentication failures
            GitHubRateLimitError: When rate limited
            GitHubActionsError: On other API errors
        """
        session = await self._get_session()

        for attempt in range(self.max_retries):
            try:
                async with session.request(method, url, **kwargs) as response:
                    if response.status == 204:
                        return {}

                    if response.status == 401:
                        raise GitHubAuthError("Invalid GitHub token")

                    if response.status == 403:
                        remaining = response.headers.get("X-RateLimit-Remaining", "?")
                        if remaining == "0":
                            reset_time = response.headers.get("X-RateLimit-Reset", "?")
                            raise GitHubRateLimitError(
                                f"Rate limit exceeded. Resets at {reset_time}"
                            )
                        raise GitHubAuthError("Access forbidden")

                    if response.status == 404:
                        raise GitHubWorkflowError(f"Resource not found: {url}")

                    if response.status >= 400:
                        error_body = await response.text()
                        raise GitHubActionsError(
                            f"API error {response.status}: {error_body}"
                        )

                    return await response.json()

            except aiohttp.ClientError as e:
                if attempt < self.max_retries - 1:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Request failed, retrying in {wait_time}s: {e}"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise GitHubActionsError(f"Request failed after {self.max_retries} attempts: {e}")

        raise GitHubActionsError("Request failed")

    async def trigger_workflow(
        self,
        workflow_id: str,
        ref: str = "main",
        inputs: Optional[Dict[str, str]] = None,
    ) -> int:
        """
        Trigger a workflow_dispatch event.

        Args:
            workflow_id: Workflow file name (e.g., "deploy.yml")
            ref: Git ref to run the workflow on
            inputs: Workflow input parameters

        Returns:
            The run_id of the triggered workflow

        Raises:
            GitHubWorkflowError: If workflow trigger fails
        """
        if not self.token:
            raise GitHubAuthError("GitHub token not configured")

        url = f"{self.repo_url}/actions/workflows/{workflow_id}/dispatches"
        payload = {"ref": ref}

        if inputs:
            payload["inputs"] = inputs

        logger.info(
            f"Triggering workflow {workflow_id} on {ref} with inputs: {inputs}"
        )

        # Trigger the workflow
        await self._request("POST", url, json=payload)

        # Wait a moment for the run to be created
        await asyncio.sleep(2)

        # Find the triggered run
        run = await self._find_latest_run(workflow_id, ref)

        if run:
            logger.info(f"Workflow triggered successfully. Run ID: {run.id}")
            return run.id

        raise GitHubWorkflowError(
            f"Workflow triggered but run not found. Check GitHub Actions."
        )

    async def _find_latest_run(
        self,
        workflow_id: str,
        ref: str,
        event: str = "workflow_dispatch",
    ) -> Optional[WorkflowRun]:
        """Find the most recent workflow run."""
        url = f"{self.repo_url}/actions/workflows/{workflow_id}/runs"
        params = {
            "branch": ref,
            "event": event,
            "per_page": 5,
        }

        data = await self._request("GET", url, params=params)
        runs = data.get("workflow_runs", [])

        if runs:
            return WorkflowRun.from_api_response(runs[0])

        return None

    async def get_workflow_run(self, run_id: int) -> WorkflowRun:
        """
        Get workflow run details.

        Args:
            run_id: The workflow run ID

        Returns:
            WorkflowRun object with current status
        """
        url = f"{self.repo_url}/actions/runs/{run_id}"
        data = await self._request("GET", url)
        return WorkflowRun.from_api_response(data)

    async def get_workflow_jobs(self, run_id: int) -> List[WorkflowJob]:
        """
        Get jobs for a workflow run.

        Args:
            run_id: The workflow run ID

        Returns:
            List of WorkflowJob objects
        """
        url = f"{self.repo_url}/actions/runs/{run_id}/jobs"
        data = await self._request("GET", url)

        jobs = []
        for job_data in data.get("jobs", []):
            jobs.append(WorkflowJob(
                id=job_data["id"],
                name=job_data["name"],
                status=job_data["status"],
                conclusion=job_data.get("conclusion"),
                started_at=datetime.fromisoformat(job_data["started_at"].replace("Z", "+00:00")) if job_data.get("started_at") else None,
                completed_at=datetime.fromisoformat(job_data["completed_at"].replace("Z", "+00:00")) if job_data.get("completed_at") else None,
                steps=job_data.get("steps", []),
            ))

        return jobs

    async def get_workflow_logs(self, run_id: int) -> str:
        """
        Download workflow logs.

        Note: Returns a URL to download logs (GitHub returns a redirect).

        Args:
            run_id: The workflow run ID

        Returns:
            Logs download URL
        """
        url = f"{self.repo_url}/actions/runs/{run_id}/logs"
        # GitHub returns a redirect, we'll return the URL for now
        return url

    async def cancel_workflow_run(self, run_id: int) -> bool:
        """
        Cancel a running workflow.

        Args:
            run_id: The workflow run ID

        Returns:
            True if cancellation was successful
        """
        url = f"{self.repo_url}/actions/runs/{run_id}/cancel"
        try:
            await self._request("POST", url)
            logger.info(f"Cancelled workflow run {run_id}")
            return True
        except GitHubActionsError as e:
            logger.error(f"Failed to cancel workflow run {run_id}: {e}")
            return False

    async def rerun_workflow(self, run_id: int) -> bool:
        """
        Re-run a workflow.

        Args:
            run_id: The workflow run ID

        Returns:
            True if re-run was successful
        """
        url = f"{self.repo_url}/actions/runs/{run_id}/rerun"
        try:
            await self._request("POST", url)
            logger.info(f"Re-running workflow {run_id}")
            return True
        except GitHubActionsError as e:
            logger.error(f"Failed to re-run workflow {run_id}: {e}")
            return False

    async def poll_workflow_status(
        self,
        run_id: int,
        poll_interval: int = 10,
        timeout: int = 600,
        callback: Optional[callable] = None,
    ) -> WorkflowRun:
        """
        Poll workflow run until completion.

        Args:
            run_id: The workflow run ID
            poll_interval: Seconds between polls
            timeout: Maximum seconds to wait
            callback: Optional callback function called on each poll
                     Signature: callback(run: WorkflowRun) -> None

        Returns:
            Final WorkflowRun status

        Raises:
            asyncio.TimeoutError: If timeout is exceeded
        """
        start_time = asyncio.get_event_loop().time()

        while True:
            run = await self.get_workflow_run(run_id)

            if callback:
                await callback(run) if asyncio.iscoroutinefunction(callback) else callback(run)

            if run.is_complete():
                return run

            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed >= timeout:
                raise asyncio.TimeoutError(
                    f"Workflow {run_id} did not complete within {timeout} seconds"
                )

            logger.debug(
                f"Workflow {run_id} status: {run.status}. "
                f"Polling again in {poll_interval}s..."
            )
            await asyncio.sleep(poll_interval)

    async def list_releases(
        self,
        per_page: int = 20,
        include_prereleases: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        List repository releases.

        Args:
            per_page: Number of releases to fetch
            include_prereleases: Include pre-release versions

        Returns:
            List of release data
        """
        url = f"{self.repo_url}/releases"
        params = {"per_page": per_page}

        data = await self._request("GET", url, params=params)

        releases = []
        for release in data:
            if not include_prereleases and release.get("prerelease"):
                continue
            releases.append({
                "tag_name": release["tag_name"],
                "name": release.get("name") or release["tag_name"],
                "body": release.get("body", ""),
                "prerelease": release.get("prerelease", False),
                "published_at": release.get("published_at"),
                "html_url": release.get("html_url"),
                "target_commitish": release.get("target_commitish"),
            })

        return releases

    async def list_tags(self, per_page: int = 20) -> List[Dict[str, Any]]:
        """
        List repository tags.

        Args:
            per_page: Number of tags to fetch

        Returns:
            List of tag data
        """
        url = f"{self.repo_url}/tags"
        params = {"per_page": per_page}

        data = await self._request("GET", url, params=params)

        return [
            {
                "name": tag["name"],
                "sha": tag["commit"]["sha"],
                "url": tag["commit"]["url"],
            }
            for tag in data
        ]


# Singleton instance
_client: Optional[GitHubActionsClient] = None


def get_github_actions_client() -> GitHubActionsClient:
    """Get the singleton GitHub Actions client instance."""
    global _client
    if _client is None:
        _client = GitHubActionsClient()
    return _client


async def cleanup_github_actions_client() -> None:
    """Cleanup the singleton client."""
    global _client
    if _client:
        await _client.close()
        _client = None
