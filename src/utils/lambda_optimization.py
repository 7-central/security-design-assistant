"""
Lambda optimization utilities for power tuning and performance analysis.
"""

import json
import logging
import os
from typing import Any

import boto3

logger = logging.getLogger(__name__)


class LambdaPowerTuner:
    """Utility for Lambda power tuning and memory optimization."""

    def __init__(self):
        """Initialize Lambda Power Tuner with CloudWatch and Lambda clients."""
        self.cloudwatch = boto3.client('cloudwatch')
        self.lambda_client = boto3.client('lambda')

    def analyze_function_performance(self, function_name: str, days: int = 7) -> dict[str, Any]:
        """
        Analyze Lambda function performance metrics from CloudWatch.

        Args:
            function_name: Name of the Lambda function
            days: Number of days of historical data to analyze

        Returns:
            Performance analysis results
        """
        try:
            import datetime
            end_time = datetime.datetime.utcnow()
            start_time = end_time - datetime.timedelta(days=days)

            # Get duration metrics
            duration_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Duration',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,  # 1 hour intervals
                Statistics=['Average', 'Maximum', 'Minimum']
            )

            # Get invocation metrics
            invocation_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Invocations',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )

            # Get error metrics
            error_response = self.cloudwatch.get_metric_statistics(
                Namespace='AWS/Lambda',
                MetricName='Errors',
                Dimensions=[
                    {'Name': 'FunctionName', 'Value': function_name}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=3600,
                Statistics=['Sum']
            )

            # Calculate averages and recommendations
            duration_stats = duration_response.get('Datapoints', [])
            invocation_stats = invocation_response.get('Datapoints', [])
            error_stats = error_response.get('Datapoints', [])

            avg_duration = sum(dp['Average'] for dp in duration_stats) / len(duration_stats) if duration_stats else 0
            max_duration = max((dp['Maximum'] for dp in duration_stats), default=0)
            total_invocations = sum(dp['Sum'] for dp in invocation_stats)
            total_errors = sum(dp['Sum'] for dp in error_stats)

            error_rate = (total_errors / total_invocations) * 100 if total_invocations > 0 else 0

            analysis = {
                'function_name': function_name,
                'analysis_period_days': days,
                'performance_metrics': {
                    'average_duration_ms': round(avg_duration, 2),
                    'maximum_duration_ms': round(max_duration, 2),
                    'total_invocations': int(total_invocations),
                    'total_errors': int(total_errors),
                    'error_rate_percent': round(error_rate, 2)
                },
                'recommendations': self._generate_memory_recommendations(avg_duration, max_duration, error_rate)
            }

            logger.info(f"Performance analysis completed for {function_name}")
            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze function performance: {e}")
            raise

    def _generate_memory_recommendations(self, avg_duration: float, max_duration: float, error_rate: float) -> dict[str, Any]:
        """
        Generate memory optimization recommendations based on performance metrics.

        Args:
            avg_duration: Average execution duration in ms
            max_duration: Maximum execution duration in ms
            error_rate: Error rate percentage

        Returns:
            Memory recommendations
        """
        recommendations = {
            'current_performance': 'unknown',
            'suggested_action': 'monitor',
            'memory_adjustment': 'maintain',
            'reasoning': []
        }

        # Performance-based recommendations
        if avg_duration < 1000:  # < 1 second
            recommendations['current_performance'] = 'excellent'
            if max_duration < 2000:
                recommendations['suggested_action'] = 'consider_reducing_memory'
                recommendations['memory_adjustment'] = 'reduce_by_25_percent'
                recommendations['reasoning'].append('Consistently fast execution suggests over-provisioning')

        elif avg_duration < 5000:  # 1-5 seconds
            recommendations['current_performance'] = 'good'
            if error_rate < 1.0:
                recommendations['suggested_action'] = 'maintain_current'
                recommendations['memory_adjustment'] = 'maintain'
                recommendations['reasoning'].append('Good performance with low error rate')
            else:
                recommendations['suggested_action'] = 'increase_memory'
                recommendations['memory_adjustment'] = 'increase_by_25_percent'
                recommendations['reasoning'].append('High error rate may indicate memory pressure')

        elif avg_duration < 15000:  # 5-15 seconds
            recommendations['current_performance'] = 'moderate'
            recommendations['suggested_action'] = 'increase_memory'
            recommendations['memory_adjustment'] = 'increase_by_50_percent'
            recommendations['reasoning'].append('Slow execution suggests under-provisioning')

        else:  # > 15 seconds
            recommendations['current_performance'] = 'poor'
            recommendations['suggested_action'] = 'significant_increase'
            recommendations['memory_adjustment'] = 'increase_by_100_percent'
            recommendations['reasoning'].append('Very slow execution needs significant memory increase')

        # Error rate adjustments
        if error_rate > 5.0:
            recommendations['suggested_action'] = 'increase_memory'
            if 'increase' not in recommendations['memory_adjustment']:
                recommendations['memory_adjustment'] = 'increase_by_50_percent'
            recommendations['reasoning'].append(f'High error rate ({error_rate:.1f}%) indicates resource constraints')

        return recommendations

    def get_current_function_config(self, function_name: str) -> dict[str, Any]:
        """
        Get current Lambda function configuration.

        Args:
            function_name: Name of the Lambda function

        Returns:
            Function configuration details
        """
        try:
            response = self.lambda_client.get_function_configuration(
                FunctionName=function_name
            )

            config = {
                'function_name': response['FunctionName'],
                'runtime': response['Runtime'],
                'memory_size': response['MemorySize'],
                'timeout': response['Timeout'],
                'architecture': response.get('Architectures', ['x86_64'])[0],
                'last_modified': response['LastModified']
            }

            logger.info(f"Retrieved configuration for {function_name}")
            return config

        except Exception as e:
            logger.error(f"Failed to get function configuration: {e}")
            raise

    def calculate_memory_adjustment(self, current_memory: int, adjustment_type: str) -> int:
        """
        Calculate new memory size based on adjustment type.

        Args:
            current_memory: Current memory allocation in MB
            adjustment_type: Type of adjustment to make

        Returns:
            New memory size in MB
        """
        memory_options = [128, 256, 512, 768, 1024, 1280, 1536, 1792, 2048, 2304, 2560, 2816, 3072, 3328, 3584, 3840, 4096, 4352, 4608, 4864, 5120, 5376, 5632, 5888, 6144, 6400, 6656, 6912, 7168, 7424, 7680, 7936, 8192, 8448, 8704, 8960, 9216, 9472, 9728, 9984, 10240]

        if adjustment_type == 'maintain':
            return current_memory

        elif adjustment_type == 'reduce_by_25_percent':
            target = int(current_memory * 0.75)
            return min(memory_options, key=lambda x: abs(x - target))

        elif adjustment_type == 'increase_by_25_percent':
            target = int(current_memory * 1.25)
            return min(memory_options, key=lambda x: abs(x - target))

        elif adjustment_type == 'increase_by_50_percent':
            target = int(current_memory * 1.5)
            return min(memory_options, key=lambda x: abs(x - target))

        elif adjustment_type == 'increase_by_100_percent':
            target = current_memory * 2
            return min(memory_options, key=lambda x: abs(x - target))

        else:
            return current_memory

    def generate_power_tuning_report(self, function_names: list[str]) -> dict[str, Any]:
        """
        Generate comprehensive power tuning report for multiple functions.

        Args:
            function_names: List of Lambda function names to analyze

        Returns:
            Comprehensive tuning report
        """
        try:
            import datetime
            report = {
                'generated_at': str(datetime.datetime.utcnow()),
                'total_functions_analyzed': len(function_names),
                'functions': {},
                'summary': {
                    'functions_needing_optimization': 0,
                    'potential_cost_savings': 0,
                    'functions_over_provisioned': 0,
                    'functions_under_provisioned': 0
                }
            }

            for function_name in function_names:
                try:
                    # Get current config and performance analysis
                    config = self.get_current_function_config(function_name)
                    analysis = self.analyze_function_performance(function_name)

                    # Calculate recommended memory
                    current_memory = config['memory_size']
                    adjustment_type = analysis['recommendations']['memory_adjustment']
                    recommended_memory = self.calculate_memory_adjustment(current_memory, adjustment_type)

                    # Calculate cost impact (approximate)
                    cost_multiplier_current = current_memory / 1024
                    cost_multiplier_recommended = recommended_memory / 1024
                    cost_change_percent = ((cost_multiplier_recommended - cost_multiplier_current) / cost_multiplier_current) * 100

                    function_report = {
                        'current_config': config,
                        'performance_analysis': analysis,
                        'recommendations': {
                            'current_memory_mb': current_memory,
                            'recommended_memory_mb': recommended_memory,
                            'memory_change_percent': round(((recommended_memory - current_memory) / current_memory) * 100, 1),
                            'estimated_cost_change_percent': round(cost_change_percent, 1),
                            'action_required': adjustment_type != 'maintain'
                        }
                    }

                    report['functions'][function_name] = function_report

                    # Update summary statistics
                    if adjustment_type != 'maintain':
                        report['summary']['functions_needing_optimization'] += 1
                        if 'reduce' in adjustment_type:
                            report['summary']['functions_over_provisioned'] += 1
                        elif 'increase' in adjustment_type:
                            report['summary']['functions_under_provisioned'] += 1

                except Exception as e:
                    logger.error(f"Failed to analyze function {function_name}: {e}")
                    report['functions'][function_name] = {'error': str(e)}

            logger.info(f"Generated power tuning report for {len(function_names)} functions")
            return report

        except Exception as e:
            logger.error(f"Failed to generate power tuning report: {e}")
            raise


def analyze_lambda_performance() -> dict[str, Any]:
    """
    Analyze performance of all Security Assistant Lambda functions.

    Returns:
        Performance analysis report
    """
    # Get environment-specific function names
    environment = os.getenv('ENVIRONMENT', 'dev')
    function_names = [
        f'security-assistant-api-{environment}',
        f'security-assistant-worker-{environment}',
        f'security-assistant-status-{environment}',
        f'security-assistant-dlq-processor-{environment}'
    ]

    tuner = LambdaPowerTuner()
    return tuner.generate_power_tuning_report(function_names)


if __name__ == '__main__':
    # CLI interface for power tuning
    import sys

    logging.basicConfig(level=logging.INFO)

    if len(sys.argv) > 1 and sys.argv[1] == 'analyze':
        try:
            report = analyze_lambda_performance()
            print(json.dumps(report, indent=2, default=str))
        except Exception as e:
            logger.error(f"Analysis failed: {e}")
            sys.exit(1)
    else:
        print("Usage: python lambda_optimization.py analyze")
