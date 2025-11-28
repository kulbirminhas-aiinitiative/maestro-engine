#!/usr/bin/env python3
"""
Unit tests for DurableJobQueueService

Tests cover:
- Job enqueueing and persistence
- Idempotency key handling
- Checkpoint-based recovery
- Worker heartbeat monitoring
- Dead letter queue management
- Job lifecycle (complete, fail, retry)
- Recovery on startup
"""

import os
import sys
import tempfile
import time
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../../src"))

from services.durable_job_queue_service import (
    DurableJobQueueService,
    DurableJob,
    JobStatus,
    JobPriority,
    JobCheckpoint,
    JobRecoveryResult,
    get_durable_job_queue_service,
)


@pytest.fixture
def service():
    """Create a fresh DurableJobQueueService instance for testing."""
    # Use temp file for isolated testing
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
        db_path = f.name

    svc = DurableJobQueueService(
        db_path=db_path,
        worker_timeout_seconds=30,
        heartbeat_interval_seconds=5,
    )
    yield svc

    # Cleanup
    svc.reset()
    try:
        os.unlink(db_path)
    except:
        pass


@pytest.fixture
def sample_payload():
    """Sample job payload."""
    return {
        "workflow_id": "wf_12345",
        "requirement": "Build a REST API",
        "personas": ["backend_developer", "qa_engineer"],
        "config": {"enable_rag": True},
    }


class TestJobEnqueuing:
    """Tests for job enqueueing."""

    def test_enqueue_basic_job(self, service, sample_payload):
        """Test basic job enqueueing."""
        job = service.enqueue(
            job_type="workflow_execution",
            payload=sample_payload,
        )

        assert job.job_id.startswith("job_")
        assert job.job_type == "workflow_execution"
        assert job.payload == sample_payload
        assert job.status == JobStatus.QUEUED
        assert job.priority == JobPriority.NORMAL

    def test_enqueue_with_priority(self, service, sample_payload):
        """Test enqueueing with priority."""
        job = service.enqueue(
            job_type="critical_task",
            payload=sample_payload,
            priority=JobPriority.CRITICAL,
        )

        assert job.priority == JobPriority.CRITICAL

    def test_enqueue_with_idempotency_key(self, service, sample_payload):
        """Test idempotency key prevents duplicates."""
        job1 = service.enqueue(
            job_type="workflow_execution",
            payload=sample_payload,
            idempotency_key="unique_key_123",
        )

        # Second enqueue with same key returns same job
        job2 = service.enqueue(
            job_type="workflow_execution",
            payload={"different": "payload"},
            idempotency_key="unique_key_123",
        )

        assert job1.job_id == job2.job_id
        assert job2.payload == sample_payload  # Original payload preserved

    def test_enqueue_with_retry_config(self, service, sample_payload):
        """Test custom retry configuration."""
        job = service.enqueue(
            job_type="workflow_execution",
            payload=sample_payload,
            max_retries=5,
            retry_delay_seconds=120,
        )

        assert job.max_retries == 5
        assert job.retry_delay_seconds == 120

    def test_enqueue_with_tags_and_metadata(self, service, sample_payload):
        """Test tags and metadata."""
        job = service.enqueue(
            job_type="workflow_execution",
            payload=sample_payload,
            tags=["priority", "customer_a"],
            metadata={"user_id": "user_123", "org_id": "org_456"},
        )

        assert job.tags == ["priority", "customer_a"]
        assert job.metadata["user_id"] == "user_123"


class TestJobPersistence:
    """Tests for job persistence."""

    def test_job_survives_service_restart(self, sample_payload):
        """Test jobs persist across service instances."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Create job with first service instance
            service1 = DurableJobQueueService(db_path=db_path)
            job = service1.enqueue(
                job_type="workflow_execution",
                payload=sample_payload,
            )
            job_id = job.job_id

            # Create new service instance (simulating restart)
            service2 = DurableJobQueueService(db_path=db_path)
            recovered_job = service2.get_job(job_id)

            assert recovered_job is not None
            assert recovered_job.job_id == job_id
            assert recovered_job.payload == sample_payload
            assert recovered_job.status == JobStatus.QUEUED
        finally:
            os.unlink(db_path)

    def test_get_nonexistent_job(self, service):
        """Test getting non-existent job returns None."""
        job = service.get_job("nonexistent_job_id")
        assert job is None


class TestJobClaiming:
    """Tests for job claiming."""

    def test_claim_next_job(self, service, sample_payload):
        """Test claiming next available job."""
        # Enqueue jobs with different priorities
        service.enqueue(job_type="low_priority", payload=sample_payload, priority=JobPriority.LOW)
        service.enqueue(job_type="high_priority", payload=sample_payload, priority=JobPriority.HIGH)
        service.enqueue(job_type="critical", payload=sample_payload, priority=JobPriority.CRITICAL)

        # Claim should return highest priority first
        job = service.claim_next_job()
        assert job.job_type == "critical"
        assert job.status == JobStatus.RUNNING
        assert job.worker_id is not None
        assert job.started_at is not None

    def test_claim_no_available_jobs(self, service):
        """Test claiming when no jobs available."""
        job = service.claim_next_job()
        assert job is None

    def test_claim_respects_retry_time(self, service, sample_payload):
        """Test claiming respects retry schedule."""
        job = service.enqueue(job_type="task", payload=sample_payload)

        # Fail and schedule retry
        claimed = service.claim_next_job()
        service.fail_job(claimed.job_id, "Test error", retry=True)

        # Job should not be available immediately (retry delay)
        next_job = service.claim_next_job()
        assert next_job is None


class TestCheckpointing:
    """Tests for checkpoint management."""

    def test_save_checkpoint(self, service, sample_payload):
        """Test saving checkpoints."""
        job = service.enqueue(job_type="task", payload=sample_payload)
        claimed = service.claim_next_job()

        checkpoint = service.save_checkpoint(
            job_id=claimed.job_id,
            phase="data_processing",
            progress_percent=45.5,
            state_data={"processed_items": 100, "total_items": 220},
        )

        assert checkpoint.checkpoint_id.startswith("ckpt_")
        assert checkpoint.phase == "data_processing"
        assert checkpoint.progress_percent == 45.5
        assert checkpoint.state_data["processed_items"] == 100

    def test_get_last_checkpoint(self, service, sample_payload):
        """Test retrieving last checkpoint."""
        job = service.enqueue(job_type="task", payload=sample_payload)
        claimed = service.claim_next_job()

        # Save multiple checkpoints
        service.save_checkpoint(claimed.job_id, "phase_1", 25.0, {"step": 1})
        service.save_checkpoint(claimed.job_id, "phase_2", 50.0, {"step": 2})
        service.save_checkpoint(claimed.job_id, "phase_3", 75.0, {"step": 3})

        # Get last checkpoint
        checkpoint = service.get_last_checkpoint(claimed.job_id)
        assert checkpoint.phase == "phase_3"
        assert checkpoint.progress_percent == 75.0
        assert checkpoint.state_data["step"] == 3

    def test_checkpoint_updates_job_progress(self, service, sample_payload):
        """Test checkpoint updates job progress."""
        job = service.enqueue(job_type="task", payload=sample_payload)
        claimed = service.claim_next_job()

        service.save_checkpoint(claimed.job_id, "processing", 60.0, {})

        updated_job = service.get_job(claimed.job_id)
        assert updated_job.current_phase == "processing"
        assert updated_job.progress_percent == 60.0


class TestJobCompletion:
    """Tests for job completion."""

    def test_complete_job(self, service, sample_payload):
        """Test marking job as completed."""
        job = service.enqueue(job_type="task", payload=sample_payload)
        claimed = service.claim_next_job()

        result = {"files_created": 10, "status": "success"}
        completed = service.complete_job(claimed.job_id, result=result)

        assert completed.status == JobStatus.COMPLETED
        assert completed.completed_at is not None
        assert completed.progress_percent == 100.0
        assert completed.metadata["result"] == result

    def test_complete_job_triggers_callback(self, service, sample_payload):
        """Test completion callback is triggered."""
        callback = MagicMock()
        service.set_callbacks(on_complete=callback)

        job = service.enqueue(job_type="task", payload=sample_payload)
        claimed = service.claim_next_job()
        service.complete_job(claimed.job_id)

        callback.assert_called_once()
        assert callback.call_args[0][0].job_id == claimed.job_id


class TestJobFailure:
    """Tests for job failure handling."""

    def test_fail_job_with_retry(self, service, sample_payload):
        """Test job failure with retry scheduling."""
        job = service.enqueue(
            job_type="task",
            payload=sample_payload,
            max_retries=3,
            retry_delay_seconds=60,
        )
        claimed = service.claim_next_job()

        failed = service.fail_job(
            claimed.job_id,
            error_message="Connection timeout",
            error_stack="Traceback...",
            retry=True,
        )

        assert failed.status == JobStatus.RETRYING
        assert failed.retry_count == 1
        assert failed.error_message == "Connection timeout"
        assert failed.next_retry_at is not None

    def test_fail_job_max_retries_exceeded(self, service, sample_payload):
        """Test job moves to dead letter after max retries."""
        job = service.enqueue(
            job_type="task",
            payload=sample_payload,
            max_retries=2,
        )

        # Simulate multiple failures
        for i in range(3):
            claimed = service.claim_next_job()
            if claimed:
                service.fail_job(claimed.job_id, f"Error {i}", retry=True)
                # Fast-forward retry time for testing
                conn = __import__("sqlite3").connect(service.db_path)
                conn.execute(
                    "UPDATE jobs SET next_retry_at = ? WHERE job_id = ?",
                    (datetime.utcnow().isoformat(), claimed.job_id),
                )
                conn.commit()
                conn.close()

        # Job should be dead after exceeding retries
        final_job = service.get_job(job.job_id)
        assert final_job.status == JobStatus.DEAD

    def test_fail_job_triggers_callback(self, service, sample_payload):
        """Test failure callback is triggered."""
        callback = MagicMock()
        service.set_callbacks(on_failed=callback)

        job = service.enqueue(job_type="task", payload=sample_payload, max_retries=0)
        claimed = service.claim_next_job()
        service.fail_job(claimed.job_id, "Error", retry=False)

        callback.assert_called_once()


class TestDeadLetterQueue:
    """Tests for dead letter queue."""

    def test_get_dead_letter_jobs(self, service, sample_payload):
        """Test retrieving dead letter jobs."""
        job = service.enqueue(job_type="task", payload=sample_payload, max_retries=0)
        claimed = service.claim_next_job()
        service.fail_job(claimed.job_id, "Fatal error", retry=True)

        dead_jobs = service.get_dead_letter_jobs()
        assert len(dead_jobs) == 1
        assert dead_jobs[0]["job_id"] == job.job_id
        assert "Fatal error" in dead_jobs[0]["reason"] or "Max retries" in dead_jobs[0]["reason"]

    def test_requeue_dead_letter_job(self, service, sample_payload):
        """Test requeuing dead letter job."""
        job = service.enqueue(job_type="task", payload=sample_payload, max_retries=0)
        claimed = service.claim_next_job()
        service.fail_job(claimed.job_id, "Error", retry=True)

        dead_jobs = service.get_dead_letter_jobs()
        requeued = service.requeue_dead_letter_job(dead_jobs[0]["id"])

        assert requeued.status == JobStatus.QUEUED
        assert requeued.retry_count == 0
        assert requeued.error_message is None

        # Dead letter queue should be empty
        assert len(service.get_dead_letter_jobs()) == 0


class TestJobRecovery:
    """Tests for job recovery on startup."""

    def test_recover_orphaned_jobs(self, sample_payload):
        """Test recovering orphaned jobs."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Create service and start a job
            service1 = DurableJobQueueService(
                db_path=db_path,
                worker_timeout_seconds=1,  # Short timeout for testing
            )
            job = service1.enqueue(job_type="task", payload=sample_payload)
            claimed = service1.claim_next_job()

            # Simulate worker crash - job is running but no heartbeat
            time.sleep(2)  # Wait for timeout

            # New service instance recovers orphaned jobs
            service2 = DurableJobQueueService(
                db_path=db_path,
                worker_timeout_seconds=1,
            )
            result = service2.recover_orphaned_jobs()

            assert result.recovered_count == 1
            assert claimed.job_id in result.resumed_jobs

            # Job should be retrying
            recovered_job = service2.get_job(claimed.job_id)
            assert recovered_job.status == JobStatus.RETRYING
        finally:
            os.unlink(db_path)

    def test_recovery_triggers_callback(self, sample_payload):
        """Test recovery callback is triggered."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            service1 = DurableJobQueueService(db_path=db_path, worker_timeout_seconds=1)
            job = service1.enqueue(job_type="task", payload=sample_payload)
            service1.claim_next_job()
            time.sleep(2)

            callback = MagicMock()
            service2 = DurableJobQueueService(db_path=db_path, worker_timeout_seconds=1)
            service2.set_callbacks(on_recovered=callback)
            service2.recover_orphaned_jobs()

            callback.assert_called_once()
        finally:
            os.unlink(db_path)


class TestJobLifecycle:
    """Tests for job lifecycle operations."""

    def test_pause_job(self, service, sample_payload):
        """Test pausing a running job."""
        job = service.enqueue(job_type="task", payload=sample_payload)
        claimed = service.claim_next_job()

        paused = service.pause_job(claimed.job_id)
        assert paused.status == JobStatus.PAUSED
        assert paused.worker_id is None

    def test_resume_job(self, service, sample_payload):
        """Test resuming a paused job."""
        job = service.enqueue(job_type="task", payload=sample_payload)
        claimed = service.claim_next_job()
        service.pause_job(claimed.job_id)

        resumed = service.resume_job(claimed.job_id)
        assert resumed.status == JobStatus.QUEUED

        # Should be claimable again
        reclaimed = service.claim_next_job()
        assert reclaimed.job_id == job.job_id

    def test_cancel_job(self, service, sample_payload):
        """Test cancelling a job."""
        job = service.enqueue(job_type="task", payload=sample_payload)

        cancelled = service.cancel_job(job.job_id)
        assert cancelled.status == JobStatus.FAILED
        assert cancelled.error_message == "Cancelled by user"

    def test_cannot_pause_completed_job(self, service, sample_payload):
        """Test cannot pause completed job."""
        job = service.enqueue(job_type="task", payload=sample_payload)
        claimed = service.claim_next_job()
        service.complete_job(claimed.job_id)

        with pytest.raises(ValueError, match="Cannot pause"):
            service.pause_job(claimed.job_id)


class TestHeartbeat:
    """Tests for heartbeat functionality."""

    def test_heartbeat_updates_timestamp(self, service, sample_payload):
        """Test heartbeat updates timestamp."""
        job = service.enqueue(job_type="task", payload=sample_payload)
        claimed = service.claim_next_job()

        original_heartbeat = claimed.heartbeat_at
        time.sleep(0.1)

        service.heartbeat(claimed.job_id)
        updated = service.get_job(claimed.job_id)

        assert updated.heartbeat_at > original_heartbeat


class TestQueueStats:
    """Tests for queue statistics."""

    def test_get_queue_stats(self, service, sample_payload):
        """Test getting queue statistics."""
        # Create various jobs
        service.enqueue(job_type="type_a", payload=sample_payload, priority=JobPriority.HIGH)
        service.enqueue(job_type="type_a", payload=sample_payload, priority=JobPriority.HIGH)
        service.enqueue(job_type="type_b", payload=sample_payload, priority=JobPriority.LOW)

        job = service.enqueue(job_type="type_a", payload=sample_payload)
        claimed = service.claim_next_job()
        service.complete_job(claimed.job_id)

        stats = service.get_queue_stats()

        assert stats["total_jobs"] == 4
        assert stats["by_status"]["queued"] == 3
        assert stats["by_status"]["completed"] == 1
        assert stats["by_type"]["type_a"] == 2  # One completed
        assert stats["by_type"]["type_b"] == 1


class TestHandlerRegistration:
    """Tests for handler registration."""

    def test_register_handler(self, service):
        """Test registering a job handler."""
        handler = MagicMock(return_value={"result": "success"})
        service.register_handler("custom_job", handler)

        assert "custom_job" in service._job_handlers
        assert service._job_handlers["custom_job"] == handler


class TestSingletonPattern:
    """Tests for singleton pattern."""

    def test_singleton_instance(self):
        """Test singleton returns same instance."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            # Reset global singleton
            import services.durable_job_queue_service as module
            module._durable_job_queue_service = None

            service1 = get_durable_job_queue_service(db_path)
            service2 = get_durable_job_queue_service(db_path)

            assert service1 is service2
        finally:
            os.unlink(db_path)


class TestReset:
    """Tests for reset functionality."""

    def test_reset_clears_state(self, service, sample_payload):
        """Test reset clears all state."""
        service.enqueue(job_type="task", payload=sample_payload)
        callback = MagicMock()
        service.set_callbacks(on_complete=callback)

        service.reset()

        assert len(service._job_handlers) == 0
        assert len(service._active_jobs) == 0
        assert service._on_job_complete is None

        # Database should be empty
        stats = service.get_queue_stats()
        assert stats["total_jobs"] == 0


class TestExactlyOnceProcessing:
    """Tests for exactly-once semantics."""

    def test_concurrent_claim_prevention(self, sample_payload):
        """Test only one worker can claim a job."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            db_path = f.name

        try:
            service1 = DurableJobQueueService(db_path=db_path)
            service2 = DurableJobQueueService(db_path=db_path)

            job = service1.enqueue(job_type="task", payload=sample_payload)

            # Both try to claim
            claimed1 = service1.claim_next_job()
            claimed2 = service2.claim_next_job()

            # Only one should succeed
            assert (claimed1 is not None) != (claimed2 is not None) or \
                   (claimed1 is None and claimed2 is None) or \
                   (claimed1.job_id != claimed2.job_id if claimed1 and claimed2 else True)
        finally:
            os.unlink(db_path)


class TestJobSerialization:
    """Tests for job serialization."""

    def test_job_to_dict_and_back(self, sample_payload):
        """Test job serialization round-trip."""
        job = DurableJob(
            job_id="test_123",
            job_type="workflow",
            payload=sample_payload,
            status=JobStatus.RUNNING,
            priority=JobPriority.HIGH,
            tags=["urgent", "customer"],
            metadata={"key": "value"},
        )

        data = job.to_dict()
        restored = DurableJob.from_dict(data)

        assert restored.job_id == job.job_id
        assert restored.job_type == job.job_type
        assert restored.payload == job.payload
        assert restored.status == job.status
        assert restored.priority == job.priority
        assert restored.tags == job.tags
        assert restored.metadata == job.metadata
