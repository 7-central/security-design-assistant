"""
Dead Letter Queue (DLQ) processor Lambda function.
Handles failed processing jobs and sends alerts for critical failures.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any

import boto3
from botocore.exceptions import ClientError

from src.models.job import JobStatus
from src.utils.error_handlers import create_correlation_id, log_structured_error
from src.utils.storage_manager import StorageManager

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler for processing messages from the Dead Letter Queue.

    This function:
    1. Processes failed job messages from DLQ
    2. Updates job status to failed in DynamoDB
    3. Sends SNS alerts for critical failures
    4. Logs detailed failure analysis

    Args:
        event: Lambda event containing SQS DLQ messages
        context: Lambda context object

    Returns:
        Processing results
    """

    logger.info(f"DLQ Processor started with {len(event.get('Records', []))} messages")

    # Initialize storage and SNS
    storage = StorageManager.get_storage()
    sns_client = boto3.client('sns')

    processed_records = []

    for record in event.get('Records', []):
        try:
            # Parse SQS message from DLQ
            message_body = json.loads(record['body'])
            correlation_id = create_correlation_id()

            logger.info(f"Processing DLQ message: {correlation_id}")

            # Process the failed job
            result = await_sync(process_failed_job(
                storage, sns_client, message_body, record, correlation_id
            ))

            processed_records.append({
                'correlation_id': correlation_id,
                'job_id': result.get('job_id', 'unknown'),
                'status': 'processed',
                'action': result.get('action', 'logged')
            })

        except Exception as e:
            logger.error(f"Error processing DLQ record: {e}", exc_info=True)
            processed_records.append({
                'status': 'error',
                'error': str(e)
            })

    return {
        'statusCode': 200,
        'body': json.dumps({
            'processed_records': len(processed_records),
            'results': processed_records
        })
    }


async def process_failed_job(
    storage,
    sns_client: boto3.client,
    message_body: dict[str, Any],
    sqs_record: dict[str, Any],
    correlation_id: str
) -> dict[str, Any]:
    """
    Process a single failed job from the DLQ.

    Args:
        storage: Storage interface
        sns_client: SNS client for alerts
        message_body: Original SQS message body
        sqs_record: SQS record metadata
        correlation_id: Correlation ID for tracing

    Returns:
        Processing results
    """

    job_id = message_body.get('job_id', 'unknown')
    company_client_job = message_body.get('company_client_job', f'unknown#{job_id}')

    try:
        # Analyze failure details
        failure_analysis = analyze_failure(sqs_record, message_body)

        # Update job status to failed
        await update_failed_job_status(storage, job_id, failure_analysis, correlation_id)

        # Determine if this is a critical failure requiring alert
        if is_critical_failure(failure_analysis):
            await send_critical_failure_alert(sns_client, job_id, failure_analysis, correlation_id)
            action = 'alerted'
        else:
            action = 'logged'

        # Log detailed failure information
        log_structured_error(
            Exception(f"Job failed after DLQ processing: {failure_analysis['error_summary']}"),
            {
                "job_id": job_id,
                "company_client_job": company_client_job,
                "failure_analysis": failure_analysis,
                "sqs_metadata": {
                    "approximate_receive_count": sqs_record.get('attributes', {}).get('ApproximateReceiveCount'),
                    "sent_timestamp": sqs_record.get('attributes', {}).get('SentTimestamp'),
                    "approximate_first_receive_timestamp": sqs_record.get('attributes', {}).get('ApproximateFirstReceiveTimestamp')
                }
            },
            correlation_id,
            job_id
        )

        logger.info(f"Processed failed job {job_id} with action: {action}")

        return {
            'job_id': job_id,
            'action': action,
            'failure_type': failure_analysis['failure_type'],
            'error_summary': failure_analysis['error_summary']
        }

    except Exception as e:
        logger.error(f"Error processing failed job {job_id}: {e}")
        raise


def analyze_failure(sqs_record: dict[str, Any], message_body: dict[str, Any]) -> dict[str, Any]:
    """
    Analyze failure details from SQS record and message body.

    Args:
        sqs_record: SQS record metadata
        message_body: Original message body

    Returns:
        Failure analysis dictionary
    """

    attributes = sqs_record.get('attributes', {})

    # Calculate failure timing
    sent_timestamp = int(attributes.get('SentTimestamp', '0')) / 1000
    first_receive_timestamp = int(attributes.get('ApproximateFirstReceiveTimestamp', '0')) / 1000

    processing_duration = first_receive_timestamp - sent_timestamp if first_receive_timestamp > 0 else 0

    # Determine failure type based on patterns
    receive_count = int(attributes.get('ApproximateReceiveCount', '0'))
    failure_type = classify_failure_type(receive_count, processing_duration, message_body)

    return {
        'timestamp': int(time.time()),
        'failure_type': failure_type,
        'receive_count': receive_count,
        'processing_duration_seconds': processing_duration,
        'sent_timestamp': sent_timestamp,
        'first_receive_timestamp': first_receive_timestamp,
        'error_summary': generate_error_summary(failure_type, receive_count, processing_duration),
        'message_attributes': sqs_record.get('messageAttributes', {}),
        'original_message': message_body
    }


def classify_failure_type(
    receive_count: int,
    processing_duration: float,
    message_body: dict[str, Any]
) -> str:
    """
    Classify the type of failure based on available data.

    Args:
        receive_count: Number of times message was received
        processing_duration: Time between send and first receive
        message_body: Original message body

    Returns:
        Failure type classification
    """

    # Timeout-related failure
    if processing_duration > 870:  # Close to 15-minute Lambda timeout
        return 'lambda_timeout'

    # Rate limit failure (inferred from timing patterns)
    if 300 <= processing_duration <= 600:  # 5-10 minute range suggests rate limiting
        return 'rate_limit_exhausted'

    # Memory/resource failure
    if receive_count >= 3 and processing_duration < 60:
        return 'resource_exhausted'

    # Infrastructure failure
    if receive_count == 1 and processing_duration < 30:
        return 'infrastructure_failure'

    # PDF/input processing failure (check message content)
    client_name = message_body.get('client_name', '').lower()
    if 'test' in client_name or 'sample' in client_name:
        return 'input_validation_failure'

    # Default classification
    if receive_count >= 3:
        return 'processing_failure'
    else:
        return 'temporary_failure'


def generate_error_summary(failure_type: str, receive_count: int, duration: float) -> str:
    """Generate human-readable error summary."""

    summaries = {
        'lambda_timeout': f'Job exceeded Lambda timeout limit ({duration:.1f}s processing)',
        'rate_limit_exhausted': f'Gemini API rate limit exhausted after {receive_count} attempts',
        'resource_exhausted': f'Lambda resource limits exceeded ({receive_count} failures in {duration:.1f}s)',
        'infrastructure_failure': f'AWS infrastructure failure (immediate failure after {duration:.1f}s)',
        'input_validation_failure': f'Invalid input data caused {receive_count} processing failures',
        'processing_failure': f'Persistent processing failure after {receive_count} attempts',
        'temporary_failure': f'Temporary failure, {receive_count} attempts over {duration:.1f}s'
    }

    return summaries.get(failure_type, f'Unknown failure type after {receive_count} attempts')


def is_critical_failure(failure_analysis: dict[str, Any]) -> bool:
    """
    Determine if failure requires immediate alert.

    Args:
        failure_analysis: Failure analysis data

    Returns:
        True if critical failure requiring alert
    """

    critical_failure_types = {
        'infrastructure_failure',
        'resource_exhausted',
        'rate_limit_exhausted'
    }

    # Critical if specific failure type
    if failure_analysis['failure_type'] in critical_failure_types:
        return True

    # Critical if high frequency failures
    if failure_analysis['receive_count'] >= 3:
        return True

    # Critical if system-wide issues (can be enhanced with pattern detection)
    return False


async def update_failed_job_status(
    storage,
    job_id: str,
    failure_analysis: dict[str, Any],
    correlation_id: str
) -> None:
    """
    Update job status to failed with detailed failure information.

    Args:
        storage: Storage interface
        job_id: Job ID
        failure_analysis: Failure analysis data
        correlation_id: Correlation ID for tracing
    """

    try:
        # Get current job data
        current_job = await storage.get_job_status(job_id)
        if not current_job:
            logger.warning(f"Job {job_id} not found when updating failed status")
            return

        # Update job with failure details
        failed_data = {
            "status": JobStatus.FAILED.value,
            "updated_at": int(time.time()),
            "failed_at": int(time.time()),
            "failure_details": failure_analysis,
            "correlation_id": correlation_id,
            "dlq_processed": True
        }

        # Preserve existing stages data
        if "stages_completed" in current_job:
            failed_data["stages_completed"] = current_job["stages_completed"]
        if "current_stage" in current_job:
            failed_data["failed_stage"] = current_job["current_stage"]
            failed_data["current_stage"] = None  # Clear current stage

        current_job.update(failed_data)
        await storage.save_job_status(job_id, current_job)

        logger.info(f"Updated job {job_id} status to failed with DLQ analysis")

    except Exception as e:
        logger.error(f"Failed to update job status for {job_id}: {e}")


async def send_critical_failure_alert(
    sns_client: boto3.client,
    job_id: str,
    failure_analysis: dict[str, Any],
    correlation_id: str
) -> None:
    """
    Send SNS alert for critical failures.

    Args:
        sns_client: SNS client
        job_id: Job ID
        failure_analysis: Failure analysis data
        correlation_id: Correlation ID for tracing
    """

    import os

    topic_arn = os.getenv('SNS_ALERT_TOPIC_ARN')
    if not topic_arn:
        logger.warning("SNS_ALERT_TOPIC_ARN not configured, skipping alert")
        return

    try:
        # Create alert message
        alert_data = {
            "alert_type": "critical_job_failure",
            "timestamp": int(time.time()),
            "correlation_id": correlation_id,
            "job_id": job_id,
            "failure_type": failure_analysis['failure_type'],
            "error_summary": failure_analysis['error_summary'],
            "receive_count": failure_analysis['receive_count'],
            "processing_duration": failure_analysis['processing_duration_seconds']
        }

        # Create human-readable message
        subject = f"Security Design Assistant - Critical Job Failure: {job_id}"
        message = f"""
Critical job failure detected:

Job ID: {job_id}
Failure Type: {failure_analysis['failure_type']}
Error Summary: {failure_analysis['error_summary']}
Attempts: {failure_analysis['receive_count']}
Duration: {failure_analysis['processing_duration_seconds']:.1f}s
Correlation ID: {correlation_id}
Timestamp: {datetime.fromtimestamp(alert_data['timestamp']).isoformat()}

This failure has been automatically processed and logged.
Check CloudWatch logs for detailed information.
"""

        # Send SNS notification
        response = sns_client.publish(
            TopicArn=topic_arn,
            Subject=subject,
            Message=message,
            MessageAttributes={
                'alert_type': {
                    'DataType': 'String',
                    'StringValue': 'critical_job_failure'
                },
                'job_id': {
                    'DataType': 'String',
                    'StringValue': job_id
                },
                'failure_type': {
                    'DataType': 'String',
                    'StringValue': failure_analysis['failure_type']
                },
                'correlation_id': {
                    'DataType': 'String',
                    'StringValue': correlation_id
                }
            }
        )

        logger.info(f"Sent critical failure alert for job {job_id}: {response['MessageId']}")

    except ClientError as e:
        logger.error(f"Failed to send SNS alert for job {job_id}: {e}")
    except Exception as e:
        logger.error(f"Error sending critical failure alert: {e}")


def await_sync(coro):
    """
    Helper function to run async code in sync context.
    This is needed because Lambda handlers are sync by default.
    """
    import asyncio

    try:
        # Get the current event loop if it exists
        loop = asyncio.get_running_loop()
        # If we're already in an async context, we shouldn't be here
        # This would indicate a design issue
        raise RuntimeError("await_sync called from within async context")
    except RuntimeError:
        # No running loop, which is expected for Lambda handlers
        return asyncio.run(coro)
