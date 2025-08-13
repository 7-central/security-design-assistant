"""
Tests for usage analysis and capacity planning utility.
"""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.utils.usage_analysis import UsageAnalyzer


class TestUsageAnalyzer:
    """Test UsageAnalyzer functionality."""

    @pytest.fixture
    def usage_analyzer(self):
        """Create UsageAnalyzer instance with mocked AWS clients."""
        with patch('boto3.client') as mock_client:
            analyzer = UsageAnalyzer('test')

            # Mock CloudWatch responses
            analyzer.cloudwatch = Mock()
            analyzer.lambda_client = Mock()
            analyzer.dynamodb = Mock()
            analyzer.s3 = Mock()

            return analyzer

    @pytest.fixture
    def sample_cloudwatch_data(self):
        """Sample CloudWatch metric data."""
        return [
            {'Sum': 100, 'Average': 1500, 'Maximum': 5},
            {'Sum': 150, 'Average': 1200, 'Maximum': 3},
            {'Sum': 80, 'Average': 1800, 'Maximum': 2},
            {'Sum': 200, 'Average': 1000, 'Maximum': 8}
        ]

    @pytest.fixture
    def sample_lambda_config(self):
        """Sample Lambda configuration response."""
        return {
            'MemorySize': 1024,
            'Timeout': 300,
            'Runtime': 'python3.11',
            'Architectures': ['arm64']
        }

    def test_initialization(self, usage_analyzer):
        """Test UsageAnalyzer initialization."""
        assert usage_analyzer.environment == 'test'
        assert len(usage_analyzer.function_names) == 5
        assert all('test' in name for name in usage_analyzer.function_names)

    @pytest.mark.asyncio
    async def test_get_cloudwatch_metric(self, usage_analyzer, sample_cloudwatch_data):
        """Test getting CloudWatch metric data."""
        usage_analyzer.cloudwatch.get_metric_statistics.return_value = {
            'Datapoints': sample_cloudwatch_data
        }

        start_time = datetime.utcnow() - timedelta(days=1)
        end_time = datetime.utcnow()

        result = await usage_analyzer._get_cloudwatch_metric(
            'AWS/Lambda', 'Invocations', 'FunctionName', 'test-function',
            start_time, end_time, 3600
        )

        assert result == sample_cloudwatch_data
        usage_analyzer.cloudwatch.get_metric_statistics.assert_called_once()

    def test_percentile_calculation(self, usage_analyzer):
        """Test percentile calculation."""
        data = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]

        p50 = usage_analyzer._percentile(data, 0.5)
        p95 = usage_analyzer._percentile(data, 0.95)
        p99 = usage_analyzer._percentile(data, 0.99)

        assert p50 == 5
        assert p95 == 9
        assert p99 == 10

    def test_percentile_empty_data(self, usage_analyzer):
        """Test percentile calculation with empty data."""
        result = usage_analyzer._percentile([], 0.95)
        assert result == 0

    def test_analyze_usage_patterns_sporadic(self, usage_analyzer):
        """Test usage pattern analysis for sporadic usage."""
        # Mostly zeros with few spikes
        hourly_data = [0, 0, 0, 100, 0, 0, 0, 0, 0, 200, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0]

        patterns = usage_analyzer._analyze_usage_patterns(hourly_data)

        assert patterns['pattern'] == 'sporadic'
        assert patterns['total_invocations'] == 300
        assert patterns['active_hours'] == 2
        assert patterns['idle_hours'] == 18
        assert patterns['utilization_rate'] == 0.1

    def test_analyze_usage_patterns_continuous(self, usage_analyzer):
        """Test usage pattern analysis for continuous usage."""
        # Consistent non-zero values
        hourly_data = [50, 60, 45, 55, 65, 40, 58, 62, 48, 52] * 2

        patterns = usage_analyzer._analyze_usage_patterns(hourly_data)

        assert patterns['pattern'] == 'continuous'
        assert patterns['active_hours'] == 20
        assert patterns['idle_hours'] == 0
        assert patterns['utilization_rate'] == 1.0

    def test_analyze_usage_patterns_bursty(self, usage_analyzer):
        """Test usage pattern analysis for bursty usage."""
        # Regular usage with high spikes
        hourly_data = [10, 15, 12, 500, 8, 14, 16, 600, 11, 13]

        patterns = usage_analyzer._analyze_usage_patterns(hourly_data)

        assert patterns['pattern'] == 'bursty'
        assert patterns['peak_invocations_per_hour'] == 600

    def test_identify_optimizations_high_duration(self, usage_analyzer):
        """Test optimization identification for high duration functions."""
        durations = [15000, 18000, 20000, 22000]  # > 10 seconds
        concurrency = [5, 3, 4, 6]
        memory_util = [45, 50, 40, 48]
        current_memory = 1024

        optimizations = usage_analyzer._identify_optimizations(
            durations, concurrency, memory_util, current_memory
        )

        assert any('increasing memory' in opt for opt in optimizations)

    def test_identify_optimizations_high_memory_util(self, usage_analyzer):
        """Test optimization identification for high memory utilization."""
        durations = [1000, 1200, 800, 900]  # Low duration
        concurrency = [2, 1, 3, 2]
        memory_util = [85, 90, 88, 82]  # High memory util
        current_memory = 512

        optimizations = usage_analyzer._identify_optimizations(
            durations, concurrency, memory_util, current_memory
        )

        assert any('increasing memory' in opt for opt in optimizations)

    def test_identify_optimizations_low_utilization(self, usage_analyzer):
        """Test optimization identification for over-provisioned functions."""
        durations = [500, 600, 400, 800]  # Very fast
        concurrency = [1, 2, 1, 1]
        memory_util = [25, 20, 30, 18]  # Low memory util
        current_memory = 1024  # High memory allocation

        optimizations = usage_analyzer._identify_optimizations(
            durations, concurrency, memory_util, current_memory
        )

        assert any('reducing memory' in opt for opt in optimizations)

    @pytest.mark.asyncio
    async def test_analyze_single_function(self, usage_analyzer, sample_cloudwatch_data, sample_lambda_config):
        """Test analyzing a single function."""
        # Mock CloudWatch responses
        usage_analyzer._get_cloudwatch_metric = AsyncMock(return_value=sample_cloudwatch_data)
        usage_analyzer.lambda_client.get_function_configuration.return_value = sample_lambda_config

        start_time = datetime.utcnow() - timedelta(days=7)
        end_time = datetime.utcnow()

        result = await usage_analyzer._analyze_single_function(
            'test-function', start_time, end_time
        )

        # Verify result structure
        assert 'total_invocations' in result
        assert 'total_duration_hours' in result
        assert 'avg_duration_ms' in result
        assert 'peak_concurrent_executions' in result
        assert 'estimated_cost' in result
        assert 'usage_patterns' in result
        assert 'optimization_opportunities' in result

        # Verify calculations
        assert result['total_invocations'] == 530  # Sum of sample data
        assert result['current_memory_mb'] == 1024
        assert result['architecture'] == 'arm64'

    @pytest.mark.asyncio
    async def test_analyze_lambda_usage_patterns(self, usage_analyzer):
        """Test analyzing Lambda usage patterns for all functions."""
        # Mock single function analysis
        sample_analysis = {
            'total_invocations': 1000,
            'total_duration_hours': 2.5,
            'estimated_cost': 15.50,
            'peak_concurrent_executions': 10
        }
        usage_analyzer._analyze_single_function = AsyncMock(return_value=sample_analysis)

        result = await usage_analyzer.analyze_lambda_usage_patterns(30)

        # Verify result structure
        assert 'analysis_period' in result
        assert 'functions' in result
        assert 'summary' in result
        assert 'recommendations' in result

        # Verify aggregated data
        expected_functions = len(usage_analyzer.function_names)
        assert result['summary']['total_invocations'] == 1000 * expected_functions
        assert result['summary']['total_duration_hours'] == 2.5 * expected_functions

    def test_generate_cost_projections(self, usage_analyzer):
        """Test generating cost projections."""
        usage_analysis = {
            'summary': {
                'total_estimated_cost': 100.0
            }
        }

        projections = usage_analyzer._generate_cost_projections(usage_analysis)

        assert projections['current_monthly'] == 100.0
        assert projections['projected_yearly'] == 1200.0
        assert 'scenarios' in projections

        # Verify optimization scenario
        optimized = projections['scenarios']['optimized']
        assert optimized['monthly_cost'] == 80.0
        assert optimized['savings_monthly'] == 20.0

        # Verify growth scenarios
        growth_50 = projections['scenarios']['growth_50_percent']
        assert growth_50['monthly_cost'] == 150.0

    def test_create_executive_summary(self, usage_analyzer):
        """Test creating executive summary."""
        usage_analysis = {
            'summary': {
                'avg_daily_invocations': 1000,
                'peak_concurrency': 25,
                'total_estimated_cost': 150.0
            },
            'functions': {'func1': {}, 'func2': {}},
            'recommendations': [
                {'priority': 'high', 'category': 'performance'},
                {'priority': 'medium', 'category': 'cost_optimization'},
                {'priority': 'high', 'category': 'capacity_planning'}
            ]
        }

        cost_projections = {
            'current_monthly': 150.0,
            'scenarios': {
                'optimized': {'savings_monthly': 30.0}
            }
        }

        summary = usage_analyzer._create_executive_summary(usage_analysis, cost_projections)

        assert summary['key_metrics']['total_monthly_invocations'] == 30000  # 1000 * 30
        assert summary['key_metrics']['current_monthly_cost'] == 150.0
        assert summary['critical_findings']['high_priority_issues'] == 2
        assert summary['critical_findings']['performance_issues'] == 1
        assert len(summary['next_actions']) > 0

    @pytest.mark.asyncio
    async def test_get_provisioned_resources(self, usage_analyzer, sample_lambda_config):
        """Test getting provisioned resource information."""
        usage_analyzer.lambda_client.get_function_configuration.return_value = sample_lambda_config

        resources = await usage_analyzer._get_provisioned_resources()

        assert 'lambda_functions' in resources
        assert 'dynamodb_tables' in resources
        assert 's3_buckets' in resources

        # Verify Lambda function data
        for func_name in usage_analyzer.function_names:
            assert func_name in resources['lambda_functions']
            func_config = resources['lambda_functions'][func_name]
            assert func_config['memory_mb'] == 1024
            assert func_config['architecture'] == 'arm64'

    @pytest.mark.asyncio
    async def test_generate_capacity_report(self, usage_analyzer):
        """Test generating comprehensive capacity report."""
        # Mock dependencies
        usage_analysis_mock = {
            'summary': {'total_estimated_cost': 75.0, 'avg_daily_invocations': 500},
            'functions': {},
            'recommendations': []
        }
        usage_analyzer.analyze_lambda_usage_patterns = AsyncMock(return_value=usage_analysis_mock)
        usage_analyzer._get_provisioned_resources = AsyncMock(return_value={})

        report = await usage_analyzer.generate_capacity_report(30)

        # Verify report structure
        assert report['report_type'] == 'capacity_planning'
        assert report['environment'] == 'test'
        assert report['analysis_period_days'] == 30
        assert 'generated_at' in report
        assert 'usage_analysis' in report
        assert 'provisioned_resources' in report
        assert 'cost_projections' in report
        assert 'executive_summary' in report


class TestTemplateConfiguration:
    """Test CloudFormation template monitoring configuration."""

    def test_cost_anomaly_detection_configured(self):
        """Test that cost anomaly detection is configured."""
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml') as f:
            template_content = f.read()

        # Check for cost anomaly detector
        assert 'CostAnomalyDetector:' in template_content
        assert 'AWS::CE::AnomalyDetector' in template_content
        assert 'SecurityAssistant-CostAnomaly' in template_content

        # Check for cost anomaly subscription
        assert 'CostAnomalySubscription:' in template_content
        assert 'AWS::CE::AnomalySubscription' in template_content

        # Check monitored services
        assert 'AWS Lambda' in template_content
        assert 'Amazon S3' in template_content
        assert 'Amazon DynamoDB' in template_content

    def test_cloudwatch_dashboards_configured(self):
        """Test that CloudWatch dashboards are configured."""
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml') as f:
            template_content = f.read()

        # Check for main dashboard
        assert 'MainDashboard:' in template_content
        assert 'AWS::CloudWatch::Dashboard' in template_content

        # Check for health monitoring dashboard
        assert 'HealthMonitoringDashboard:' in template_content

        # Check dashboard widgets
        assert 'Lambda Invocations' in template_content
        assert 'Lambda Errors' in template_content
        assert 'SQS Queue Depth' in template_content

    def test_cloudwatch_alarms_configured(self):
        """Test that CloudWatch alarms are properly configured."""
        with open('/Users/leehayton/Cursor Projects/7central/security_and_design/infrastructure/template.yaml') as f:
            template_content = f.read()

        # Check for various alarm types
        assert 'ApiLambdaErrorRateAlarm:' in template_content
        assert 'WorkerLambdaErrorRateAlarm:' in template_content
        assert 'DLQDepthAlarm:' in template_content
        assert 'TokenCostAlarm:' in template_content

        # Check alarm thresholds
        assert 'Threshold: 0.10' in template_content  # Error rate threshold
        assert 'Threshold: 100.0' in template_content  # Cost threshold
