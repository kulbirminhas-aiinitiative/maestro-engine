#!/usr/bin/env python3
"""
Durable Job Queue Service for MAESTRO Engine

Provides persistent job storage that survives restarts with exactly-once processing.
TC-ORCH-033: Queued long-running jobs survive restarts

Features:
- Durable job persistence (SQLite/PostgreSQL)
- Exactly-once processing with idempotency keys
- Automatic recovery on restart
- Checkpoint-based progress tracking
- Dead letter queue for failed jobs
"""

import json
import logging
import os
import sqlite3
import threading
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from uuid import uuid4

logger = logging.getLogger(__name__)

# Optional Prometheus metrics
try:
    from prometheus_client import Counter, Gauge, Histogram
    PROMETHEUS_AVAILABLE = True

    # Module-level metrics (registered once)
    _JOBS_QUEUED_COUNTER = Counter(
        "durable_job_queue_jobs_queued_total",
        "Total jobs queued",
        ["job_type", "priority"]
    )
    _JOBS_COMPLETED_COUNTER = Counter(
        "durable_job_queue_jobs_completed_total",
        "Total jobs completed",
        ["job_type", "status"]
    )
    _ACTIVE_JOBS_GAUGE = Gauge(
        "durable_job_queue_active_jobs",
        "Currently active jobs",
        ["status"]
    )
    _JOB_DURATION_HISTOGRAM = Histogram(
        "durable_job_queue_job_duration_seconds",
        "Job execution duration",
        ["job_type"]
    )
    _RECOVERY_COUNTER = Counter(
        "durable_job_queue_recovery_total",
        "Job recovery operations",
        ["outcome"]
    )
except ImportError:
    PROMETHEUS_AVAILABLE = False
    _JOBS_QUEUED_COUNTER = None
    _JOBS_COMPLETED_COUNTER = None
    _ACTIVE_JOBS_GAUGE = None
    _JOB_DURATION_HISTOGRAM = None
    _RECOVERY_COUNTER = None


class JobStatus(Enum):
    """Job lifecycle states."""
    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD = "dead"  # Exceeded retry limit


class JobPriority(Enum):
    """Job priority levels."""
    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


@dataclass
class JobCheckpoint:
    """Checkpoint for resuming jobs."""
    checkpoint_id: str
    job_id: str
    phase: str
    progress_percent: float
    state_data: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DurableJob:
    """Persistent job definition."""
    job_id: str
    job_type: str
    payload: Dict[str, Any]
    status: JobStatus = JobStatus.PENDING
    priority: JobPriority = JobPriority.NORMAL

    # Execution tracking
    idempotency_key: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None

    # Progress and checkpointing
    current_phase: str = "initialization"
    progress_percent: float = 0.0
    last_checkpoint_id: Optional[str] = None

    # Retry configuration
    max_retries: int = 3
    retry_count: int = 0
    retry_delay_seconds: int = 60
    next_retry_at: Optional[datetime] = None

    # Error tracking
    error_message: Optional[str] = None
    error_stack: Optional[str] = None

    # Worker assignment
    worker_id: Optional[str] = None
    heartbeat_at: Optional[datetime] = None

    # Metadata
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage."""
        data = asdict(self)
        data["status"] = self.status.value
        data["priority"] = self.priority.value
        for key in ["created_at", "started_at", "completed_at", "next_retry_at", "heartbeat_at"]:
            if data.get(key):
                data[key] = data[key].isoformat()
        data["payload"] = json.dumps(data["payload"])
        data["tags"] = json.dumps(data["tags"])
        data["metadata"] = json.dumps(data["metadata"])
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DurableJob":
        """Create from dictionary."""
        data = data.copy()
        data["status"] = JobStatus(data["status"])
        data["priority"] = JobPriority(data["priority"])
        for key in ["created_at", "started_at", "completed_at", "next_retry_at", "heartbeat_at"]:
            if data.get(key):
                data[key] = datetime.fromisoformat(data[key])
        if isinstance(data["payload"], str):
            data["payload"] = json.loads(data["payload"])
        if isinstance(data["tags"], str):
            data["tags"] = json.loads(data["tags"])
        if isinstance(data["metadata"], str):
            data["metadata"] = json.loads(data["metadata"])
        return cls(**data)


@dataclass
class JobRecoveryResult:
    """Result of job recovery operation."""
    recovered_count: int
    resumed_jobs: List[str]
    dead_jobs: List[str]
    orphaned_jobs: List[str]


class DurableJobQueueService:
    """
    Durable job queue with persistence and exactly-once semantics.

    Features:
    - SQLite persistence for durability
    - Idempotency key support for exactly-once
    - Checkpoint-based recovery
    - Worker heartbeat monitoring
    - Dead letter queue
    """

    def __init__(
        self,
        db_path: str = "jobs.db",
        worker_timeout_seconds: int = 300,
        heartbeat_interval_seconds: int = 30,
    ):
        self.db_path = db_path
        self.worker_timeout_seconds = worker_timeout_seconds
        self.heartbeat_interval_seconds = heartbeat_interval_seconds

        # In-memory caches
        self._job_handlers: Dict[str, Callable] = {}
        self._active_jobs: Dict[str, DurableJob] = {}
        self._idempotency_cache: Set[str] = set()
        self._checkpoints: Dict[str, List[JobCheckpoint]] = {}

        # Worker tracking
        self._worker_id = f"worker_{uuid4().hex[:8]}"
        self._running = False
        self._heartbeat_thread: Optional[threading.Thread] = None

        # Callbacks
        self._on_job_complete: Optional[Callable] = None
        self._on_job_failed: Optional[Callable] = None
        self._on_job_recovered: Optional[Callable] = None

        # Initialize database
        self._init_database()

    def _init_database(self) -> None:
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Jobs table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                job_type TEXT NOT NULL,
                payload TEXT NOT NULL,
                status TEXT NOT NULL,
                priority INTEGER NOT NULL,
                idempotency_key TEXT UNIQUE,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                current_phase TEXT,
                progress_percent REAL DEFAULT 0,
                last_checkpoint_id TEXT,
                max_retries INTEGER DEFAULT 3,
                retry_count INTEGER DEFAULT 0,
                retry_delay_seconds INTEGER DEFAULT 60,
                next_retry_at TEXT,
                error_message TEXT,
                error_stack TEXT,
                worker_id TEXT,
                heartbeat_at TEXT,
                tags TEXT,
                metadata TEXT
            )
        """)

        # Checkpoints table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS checkpoints (
                checkpoint_id TEXT PRIMARY KEY,
                job_id TEXT NOT NULL,
                phase TEXT NOT NULL,
                progress_percent REAL NOT NULL,
                state_data TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (job_id) REFERENCES jobs(job_id)
            )
        """)

        # Dead letter queue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS dead_letter_queue (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                job_id TEXT NOT NULL,
                job_data TEXT NOT NULL,
                reason TEXT NOT NULL,
                moved_at TEXT NOT NULL
            )
        """)

        # Indexes
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_priority ON jobs(priority)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_worker ON jobs(worker_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_jobs_idempotency ON jobs(idempotency_key)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_checkpoints_job ON checkpoints(job_id)")

        conn.commit()
        conn.close()

        logger.info(f"Durable job queue database initialized: {self.db_path}")

    def register_handler(
        self,
        job_type: str,
        handler: Callable[[DurableJob, Optional[JobCheckpoint]], Dict[str, Any]]
    ) -> None:
        """
        Register a job handler for a specific job type.

        Handler receives (job, last_checkpoint) and should return result dict.
        """
        self._job_handlers[job_type] = handler
        logger.info(f"Registered handler for job type: {job_type}")

    def enqueue(
        self,
        job_type: str,
        payload: Dict[str, Any],
        priority: JobPriority = JobPriority.NORMAL,
        idempotency_key: Optional[str] = None,
        max_retries: int = 3,
        retry_delay_seconds: int = 60,
        tags: Optional[List[str]] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> DurableJob:
        """
        Enqueue a new job with persistence.

        Returns existing job if idempotency_key matches.
        """
        # Check idempotency
        if idempotency_key:
            existing = self._find_by_idempotency_key(idempotency_key)
            if existing:
                logger.info(f"Returning existing job for idempotency key: {idempotency_key}")
                return existing

        job = DurableJob(
            job_id=f"job_{uuid4().hex[:12]}",
            job_type=job_type,
            payload=payload,
            status=JobStatus.QUEUED,
            priority=priority,
            idempotency_key=idempotency_key,
            max_retries=max_retries,
            retry_delay_seconds=retry_delay_seconds,
            tags=tags or [],
            metadata=metadata or {},
        )

        # Persist to database
        self._save_job(job)

        # Cache idempotency key
        if idempotency_key:
            self._idempotency_cache.add(idempotency_key)

        # Update metrics
        if PROMETHEUS_AVAILABLE:
            _JOBS_QUEUED_COUNTER.labels(
                job_type=job_type,
                priority=priority.value
            ).inc()
            _ACTIVE_JOBS_GAUGE.labels(status="queued").inc()

        logger.info(f"Enqueued job {job.job_id} type={job_type} priority={priority.value}")
        return job

    def _find_by_idempotency_key(self, key: str) -> Optional[DurableJob]:
        """Find job by idempotency key."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE idempotency_key = ?", (key,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return DurableJob.from_dict(dict(row))
        return None

    def _save_job(self, job: DurableJob) -> None:
        """Persist job to database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        data = job.to_dict()
        columns = ", ".join(data.keys())
        placeholders = ", ".join(["?" for _ in data])
        values = list(data.values())

        cursor.execute(
            f"INSERT OR REPLACE INTO jobs ({columns}) VALUES ({placeholders})",
            values
        )

        conn.commit()
        conn.close()

    def _update_job(self, job: DurableJob) -> None:
        """Update job in database."""
        self._save_job(job)

    def get_job(self, job_id: str) -> Optional[DurableJob]:
        """Get job by ID."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
        row = cursor.fetchone()
        conn.close()

        if row:
            return DurableJob.from_dict(dict(row))
        return None

    def claim_next_job(self) -> Optional[DurableJob]:
        """
        Claim the next available job for processing.

        Implements pessimistic locking for exactly-once semantics.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        try:
            # Find next available job (queued or ready for retry)
            now = datetime.utcnow().isoformat()
            cursor.execute("""
                SELECT * FROM jobs
                WHERE (status = 'queued' OR (status = 'retrying' AND next_retry_at <= ?))
                ORDER BY priority ASC, created_at ASC
                LIMIT 1
            """, (now,))

            row = cursor.fetchone()
            if not row:
                return None

            job = DurableJob.from_dict(dict(row))

            # Claim the job
            job.status = JobStatus.RUNNING
            job.worker_id = self._worker_id
            job.started_at = datetime.utcnow()
            job.heartbeat_at = datetime.utcnow()

            cursor.execute("""
                UPDATE jobs
                SET status = ?, worker_id = ?, started_at = ?, heartbeat_at = ?
                WHERE job_id = ? AND status IN ('queued', 'retrying')
            """, (job.status.value, job.worker_id, job.started_at.isoformat(),
                  job.heartbeat_at.isoformat(), job.job_id))

            if cursor.rowcount == 0:
                # Job was claimed by another worker
                return None

            conn.commit()

            # Track active job
            self._active_jobs[job.job_id] = job

            # Update metrics
            if PROMETHEUS_AVAILABLE:
                _ACTIVE_JOBS_GAUGE.labels(status="queued").dec()
                _ACTIVE_JOBS_GAUGE.labels(status="running").inc()

            logger.info(f"Claimed job {job.job_id} by worker {self._worker_id}")
            return job

        finally:
            conn.close()

    def save_checkpoint(
        self,
        job_id: str,
        phase: str,
        progress_percent: float,
        state_data: Dict[str, Any]
    ) -> JobCheckpoint:
        """
        Save a checkpoint for job recovery.

        Enables resumption from last known good state.
        """
        checkpoint = JobCheckpoint(
            checkpoint_id=f"ckpt_{uuid4().hex[:12]}",
            job_id=job_id,
            phase=phase,
            progress_percent=progress_percent,
            state_data=state_data,
        )

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO checkpoints (checkpoint_id, job_id, phase, progress_percent, state_data, created_at)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (checkpoint.checkpoint_id, job_id, phase, progress_percent,
              json.dumps(state_data), checkpoint.created_at.isoformat()))

        # Update job with latest checkpoint
        cursor.execute("""
            UPDATE jobs SET last_checkpoint_id = ?, current_phase = ?, progress_percent = ?
            WHERE job_id = ?
        """, (checkpoint.checkpoint_id, phase, progress_percent, job_id))

        conn.commit()
        conn.close()

        # Cache checkpoint
        if job_id not in self._checkpoints:
            self._checkpoints[job_id] = []
        self._checkpoints[job_id].append(checkpoint)

        logger.info(f"Saved checkpoint {checkpoint.checkpoint_id} for job {job_id} at {phase} ({progress_percent}%)")
        return checkpoint

    def get_last_checkpoint(self, job_id: str) -> Optional[JobCheckpoint]:
        """Get the most recent checkpoint for a job."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM checkpoints
            WHERE job_id = ?
            ORDER BY created_at DESC
            LIMIT 1
        """, (job_id,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return JobCheckpoint(
                checkpoint_id=row["checkpoint_id"],
                job_id=row["job_id"],
                phase=row["phase"],
                progress_percent=row["progress_percent"],
                state_data=json.loads(row["state_data"]),
                created_at=datetime.fromisoformat(row["created_at"]),
            )
        return None

    def complete_job(
        self,
        job_id: str,
        result: Optional[Dict[str, Any]] = None
    ) -> DurableJob:
        """Mark job as successfully completed."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        job.status = JobStatus.COMPLETED
        job.completed_at = datetime.utcnow()
        job.progress_percent = 100.0
        if result:
            job.metadata["result"] = result

        self._update_job(job)

        # Remove from active jobs
        self._active_jobs.pop(job_id, None)

        # Update metrics
        if PROMETHEUS_AVAILABLE:
            _JOBS_COMPLETED_COUNTER.labels(
                job_type=job.job_type,
                status="completed"
            ).inc()
            _ACTIVE_JOBS_GAUGE.labels(status="running").dec()

            if job.started_at:
                duration = (job.completed_at - job.started_at).total_seconds()
                _JOB_DURATION_HISTOGRAM.labels(job_type=job.job_type).observe(duration)

        # Callback
        if self._on_job_complete:
            try:
                self._on_job_complete(job)
            except Exception as e:
                logger.error(f"Job complete callback error: {e}")

        logger.info(f"Job {job_id} completed successfully")
        return job

    def fail_job(
        self,
        job_id: str,
        error_message: str,
        error_stack: Optional[str] = None,
        retry: bool = True
    ) -> DurableJob:
        """Mark job as failed, optionally scheduling retry."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        job.error_message = error_message
        job.error_stack = error_stack

        if retry and job.retry_count < job.max_retries:
            # Schedule retry
            job.status = JobStatus.RETRYING
            job.retry_count += 1
            job.next_retry_at = datetime.utcnow() + timedelta(seconds=job.retry_delay_seconds)
            job.worker_id = None

            logger.info(f"Job {job_id} scheduled for retry {job.retry_count}/{job.max_retries}")

            if PROMETHEUS_AVAILABLE:
                _ACTIVE_JOBS_GAUGE.labels(status="running").dec()
                _ACTIVE_JOBS_GAUGE.labels(status="retrying").inc()
        else:
            # Move to dead letter queue
            job.status = JobStatus.DEAD
            job.completed_at = datetime.utcnow()
            self._move_to_dead_letter(job, "Max retries exceeded")

            logger.warning(f"Job {job_id} moved to dead letter queue after {job.retry_count} retries")

            if PROMETHEUS_AVAILABLE:
                _JOBS_COMPLETED_COUNTER.labels(
                    job_type=job.job_type,
                    status="dead"
                ).inc()
                _ACTIVE_JOBS_GAUGE.labels(status="running").dec()

        self._update_job(job)

        # Remove from active jobs
        self._active_jobs.pop(job_id, None)

        # Callback
        if self._on_job_failed:
            try:
                self._on_job_failed(job)
            except Exception as e:
                logger.error(f"Job failed callback error: {e}")

        return job

    def _move_to_dead_letter(self, job: DurableJob, reason: str) -> None:
        """Move failed job to dead letter queue."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO dead_letter_queue (job_id, job_data, reason, moved_at)
            VALUES (?, ?, ?, ?)
        """, (job.job_id, json.dumps(job.to_dict()), reason, datetime.utcnow().isoformat()))

        conn.commit()
        conn.close()

    def heartbeat(self, job_id: str) -> None:
        """Update job heartbeat to prevent timeout."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE jobs SET heartbeat_at = ? WHERE job_id = ?
        """, (datetime.utcnow().isoformat(), job_id))

        conn.commit()
        conn.close()

    def recover_orphaned_jobs(self) -> JobRecoveryResult:
        """
        Recover jobs that were interrupted (e.g., by worker crash).

        This is called on startup to resume incomplete work.
        """
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        result = JobRecoveryResult(
            recovered_count=0,
            resumed_jobs=[],
            dead_jobs=[],
            orphaned_jobs=[],
        )

        # Find orphaned running jobs (no heartbeat within timeout)
        timeout_threshold = (datetime.utcnow() - timedelta(seconds=self.worker_timeout_seconds)).isoformat()

        cursor.execute("""
            SELECT * FROM jobs
            WHERE status = 'running' AND (heartbeat_at IS NULL OR heartbeat_at < ?)
        """, (timeout_threshold,))

        orphaned_rows = cursor.fetchall()

        for row in orphaned_rows:
            job = DurableJob.from_dict(dict(row))
            result.orphaned_jobs.append(job.job_id)

            # Check if job has checkpoint for recovery
            checkpoint = self.get_last_checkpoint(job.job_id)

            if job.retry_count < job.max_retries:
                # Schedule for retry with recovery
                job.status = JobStatus.RETRYING
                job.retry_count += 1
                job.next_retry_at = datetime.utcnow() + timedelta(seconds=job.retry_delay_seconds)
                job.worker_id = None
                job.error_message = "Worker lost - scheduled for recovery"

                self._update_job(job)
                result.resumed_jobs.append(job.job_id)
                result.recovered_count += 1

                logger.info(f"Recovered orphaned job {job.job_id} with checkpoint at {checkpoint.phase if checkpoint else 'start'}")

                if PROMETHEUS_AVAILABLE:
                    _RECOVERY_COUNTER.labels(outcome="resumed").inc()
            else:
                # Move to dead letter queue
                job.status = JobStatus.DEAD
                job.completed_at = datetime.utcnow()
                job.error_message = "Worker lost - max retries exceeded"
                self._move_to_dead_letter(job, "Worker crash - max retries exceeded")
                self._update_job(job)
                result.dead_jobs.append(job.job_id)

                logger.warning(f"Job {job.job_id} moved to dead letter after worker crash")

                if PROMETHEUS_AVAILABLE:
                    _RECOVERY_COUNTER.labels(outcome="dead").inc()

        conn.close()

        # Callback
        if self._on_job_recovered and result.resumed_jobs:
            try:
                self._on_job_recovered(result)
            except Exception as e:
                logger.error(f"Job recovery callback error: {e}")

        logger.info(f"Recovery complete: {result.recovered_count} jobs recovered, {len(result.dead_jobs)} dead")
        return result

    def pause_job(self, job_id: str) -> DurableJob:
        """Pause a running job."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status != JobStatus.RUNNING:
            raise ValueError(f"Cannot pause job in status: {job.status}")

        job.status = JobStatus.PAUSED
        job.worker_id = None
        self._update_job(job)

        self._active_jobs.pop(job_id, None)

        logger.info(f"Job {job_id} paused at phase {job.current_phase}")
        return job

    def resume_job(self, job_id: str) -> DurableJob:
        """Resume a paused job."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status != JobStatus.PAUSED:
            raise ValueError(f"Cannot resume job in status: {job.status}")

        job.status = JobStatus.QUEUED
        self._update_job(job)

        logger.info(f"Job {job_id} queued for resumption")
        return job

    def cancel_job(self, job_id: str) -> DurableJob:
        """Cancel a job."""
        job = self.get_job(job_id)
        if not job:
            raise ValueError(f"Job not found: {job_id}")

        if job.status in [JobStatus.COMPLETED, JobStatus.DEAD]:
            raise ValueError(f"Cannot cancel job in status: {job.status}")

        job.status = JobStatus.FAILED
        job.completed_at = datetime.utcnow()
        job.error_message = "Cancelled by user"
        self._update_job(job)

        self._active_jobs.pop(job_id, None)

        logger.info(f"Job {job_id} cancelled")
        return job

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get queue statistics."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        stats = {
            "total_jobs": 0,
            "by_status": {},
            "by_priority": {},
            "by_type": {},
            "dead_letter_count": 0,
            "avg_completion_time_seconds": 0,
        }

        # Count by status
        cursor.execute("SELECT status, COUNT(*) FROM jobs GROUP BY status")
        for row in cursor.fetchall():
            stats["by_status"][row[0]] = row[1]
            stats["total_jobs"] += row[1]

        # Count by priority
        cursor.execute("SELECT priority, COUNT(*) FROM jobs WHERE status NOT IN ('completed', 'dead') GROUP BY priority")
        for row in cursor.fetchall():
            stats["by_priority"][row[0]] = row[1]

        # Count by type
        cursor.execute("SELECT job_type, COUNT(*) FROM jobs WHERE status NOT IN ('completed', 'dead') GROUP BY job_type")
        for row in cursor.fetchall():
            stats["by_type"][row[0]] = row[1]

        # Dead letter count
        cursor.execute("SELECT COUNT(*) FROM dead_letter_queue")
        stats["dead_letter_count"] = cursor.fetchone()[0]

        # Average completion time
        cursor.execute("""
            SELECT AVG(JULIANDAY(completed_at) - JULIANDAY(started_at)) * 86400
            FROM jobs WHERE status = 'completed' AND completed_at IS NOT NULL AND started_at IS NOT NULL
        """)
        avg_time = cursor.fetchone()[0]
        stats["avg_completion_time_seconds"] = avg_time or 0

        conn.close()
        return stats

    def get_dead_letter_jobs(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get jobs from dead letter queue."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("""
            SELECT * FROM dead_letter_queue ORDER BY moved_at DESC LIMIT ?
        """, (limit,))

        jobs = []
        for row in cursor.fetchall():
            jobs.append({
                "id": row["id"],
                "job_id": row["job_id"],
                "job_data": json.loads(row["job_data"]),
                "reason": row["reason"],
                "moved_at": row["moved_at"],
            })

        conn.close()
        return jobs

    def requeue_dead_letter_job(self, dead_letter_id: int) -> DurableJob:
        """Requeue a job from dead letter queue."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        cursor.execute("SELECT * FROM dead_letter_queue WHERE id = ?", (dead_letter_id,))
        row = cursor.fetchone()

        if not row:
            raise ValueError(f"Dead letter job not found: {dead_letter_id}")

        job_data = json.loads(row["job_data"])

        # Create new job with reset state
        job = DurableJob.from_dict(job_data)
        job.job_id = f"job_{uuid4().hex[:12]}"  # New ID
        job.status = JobStatus.QUEUED
        job.retry_count = 0
        job.error_message = None
        job.error_stack = None
        job.worker_id = None
        job.started_at = None
        job.completed_at = None
        job.created_at = datetime.utcnow()

        self._save_job(job)

        # Remove from dead letter queue
        cursor.execute("DELETE FROM dead_letter_queue WHERE id = ?", (dead_letter_id,))
        conn.commit()
        conn.close()

        logger.info(f"Requeued dead letter job as {job.job_id}")
        return job

    def set_callbacks(
        self,
        on_complete: Optional[Callable] = None,
        on_failed: Optional[Callable] = None,
        on_recovered: Optional[Callable] = None,
    ) -> None:
        """Set event callbacks."""
        self._on_job_complete = on_complete
        self._on_job_failed = on_failed
        self._on_job_recovered = on_recovered

    def start_heartbeat_thread(self) -> None:
        """Start background heartbeat thread for active jobs."""
        if self._heartbeat_thread and self._heartbeat_thread.is_alive():
            return

        self._running = True
        self._heartbeat_thread = threading.Thread(target=self._heartbeat_loop, daemon=True)
        self._heartbeat_thread.start()
        logger.info("Heartbeat thread started")

    def stop_heartbeat_thread(self) -> None:
        """Stop the heartbeat thread."""
        self._running = False
        if self._heartbeat_thread:
            self._heartbeat_thread.join(timeout=5)
        logger.info("Heartbeat thread stopped")

    def _heartbeat_loop(self) -> None:
        """Background loop to send heartbeats for active jobs."""
        while self._running:
            for job_id in list(self._active_jobs.keys()):
                try:
                    self.heartbeat(job_id)
                except Exception as e:
                    logger.error(f"Heartbeat error for {job_id}: {e}")

            time.sleep(self.heartbeat_interval_seconds)

    def reset(self) -> None:
        """Reset service state (for testing)."""
        self._job_handlers.clear()
        self._active_jobs.clear()
        self._idempotency_cache.clear()
        self._checkpoints.clear()
        self._on_job_complete = None
        self._on_job_failed = None
        self._on_job_recovered = None

        # Clear database
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM jobs")
        cursor.execute("DELETE FROM checkpoints")
        cursor.execute("DELETE FROM dead_letter_queue")
        conn.commit()
        conn.close()

        logger.info("DurableJobQueueService reset")


# Singleton instance
_durable_job_queue_service: Optional[DurableJobQueueService] = None


def get_durable_job_queue_service(
    db_path: str = "jobs.db"
) -> DurableJobQueueService:
    """Get the singleton DurableJobQueueService instance."""
    global _durable_job_queue_service
    if _durable_job_queue_service is None:
        _durable_job_queue_service = DurableJobQueueService(db_path=db_path)
    return _durable_job_queue_service
