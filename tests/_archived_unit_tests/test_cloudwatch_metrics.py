"""
Unit tests for CloudWatch metrics utility.
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.utils.cloudwatch_metrics import (
    GEMINI_FLASH_COST_PER_MILLION,
    GEMINI_PRO_COST_PER_MILLION,
    CloudWatchMetrics,
    get_metrics_client,
)


class TestCloudWatchMetrics:
    """Test cases for CloudWatchMetrics class."""

    @pytest.fixture
    def metrics_client(self):
        """Create CloudWatch metrics client for testing."""
        with patch('src.utils.cloudwatch_metrics.boto3.client') as mock_boto:
            mock_cloudwatch = Mock()
            mock_boto.return_value = mock_cloudwatch
            return CloudWatchMetrics(environment='test')

    def test_initialization(self, metrics_client):
        """Test CloudWatch metrics client initialization."""
        assert metrics_client.environment == 'test'
        assert metrics_client.cloudwatch is not None

    def test_create_dimensions(self, metrics_client):
        """Test dimension creation with environment."""
        dimensions = metrics_client._create_dimensions(
            Stage='pdf_processing',
            Client='test_client'
        )

        expected_dims = [
            {'Name': 'Environment', 'Value': 'test'},
            {'Name': 'Stage', 'Value': 'pdf_processing'},
            {'Name': 'Client', 'Value': 'test_client'}
        ]

        assert dimensions == expected_dims

    def test_create_dimensions_with_none_values(self, metrics_client):
        """Test dimension creation with None values are filtered out."""
        dimensions = metrics_client._create_dimensions(
            Stage='pdf_processing',
            Client=None,
            Project='test_project'
        )

        expected_dims = [
            {'Name': 'Environment', 'Value': 'test'},
            {'Name': 'Stage', 'Value': 'pdf_processing'},
            {'Name': 'Project', 'Value': 'test_project'}
        ]

        assert dimensions == expected_dims

    def test_put_metric_data_success(self, metrics_client):
        """Test successful metric data publishing."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        metrics = [
            {
                'MetricName': 'TestMetric',
                'Value': 1.0,
                'Unit': 'Count',
                'Dimensions': [{'Name': 'Environment', 'Value': 'test'}],
                'Timestamp': datetime.utcnow()
            }
        ]

        result = metrics_client._put_metric_data('TestNamespace', metrics)

        assert result is True
        mock_cloudwatch.put_metric_data.assert_called_once_with(
            Namespace='TestNamespace',
            MetricData=metrics
        )

    def test_put_metric_data_batching(self, metrics_client):
        """Test metric data batching for large datasets."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        # Create 25 metrics (should require 2 batches of max 20)
        metrics = []
        for i in range(25):
            metrics.append({
                'MetricName': f'TestMetric{i}',
                'Value': 1.0,
                'Unit': 'Count',
                'Dimensions': [{'Name': 'Environment', 'Value': 'test'}],
                'Timestamp': datetime.utcnow()
            })

        result = metrics_client._put_metric_data('TestNamespace', metrics)

        assert result is True
        assert mock_cloudwatch.put_metric_data.call_count == 2

    def test_track_job_processing_duration(self, metrics_client):
        """Test job processing duration tracking."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        result = metrics_client.track_job_processing_duration(
            job_id='test_job_123',
            stage_name='pdf_processing',
            duration_seconds=45.5,
            status='completed',
            client_name='test_client',
            project_name='test_project'
        )

        assert result is True
        mock_cloudwatch.put_metric_data.assert_called_once()

        # Check the call arguments
        call_args = mock_cloudwatch.put_metric_data.call_args
        assert call_args[1]['Namespace'] == 'SecurityAssistant/Pipeline'

        metrics_data = call_args[1]['MetricData']
        assert len(metrics_data) == 2  # Duration and Completion metrics

        duration_metric = metrics_data[0]
        assert duration_metric['MetricName'] == 'ProcessingDuration'
        assert duration_metric['Value'] == 45.5
        assert duration_metric['Unit'] == 'Seconds'

    def test_track_gemini_token_usage_flash_model(self, metrics_client):
        """Test Gemini token usage tracking for Flash model."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        result = metrics_client.track_gemini_token_usage(
            job_id='test_job_123',
            model_name='gemini-2.0-flash-exp',
            input_tokens=1000,
            output_tokens=500,
            operation='pdf_analysis'
        )

        assert result is True

        # Check the call arguments
        call_args = mock_cloudwatch.put_metric_data.call_args
        assert call_args[1]['Namespace'] == 'SecurityAssistant/TokenUsage'

        metrics_data = call_args[1]['MetricData']
        assert len(metrics_data) == 4  # Input, Output, Total, Cost

        # Verify cost calculation for Flash model
        total_tokens = 1500
        expected_cost = (total_tokens / 1_000_000) * GEMINI_FLASH_COST_PER_MILLION

        cost_metric = next(m for m in metrics_data if m['MetricName'] == 'EstimatedCost')
        assert cost_metric['Value'] == expected_cost

    def test_track_gemini_token_usage_pro_model(self, metrics_client):
        """Test Gemini token usage tracking for Pro model."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        result = metrics_client.track_gemini_token_usage(
            job_id='test_job_123',
            model_name='gemini-2.0-pro',
            input_tokens=2000,
            output_tokens=1000,
            operation='evaluation'
        )

        assert result is True

        # Check cost calculation for Pro model
        call_args = mock_cloudwatch.put_metric_data.call_args
        metrics_data = call_args[1]['MetricData']

        total_tokens = 3000
        expected_cost = (total_tokens / 1_000_000) * GEMINI_PRO_COST_PER_MILLION

        cost_metric = next(m for m in metrics_data if m['MetricName'] == 'EstimatedCost')
        assert cost_metric['Value'] == expected_cost

    def test_track_stage_success_failure_success(self, metrics_client):
        """Test tracking successful stage completion."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        result = metrics_client.track_stage_success_failure(
            job_id='test_job_123',
            stage_name='pdf_processing',
            success=True
        )

        assert result is True

        call_args = mock_cloudwatch.put_metric_data.call_args
        metrics_data = call_args[1]['MetricData']

        success_metric = metrics_data[0]
        assert success_metric['MetricName'] == 'StageSuccess'
        assert success_metric['Value'] == 1

    def test_track_stage_success_failure_with_retry(self, metrics_client):
        """Test tracking failed stage with retry count."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        result = metrics_client.track_stage_success_failure(
            job_id='test_job_123',
            stage_name='drawing_analysis',
            success=False,
            error_type='RateLimitExceededException',
            retry_count=3
        )

        assert result is True

        call_args = mock_cloudwatch.put_metric_data.call_args
        metrics_data = call_args[1]['MetricData']

        assert len(metrics_data) == 2  # Failure and Retry metrics

        failure_metric = metrics_data[0]
        assert failure_metric['MetricName'] == 'StageFailure'

        retry_metric = metrics_data[1]
        assert retry_metric['MetricName'] == 'StageRetries'
        assert retry_metric['Value'] == 3

    def test_track_lambda_metrics(self, metrics_client):
        """Test Lambda function metrics tracking."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        result = metrics_client.track_lambda_metrics(
            function_name='test_function',
            execution_time=2.5,
            memory_used_mb=512,
            success=True,
            job_id='test_job_123'
        )

        assert result is True

        call_args = mock_cloudwatch.put_metric_data.call_args
        assert call_args[1]['Namespace'] == 'SecurityAssistant/Lambda'

        metrics_data = call_args[1]['MetricData']
        assert len(metrics_data) == 3  # ExecutionTime, Invocations, MemoryUsage

        execution_metric = next(m for m in metrics_data if m['MetricName'] == 'ExecutionTime')
        assert execution_metric['Value'] == 2.5
        assert execution_metric['Unit'] == 'Seconds'

    def test_track_api_metrics(self, metrics_client):
        """Test API metrics tracking."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        result = metrics_client.track_api_metrics(
            endpoint='/process-drawing',
            method='POST',
            status_code=202,
            response_time=1.2,
            request_size_bytes=1024,
            response_size_bytes=512
        )

        assert result is True

        call_args = mock_cloudwatch.put_metric_data.call_args
        assert call_args[1]['Namespace'] == 'SecurityAssistant/API'

        metrics_data = call_args[1]['MetricData']
        # ResponseTime, RequestCount, RequestSize, ResponseSize, SuccessfulRequests
        assert len(metrics_data) == 5

        response_time_metric = next(m for m in metrics_data if m['MetricName'] == 'ResponseTime')
        assert response_time_metric['Value'] == 1.2

    def test_track_queue_metrics(self, metrics_client):
        """Test SQS queue metrics tracking."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        result = metrics_client.track_queue_metrics(
            queue_name='test_queue',
            approximate_message_count=5,
            approximate_message_age_seconds=300
        )

        assert result is True

        call_args = mock_cloudwatch.put_metric_data.call_args
        assert call_args[1]['Namespace'] == 'SecurityAssistant'

        metrics_data = call_args[1]['MetricData']
        assert len(metrics_data) == 2  # QueueDepth and OldestMessageAge

        depth_metric = next(m for m in metrics_data if m['MetricName'] == 'QueueDepth')
        assert depth_metric['Value'] == 5

    def test_batch_track_metrics(self, metrics_client):
        """Test batch metrics tracking."""
        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.return_value = {}

        batch_metrics = [
            {
                'metric_type': 'processing_duration',
                'job_id': 'test_job_1',
                'stage_name': 'pdf_processing',
                'duration_seconds': 30.0,
                'status': 'completed',
                'client_name': 'test_client',
                'project_name': 'test_project'
            },
            {
                'metric_type': 'token_usage',
                'job_id': 'test_job_1',
                'model_name': 'gemini-2.0-flash-exp',
                'input_tokens': 1000,
                'output_tokens': 500,
                'operation': 'pdf_analysis'
            }
        ]

        result = metrics_client.batch_track_metrics(batch_metrics)

        assert result is True
        assert mock_cloudwatch.put_metric_data.call_count == 2

    def test_error_handling_put_metric_data(self, metrics_client):
        """Test error handling in put_metric_data."""
        from botocore.exceptions import ClientError

        mock_cloudwatch = metrics_client.cloudwatch
        mock_cloudwatch.put_metric_data.side_effect = ClientError(
            {'Error': {'Code': 'ValidationException', 'Message': 'Invalid metric data'}},
            'PutMetricData'
        )

        metrics = [
            {
                'MetricName': 'TestMetric',
                'Value': 1.0,
                'Unit': 'Count',
                'Dimensions': [{'Name': 'Environment', 'Value': 'test'}],
                'Timestamp': datetime.utcnow()
            }
        ]

        result = metrics_client._put_metric_data('TestNamespace', metrics)

        assert result is False


class TestMetricsClientSingleton:
    """Test cases for global metrics client management."""

    def test_get_metrics_client_singleton(self):
        """Test that get_metrics_client returns singleton instance."""
        with patch('src.utils.cloudwatch_metrics.CloudWatchMetrics') as mock_cwm:
            mock_instance = Mock()
            mock_cwm.return_value = mock_instance

            client1 = get_metrics_client('test')
            client2 = get_metrics_client('test')

            assert client1 is client2
            mock_cwm.assert_called_once_with('test')

    def test_get_metrics_client_default_environment(self):
        """Test default environment parameter."""
        with patch('src.utils.cloudwatch_metrics.CloudWatchMetrics') as mock_cwm:
            mock_instance = Mock()
            mock_cwm.return_value = mock_instance

            # Reset global instance for test
            import src.utils.cloudwatch_metrics
            src.utils.cloudwatch_metrics._metrics_instance = None

            get_metrics_client()

            mock_cwm.assert_called_with('dev')


class TestCostCalculations:
    """Test cases for cost calculation logic."""

    def test_flash_model_cost_calculation(self):
        """Test cost calculation for Flash model."""
        total_tokens = 1_000_000  # 1M tokens
        expected_cost = GEMINI_FLASH_COST_PER_MILLION

        with patch('src.utils.cloudwatch_metrics.boto3.client'):
            CloudWatchMetrics('test')

            # Calculate cost using the same logic as in the class
            calculated_cost = (total_tokens / 1_000_000) * GEMINI_FLASH_COST_PER_MILLION

            assert calculated_cost == expected_cost
            assert calculated_cost == 0.075

    def test_pro_model_cost_calculation(self):
        """Test cost calculation for Pro model."""
        total_tokens = 1_000_000  # 1M tokens
        expected_cost = GEMINI_PRO_COST_PER_MILLION

        with patch('src.utils.cloudwatch_metrics.boto3.client'):
            CloudWatchMetrics('test')

            # Calculate cost using the same logic as in the class
            calculated_cost = (total_tokens / 1_000_000) * GEMINI_PRO_COST_PER_MILLION

            assert calculated_cost == expected_cost
            assert calculated_cost == 2.50
