from celery import Celery, signals
from app.core.config import settings
from loguru import logger

celery_app = Celery(
    "marksheet_extraction",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.tasks.extraction_tasks", "app.tasks.batch_tasks"]
)

# Production-grade configuration
celery_app.conf.update(
    # Serialization
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    
    # Timezone
    timezone="UTC",
    enable_utc=True,
    
    # Task execution
    task_track_started=True,
    task_time_limit=300,  # Hard limit: 5 minutes
    task_soft_time_limit=240,  # Soft limit: 4 minutes
    task_acks_late=True,  # Acknowledge after task completion (reliability)
    task_reject_on_worker_lost=True,  # Requeue if worker crashes
    
    # Worker
    worker_prefetch_multiplier=1,  # Only fetch 1 task at a time (fair distribution)
    worker_max_tasks_per_child=50,  # Restart worker after 50 tasks (prevent memory leaks)
    worker_disable_rate_limits=False,
    worker_send_task_events=True,  # Enable monitoring
    
    # Results
    result_expires=3600,  # Results expire after 1 hour
    result_extended=True,  # Store task args/kwargs in result
    result_backend_transport_options={
        "master_name": "mymaster",
        "socket_keepalive": True,
        "retry_on_timeout": True,
        "health_check_interval": 10,
    },
    
    # Broker connection
    broker_connection_retry_on_startup=True,
    broker_connection_retry=True,
    broker_connection_max_retries=10,
    broker_transport_options={
        "visibility_timeout": 3600,  # 1 hour
        "socket_keepalive": True,
        "socket_timeout": 10,
        "retry_on_timeout": True,
    },
    
    # Monitoring
    task_send_sent_event=True,
    task_ignore_result=False,
)


# Celery signals for logging
@signals.task_prerun.connect
def task_prerun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, **extra):
    logger.info(f"Task started: {task.name}[{task_id}]")


@signals.task_postrun.connect
def task_postrun_handler(sender=None, task_id=None, task=None, args=None, kwargs=None, retval=None, state=None, **extra):
    logger.info(f"Task completed: {task.name}[{task_id}] - State: {state}")


@signals.task_failure.connect
def task_failure_handler(sender=None, task_id=None, exception=None, traceback=None, **extra):
    logger.error(f"Task failed: {sender.name}[{task_id}] - Exception: {exception}")
