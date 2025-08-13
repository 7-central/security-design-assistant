"""
Centralized error handling utilities for Lambda functions.
Provides structured error handling, logging, and response formatting.
"""

import json
import logging
import time
import traceback
from typing import Any, Optional
from uuid import uuid4

from src.models.job import JobStatus

logger = logging.getLogger(__name__)

# Constants for error handling thresholds
DEFAULT_LAMBDA_TIMEOUT_BUFFER_SECONDS = 60
DEFAULT_MEMORY_THRESHOLD_PERCENT = 85.0
CRITICAL_MEMORY_THRESHOLD_PERCENT = 95.0
FALLBACK_LAMBDA_TIMEOUT_SECONDS = 900  # 15 minutes


class LambdaError(Exception):
    """Base class for Lambda-specific errors."""

    def __init__(self, message: str, error_code: str, details: Optional[dict[str, Any]] = None):
        super().__init__(message)
        self.message = message
        self.error_code = error_code
        self.details = details or {}
        self.timestamp = int(time.time())
        self.correlation_id = str(uuid4())


class TimeoutApproachingError(LambdaError):
    """Raised when Lambda timeout is approaching."""

    def __init__(self, remaining_time: float, message: Optional[str] = None):
        super().__init__(
            message or f"Lambda timeout approaching, {remaining_time:.1f}s remaining",
            "LAMBDA_TIMEOUT_APPROACHING",
            {"remaining_time": remaining_time}
        )


class MemoryExhaustedError(LambdaError):
    """Raised when Lambda memory is exhausted."""

    def __init__(self, current_usage: Optional[int] = None, limit: Optional[int] = None):
        super().__init__(
            f"Lambda memory exhausted (usage: {current_usage}MB, limit: {limit}MB)",
            "LAMBDA_MEMORY_EXHAUSTED",
            {"current_usage_mb": current_usage, "limit_mb": limit}
        )


class ProcessingStageError(LambdaError):
    """Raised when a processing stage fails."""

    def __init__(self, stage: str, original_error: Exception, job_id: str):
        super().__init__(
            f"Processing stage '{stage}' failed for job {job_id}: {original_error}",
            "PROCESSING_STAGE_FAILED",
            {
                "stage": stage,
                "job_id": job_id,
                "original_error": str(original_error),
                "original_error_type": type(original_error).__name__
            }
        )


def create_correlation_id(job_id: Optional[str] = None) -> str:
    """
    Create a correlation ID for request tracing.

    Args:
        job_id: Optional job ID to include in correlation ID

    Returns:
        Correlation ID string
    """
    timestamp = int(time.time())
    if job_id:
        return f"job_{job_id}_{timestamp}_{str(uuid4())[:8]}"
    return f"req_{timestamp}_{str(uuid4())[:8]}"


def log_structured_error(
    error: Exception,
    context: dict[str, Any],
    correlation_id: Optional[str] = None,
    job_id: Optional[str] = None
) -> None:
    """
    Log error with structured format for CloudWatch analysis.

    Args:
        error: Exception that occurred
        context: Additional context information
        correlation_id: Optional correlation ID for tracing
        job_id: Optional job ID
    """

    error_data = {
        "event_type": "error",
        "timestamp": int(time.time()),
        "correlation_id": correlation_id or create_correlation_id(job_id),
        "error": {
            "type": type(error).__name__,
            "message": str(error),
            "traceback": traceback.format_exc(),
        },
        "context": context
    }

    if job_id:
        error_data["job_id"] = job_id

    # Add Lambda-specific error details
    if isinstance(error, LambdaError):
        error_data["error"].update({
            "error_code": error.error_code,
            "details": error.details,
            "lambda_error": True
        })

    logger.error(json.dumps(error_data))


def check_lambda_timeout(
    context: Any,
    start_time: float,
    buffer_seconds: int = DEFAULT_LAMBDA_TIMEOUT_BUFFER_SECONDS,
    job_id: Optional[str] = None
) -> None:
    """
    Check if Lambda timeout is approaching and raise error if needed.

    Args:
        context: Lambda context object
        start_time: Processing start time
        buffer_seconds: Seconds to leave as buffer before timeout
        job_id: Optional job ID for logging

    Raises:
        TimeoutApproachingError: If timeout is approaching
    """

    if context:
        remaining_time = context.get_remaining_time_in_millis() / 1000
    else:
        # Fallback calculation
        elapsed_time = time.time() - start_time
        remaining_time = FALLBACK_LAMBDA_TIMEOUT_SECONDS - elapsed_time

    if remaining_time < buffer_seconds:
        correlation_id = create_correlation_id(job_id)

        log_structured_error(
            TimeoutApproachingError(remaining_time),
            {
                "remaining_time": remaining_time,
                "buffer_seconds": buffer_seconds,
                "elapsed_time": time.time() - start_time
            },
            correlation_id,
            job_id
        )

        raise TimeoutApproachingError(remaining_time)


def check_memory_usage(
    threshold_percent: float = DEFAULT_MEMORY_THRESHOLD_PERCENT,
    job_id: Optional[str] = None
) -> None:
    """
    Check Lambda memory usage and warn/error if threshold exceeded.

    Args:
        threshold_percent: Memory usage threshold percentage
        job_id: Optional job ID for logging

    Raises:
        MemoryExhaustedError: If memory usage exceeds threshold
    """

    try:
        import os

        import psutil

        # Get current memory usage
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        current_usage_mb = memory_info.rss / (1024 * 1024)

        # Get Lambda memory limit from environment
        memory_limit_mb = int(os.getenv('AWS_LAMBDA_FUNCTION_MEMORY_SIZE', '1024'))

        usage_percent = (current_usage_mb / memory_limit_mb) * 100

        if usage_percent >= threshold_percent:
            correlation_id = create_correlation_id(job_id)

            log_structured_error(
                MemoryExhaustedError(int(current_usage_mb), memory_limit_mb),
                {
                    "memory_usage_mb": current_usage_mb,
                    "memory_limit_mb": memory_limit_mb,
                    "usage_percent": usage_percent,
                    "threshold_percent": threshold_percent
                },
                correlation_id,
                job_id
            )

            if usage_percent >= CRITICAL_MEMORY_THRESHOLD_PERCENT:
                raise MemoryExhaustedError(int(current_usage_mb), memory_limit_mb)
            else:
                logger.warning(f"Memory usage high: {usage_percent:.1f}% of {memory_limit_mb}MB")

    except ImportError:
        # psutil not available, skip memory check
        logger.debug("psutil not available, skipping memory check")
    except Exception as e:
        logger.warning(f"Could not check memory usage: {e}")


async def handle_processing_stage(
    stage_name: str,
    stage_func: callable,
    job_id: str,
    storage,
    context: Any,
    start_time: float,
    *args,
    **kwargs
) -> Any:
    """
    Handle a processing stage with comprehensive error handling.

    Args:
        stage_name: Name of the processing stage
        stage_func: Function to execute for this stage
        job_id: Job ID for tracking
        storage: Storage interface
        context: Lambda context
        start_time: Processing start time
        *args: Arguments for stage function
        **kwargs: Keyword arguments for stage function

    Returns:
        Stage function result

    Raises:
        ProcessingStageError: If stage processing fails
    """

    correlation_id = create_correlation_id(job_id)

    try:
        # Check timeout before starting stage
        check_lambda_timeout(context, start_time, job_id=job_id)

        # Check memory usage
        check_memory_usage(job_id=job_id)

        # Update job status
        await update_job_stage_status(
            storage, job_id, stage_name, "in_progress", correlation_id
        )

        logger.info(json.dumps({
            "event_type": "stage_start",
            "timestamp": int(time.time()),
            "correlation_id": correlation_id,
            "job_id": job_id,
            "stage": stage_name
        }))

        # Execute stage function
        result = await stage_func(*args, **kwargs)

        # Update job status on success
        await update_job_stage_status(
            storage, job_id, stage_name, "completed", correlation_id
        )

        logger.info(json.dumps({
            "event_type": "stage_complete",
            "timestamp": int(time.time()),
            "correlation_id": correlation_id,
            "job_id": job_id,
            "stage": stage_name
        }))

        return result

    except Exception as e:
        # Log structured error
        log_structured_error(
            e,
            {
                "stage": stage_name,
                "job_id": job_id,
                "function_name": stage_func.__name__ if hasattr(stage_func, '__name__') else str(stage_func)
            },
            correlation_id,
            job_id
        )

        # Update job status on failure
        await update_job_stage_status(
            storage, job_id, stage_name, "failed", correlation_id, error=str(e)
        )

        # Wrap in ProcessingStageError
        raise ProcessingStageError(stage_name, e, job_id) from e


async def update_job_stage_status(
    storage,
    job_id: str,
    stage_name: str,
    stage_status: str,
    correlation_id: str,
    error: Optional[str] = None
) -> None:
    """
    Update job status with stage-based progress tracking.

    Args:
        storage: Storage interface
        job_id: Job ID
        stage_name: Name of the processing stage
        stage_status: Status of the stage (in_progress, completed, failed)
        correlation_id: Correlation ID for tracing
        error: Optional error message if stage failed
    """

    try:
        # Get current job data
        current_job = await storage.get_job_status(job_id)
        if not current_job:
            logger.warning(f"Job {job_id} not found when updating stage status")
            return

        # Update stage tracking
        stages_completed = current_job.get("stages_completed", [])
        current_stage = stage_name

        if stage_status == "completed" and stage_name not in stages_completed:
            stages_completed.append(stage_name)
            current_stage = None  # Clear current stage when completed

        # Prepare update data
        update_data = {
            "status": JobStatus.PROCESSING.value if stage_status != "failed" else JobStatus.FAILED.value,
            "updated_at": int(time.time()),
            "current_stage": current_stage,
            "stages_completed": stages_completed,
            "last_checkpoint": int(time.time()),
            "correlation_id": correlation_id
        }

        if error:
            update_data["error_details"] = {
                "stage": stage_name,
                "error": error,
                "timestamp": int(time.time())
            }

        # Update job data
        current_job.update(update_data)
        await storage.save_job_status(job_id, current_job)

        logger.info(f"Updated job {job_id} stage status: {stage_name} -> {stage_status}")

    except Exception as e:
        logger.error(f"Failed to update job stage status: {e}")


def create_api_error_response(
    status_code: int,
    message: str,
    error_code: Optional[str] = None,
    details: Optional[dict[str, Any]] = None,
    correlation_id: Optional[str] = None
) -> dict[str, Any]:
    """
    Create standardized API error response.

    Args:
        status_code: HTTP status code
        message: Error message
        error_code: Optional error code
        details: Optional additional details
        correlation_id: Optional correlation ID for tracing

    Returns:
        Formatted API Gateway response
    """

    error_response = {
        "error": message,
        "timestamp": int(time.time()),
        "correlation_id": correlation_id or create_correlation_id()
    }

    if error_code:
        error_response["error_code"] = error_code

    if details:
        error_response["details"] = details

    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
            'Access-Control-Allow-Methods': 'GET,POST,OPTIONS',
            'X-Correlation-ID': error_response["correlation_id"]
        },
        'body': json.dumps(error_response)
    }


def log_lambda_metrics(
    function_name: str,
    execution_time: float,
    memory_used: Optional[int] = None,
    success: bool = True,
    error_count: int = 0,
    job_id: Optional[str] = None
) -> None:
    """
    Log Lambda execution metrics for CloudWatch analysis.

    Args:
        function_name: Lambda function name
        execution_time: Execution time in seconds
        memory_used: Memory usage in MB
        success: Whether execution was successful
        error_count: Number of errors encountered
        job_id: Optional job ID
    """

    metrics_data = {
        "event_type": "lambda_metrics",
        "timestamp": int(time.time()),
        "function_name": function_name,
        "execution_time_seconds": execution_time,
        "success": success,
        "error_count": error_count
    }

    if memory_used:
        metrics_data["memory_used_mb"] = memory_used

    if job_id:
        metrics_data["job_id"] = job_id

    logger.info(json.dumps(metrics_data))
