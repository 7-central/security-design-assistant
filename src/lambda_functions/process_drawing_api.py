import json
import logging
import os
import time
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.config.settings import settings
from src.models.job import JobStatus
from src.utils.id_generator import generate_job_id
from src.utils.storage_manager import StorageManager
from src.utils.validators import validate_file_size, validate_pdf_file
from src.utils.error_handlers import (
    create_correlation_id,
    log_structured_error,
    log_lambda_metrics,
    create_api_error_response
)
from src.utils.cloudwatch_metrics import get_metrics_client

# Configure structured logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler for processing drawing upload requests.

    This function:
    1. Validates the uploaded PDF file
    2. Generates a job ID and saves initial status to DynamoDB
    3. Sends a message to SQS for async processing
    4. Returns job_id and status immediately

    Args:
        event: Lambda event containing API Gateway request
        context: Lambda context object

    Returns:
        API Gateway response with job_id and status
    """
    # Track execution metrics
    start_time = time.time()
    function_name = context.function_name if context else "process_drawing_api"
    correlation_id = create_correlation_id()
    
    # Log structured request start
    logger.info(json.dumps({
        "event_type": "api_request",
        "timestamp": int(time.time()),
        "correlation_id": correlation_id,
        "function_name": function_name,
        "http_method": event.get('httpMethod'),
        "path": event.get('path'),
        "source_ip": event.get('requestContext', {}).get('identity', {}).get('sourceIp')
    }))

    try:
        # Parse request from API Gateway
        if event.get('httpMethod') != 'POST':
            return create_api_error_response(405, "Method not allowed", correlation_id=correlation_id)

        # Parse multipart form data
        request_data = parse_multipart_request(event)

        if 'error' in request_data:
            return create_api_error_response(400, request_data['error'], correlation_id=correlation_id)

        drawing_file = request_data.get('drawing_file')
        client_name = request_data.get('client_name')
        project_name = request_data.get('project_name')
        context_file = request_data.get('context_file')
        context_text = request_data.get('context_text')

        # Validate required fields
        if not drawing_file:
            return create_api_error_response(400, "No drawing file provided", correlation_id=correlation_id)

        if not client_name or not project_name:
            return create_api_error_response(400, "client_name and project_name are required", correlation_id=correlation_id)

        # Validate file size
        file_content = drawing_file['content']
        file_size = len(file_content)

        size_valid, size_error = validate_file_size(file_size, MAX_FILE_SIZE)
        if not size_valid:
            if "exceeds" in size_error:
                return create_api_error_response(413, size_error, correlation_id=correlation_id)
            else:
                return create_api_error_response(400, size_error, correlation_id=correlation_id)

        # Validate PDF file
        pdf_valid, pdf_error = validate_pdf_file(file_content)
        if not pdf_valid:
            return create_api_error_response(422, pdf_error, correlation_id=correlation_id)

        # Generate job ID
        job_id = generate_job_id()
        correlation_id = create_correlation_id(job_id)  # Update correlation ID with job ID

        # Log structured job creation
        logger.info(json.dumps({
            "event_type": "job_created",
            "timestamp": int(time.time()),
            "correlation_id": correlation_id,
            "job_id": job_id,
            "client_name": client_name,
            "project_name": project_name,
            "file_size_mb": round(file_size / (1024 * 1024), 2),
            "has_context": bool(context_file or context_text)
        }))

        # Create composite key for multi-tenant structure
        company_client_job = f"7central#{client_name}#{job_id}"

        # Initialize storage
        storage = StorageManager.get_storage()

        # Save files to storage
        file_name = drawing_file['filename']
        drawing_s3_key = f"7central/{client_name}/{project_name}/{job_id}/{file_name}"

        # Save drawing file
        drawing_metadata = {
            "job_id": job_id,
            "client_name": client_name,
            "project_name": project_name,
            "file_type": "drawing",
            "original_filename": file_name,
            "content_type": "application/pdf",
            "file_size": file_size,
            "uploaded_at": datetime.utcnow().isoformat()
        }

        drawing_s3_path = await_sync(storage.save_file(
            drawing_s3_key,
            file_content,
            drawing_metadata
        ))

        # Save context file if provided
        context_s3_key = None
        if context_file:
            context_filename = context_file['filename']
            context_s3_key = f"7central/{client_name}/{project_name}/{job_id}/{context_filename}"

            context_metadata = {
                "job_id": job_id,
                "client_name": client_name,
                "project_name": project_name,
                "file_type": "context",
                "original_filename": context_filename,
                "content_type": context_file.get('content_type', 'text/plain'),
                "file_size": len(context_file['content']),
                "uploaded_at": datetime.utcnow().isoformat()
            }

            await_sync(storage.save_file(
                context_s3_key,
                context_file['content'],
                context_metadata
            ))

        # Create job record
        created_at = int(time.time())
        job_data = {
            "company_client_job": company_client_job,
            "job_id": job_id,
            "status": JobStatus.QUEUED.value,
            "client_name": client_name,
            "project_name": project_name,
            "created_at": created_at,
            "updated_at": created_at,
            "input_files": {
                "drawing": drawing_s3_key,
                "context": context_s3_key
            },
            "metadata": {
                "client_name": client_name,
                "project_name": project_name,
                "file_name": file_name,
                "file_size_mb": round(file_size / (1024 * 1024), 2)
            },
            "stages_completed": [],
            "current_stage": None,
            "output_files": {},
            # Add TTL for 30 days
            "ttl": created_at + (30 * 24 * 60 * 60)
        }

        # Save initial job status to DynamoDB
        await_sync(storage.save_job_status(job_id, job_data))

        # Prepare SQS message
        sqs_message = {
            "job_id": job_id,
            "company_client_job": company_client_job,
            "drawing_s3_key": drawing_s3_key,
            "context_s3_key": context_s3_key,
            "context_text": context_text,
            "pipeline_config": "full_analysis",
            "client_name": client_name,
            "project_name": project_name,
            "created_at": created_at
        }

        # Send message to SQS queue
        queue_url = settings.SQS_QUEUE_URL
        if not queue_url:
            log_structured_error(
                Exception("SQS_QUEUE_URL environment variable not set"),
                {"configuration_error": "missing_sqs_queue_url"},
                correlation_id,
                job_id
            )
            return create_api_error_response(500, "Queue configuration error", correlation_id=correlation_id)

        try:
            # Initialize SQS client here to avoid module-level initialization
            sqs_client = boto3.client('sqs')
            response = sqs_client.send_message(
                QueueUrl=queue_url,
                MessageBody=json.dumps(sqs_message),
                MessageAttributes={
                    'job_id': {
                        'StringValue': job_id,
                        'DataType': 'String'
                    },
                    'client_name': {
                        'StringValue': client_name,
                        'DataType': 'String'
                    }
                }
            )

            # Log structured SQS success
            logger.info(json.dumps({
                "event_type": "sqs_message_sent",
                "timestamp": int(time.time()),
                "correlation_id": correlation_id,
                "job_id": job_id,
                "sqs_message_id": response['MessageId'],
                "queue_url": queue_url
            }))

        except ClientError as e:
            log_structured_error(
                e,
                {
                    "operation": "sqs_send_message",
                    "queue_url": queue_url,
                    "job_id": job_id
                },
                correlation_id,
                job_id
            )
            return create_api_error_response(500, "Failed to queue processing job", correlation_id=correlation_id)

        # Return immediate response
        response_data = {
            "job_id": job_id,
            "status": JobStatus.QUEUED.value,
            "estimated_time_seconds": 300,
            "message": "Job queued for processing",
            "correlation_id": correlation_id
        }

        # Log successful API response
        execution_time = time.time() - start_time
        logger.info(json.dumps({
            "event_type": "api_response_success",
            "timestamp": int(time.time()),
            "correlation_id": correlation_id,
            "job_id": job_id,
            "status_code": 202,
            "execution_time_seconds": execution_time
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
        request_size = len(json.dumps(event).encode('utf-8')) if event else 0
        response_size = len(json.dumps(response_data).encode('utf-8'))
        
        metrics.track_api_metrics(
            endpoint="/process-drawing",
            method="POST",
            status_code=202,
            response_time=execution_time,
            request_size_bytes=request_size,
            response_size_bytes=response_size
        )

        return {
            'statusCode': 202,  # Accepted
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
                'Access-Control-Allow-Methods': 'POST,OPTIONS',
                'X-Correlation-ID': correlation_id
            },
            'body': json.dumps(response_data)
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


def parse_multipart_request(event: dict[str, Any]) -> dict[str, Any]:
    """
    Parse multipart/form-data from API Gateway event.

    Args:
        event: API Gateway event

    Returns:
        Parsed form data or error message
    """
    try:
        # Get content type and boundary
        content_type = event.get('headers', {}).get('content-type', '').lower()
        if not content_type.startswith('multipart/form-data'):
            return {"error": "Content-Type must be multipart/form-data"}

        # Extract boundary
        boundary_parts = content_type.split('boundary=')
        if len(boundary_parts) != 2:
            return {"error": "Missing boundary in Content-Type header"}

        boundary = boundary_parts[1]

        # Get body (base64 decode if needed)
        body = event.get('body', '')
        is_base64 = event.get('isBase64Encoded', False)

        if is_base64:
            import base64
            body = base64.b64decode(body).decode('utf-8')

        # Simple multipart parser (this is a basic implementation)
        # In production, you might want to use a proper multipart parser
        parts = body.split(f'--{boundary}')

        result = {}

        for part in parts:
            if not part.strip() or part.strip() == '--':
                continue

            # Split headers and content
            if '\r\n\r\n' in part:
                headers_section, content = part.split('\r\n\r\n', 1)
            elif '\n\n' in part:
                headers_section, content = part.split('\n\n', 1)
            else:
                continue

            # Parse headers
            headers = {}
            for header_line in headers_section.strip().split('\n'):
                if ':' in header_line:
                    key, value = header_line.split(':', 1)
                    headers[key.strip().lower()] = value.strip()

            # Extract field name from Content-Disposition
            content_disposition = headers.get('content-disposition', '')
            if 'name=' in content_disposition:
                # Extract field name
                name_part = content_disposition.split('name=')[1]
                if name_part.startswith('"') and '"' in name_part[1:]:
                    field_name = name_part[1:name_part.index('"', 1)]
                else:
                    field_name = name_part.split(';')[0].strip()

                # Check if it's a file field
                if 'filename=' in content_disposition:
                    # Extract filename
                    filename_part = content_disposition.split('filename=')[1]
                    if filename_part.startswith('"') and '"' in filename_part[1:]:
                        filename = filename_part[1:filename_part.index('"', 1)]
                    else:
                        filename = filename_part.strip()

                    # File field
                    result[field_name] = {
                        'filename': filename,
                        'content_type': headers.get('content-type', 'application/octet-stream'),
                        'content': content.rstrip('\r\n--').encode('latin1')  # Binary content
                    }
                else:
                    # Text field
                    result[field_name] = content.rstrip('\r\n--')

        return result

    except Exception as e:
        logger.error(f"Error parsing multipart request: {e}")
        return {"error": f"Failed to parse multipart data: {e!s}"}


def create_error_response(status_code: int, message: str) -> dict[str, Any]:
    """Create an error response for API Gateway."""
    return {
        'statusCode': status_code,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type,X-Amz-Date,Authorization,X-Api-Key',
            'Access-Control-Allow-Methods': 'POST,OPTIONS'
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
