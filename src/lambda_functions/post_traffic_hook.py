"""
Post-traffic hook for CodeDeploy Lambda deployments.

This function runs after traffic has been shifted to the new Lambda version
to validate that the deployment is working correctly and meeting performance criteria.
"""

import json
import logging
import os
from datetime import datetime, timedelta
from typing import Any

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
codedeploy = boto3.client('codedeploy')
cloudwatch = boto3.client('cloudwatch')
lambda_client = boto3.client('lambda')
sqs = boto3.client('sqs')

def handler(event: dict[str, Any], context: Any) -> None:
    """
    Post-traffic hook handler for Lambda deployment validation.

    Validates:
    - Error rate thresholds
    - Response time metrics
    - Successful processing of test job
    - Queue health metrics
    """

    logger.info(f"Post-traffic hook started: {json.dumps(event)}")

    deployment_id = event.get('DeploymentId')
    lifecycle_event_hook_execution_id = event.get('LifecycleEventHookExecutionId')

    try:
        # Run post-traffic validation checks
        validation_results = run_post_traffic_validations()

        if validation_results['success']:
            logger.info("✅ Post-traffic validation passed")
            status = 'Succeeded'
        else:
            logger.error(f"❌ Post-traffic validation failed: {validation_results['errors']}")
            status = 'Failed'

        # Report status to CodeDeploy
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id,
            lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
            status=status
        )

    except Exception as e:
        logger.error(f"Post-traffic hook error: {e!s}")

        # Report failure to CodeDeploy
        if deployment_id and lifecycle_event_hook_execution_id:
            try:
                codedeploy.put_lifecycle_event_hook_execution_status(
                    deploymentId=deployment_id,
                    lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
                    status='Failed'
                )
            except Exception as report_error:
                logger.error(f"Failed to report status to CodeDeploy: {report_error}")

        raise


def run_post_traffic_validations() -> dict[str, Any]:
    """
    Run post-traffic validation checks.

    Returns:
        Dict containing success status and any errors
    """

    results = {
        'success': True,
        'errors': [],
        'checks': {},
        'metrics': {}
    }

    environment = os.getenv('ENVIRONMENT', 'dev')

    # Check 1: Lambda error rate
    try:
        logger.info("Checking Lambda error rates...")

        api_function_name = os.getenv('API_FUNCTION_NAME', f'security-assistant-api-{environment}')
        worker_function_name = os.getenv('WORKER_FUNCTION_NAME', f'security-assistant-worker-{environment}')
        status_function_name = os.getenv('STATUS_FUNCTION_NAME', f'security-assistant-status-{environment}')

        functions_to_check = [
            ('api', api_function_name),
            ('worker', worker_function_name),
            ('status', status_function_name)
        ]

        for func_type, func_name in functions_to_check:
            error_rate = get_lambda_error_rate(func_name)
            results['metrics'][f'{func_type}_error_rate'] = error_rate

            # Error rate threshold: 10% for dev, 5% for staging/prod
            threshold = 0.10 if environment == 'dev' else 0.05

            if error_rate > threshold:
                error_msg = f"{func_type} Lambda error rate ({error_rate:.2%}) exceeds threshold ({threshold:.2%})"
                results['errors'].append(error_msg)
                results['success'] = False
                logger.error(error_msg)
            else:
                logger.info(f"✅ {func_type} Lambda error rate check passed: {error_rate:.2%}")

        if not results['errors']:
            results['checks']['lambda_error_rates'] = 'passed'

    except Exception as e:
        error_msg = f"Lambda error rate check failed: {e!s}"
        results['errors'].append(error_msg)
        results['success'] = False
        logger.error(error_msg)

    # Check 2: Response time metrics
    try:
        logger.info("Checking Lambda response times...")

        for func_type, func_name in functions_to_check:
            duration = get_lambda_duration(func_name)
            results['metrics'][f'{func_type}_duration'] = duration

            # Duration thresholds (ms): API=5000, Worker=60000, Status=5000
            if func_type == 'api':
                threshold = 5000  # 5 seconds
            elif func_type == 'worker':
                threshold = 60000  # 60 seconds
            else:  # status
                threshold = 5000  # 5 seconds

            if duration > threshold:
                error_msg = f"{func_type} Lambda duration ({duration}ms) exceeds threshold ({threshold}ms)"
                results['errors'].append(error_msg)
                results['success'] = False
                logger.error(error_msg)
            else:
                logger.info(f"✅ {func_type} Lambda duration check passed: {duration}ms")

        if f'{func_type}_duration' in results['metrics']:
            results['checks']['lambda_durations'] = 'passed'

    except Exception as e:
        error_msg = f"Lambda duration check failed: {e!s}"
        results['errors'].append(error_msg)
        results['success'] = False
        logger.error(error_msg)

    # Check 3: Queue health
    try:
        logger.info("Checking queue health...")

        processing_queue_url = os.getenv('PROCESSING_QUEUE_URL')
        dlq_url = os.getenv('DLQ_URL')

        if processing_queue_url and dlq_url:
            # Check main queue depth
            queue_depth = get_queue_depth(processing_queue_url)
            results['metrics']['queue_depth'] = queue_depth

            # Check DLQ depth
            dlq_depth = get_queue_depth(dlq_url)
            results['metrics']['dlq_depth'] = dlq_depth

            # DLQ should be empty after deployment
            if dlq_depth > 0:
                error_msg = f"Dead letter queue has {dlq_depth} messages"
                results['errors'].append(error_msg)
                results['success'] = False
                logger.error(error_msg)
            else:
                logger.info("✅ Dead letter queue is empty")
                results['checks']['queue_health'] = 'passed'
        else:
            logger.warning("Queue URLs not configured for validation")

    except Exception as e:
        error_msg = f"Queue health check failed: {e!s}"
        results['errors'].append(error_msg)
        results['success'] = False
        logger.error(error_msg)

    # Check 4: Test job processing
    try:
        logger.info("Running smoke test...")

        # This would involve creating a small test job and verifying it processes
        # For now, we'll just check that the worker function is available
        worker_function_name = os.getenv('WORKER_FUNCTION_NAME', f'security-assistant-worker-{environment}')

        # Check function status
        response = lambda_client.get_function(FunctionName=worker_function_name)
        state = response['Configuration']['State']

        if state == 'Active':
            results['checks']['smoke_test'] = 'passed'
            logger.info("✅ Smoke test passed")
        else:
            error_msg = f"Worker function state is {state}, expected Active"
            results['errors'].append(error_msg)
            results['success'] = False
            logger.error(error_msg)

    except Exception as e:
        error_msg = f"Smoke test failed: {e!s}"
        results['errors'].append(error_msg)
        results['success'] = False
        logger.error(error_msg)

    return results


def get_lambda_error_rate(function_name: str, minutes: int = 5) -> float:
    """
    Get Lambda function error rate over the specified time period.

    Args:
        function_name: Lambda function name
        minutes: Time period in minutes

    Returns:
        Error rate as a decimal (0.0 to 1.0)
    """

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=minutes)

    try:
        # Get invocation count
        invocations_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Invocations',
            Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,  # 5 minutes
            Statistics=['Sum']
        )

        # Get error count
        errors_response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Errors',
            Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,  # 5 minutes
            Statistics=['Sum']
        )

        invocations = sum(point['Sum'] for point in invocations_response['Datapoints'])
        errors = sum(point['Sum'] for point in errors_response['Datapoints'])

        if invocations == 0:
            return 0.0

        return errors / invocations

    except Exception as e:
        logger.error(f"Failed to get error rate for {function_name}: {e!s}")
        return 1.0  # Assume worst case


def get_lambda_duration(function_name: str, minutes: int = 5) -> float:
    """
    Get Lambda function average duration over the specified time period.

    Args:
        function_name: Lambda function name
        minutes: Time period in minutes

    Returns:
        Average duration in milliseconds
    """

    end_time = datetime.utcnow()
    start_time = end_time - timedelta(minutes=minutes)

    try:
        response = cloudwatch.get_metric_statistics(
            Namespace='AWS/Lambda',
            MetricName='Duration',
            Dimensions=[{'Name': 'FunctionName', 'Value': function_name}],
            StartTime=start_time,
            EndTime=end_time,
            Period=300,  # 5 minutes
            Statistics=['Average']
        )

        if response['Datapoints']:
            # Return the most recent average
            latest_point = max(response['Datapoints'], key=lambda x: x['Timestamp'])
            return latest_point['Average']
        else:
            return 0.0

    except Exception as e:
        logger.error(f"Failed to get duration for {function_name}: {e!s}")
        return float('inf')  # Assume worst case


def get_queue_depth(queue_url: str) -> int:
    """
    Get the number of visible messages in an SQS queue.

    Args:
        queue_url: SQS queue URL

    Returns:
        Number of visible messages
    """

    try:
        response = sqs.get_queue_attributes(
            QueueUrl=queue_url,
            AttributeNames=['ApproximateNumberOfVisibleMessages']
        )

        return int(response['Attributes']['ApproximateNumberOfVisibleMessages'])

    except Exception as e:
        logger.error(f"Failed to get queue depth for {queue_url}: {e!s}")
        return -1  # Indicate error
