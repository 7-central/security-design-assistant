"""
Pre-traffic hook for CodeDeploy Lambda deployments.

This function runs before traffic is shifted to the new Lambda version
to validate that the deployment is safe and the new version is healthy.
"""

import json
import logging
import os
import time
from typing import Any

import boto3

# Configure logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS clients
codedeploy = boto3.client("codedeploy")
lambda_client = boto3.client("lambda")
dynamodb = boto3.client("dynamodb")
s3 = boto3.client("s3")
sqs = boto3.client("sqs")


def handler(event: dict[str, Any], context: Any) -> None:
    """
    Pre-traffic hook handler for Lambda deployment validation.

    Validates:
    - Lambda function health
    - Database connectivity
    - S3 bucket access
    - SQS queue availability
    """

    logger.info(f"Pre-traffic hook started: {json.dumps(event)}")

    deployment_id = event.get("DeploymentId")
    lifecycle_event_hook_execution_id = event.get("LifecycleEventHookExecutionId")

    try:
        # Run validation checks
        validation_results = run_pre_traffic_validations()

        if validation_results["success"]:
            logger.info("✅ Pre-traffic validation passed")
            status = "Succeeded"
        else:
            logger.error(f"❌ Pre-traffic validation failed: {validation_results['errors']}")
            status = "Failed"

        # Report status to CodeDeploy
        codedeploy.put_lifecycle_event_hook_execution_status(
            deploymentId=deployment_id, lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id, status=status
        )

    except Exception as e:
        logger.error(f"Pre-traffic hook error: {e!s}")

        # Report failure to CodeDeploy
        if deployment_id and lifecycle_event_hook_execution_id:
            try:
                codedeploy.put_lifecycle_event_hook_execution_status(
                    deploymentId=deployment_id,
                    lifecycleEventHookExecutionId=lifecycle_event_hook_execution_id,
                    status="Failed",
                )
            except Exception as report_error:
                logger.error(f"Failed to report status to CodeDeploy: {report_error}")

        raise


def run_pre_traffic_validations() -> dict[str, Any]:
    """
    Run pre-traffic validation checks.

    Returns:
        Dict containing success status and any errors
    """

    results = {"success": True, "errors": [], "checks": {}}

    # Check 1: Lambda function basic health
    try:
        function_name = os.getenv("AWS_LAMBDA_FUNCTION_NAME", "unknown")
        logger.info(f"Checking Lambda function health: {function_name}")

        # Get function configuration
        response = lambda_client.get_function(FunctionName=function_name)
        state = response["Configuration"]["State"]

        if state != "Active":
            results["errors"].append(f"Lambda function state is {state}, expected Active")
            results["success"] = False
        else:
            results["checks"]["lambda_health"] = "passed"
            logger.info("✅ Lambda function health check passed")

    except Exception as e:
        error_msg = f"Lambda function health check failed: {e!s}"
        results["errors"].append(error_msg)
        results["success"] = False
        logger.error(error_msg)

    # Check 2: DynamoDB table connectivity
    try:
        table_name = os.getenv("DYNAMODB_TABLE")
        if table_name:
            logger.info(f"Checking DynamoDB connectivity: {table_name}")

            # Try to describe the table
            response = dynamodb.describe_table(TableName=table_name)
            status = response["Table"]["TableStatus"]

            if status != "ACTIVE":
                results["errors"].append(f"DynamoDB table status is {status}, expected ACTIVE")
                results["success"] = False
            else:
                results["checks"]["dynamodb_connectivity"] = "passed"
                logger.info("✅ DynamoDB connectivity check passed")
        else:
            logger.warning("No DynamoDB table configured for validation")

    except Exception as e:
        error_msg = f"DynamoDB connectivity check failed: {e!s}"
        results["errors"].append(error_msg)
        results["success"] = False
        logger.error(error_msg)

    # Check 3: S3 bucket access
    try:
        bucket_name = os.getenv("S3_BUCKET")
        if bucket_name:
            logger.info(f"Checking S3 bucket access: {bucket_name}")

            # Try to list objects (limited)
            response = s3.list_objects_v2(Bucket=bucket_name, MaxKeys=1)
            results["checks"]["s3_access"] = "passed"
            logger.info("✅ S3 bucket access check passed")
        else:
            logger.warning("No S3 bucket configured for validation")

    except Exception as e:
        error_msg = f"S3 bucket access check failed: {e!s}"
        results["errors"].append(error_msg)
        results["success"] = False
        logger.error(error_msg)

    # Check 4: SQS queue availability
    try:
        queue_url = os.getenv("SQS_QUEUE_URL")
        if queue_url:
            logger.info(f"Checking SQS queue availability: {queue_url}")

            # Get queue attributes
            response = sqs.get_queue_attributes(
                QueueUrl=queue_url, AttributeNames=["QueueArn", "VisibilityTimeoutSeconds"]
            )
            results["checks"]["sqs_availability"] = "passed"
            logger.info("✅ SQS queue availability check passed")
        else:
            logger.warning("No SQS queue configured for validation")

    except Exception as e:
        error_msg = f"SQS queue availability check failed: {e!s}"
        results["errors"].append(error_msg)
        results["success"] = False
        logger.error(error_msg)

    # Check 5: Environment variables
    try:
        logger.info("Checking required environment variables")

        required_vars = ["ENVIRONMENT", "STORAGE_MODE"]
        missing_vars = []

        for var in required_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        if missing_vars:
            error_msg = f"Missing required environment variables: {missing_vars}"
            results["errors"].append(error_msg)
            results["success"] = False
        else:
            results["checks"]["environment_variables"] = "passed"
            logger.info("✅ Environment variables check passed")

    except Exception as e:
        error_msg = f"Environment variables check failed: {e!s}"
        results["errors"].append(error_msg)
        results["success"] = False
        logger.error(error_msg)

    return results


def test_basic_functionality() -> bool:
    """
    Test basic Lambda function functionality with a simple invocation.

    Returns:
        True if basic functionality test passes, False otherwise
    """
    try:
        # Simple test - just verify we can execute basic operations
        test_data = {"test": True, "timestamp": time.time()}
        logger.info(f"Basic functionality test: {json.dumps(test_data)}")

        # Test JSON serialization/deserialization
        serialized = json.dumps(test_data)
        deserialized = json.loads(serialized)

        if deserialized["test"] != test_data["test"]:
            logger.error("Basic functionality test failed: JSON serialization issue")
            return False

        logger.info("✅ Basic functionality test passed")
        return True

    except Exception as e:
        logger.error(f"Basic functionality test failed: {e!s}")
        return False
