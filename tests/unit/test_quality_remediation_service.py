"""
Unit tests for QualityRemediationService.

Tests cover:
- Importing failing results
- Creating remediation tasks
- Verifying fixes
- Remediation cycle management
- Statistics
"""

from datetime import datetime, timedelta
from unittest.mock import MagicMock
import pytest

from src.services.quality_remediation_service import (
    FailureType,
    QualityFailure,
    QualityRemediationService,
    RemediationCycle,
    RemediationPriority,
    RemediationStatus,
    RemediationTask,
    VerificationResult,
    get_quality_remediation_service,
)


@pytest.fixture
def service():
    """Create a fresh QualityRemediationService instance for testing."""
    svc = QualityRemediationService()
    svc.reset()
    return svc


@pytest.fixture
def sample_validation_result():
    """Sample validation result with failures."""
    return {
        "failed_tests": [
            {
                "name": "test_user_authentication",
                "category": "integration",
                "message": "AssertionError: Expected 200, got 401",
                "stack_trace": "File test_auth.py line 45\n  assert response.status == 200",
                "file_path": "tests/integration/test_auth.py",
                "line_number": 45,
                "severity": "high",
                "test_id": "test_001",
            },
            {
                "name": "test_payment_processing",
                "category": "functional",
                "message": "TimeoutError: Payment gateway timeout",
                "severity": "critical",
                "test_id": "test_002",
            },
        ],
        "threshold_violations": [
            {
                "type": "coverage",
                "threshold": 80,
                "actual": 72,
                "message": "Coverage 72% below minimum 80%",
            },
        ],
    }


@pytest.fixture
def sample_failure(service):
    """Create a sample failure."""
    failure = QualityFailure(
        failure_id="fail_test_001",
        failure_type=FailureType.TEST_FAILURE,
        test_name="test_user_login",
        test_category="integration",
        error_message="Login failed",
        file_path="tests/test_auth.py",
        line_number=50,
        severity="high",
    )
    service._failures[failure.failure_id] = failure
    return failure


@pytest.fixture
def sample_task(service, sample_failure):
    """Create a sample remediation task."""
    task = RemediationTask(
        task_id="rem_test_001",
        failure_id=sample_failure.failure_id,
        title="[Test] Fix: test_user_login",
        description="Fix the failing login test",
        priority=RemediationPriority.HIGH,
        status=RemediationStatus.OPEN,
        created_at=datetime.utcnow(),
    )
    service._tasks[task.task_id] = task
    return task


class TestConfiguration:
    """Tests for service configuration."""

    def test_configure(self, service):
        """Test configuring the service."""
        service.configure(
            auto_create_tasks=False,
            auto_verify_on_commit=False,
        )
        assert service._auto_create_tasks is False
        assert service._auto_verify_on_commit is False

    def test_register_task_adapter(self, service):
        """Test registering a task adapter."""
        adapter = MagicMock(return_value="JIRA-123")
        service.register_task_adapter(adapter)
        assert service._task_adapter == adapter

    def test_register_test_runner(self, service):
        """Test registering a test runner."""
        runner = MagicMock()
        service.register_test_runner(runner)
        assert service._test_runner == runner

    def test_register_notification_handler(self, service):
        """Test registering a notification handler."""
        handler = MagicMock()
        service.register_notification_handler(handler)
        assert service._notification_handler == handler


class TestImportFailures:
    """Tests for importing failures."""

    def test_import_test_failures(self, service, sample_validation_result):
        """Test importing test failures from validation result."""
        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )

        assert len(failures) == 3  # 2 failed tests + 1 threshold violation
        assert failures[0].failure_type == FailureType.TEST_FAILURE
        assert failures[0].test_name == "test_user_authentication"
        assert failures[0].severity == "high"

    def test_import_threshold_violations(self, service, sample_validation_result):
        """Test importing threshold violations."""
        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )

        # Find the coverage violation
        coverage_failure = next(
            f for f in failures if f.test_name == "Threshold: coverage"
        )
        assert coverage_failure.failure_type == FailureType.COVERAGE_GAP

    def test_import_static_analysis_issues(self, service):
        """Test importing static analysis issues."""
        issues = [
            {
                "rule": "security/sql-injection",
                "message": "Potential SQL injection vulnerability",
                "file": "src/db/queries.py",
                "line": 42,
                "severity": "critical",
                "tool": "bandit",
            },
            {
                "rule": "lint/unused-variable",
                "message": "Unused variable 'temp'",
                "file": "src/utils.py",
                "line": 15,
                "severity": "low",
            },
        ]

        failures = service.import_static_analysis_issues(
            issues,
            workflow_id="wf_001",
            phase_id="phase_001",
        )

        assert len(failures) == 2
        assert failures[0].failure_type == FailureType.STATIC_ANALYSIS
        assert failures[0].file_path == "src/db/queries.py"
        assert failures[0].severity == "critical"

    def test_import_empty_result(self, service):
        """Test importing empty validation result."""
        failures = service.import_failures(
            {},
            workflow_id="wf_001",
            phase_id="phase_001",
        )
        assert len(failures) == 0


class TestCreateRemediationTasks:
    """Tests for creating remediation tasks."""

    def test_create_tasks_from_failures(self, service, sample_validation_result):
        """Test creating remediation tasks from failures."""
        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )

        tasks = service.create_remediation_tasks(failures)

        assert len(tasks) == 3
        assert all(isinstance(t, RemediationTask) for t in tasks)
        assert all(t.status == RemediationStatus.OPEN for t in tasks)

    def test_task_priority_from_severity(self, service, sample_validation_result):
        """Test task priority is set from failure severity."""
        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )

        tasks = service.create_remediation_tasks(failures)

        # Find critical severity task
        critical_task = next(
            t for t in tasks if "payment" in t.title.lower()
        )
        assert critical_task.priority == RemediationPriority.CRITICAL

    def test_auto_assign_tasks(self, service, sample_validation_result):
        """Test auto-assigning tasks to a user."""
        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )

        tasks = service.create_remediation_tasks(failures, auto_assign="dev@example.com")

        assert all(t.assigned_to == "dev@example.com" for t in tasks)

    def test_external_task_creation_via_adapter(self, service, sample_validation_result):
        """Test creating external tasks via adapter."""
        adapter = MagicMock(return_value="JIRA-456")
        service.register_task_adapter(adapter)

        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )

        tasks = service.create_remediation_tasks(failures)

        assert adapter.call_count == 3
        assert all(t.external_task_id == "JIRA-456" for t in tasks)

    def test_notification_on_task_creation(self, service, sample_validation_result):
        """Test notifications are sent on task creation."""
        handler = MagicMock()
        service.register_notification_handler(handler)

        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )

        tasks = service.create_remediation_tasks(failures)

        assert handler.call_count == 3
        handler.assert_called_with(tasks[-1], "created")


class TestTaskStatusManagement:
    """Tests for task status management."""

    def test_update_task_status(self, service, sample_task):
        """Test updating task status."""
        task = service.update_task_status(
            sample_task.task_id,
            RemediationStatus.IN_PROGRESS,
        )

        assert task.status == RemediationStatus.IN_PROGRESS

    def test_update_with_fix_info(self, service, sample_task):
        """Test updating task with fix information."""
        task = service.update_task_status(
            sample_task.task_id,
            RemediationStatus.PENDING_VERIFICATION,
            fix_branch="fix/login-auth",
            fix_commit="abc123def",
        )

        assert task.fix_branch == "fix/login-auth"
        assert task.fix_commit == "abc123def"

    def test_close_task(self, service, sample_task):
        """Test closing a task."""
        task = service.update_task_status(
            sample_task.task_id,
            RemediationStatus.CLOSED,
            notes="Fixed by updating the auth token validation",
        )

        assert task.status == RemediationStatus.CLOSED
        assert task.closed_at is not None
        assert task.resolution_notes is not None

    def test_assign_task(self, service, sample_task):
        """Test assigning a task."""
        task = service.assign_task(sample_task.task_id, "developer@example.com")

        assert task.assigned_to == "developer@example.com"
        assert task.status == RemediationStatus.IN_PROGRESS

    def test_update_nonexistent_task(self, service):
        """Test updating non-existent task returns None."""
        result = service.update_task_status("nonexistent", RemediationStatus.CLOSED)
        assert result is None


class TestVerification:
    """Tests for fix verification."""

    def test_verify_fix_success(self, service, sample_task, sample_failure):
        """Test successful fix verification."""
        # The mock runner returns passed=True by default
        result = service.verify_fix(sample_task.task_id)

        assert isinstance(result, VerificationResult)
        assert result.passed is True
        assert sample_task.status == RemediationStatus.VERIFIED
        assert sample_task.verified_at is not None

    def test_verify_with_custom_runner(self, service, sample_task, sample_failure):
        """Test verification with custom test runner."""
        def custom_runner(test_name, category):
            return VerificationResult(
                verification_id="ver_custom",
                task_id=sample_task.task_id,
                run_id="run_custom",
                test_name=test_name,
                passed=True,
                timestamp=datetime.utcnow(),
                duration_ms=150.0,
                message="Custom runner passed",
            )

        service.register_test_runner(custom_runner)
        result = service.verify_fix(sample_task.task_id)

        assert result.verification_id == "ver_custom"
        assert result.message == "Custom runner passed"

    def test_verify_fix_failure(self, service, sample_task, sample_failure):
        """Test failed verification."""
        def failing_runner(test_name, category):
            return VerificationResult(
                verification_id="ver_fail",
                task_id=sample_task.task_id,
                run_id="run_fail",
                test_name=test_name,
                passed=False,
                timestamp=datetime.utcnow(),
                duration_ms=100.0,
                message="Test still failing",
            )

        service.register_test_runner(failing_runner)
        result = service.verify_fix(sample_task.task_id)

        assert result.passed is False
        assert sample_task.retry_count == 1

    def test_retry_limit_reached(self, service, sample_task, sample_failure):
        """Test task status when retry limit reached."""
        def failing_runner(test_name, category):
            return VerificationResult(
                verification_id=f"ver_{sample_task.retry_count}",
                task_id=sample_task.task_id,
                run_id=f"run_{sample_task.retry_count}",
                test_name=test_name,
                passed=False,
                timestamp=datetime.utcnow(),
                duration_ms=100.0,
            )

        service.register_test_runner(failing_runner)

        # Verify 3 times (max retries)
        for _ in range(3):
            service.verify_fix(sample_task.task_id)

        assert sample_task.retry_count == 3
        assert sample_task.status == RemediationStatus.OPEN

    def test_batch_verify(self, service, sample_validation_result):
        """Test batch verification."""
        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )
        tasks = service.create_remediation_tasks(failures)

        task_ids = [t.task_id for t in tasks]
        results = service.batch_verify(task_ids, run_id="batch_001")

        assert len(results) == 3
        assert all(r.run_id == "batch_001" for r in results)


class TestRemediationCycle:
    """Tests for remediation cycle management."""

    def test_start_remediation_cycle(self, service, sample_validation_result):
        """Test starting a remediation cycle."""
        cycle = service.start_remediation_cycle(
            workflow_id="wf_001",
            phase_id="phase_001",
            validation_result=sample_validation_result,
        )

        assert isinstance(cycle, RemediationCycle)
        assert cycle.workflow_id == "wf_001"
        assert len(cycle.failures) == 3
        assert len(cycle.tasks) == 3
        assert cycle.status == "in_progress"

    def test_complete_remediation_cycle(self, service, sample_validation_result):
        """Test completing a remediation cycle."""
        cycle = service.start_remediation_cycle(
            workflow_id="wf_001",
            phase_id="phase_001",
            validation_result=sample_validation_result,
        )

        # Verify all tasks
        for task in cycle.tasks:
            service.verify_fix(task.task_id)

        updated_cycle = service.complete_remediation_cycle(cycle.cycle_id)

        assert updated_cycle.status == "completed"
        assert updated_cycle.completed_at is not None
        assert updated_cycle.metrics["verified_fixes"] == 3

    def test_cycle_with_pending_tasks(self, service, sample_validation_result):
        """Test cycle completion with pending tasks."""
        cycle = service.start_remediation_cycle(
            workflow_id="wf_001",
            phase_id="phase_001",
            validation_result=sample_validation_result,
        )

        # Only verify some tasks
        service.verify_fix(cycle.tasks[0].task_id)

        updated_cycle = service.complete_remediation_cycle(cycle.cycle_id)

        assert updated_cycle.status == "in_progress"  # Not complete yet
        assert updated_cycle.metrics["pending_fixes"] == 2


class TestQueryMethods:
    """Tests for query methods."""

    def test_get_task(self, service, sample_task):
        """Test getting a task by ID."""
        task = service.get_task(sample_task.task_id)
        assert task == sample_task

    def test_get_failure(self, service, sample_failure):
        """Test getting a failure by ID."""
        failure = service.get_failure(sample_failure.failure_id)
        assert failure == sample_failure

    def test_get_open_tasks(self, service, sample_validation_result):
        """Test getting open tasks."""
        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )
        service.create_remediation_tasks(failures)

        open_tasks = service.get_open_tasks()
        assert len(open_tasks) == 3

    def test_get_open_tasks_by_priority(self, service, sample_validation_result):
        """Test filtering open tasks by priority."""
        failures = service.import_failures(
            sample_validation_result,
            workflow_id="wf_001",
            phase_id="phase_001",
        )
        service.create_remediation_tasks(failures)

        critical_tasks = service.get_open_tasks(priority=RemediationPriority.CRITICAL)
        assert len(critical_tasks) == 1

    def test_get_tasks_pending_verification(self, service, sample_task):
        """Test getting tasks pending verification."""
        service.update_task_status(
            sample_task.task_id,
            RemediationStatus.PENDING_VERIFICATION,
        )

        pending = service.get_tasks_pending_verification()
        assert len(pending) == 1
        assert pending[0].task_id == sample_task.task_id


class TestStatistics:
    """Tests for statistics."""

    def test_get_statistics_empty(self, service):
        """Test statistics with no data."""
        stats = service.get_statistics()
        assert stats["total_failures"] == 0
        assert stats["total_tasks"] == 0

    def test_get_statistics_with_data(self, service, sample_validation_result):
        """Test statistics with data."""
        cycle = service.start_remediation_cycle(
            workflow_id="wf_001",
            phase_id="phase_001",
            validation_result=sample_validation_result,
        )

        # Verify some tasks
        service.verify_fix(cycle.tasks[0].task_id)
        service.verify_fix(cycle.tasks[1].task_id)

        stats = service.get_statistics()

        assert stats["total_failures"] == 3
        assert stats["total_tasks"] == 3
        assert stats["total_verifications"] == 2
        assert stats["verification_pass_rate"] == 1.0  # Both passed
        assert stats["active_cycles"] == 1


class TestSingletonPattern:
    """Tests for singleton pattern."""

    def test_singleton_instance(self):
        """Test that service is a singleton."""
        service1 = QualityRemediationService()
        service2 = QualityRemediationService()
        assert service1 is service2

    def test_get_service_function(self):
        """Test get_quality_remediation_service function."""
        service = get_quality_remediation_service()
        assert isinstance(service, QualityRemediationService)


class TestReset:
    """Tests for service reset."""

    def test_reset_clears_state(self, service, sample_validation_result):
        """Test reset clears all state."""
        service.start_remediation_cycle(
            workflow_id="wf_001",
            phase_id="phase_001",
            validation_result=sample_validation_result,
        )

        service.reset()

        assert len(service._failures) == 0
        assert len(service._tasks) == 0
        assert len(service._verifications) == 0
        assert len(service._cycles) == 0
