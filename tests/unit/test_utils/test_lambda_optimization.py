"""
Tests for Lambda optimization utilities.
"""

import json
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.utils.lambda_optimization import LambdaPowerTuner, analyze_lambda_performance


class TestLambdaPowerTuner:
    """Test Lambda Power Tuner functionality."""

    @pytest.fixture
    def tuner(self):
        """Create LambdaPowerTuner instance with mocked AWS clients."""
        with patch('boto3.client') as mock_client:
            yield LambdaPowerTuner()

    def test_memory_calculation_maintain(self, tuner):
        """Test memory calculation with maintain adjustment."""
        result = tuner.calculate_memory_adjustment(1024, 'maintain')
        assert result == 1024

    def test_memory_calculation_reduce_25_percent(self, tuner):
        """Test memory calculation with 25% reduction."""
        result = tuner.calculate_memory_adjustment(1024, 'reduce_by_25_percent')
        assert result == 768  # Closest valid memory size to 768

    def test_memory_calculation_increase_50_percent(self, tuner):
        """Test memory calculation with 50% increase."""
        result = tuner.calculate_memory_adjustment(1024, 'increase_by_50_percent')
        assert result == 1536  # Closest valid memory size to 1536

    def test_memory_calculation_increase_100_percent(self, tuner):
        """Test memory calculation with 100% increase."""
        result = tuner.calculate_memory_adjustment(512, 'increase_by_100_percent')
        assert result == 1024

    def test_generate_memory_recommendations_excellent_performance(self, tuner):
        """Test recommendations for excellent performance."""
        recommendations = tuner._generate_memory_recommendations(500, 800, 0.5)
        
        assert recommendations['current_performance'] == 'excellent'
        assert recommendations['suggested_action'] == 'consider_reducing_memory'
        assert recommendations['memory_adjustment'] == 'reduce_by_25_percent'
        assert len(recommendations['reasoning']) > 0

    def test_generate_memory_recommendations_poor_performance(self, tuner):
        """Test recommendations for poor performance."""
        recommendations = tuner._generate_memory_recommendations(20000, 25000, 2.0)
        
        assert recommendations['current_performance'] == 'poor'
        assert recommendations['suggested_action'] == 'significant_increase'
        assert recommendations['memory_adjustment'] == 'increase_by_100_percent'

    def test_generate_memory_recommendations_high_error_rate(self, tuner):
        """Test recommendations with high error rate."""
        recommendations = tuner._generate_memory_recommendations(3000, 4000, 8.0)
        
        assert 'increase' in recommendations['suggested_action'].lower()
        assert any('error rate' in reason.lower() for reason in recommendations['reasoning'])

    @patch('boto3.client')
    def test_get_current_function_config(self, mock_boto_client):
        """Test getting current function configuration."""
        mock_lambda_client = Mock()
        mock_boto_client.return_value = mock_lambda_client
        
        mock_response = {
            'FunctionName': 'test-function',
            'Runtime': 'python3.11',
            'MemorySize': 1024,
            'Timeout': 300,
            'Architectures': ['arm64'],
            'LastModified': '2025-08-10T10:00:00.000+0000'
        }
        mock_lambda_client.get_function_configuration.return_value = mock_response
        
        tuner = LambdaPowerTuner()
        config = tuner.get_current_function_config('test-function')
        
        assert config['function_name'] == 'test-function'
        assert config['memory_size'] == 1024
        assert config['architecture'] == 'arm64'
        mock_lambda_client.get_function_configuration.assert_called_once_with(
            FunctionName='test-function'
        )

    @patch('boto3.client')
    def test_analyze_function_performance(self, mock_boto_client):
        """Test function performance analysis."""
        mock_cloudwatch = Mock()
        mock_boto_client.return_value = mock_cloudwatch
        
        # Mock CloudWatch responses
        duration_response = {
            'Datapoints': [
                {'Average': 2000, 'Maximum': 3000, 'Minimum': 1000},
                {'Average': 2500, 'Maximum': 3500, 'Minimum': 1500}
            ]
        }
        invocation_response = {
            'Datapoints': [
                {'Sum': 100},
                {'Sum': 150}
            ]
        }
        error_response = {
            'Datapoints': [
                {'Sum': 2},
                {'Sum': 3}
            ]
        }
        
        mock_cloudwatch.get_metric_statistics.side_effect = [
            duration_response,
            invocation_response,
            error_response
        ]
        
        tuner = LambdaPowerTuner()
        analysis = tuner.analyze_function_performance('test-function', 7)
        
        assert analysis['function_name'] == 'test-function'
        assert analysis['analysis_period_days'] == 7
        assert 'performance_metrics' in analysis
        assert 'recommendations' in analysis
        
        metrics = analysis['performance_metrics']
        assert metrics['average_duration_ms'] == 2250  # (2000 + 2500) / 2
        assert metrics['maximum_duration_ms'] == 3500
        assert metrics['total_invocations'] == 250  # 100 + 150
        assert metrics['total_errors'] == 5  # 2 + 3
        assert metrics['error_rate_percent'] == 2.0  # (5/250) * 100

    @patch('boto3.client')
    def test_generate_power_tuning_report(self, mock_boto_client):
        """Test comprehensive power tuning report generation."""
        # Setup mocks
        mock_cloudwatch = Mock()
        mock_lambda_client = Mock()
        
        def mock_client_side_effect(service_name, **kwargs):
            if service_name == 'cloudwatch':
                return mock_cloudwatch
            elif service_name == 'lambda':
                return mock_lambda_client
            return Mock()
        
        mock_boto_client.side_effect = mock_client_side_effect
        
        # Mock Lambda config response
        mock_lambda_client.get_function_configuration.return_value = {
            'FunctionName': 'test-function',
            'Runtime': 'python3.11',
            'MemorySize': 1024,
            'Timeout': 300,
            'Architectures': ['arm64'],
            'LastModified': '2025-08-10T10:00:00.000+0000'
        }
        
        # Mock CloudWatch responses
        mock_cloudwatch.get_metric_statistics.side_effect = [
            {'Datapoints': [{'Average': 2000, 'Maximum': 3000, 'Minimum': 1000}]},  # Duration
            {'Datapoints': [{'Sum': 100}]},  # Invocations
            {'Datapoints': [{'Sum': 2}]}  # Errors
        ]
        
        tuner = LambdaPowerTuner()
        report = tuner.generate_power_tuning_report(['test-function'])
        
        assert 'generated_at' in report
        assert report['total_functions_analyzed'] == 1
        assert 'test-function' in report['functions']
        assert 'summary' in report
        
        function_report = report['functions']['test-function']
        assert 'current_config' in function_report
        assert 'performance_analysis' in function_report
        assert 'recommendations' in function_report

    @patch.dict('os.environ', {'ENVIRONMENT': 'test'})
    @patch('src.utils.lambda_optimization.LambdaPowerTuner')
    def test_analyze_lambda_performance_function(self, mock_tuner_class):
        """Test the analyze_lambda_performance function."""
        mock_tuner = Mock()
        mock_tuner_class.return_value = mock_tuner
        mock_report = {'test': 'report'}
        mock_tuner.generate_power_tuning_report.return_value = mock_report
        
        result = analyze_lambda_performance()
        
        assert result == mock_report
        expected_functions = [
            'security-assistant-api-test',
            'security-assistant-worker-test',
            'security-assistant-status-test',
            'security-assistant-dlq-processor-test'
        ]
        mock_tuner.generate_power_tuning_report.assert_called_once_with(expected_functions)


class TestConnectionPooling:
    """Test connection pooling functionality in AWS storage."""

    @patch('boto3.client')
    @patch('boto3.resource')
    def test_aws_storage_connection_pooling(self, mock_resource, mock_client):
        """Test that AWSStorage initializes with connection pooling."""
        from src.storage.aws_storage import AWSStorage
        
        # Create AWSStorage instance
        storage = AWSStorage()
        
        # Verify boto3 clients were called with connection pooling config
        mock_client.assert_called()
        mock_resource.assert_called()
        
        # Get the config passed to boto3 clients
        s3_call_args = mock_client.call_args
        dynamodb_call_args = mock_resource.call_args
        
        # Verify config was passed (config should be in kwargs)
        assert 'config' in s3_call_args.kwargs
        assert 'config' in dynamodb_call_args.kwargs


class TestARMArchitecture:
    """Test ARM64 architecture configuration."""

    def test_template_has_arm64_architecture(self):
        """Test that SAM template includes ARM64 architecture."""
        # Read template as text instead of parsing YAML due to CloudFormation intrinsics
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml', 'r') as f:
            template_content = f.read()
        
        # Check for ARM64 architecture in Globals section
        assert 'Architectures:' in template_content
        assert '- arm64' in template_content
        
        # Check Lambda Layer compatibility
        assert 'CompatibleArchitectures:' in template_content

    def test_provisioned_concurrency_configured(self):
        """Test that provisioned concurrency is configured for API function."""
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml', 'r') as f:
            template_content = f.read()
        
        # Check API function for provisioned concurrency
        assert 'ProvisionedConcurrencyConfig:' in template_content
        assert 'ProvisionedConcurrencyExecution: 2' in template_content


class TestDynamoDBOptimization:
    """Test DynamoDB optimization configuration."""

    def test_dynamodb_on_demand_billing(self):
        """Test that DynamoDB table uses on-demand billing."""
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml', 'r') as f:
            template_content = f.read()
        
        # Check for on-demand billing mode
        assert 'BillingMode: PAY_PER_REQUEST' in template_content
        
        # Verify provisioned throughput was removed from GSIs
        assert 'ReadCapacityUnits' not in template_content
        assert 'WriteCapacityUnits' not in template_content