#!/usr/bin/env python3
"""
Celery Configuration for MAESTRO Engine
Handles async workflow execution via RabbitMQ
"""

import os

from celery import Celery
from kombu import Exchange, Queue

# Celery app instance
# Using existing RabbitMQ container (maestro-templates-rabbitmq on port 5672)
celery_app = Celery(
    "maestro_workflows",
    broker="amqp://maestro_rabbit:changeme_rabbit_password@localhost:5672/%2Fmaestro_templates",  # RabbitMQ (URL-encoded vhost)
    backend="redis://localhost:6379/1",  # Redis for result storage
)

# Celery configuration
celery_app.conf.update(
    # Task settings
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Result backend settings
    result_backend="redis://localhost:6379/1",
    result_expires=3600 * 24,  # 24 hours
    result_persistent=True,
    # Task execution settings
    task_track_started=True,
    task_time_limit=3600 * 4,  # 4 hours max per task
    task_soft_time_limit=3600 * 3,  # 3 hours soft limit
    task_acks_late=True,  # Acknowledge after task completes
    task_reject_on_worker_lost=True,
    # Worker settings
    worker_prefetch_multiplier=1,  # Take one task at a time (long-running tasks)
    worker_max_tasks_per_child=10,  # Restart worker after 10 tasks (prevent memory leaks)
    worker_disable_rate_limits=True,
    # Broker settings
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    # Queue configuration
    task_default_queue="maestro_default",
    task_queues=(
        Queue("maestro_default", Exchange("maestro"), routing_key="maestro.default"),
        Queue("maestro_priority", Exchange("maestro"), routing_key="maestro.priority"),
        Queue("maestro_long_running", Exchange("maestro"), routing_key="maestro.long"),
    ),
    # Monitoring
    worker_send_task_events=True,
    task_send_sent_event=True,
)

# Task routes (which queue for which task)
celery_app.conf.task_routes = {
    "celery_tasks.execute_workflow_task": {
        "queue": "maestro_long_running",
        "routing_key": "maestro.long",
    },
}

# Redis client for status tracking
import redis

redis_client = redis.Redis(host="localhost", port=6379, db=0, decode_responses=True)


def get_redis_client():
    """Get Redis client for status tracking"""
    return redis_client
