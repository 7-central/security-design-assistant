import json
import logging
import os
import time
from datetime import UTC
from typing import Any

from src.utils.cloudwatch_metrics import get_metrics_client
from src.utils.error_handlers import (
    create_api_error_response,
    create_correlation_id,
    log_lambda_metrics,
    log_structured_error,
)
from src.utils.storage_manager import StorageManager

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler for getting job status.

    This function:
    1. Checks if this is a warmer request and handles it early
    2. Extracts job_id from path parameters
    3. Queries DynamoDB for job status and progress information
    4. Returns structured response per REST API spec
    5. Includes download URLs for completed files

    Args:
        event: Lambda event containing API Gateway request
        context: Lambda context object

    Returns:
        API Gateway response with job status
    """
    # Check for warmer request early to minimize cold start impact
    from src.lambda_functions.lambda_warmer import check_and_handle_warmer
    if check_and_handle_warmer(event):
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Function warmed successfully', 'warmer': True})
        }

    # Track execution metrics
    start_time = time.time()
    function_name = context.function_name if context else "get_job_status"
    correlation_id = create_correlation_id()

    # Log structured request start
    logger.info(json.dumps({
        "event_type": "status_request",
        "timestamp": int(time.time()),
        "correlation_id": correlation_id,
        "function_name": function_name,
        "http_method": event.get('httpMethod'),
        "path": event.get('path')
    }))

    try:
        # Parse request from API Gateway
        if event.get('httpMethod') != 'GET':
            return create_api_error_response(405, "Method not allowed", correlation_id=correlation_id)

        # Extract job_id from path parameters
        path_parameters = event.get('pathParameters', {})
        if not path_parameters or 'job_id' not in path_parameters:
            return create_api_error_response(400, "Missing job_id in path", correlation_id=correlation_id)

        job_id = path_parameters['job_id']

        if not job_id:
            return create_api_error_response(400, "job_id cannot be empty", correlation_id=correlation_id)

        # Update correlation ID with job ID
        correlation_id = create_correlation_id(job_id)

        # Initialize storage
        storage = StorageManager.get_storage()

        # Get job status from storage
        job_data = await_sync(storage.get_job_status(job_id))

        if not job_data:
            logger.info(json.dumps({
                "event_type": "job_not_found",
                "timestamp": int(time.time()),
                "correlation_id": correlation_id,
                "job_id": job_id
            }))
            return create_api_error_response(404, f"Job {job_id} not found", correlation_id=correlation_id)

        # Build response with all relevant information
        response = {
            "job_id": job_id,
            "status": job_data.get("status", "unknown"),
            "created_at": format_timestamp(job_data.get("created_at")),
            "updated_at": format_timestamp(job_data.get("updated_at")),
            "processing_time_seconds": job_data.get("total_processing_time_seconds"),
            "metadata": job_data.get("metadata", {}),
            "current_stage": job_data.get("current_stage"),
            "stages_completed": job_data.get("stages_completed", [])
        }

        # Add progress information based on current stage
        status = job_data.get("status", "unknown").lower()
        current_stage = job_data.get("current_stage")
        stages_completed = job_data.get("stages_completed", [])

        if status == "queued":
            response["progress"] = {
                "percentage": 0,
                "current_step": "Waiting in queue",
                "estimated_time_remaining_seconds": 300
            }
        elif status == "processing":
            # Calculate progress based on completed stages
            total_stages = ["pdf_processing", "context_processing", "component_extraction", "excel_generation", "evaluation"]
            completed_count = len(stages_completed)
            progress_percentage = min(90, (completed_count / len(total_stages)) * 100)  # Cap at 90% until complete

            stage_names = {
                "pdf_processing": "Processing PDF",
                "context_processing": "Processing context",
                "component_extraction": "Extracting components",
                "excel_generation": "Generating Excel file",
                "evaluation": "Running quality evaluation"
            }

            current_step = stage_names.get(current_stage, f"Processing ({current_stage})")

            response["progress"] = {
                "percentage": int(progress_percentage),
                "current_step": current_step,
                "stages_completed": stages_completed,
                "estimated_time_remaining_seconds": max(30, 300 - (completed_count * 60))
            }
        elif status == "completed":
            response["progress"] = {
                "percentage": 100,
                "current_step": "Completed",
                "stages_completed": stages_completed
            }
        elif status == "failed":
            response["progress"] = {
                "percentage": 0,
                "current_step": "Failed",
                "error": job_data.get("error", "Processing failed")
            }

        # Add file information and download URLs if available
        processing_results = job_data.get("processing_results", {})
        excel_generation = processing_results.get("excel_generation", {})

        response["files"] = {}

        # Excel file
        excel_file_path = None
        if excel_generation.get("completed"):
            excel_file_path = excel_generation.get("file_path")
        elif job_data.get("metadata", {}).get("excel_file_path"):
            # Legacy path for backward compatibility
            excel_file_path = job_data["metadata"]["excel_file_path"]

        if excel_file_path:
            # Generate presigned URL for download
            download_url = await_sync(storage.generate_presigned_url(excel_file_path, expiration=3600))
            response["files"]["excel"] = {
                "type": "excel",
                "filename": f"schedule_{job_id}.xlsx",
                "download_url": download_url,
                "description": "Generated security schedule"
            }

        # Components JSON (always available if schedule agent completed)
        schedule_results = processing_results.get("schedule_agent", {})
        if schedule_results and schedule_results.get("completed"):
            components = schedule_results.get("components", {})
            if components:
                response["files"]["components"] = {
                    "type": "json",
                    "filename": f"components_{job_id}.json",
                    "data": components,  # Include inline for JSON
                    "description": "Extracted security components"
                }

        # Original drawing file (for reference)
        input_files = job_data.get("input_files", {})
        if input_files.get("drawing"):
            drawing_url = await_sync(storage.generate_presigned_url(input_files["drawing"], expiration=3600))
            response["files"]["drawing"] = {
                "type": "pdf",
                "filename": job_data.get("metadata", {}).get("file_name", "drawing.pdf"),
                "download_url": drawing_url,
                "description": "Original drawing file"
            }

        # Add summary information
        if status == "completed":
            flattened_components = schedule_results.get("flattened_components", [])
            response["summary"] = {
                "total_components_found": len(flattened_components),
                "processing_time_seconds": job_data.get("total_processing_time_seconds"),
                "excel_generated": excel_generation.get("completed", False)
            }

            # Add Excel generation summary if available
            if excel_generation.get("summary"):
                response["summary"]["excel_summary"] = excel_generation["summary"]

        # Add evaluation results if available
        evaluation = processing_results.get("evaluation")
        if evaluation and isinstance(evaluation, dict):
            response["evaluation"] = {
                "overall_assessment": evaluation.get("overall_assessment"),
                "completeness": evaluation.get("completeness"),
                "correctness": evaluation.get("correctness"),
                "improvement_suggestions": evaluation.get("improvement_suggestions", [])
            }

        # Add error information if failed
        if status == "failed":
            response["error"] = {
                "message": job_data.get("error", "Processing failed"),
                "failed_at": format_timestamp(job_data.get("failed_at")),
                "stage": current_stage or "unknown"
            }

        # Add timeout information if detected
        if job_data.get("timeout_detected"):
            response["timeout_info"] = {
                "detected": True,
                "message": "Processing was interrupted due to Lambda timeout",
                "can_resume": status == "processing"  # Could implement resume functionality
            }

        # Add correlation ID to response
        response["correlation_id"] = correlation_id

        # Log successful status response
        execution_time = time.time() - start_time
        logger.info(json.dumps({
            "event_type": "status_response_success",
            "timestamp": int(time.time()),
            "correlation_id": correlation_id,
            "job_id": job_id,
            "job_status": status,
            "status_code": 200,
            "execution_time_seconds": execution_time,
            "has_files": len(response.get("files", {})) > 0
        }))

        # Log execution metrics
        log_lambda_metrics(
            function_name,
            execution_time,
            success=True,
            job_id=job_id
        )

        # Track API metrics
        metrics = get_metrics_client(os.getenv('ENVIRONMENT', 'dev'))
        response_body = json.dumps(response, indent=2)
        response_size = len(response_body.encode('utf-8'))

        metrics.track_api_metrics(
            endpoint=f"/status/{job_id}",
            method="GET",
            status_code=200,
            response_time=execution_time,
            response_size_bytes=response_size
        )

        # Determine cache headers based on job status
        from src.utils.env_cache import get_cache_headers
        cache_headers = {}

        if status in ['completed', 'failed']:
            # Cache completed/failed jobs for longer (1 hour)
            cache_headers = get_cache_headers(max_age=3600)
        elif status in ['processing', 'queued']:
            # Cache in-progress jobs for shorter time (1 minute)
            cache_headers = get_cache_headers(max_age=60)

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                **cache_headers,
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
                'Access-Control-Allow-Methods': 'GET,OPTIONS',
                'X-Correlation-ID': correlation_id
            },
            'body': json.dumps(response, indent=2)
        }

    except Exception as e:
        execution_time = time.time() - start_time

        log_structured_error(
            e,
            {
                "function_name": function_name,
                "execution_time": execution_time,
                "event": event
            },
            correlation_id
        )

        log_lambda_metrics(
            function_name,
            execution_time,
            success=False,
            error_count=1
        )

        return create_api_error_response(500, "Internal server error", correlation_id=correlation_id)


def format_timestamp(timestamp) -> str:
    """
    Format timestamp for API response.

    Args:
        timestamp: Unix timestamp (int/float) or ISO string

    Returns:
        ISO formatted timestamp string or None
    """
    if not timestamp:
        return None

    if isinstance(timestamp, (int, float)):
        from datetime import datetime
        return datetime.fromtimestamp(timestamp, UTC).isoformat()

    return str(timestamp)  # Assume already formatted


def create_error_response(status_code: int, message: str) -> dict[str, Any]:
    """Create an error response for API Gateway."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
            'Access-Control-Allow-Methods': 'GET,OPTIONS'
        },
        'body': json.dumps({
            'error': message
        })
    }


def await_sync(coro):
    """
    Helper function to run async code in sync context.
    This is needed because Lambda handlers are sync by default.
    """
    import asyncio

    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create a new one
        return asyncio.run(coro)
