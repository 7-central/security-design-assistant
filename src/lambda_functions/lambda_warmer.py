"""
Lambda warmer function to keep functions warm and reduce cold starts.
"""

import json
import logging
import os
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    Lambda warmer function to invoke critical functions and keep them warm.

    Args:
        event: EventBridge scheduled event
        context: Lambda context

    Returns:
        Warmer execution results
    """
    logger.info("Lambda warmer starting execution")

    try:
        # Get environment-specific function names
        environment = os.getenv('ENVIRONMENT', 'dev')
        functions_to_warm = [
            f'security-assistant-api-{environment}',
            f'security-assistant-status-{environment}'
        ]

        # Don't warm the worker function as it should scale based on SQS messages
        # Don't warm DLQ processor as it only runs on failures

        lambda_client = boto3.client('lambda')
        results = []

        for function_name in functions_to_warm:
            try:
                result = warm_function(lambda_client, function_name)
                results.append(result)
                logger.info(f"Successfully warmed {function_name}")

            except Exception as e:
                error_result = {
                    'function_name': function_name,
                    'status': 'error',
                    'error': str(e)
                }
                results.append(error_result)
                logger.error(f"Failed to warm {function_name}: {e}")

        # Summary statistics
        successful_warms = sum(1 for r in results if r['status'] == 'success')
        total_functions = len(functions_to_warm)

        response = {
            'statusCode': 200,
            'body': json.dumps({
                'warmer_execution': 'completed',
                'total_functions': total_functions,
                'successful_warms': successful_warms,
                'failed_warms': total_functions - successful_warms,
                'results': results
            })
        }

        logger.info(f"Warmer completed: {successful_warms}/{total_functions} functions warmed successfully")
        return response

    except Exception as e:
        logger.error(f"Lambda warmer execution failed: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Lambda warmer execution failed',
                'details': str(e)
            })
        }


def warm_function(lambda_client: Any, function_name: str) -> dict[str, Any]:
    """
    Warm a specific Lambda function by invoking it with a warmer payload.

    Args:
        lambda_client: Boto3 Lambda client
        function_name: Name of the function to warm

    Returns:
        Warming result
    """
    import uuid

    # Create warmer payload
    warmer_payload = {
        'warmer': True,
        'source': 'lambda-warmer',
        'function_name': function_name,
        'timestamp': str(uuid.uuid4())
    }

    try:
        # Invoke the function asynchronously to avoid blocking
        response = lambda_client.invoke(
            FunctionName=function_name,
            InvocationType='Event',  # Async invocation
            Payload=json.dumps(warmer_payload)
        )

        result = {
            'function_name': function_name,
            'status': 'success',
            'status_code': response['StatusCode'],
            'request_id': response['ResponseMetadata']['RequestId']
        }

        return result

    except ClientError as e:
        raise Exception(f"AWS error warming function {function_name}: {e}")
    except Exception as e:
        raise Exception(f"Unexpected error warming function {function_name}: {e}")


def is_warmer_request(event: dict[str, Any]) -> bool:
    """
    Check if an incoming Lambda event is a warmer request.

    Args:
        event: Lambda event payload

    Returns:
        True if this is a warmer request
    """
    return (
        isinstance(event, dict) and
        event.get('warmer') is True and
        event.get('source') == 'lambda-warmer'
    )


def handle_warmer_request(event: dict[str, Any]) -> dict[str, Any]:
    """
    Handle a warmer request by returning immediately with success.

    Args:
        event: Warmer event payload

    Returns:
        Warmer response
    """
    function_name = event.get('function_name', 'unknown')
    logger.info(f"Handling warmer request for {function_name}")

    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': f'Function {function_name} warmed successfully',
            'warmer': True,
            'timestamp': event.get('timestamp', 'unknown')
        })
    }


# Helper function for other Lambda functions to use
def check_and_handle_warmer(event: dict[str, Any]) -> bool:
    """
    Check if event is a warmer request and handle it.

    Args:
        event: Lambda event

    Returns:
        True if this was a warmer request (caller should return immediately)
    """
    if is_warmer_request(event):
        handle_warmer_request(event)
        return True
    return False
