"""
Custom CloudWatch metrics collection utility.
Provides structured metrics tracking for security-assistant services.
"""

import json
import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Union

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)

# Constants for metrics namespacing and dimensions
METRICS_NAMESPACE = "SecurityAssistant"
LAMBDA_METRICS_NAMESPACE = "SecurityAssistant/Lambda"
PIPELINE_METRICS_NAMESPACE = "SecurityAssistant/Pipeline"
API_METRICS_NAMESPACE = "SecurityAssistant/API"
TOKEN_METRICS_NAMESPACE = "SecurityAssistant/TokenUsage"

# Cost tracking constants (Gemini API pricing per 1M tokens)
GEMINI_FLASH_COST_PER_MILLION = 0.075  # $0.075 per 1M tokens
GEMINI_PRO_COST_PER_MILLION = 2.50    # $2.50 per 1M tokens


class CloudWatchMetrics:
    """
    CloudWatch custom metrics collector for security-assistant services.
    
    Provides methods to track:
    - Job processing duration by pipeline stage
    - Gemini API token usage and estimated costs
    - Success/failure rates for each processing stage
    - Lambda function performance metrics
    - API Gateway request metrics
    """

    def __init__(self, environment: str = "dev"):
        """
        Initialize CloudWatch metrics client.
        
        Args:
            environment: Environment name (dev, staging, prod)
        """
        self.environment = environment
        self.cloudwatch = boto3.client('cloudwatch')
        
    def _create_dimensions(self, **dimensions) -> List[Dict[str, str]]:
        """
        Create CloudWatch dimensions with environment.
        
        Args:
            **dimensions: Key-value pairs for additional dimensions
            
        Returns:
            List of dimension dictionaries
        """
        dims = [{'Name': 'Environment', 'Value': self.environment}]
        for name, value in dimensions.items():
            if value is not None:
                dims.append({'Name': name, 'Value': str(value)})
        return dims
        
    def _put_metric_data(
        self,
        namespace: str,
        metrics: List[Dict[str, Any]]
    ) -> bool:
        """
        Send metrics data to CloudWatch.
        
        Args:
            namespace: CloudWatch metrics namespace
            metrics: List of metric data dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # CloudWatch accepts max 20 metrics per call
            for i in range(0, len(metrics), 20):
                batch = metrics[i:i+20]
                self.cloudwatch.put_metric_data(
                    Namespace=namespace,
                    MetricData=batch
                )
                
            logger.debug(f"Published {len(metrics)} metrics to {namespace}")
            return True
            
        except ClientError as e:
            logger.error(f"Failed to publish metrics to CloudWatch: {e}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error publishing metrics: {e}")
            return False

    def track_job_processing_duration(
        self,
        job_id: str,
        stage_name: str,
        duration_seconds: float,
        status: str = "completed",
        client_name: Optional[str] = None,
        project_name: Optional[str] = None
    ) -> bool:
        """
        Track job processing duration by pipeline stage.
        
        Args:
            job_id: Unique job identifier
            stage_name: Pipeline stage name (pdf_processing, context_processing, etc.)
            duration_seconds: Processing duration in seconds
            status: Stage completion status (completed, failed, timeout)
            client_name: Optional client name for segmentation
            project_name: Optional project name for segmentation
            
        Returns:
            True if metric was published successfully
        """
        dimensions = self._create_dimensions(
            Stage=stage_name,
            Status=status,
            Client=client_name,
            Project=project_name
        )
        
        metrics = [
            {
                'MetricName': 'ProcessingDuration',
                'Value': duration_seconds,
                'Unit': 'Seconds',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'StageCompletion',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            }
        ]
        
        # Log structured metric data
        logger.info(json.dumps({
            "event_type": "custom_metric",
            "metric_type": "processing_duration",
            "job_id": job_id,
            "stage_name": stage_name,
            "duration_seconds": duration_seconds,
            "status": status,
            "timestamp": int(time.time())
        }))
        
        return self._put_metric_data(PIPELINE_METRICS_NAMESPACE, metrics)

    def track_gemini_token_usage(
        self,
        job_id: str,
        model_name: str,
        input_tokens: int,
        output_tokens: int,
        operation: str,
        estimated_cost: Optional[float] = None
    ) -> bool:
        """
        Track Gemini API token usage and estimated costs.
        
        Args:
            job_id: Unique job identifier
            model_name: Gemini model name (flash, pro)
            input_tokens: Number of input tokens consumed
            output_tokens: Number of output tokens generated
            operation: Operation type (pdf_analysis, excel_generation, etc.)
            estimated_cost: Pre-calculated cost estimate
            
        Returns:
            True if metric was published successfully
        """
        total_tokens = input_tokens + output_tokens
        
        # Calculate estimated cost if not provided
        if estimated_cost is None:
            if "flash" in model_name.lower():
                estimated_cost = (total_tokens / 1_000_000) * GEMINI_FLASH_COST_PER_MILLION
            elif "pro" in model_name.lower():
                estimated_cost = (total_tokens / 1_000_000) * GEMINI_PRO_COST_PER_MILLION
            else:
                # Default to flash pricing
                estimated_cost = (total_tokens / 1_000_000) * GEMINI_FLASH_COST_PER_MILLION
        
        dimensions = self._create_dimensions(
            Model=model_name,
            Operation=operation
        )
        
        metrics = [
            {
                'MetricName': 'InputTokens',
                'Value': input_tokens,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'OutputTokens',
                'Value': output_tokens,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'TotalTokens',
                'Value': total_tokens,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'EstimatedCost',
                'Value': estimated_cost,
                'Unit': 'None',  # Cost in USD
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            }
        ]
        
        # Log structured token usage
        logger.info(json.dumps({
            "event_type": "custom_metric",
            "metric_type": "token_usage",
            "job_id": job_id,
            "model_name": model_name,
            "operation": operation,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "total_tokens": total_tokens,
            "estimated_cost_usd": round(estimated_cost, 6),
            "timestamp": int(time.time())
        }))
        
        return self._put_metric_data(TOKEN_METRICS_NAMESPACE, metrics)

    def track_stage_success_failure(
        self,
        job_id: str,
        stage_name: str,
        success: bool,
        error_type: Optional[str] = None,
        retry_count: int = 0
    ) -> bool:
        """
        Track success/failure rates for each processing stage.
        
        Args:
            job_id: Unique job identifier
            stage_name: Pipeline stage name
            success: Whether the stage completed successfully
            error_type: Type of error if failed (timeout, rate_limit, etc.)
            retry_count: Number of retries attempted
            
        Returns:
            True if metric was published successfully
        """
        dimensions = self._create_dimensions(
            Stage=stage_name,
            Success=str(success).lower(),
            ErrorType=error_type if not success else None
        )
        
        metrics = [
            {
                'MetricName': 'StageSuccess' if success else 'StageFailure',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            }
        ]
        
        # Add retry metrics if applicable
        if retry_count > 0:
            metrics.append({
                'MetricName': 'StageRetries',
                'Value': retry_count,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            })
        
        # Log structured success/failure data
        logger.info(json.dumps({
            "event_type": "custom_metric",
            "metric_type": "stage_outcome",
            "job_id": job_id,
            "stage_name": stage_name,
            "success": success,
            "error_type": error_type,
            "retry_count": retry_count,
            "timestamp": int(time.time())
        }))
        
        return self._put_metric_data(PIPELINE_METRICS_NAMESPACE, metrics)

    def track_lambda_metrics(
        self,
        function_name: str,
        execution_time: float,
        memory_used_mb: Optional[int] = None,
        success: bool = True,
        error_type: Optional[str] = None,
        job_id: Optional[str] = None
    ) -> bool:
        """
        Track Lambda function performance metrics.
        
        Args:
            function_name: Lambda function name
            execution_time: Function execution time in seconds
            memory_used_mb: Memory usage in MB
            success: Whether execution was successful
            error_type: Type of error if failed
            job_id: Optional job ID for correlation
            
        Returns:
            True if metric was published successfully
        """
        dimensions = self._create_dimensions(
            FunctionName=function_name,
            Success=str(success).lower(),
            ErrorType=error_type if not success else None
        )
        
        metrics = [
            {
                'MetricName': 'ExecutionTime',
                'Value': execution_time,
                'Unit': 'Seconds',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'Invocations',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            }
        ]
        
        if memory_used_mb:
            metrics.append({
                'MetricName': 'MemoryUsage',
                'Value': memory_used_mb,
                'Unit': 'None',  # MB
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            })
        
        if not success:
            metrics.append({
                'MetricName': 'Errors',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            })
        
        return self._put_metric_data(LAMBDA_METRICS_NAMESPACE, metrics)

    def track_api_metrics(
        self,
        endpoint: str,
        method: str,
        status_code: int,
        response_time: float,
        request_size_bytes: Optional[int] = None,
        response_size_bytes: Optional[int] = None
    ) -> bool:
        """
        Track API Gateway request metrics.
        
        Args:
            endpoint: API endpoint path
            method: HTTP method
            status_code: HTTP response status code
            response_time: Response time in seconds
            request_size_bytes: Request payload size
            response_size_bytes: Response payload size
            
        Returns:
            True if metric was published successfully
        """
        dimensions = self._create_dimensions(
            Endpoint=endpoint,
            Method=method,
            StatusCode=str(status_code)
        )
        
        metrics = [
            {
                'MetricName': 'ResponseTime',
                'Value': response_time,
                'Unit': 'Seconds',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            },
            {
                'MetricName': 'RequestCount',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            }
        ]
        
        if request_size_bytes:
            metrics.append({
                'MetricName': 'RequestSize',
                'Value': request_size_bytes,
                'Unit': 'Bytes',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            })
        
        if response_size_bytes:
            metrics.append({
                'MetricName': 'ResponseSize',
                'Value': response_size_bytes,
                'Unit': 'Bytes',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            })
        
        # Track success/error rates
        if 200 <= status_code < 400:
            metrics.append({
                'MetricName': 'SuccessfulRequests',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            })
        else:
            metrics.append({
                'MetricName': 'ErrorRequests',
                'Value': 1,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            })
        
        return self._put_metric_data(API_METRICS_NAMESPACE, metrics)

    def track_queue_metrics(
        self,
        queue_name: str,
        approximate_message_count: int,
        approximate_message_age_seconds: Optional[int] = None
    ) -> bool:
        """
        Track SQS queue depth and message age metrics.
        
        Args:
            queue_name: SQS queue name
            approximate_message_count: Number of messages in queue
            approximate_message_age_seconds: Age of oldest message in seconds
            
        Returns:
            True if metric was published successfully
        """
        dimensions = self._create_dimensions(QueueName=queue_name)
        
        metrics = [
            {
                'MetricName': 'QueueDepth',
                'Value': approximate_message_count,
                'Unit': 'Count',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            }
        ]
        
        if approximate_message_age_seconds is not None:
            metrics.append({
                'MetricName': 'OldestMessageAge',
                'Value': approximate_message_age_seconds,
                'Unit': 'Seconds',
                'Dimensions': dimensions,
                'Timestamp': datetime.utcnow()
            })
        
        return self._put_metric_data(METRICS_NAMESPACE, metrics)

    def batch_track_metrics(self, metrics_batch: List[Dict[str, Any]]) -> bool:
        """
        Track multiple metrics in a single batch for efficiency.
        
        Args:
            metrics_batch: List of metric tracking dictionaries with:
                - metric_type: Type of metric to track
                - **kwargs: Arguments for the specific metric type
                
        Returns:
            True if all metrics were published successfully
        """
        success_count = 0
        
        for metric_data in metrics_batch:
            metric_type = metric_data.pop('metric_type', None)
            
            if metric_type == 'processing_duration':
                success = self.track_job_processing_duration(**metric_data)
            elif metric_type == 'token_usage':
                success = self.track_gemini_token_usage(**metric_data)
            elif metric_type == 'stage_outcome':
                success = self.track_stage_success_failure(**metric_data)
            elif metric_type == 'lambda_metrics':
                success = self.track_lambda_metrics(**metric_data)
            elif metric_type == 'api_metrics':
                success = self.track_api_metrics(**metric_data)
            elif metric_type == 'queue_metrics':
                success = self.track_queue_metrics(**metric_data)
            else:
                logger.warning(f"Unknown metric type: {metric_type}")
                continue
                
            if success:
                success_count += 1
        
        return success_count == len(metrics_batch)


# Global metrics instance (lazy-initialized)
_metrics_instance: Optional[CloudWatchMetrics] = None


def get_metrics_client(environment: str = "dev") -> CloudWatchMetrics:
    """
    Get or create global CloudWatch metrics client.
    
    Args:
        environment: Environment name
        
    Returns:
        CloudWatch metrics client instance
    """
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = CloudWatchMetrics(environment)
    return _metrics_instance