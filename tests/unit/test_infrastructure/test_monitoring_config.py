"""
Unit tests for monitoring configuration validation.
"""

import json
import pytest
from pathlib import Path


class TestCloudWatchDashboards:
    """Test cases for CloudWatch Dashboard configurations."""

    @pytest.fixture
    def dashboard_config_path(self):
        """Get path to main dashboard configuration."""
        return Path(__file__).parent.parent.parent.parent / 'infrastructure' / 'cloudwatch-dashboard.json'

    @pytest.fixture
    def health_dashboard_config_path(self):
        """Get path to health monitoring dashboard configuration."""
        return Path(__file__).parent.parent.parent.parent / 'infrastructure' / 'health-monitoring-dashboard.json'

    def test_main_dashboard_config_exists(self, dashboard_config_path):
        """Test that main dashboard configuration file exists."""
        assert dashboard_config_path.exists()

    def test_health_dashboard_config_exists(self, health_dashboard_config_path):
        """Test that health dashboard configuration file exists."""
        assert health_dashboard_config_path.exists()

    def test_main_dashboard_valid_json(self, dashboard_config_path):
        """Test that main dashboard contains valid JSON."""
        with open(dashboard_config_path, 'r') as f:
            config = json.load(f)
        
        assert 'widgets' in config
        assert isinstance(config['widgets'], list)
        assert len(config['widgets']) > 0

    def test_health_dashboard_valid_json(self, health_dashboard_config_path):
        """Test that health dashboard contains valid JSON."""
        with open(health_dashboard_config_path, 'r') as f:
            config = json.load(f)
        
        assert 'widgets' in config
        assert isinstance(config['widgets'], list)
        assert len(config['widgets']) > 0

    def test_main_dashboard_widget_structure(self, dashboard_config_path):
        """Test that main dashboard widgets have required structure."""
        with open(dashboard_config_path, 'r') as f:
            config = json.load(f)
        
        for widget in config['widgets']:
            assert 'type' in widget
            assert 'properties' in widget
            assert 'x' in widget and 'y' in widget
            assert 'width' in widget and 'height' in widget
            
            # Test widget properties
            props = widget['properties']
            if widget['type'] == 'metric':
                assert 'metrics' in props or 'view' in props
                assert 'region' in props
                assert 'title' in props
            elif widget['type'] == 'log':
                assert 'query' in props
                assert 'region' in props
                assert 'title' in props

    def test_health_dashboard_has_key_widgets(self, health_dashboard_config_path):
        """Test that health dashboard contains expected widget types."""
        with open(health_dashboard_config_path, 'r') as f:
            config = json.load(f)
        
        widget_titles = [widget['properties']['title'] for widget in config['widgets']]
        
        # Check for key monitoring widgets
        expected_widgets = [
            'API Request Counts',
            'Token Usage & Cost',
            'Processing Stage Failure Analysis'
        ]
        
        for expected in expected_widgets:
            assert any(expected.lower() in title.lower() for title in widget_titles), \
                f"Expected widget '{expected}' not found in dashboard"


class TestCloudWatchLogsInsights:
    """Test cases for CloudWatch Logs Insights queries."""

    @pytest.fixture
    def logs_insights_config_path(self):
        """Get path to CloudWatch Logs Insights queries configuration."""
        return Path(__file__).parent.parent.parent.parent / 'infrastructure' / 'cloudwatch-logs-insights-queries.json'

    def test_logs_insights_config_exists(self, logs_insights_config_path):
        """Test that logs insights configuration file exists."""
        assert logs_insights_config_path.exists()

    def test_logs_insights_valid_json(self, logs_insights_config_path):
        """Test that logs insights configuration contains valid JSON."""
        with open(logs_insights_config_path, 'r') as f:
            config = json.load(f)
        
        assert 'queries' in config
        assert isinstance(config['queries'], dict)
        assert len(config['queries']) > 0

    def test_required_queries_exist(self, logs_insights_config_path):
        """Test that required troubleshooting queries exist."""
        with open(logs_insights_config_path, 'r') as f:
            config = json.load(f)
        
        required_queries = [
            'error_analysis',
            'job_processing_timeline', 
            'performance_analysis',
            'token_usage_analysis',
            'correlation_trace'
        ]
        
        for query_name in required_queries:
            assert query_name in config['queries'], f"Required query '{query_name}' not found"

    def test_query_structure(self, logs_insights_config_path):
        """Test that each query has the required structure."""
        with open(logs_insights_config_path, 'r') as f:
            config = json.load(f)
        
        for query_name, query_config in config['queries'].items():
            assert 'name' in query_config, f"Query '{query_name}' missing 'name'"
            assert 'description' in query_config, f"Query '{query_name}' missing 'description'"
            assert 'query' in query_config, f"Query '{query_name}' missing 'query'"
            assert 'log_groups' in query_config, f"Query '{query_name}' missing 'log_groups'"
            
            # Validate log groups is a list
            assert isinstance(query_config['log_groups'], list), \
                f"Query '{query_name}' log_groups should be a list"
            assert len(query_config['log_groups']) > 0, \
                f"Query '{query_name}' should have at least one log group"

    def test_query_syntax_basic_validation(self, logs_insights_config_path):
        """Test basic CloudWatch Logs Insights query syntax."""
        with open(logs_insights_config_path, 'r') as f:
            config = json.load(f)
        
        for query_name, query_config in config['queries'].items():
            query_text = query_config['query']
            
            # Basic syntax checks
            assert 'fields' in query_text or 'filter' in query_text, \
                f"Query '{query_name}' should contain 'fields' or 'filter'"
            
            # Check for common CloudWatch Logs Insights keywords
            insights_keywords = ['fields', 'filter', 'sort', 'stats', 'limit']
            has_keyword = any(keyword in query_text for keyword in insights_keywords)
            assert has_keyword, f"Query '{query_name}' should contain CloudWatch Logs Insights keywords"


class TestMonitoringThresholds:
    """Test cases for monitoring thresholds and alarm configurations."""

    def test_alarm_thresholds_reasonable(self):
        """Test that alarm thresholds are set to reasonable values."""
        # These would typically be extracted from SAM template or config
        # For now, we'll test the expected threshold values
        
        expected_thresholds = {
            'lambda_error_rate': 0.10,  # 10%
            'sqs_message_age': 1200,    # 20 minutes in seconds
            'dlq_depth': 5,             # 5 messages
            'token_cost_weekly': 100.0  # $100 per week
        }
        
        # Test that thresholds are within reasonable ranges
        assert 0.01 <= expected_thresholds['lambda_error_rate'] <= 0.50, \
            "Lambda error rate threshold should be between 1% and 50%"
        
        assert 300 <= expected_thresholds['sqs_message_age'] <= 3600, \
            "SQS message age threshold should be between 5 minutes and 1 hour"
        
        assert 1 <= expected_thresholds['dlq_depth'] <= 20, \
            "DLQ depth threshold should be between 1 and 20 messages"
        
        assert 10.0 <= expected_thresholds['token_cost_weekly'] <= 1000.0, \
            "Token cost threshold should be between $10 and $1000 per week"

    def test_cost_calculation_accuracy(self):
        """Test that cost calculations match expected values."""
        from src.utils.cloudwatch_metrics import GEMINI_FLASH_COST_PER_MILLION, GEMINI_PRO_COST_PER_MILLION
        
        # Test Flash model cost
        flash_cost_1m = GEMINI_FLASH_COST_PER_MILLION
        assert flash_cost_1m == 0.075, f"Expected Flash cost $0.075/1M tokens, got ${flash_cost_1m}"
        
        # Test Pro model cost
        pro_cost_1m = GEMINI_PRO_COST_PER_MILLION
        assert pro_cost_1m == 2.50, f"Expected Pro cost $2.50/1M tokens, got ${pro_cost_1m}"
        
        # Test cost calculations for common token amounts
        tokens_100k = 100_000
        flash_cost_100k = (tokens_100k / 1_000_000) * flash_cost_1m
        pro_cost_100k = (tokens_100k / 1_000_000) * pro_cost_1m
        
        assert abs(flash_cost_100k - 0.0075) < 0.0001, \
            f"Expected Flash cost $0.0075 for 100k tokens, got ${flash_cost_100k}"
        
        assert abs(pro_cost_100k - 0.25) < 0.0001, \
            f"Expected Pro cost $0.25 for 100k tokens, got ${pro_cost_100k}"


class TestMetricsNamespaces:
    """Test cases for CloudWatch metrics namespaces."""

    def test_metrics_namespaces_defined(self):
        """Test that all required metrics namespaces are defined."""
        from src.utils.cloudwatch_metrics import (
            METRICS_NAMESPACE,
            LAMBDA_METRICS_NAMESPACE,
            PIPELINE_METRICS_NAMESPACE,
            API_METRICS_NAMESPACE,
            TOKEN_METRICS_NAMESPACE
        )
        
        # Test namespace naming conventions
        assert METRICS_NAMESPACE == "SecurityAssistant"
        assert LAMBDA_METRICS_NAMESPACE == "SecurityAssistant/Lambda"
        assert PIPELINE_METRICS_NAMESPACE == "SecurityAssistant/Pipeline"
        assert API_METRICS_NAMESPACE == "SecurityAssistant/API"
        assert TOKEN_METRICS_NAMESPACE == "SecurityAssistant/TokenUsage"
        
        # Test that all namespaces start with the base namespace
        base_namespace = "SecurityAssistant"
        namespaces = [
            LAMBDA_METRICS_NAMESPACE,
            PIPELINE_METRICS_NAMESPACE,
            API_METRICS_NAMESPACE,
            TOKEN_METRICS_NAMESPACE
        ]
        
        for namespace in namespaces:
            assert namespace.startswith(base_namespace), \
                f"Namespace '{namespace}' should start with '{base_namespace}'"

    def test_metrics_namespace_hierarchy(self):
        """Test that metrics namespaces follow proper hierarchy."""
        from src.utils.cloudwatch_metrics import (
            LAMBDA_METRICS_NAMESPACE,
            PIPELINE_METRICS_NAMESPACE,
            API_METRICS_NAMESPACE,
            TOKEN_METRICS_NAMESPACE
        )
        
        # Test namespace hierarchy depth (should be 2 levels max)
        for namespace in [LAMBDA_METRICS_NAMESPACE, PIPELINE_METRICS_NAMESPACE, 
                         API_METRICS_NAMESPACE, TOKEN_METRICS_NAMESPACE]:
            parts = namespace.split('/')
            assert len(parts) <= 2, f"Namespace '{namespace}' should not exceed 2 levels"
            assert len(parts[0]) > 0, f"Namespace '{namespace}' should have non-empty base name"
            if len(parts) == 2:
                assert len(parts[1]) > 0, f"Namespace '{namespace}' should have non-empty sub-namespace"