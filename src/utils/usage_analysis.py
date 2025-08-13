"""
Usage analysis and capacity planning utility for serverless optimization.
"""

import json
import logging
import statistics
from datetime import datetime, timedelta
from typing import Any

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger(__name__)


class UsageAnalyzer:
    """Analyzes usage patterns and provides capacity planning recommendations."""

    def __init__(self, environment: str):
        """Initialize usage analyzer.

        Args:
            environment: Environment name (dev, staging, prod)
        """
        self.environment = environment
        self.cloudwatch = boto3.client('cloudwatch')
        self.lambda_client = boto3.client('lambda')
        self.dynamodb = boto3.client('dynamodb')
        self.s3 = boto3.client('s3')

        # Function names for this environment
        self.function_names = [
            f'security-assistant-api-{environment}',
            f'security-assistant-worker-{environment}',
            f'security-assistant-status-{environment}',
            f'security-assistant-dlq-processor-{environment}',
            f'security-assistant-warmer-{environment}'
        ]

    async def analyze_lambda_usage_patterns(self, days: int = 30) -> dict[str, Any]:
        """Analyze Lambda function usage patterns over specified period.

        Args:
            days: Number of days to analyze

        Returns:
            Usage analysis with recommendations
        """
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)

        analysis = {
            'analysis_period': f'{days} days',
            'generated_at': end_time.isoformat(),
            'functions': {},
            'summary': {
                'total_invocations': 0,
                'total_duration_hours': 0,
                'total_estimated_cost': 0,
                'peak_concurrency': 0,
                'avg_daily_invocations': 0
            },
            'recommendations': []
        }

        for function_name in self.function_names:
            try:
                function_analysis = await self._analyze_single_function(
                    function_name, start_time, end_time
                )
                analysis['functions'][function_name] = function_analysis

                # Aggregate summary stats
                analysis['summary']['total_invocations'] += function_analysis['total_invocations']
                analysis['summary']['total_duration_hours'] += function_analysis['total_duration_hours']
                analysis['summary']['total_estimated_cost'] += function_analysis['estimated_cost']
                analysis['summary']['peak_concurrency'] = max(
                    analysis['summary']['peak_concurrency'],
                    function_analysis.get('peak_concurrent_executions', 0)
                )

            except Exception as e:
                logger.error(f"Failed to analyze function {function_name}: {e}")
                analysis['functions'][function_name] = {'error': str(e)}

        # Calculate averages and generate recommendations
        if days > 0:
            analysis['summary']['avg_daily_invocations'] = analysis['summary']['total_invocations'] / days

        analysis['recommendations'] = await self._generate_capacity_recommendations(analysis)

        return analysis

    async def _analyze_single_function(
        self,
        function_name: str,
        start_time: datetime,
        end_time: datetime
    ) -> dict[str, Any]:
        """Analyze a single Lambda function's usage patterns."""

        # Get invocation metrics
        invocation_data = await self._get_cloudwatch_metric(
            'AWS/Lambda', 'Invocations', 'FunctionName', function_name,
            start_time, end_time, 3600  # 1 hour periods
        )

        # Get duration metrics
        duration_data = await self._get_cloudwatch_metric(
            'AWS/Lambda', 'Duration', 'FunctionName', function_name,
            start_time, end_time, 3600
        )

        # Get concurrent execution metrics
        concurrency_data = await self._get_cloudwatch_metric(
            'AWS/Lambda', 'ConcurrentExecutions', 'FunctionName', function_name,
            start_time, end_time, 3600
        )

        # Get memory utilization if available
        memory_data = await self._get_cloudwatch_metric(
            'AWS/Lambda', 'MemoryUtilization', 'FunctionName', function_name,
            start_time, end_time, 3600
        )

        # Calculate statistics
        invocations = [dp['Sum'] for dp in invocation_data]
        durations = [dp['Average'] for dp in duration_data if dp['Average'] > 0]
        concurrency = [dp['Maximum'] for dp in concurrency_data]
        memory_util = [dp['Average'] for dp in memory_data if dp['Average'] > 0]

        total_invocations = sum(invocations)
        total_duration_ms = sum(d * i for d, i in zip(durations, invocations, strict=False) if d and i)
        total_duration_hours = (total_duration_ms / 1000 / 3600) if total_duration_ms > 0 else 0

        # Get current function configuration
        try:
            config_response = self.lambda_client.get_function_configuration(FunctionName=function_name)
            current_memory = config_response['MemorySize']
            current_timeout = config_response['Timeout']
            architecture = config_response.get('Architectures', ['x86_64'])[0]
        except ClientError:
            current_memory = 0
            current_timeout = 0
            architecture = 'unknown'

        # Calculate cost estimate (ARM64 pricing)
        cost_per_request = 0.0000002  # $0.0000002 per request
        cost_per_gb_second = 0.0000133334 if architecture == 'arm64' else 0.0000166667

        request_cost = total_invocations * cost_per_request
        compute_cost = (total_duration_hours * (current_memory / 1024) * cost_per_gb_second * 3600)
        total_cost = request_cost + compute_cost

        return {
            'total_invocations': int(total_invocations),
            'total_duration_hours': round(total_duration_hours, 4),
            'avg_duration_ms': round(statistics.mean(durations), 2) if durations else 0,
            'p95_duration_ms': round(self._percentile(durations, 0.95), 2) if durations else 0,
            'p99_duration_ms': round(self._percentile(durations, 0.99), 2) if durations else 0,
            'peak_concurrent_executions': int(max(concurrency)) if concurrency else 0,
            'avg_concurrent_executions': round(statistics.mean(concurrency), 2) if concurrency else 0,
            'current_memory_mb': current_memory,
            'current_timeout_seconds': current_timeout,
            'architecture': architecture,
            'avg_memory_utilization_percent': round(statistics.mean(memory_util), 2) if memory_util else None,
            'estimated_cost': round(total_cost, 4),
            'cost_breakdown': {
                'request_cost': round(request_cost, 4),
                'compute_cost': round(compute_cost, 4)
            },
            'usage_patterns': self._analyze_usage_patterns(invocations),
            'optimization_opportunities': self._identify_optimizations(
                durations, concurrency, memory_util, current_memory
            )
        }

    def _percentile(self, data: list[float], percentile: float) -> float:
        """Calculate percentile of data."""
        if not data:
            return 0
        sorted_data = sorted(data)
        index = int(percentile * len(sorted_data))
        if index >= len(sorted_data):
            return sorted_data[-1]
        return sorted_data[index]

    def _analyze_usage_patterns(self, hourly_invocations: list[float]) -> dict[str, Any]:
        """Analyze usage patterns from hourly invocation data."""
        if not hourly_invocations:
            return {'pattern': 'no_data'}

        # Calculate statistics
        total_invocations = sum(hourly_invocations)
        non_zero_hours = len([x for x in hourly_invocations if x > 0])
        zero_hours = len(hourly_invocations) - non_zero_hours

        avg_invocations = statistics.mean(hourly_invocations)
        peak_invocations = max(hourly_invocations)

        # Determine usage pattern
        if non_zero_hours < len(hourly_invocations) * 0.1:
            pattern = 'sporadic'
        elif zero_hours < len(hourly_invocations) * 0.1:
            pattern = 'continuous'
        elif peak_invocations > avg_invocations * 5:
            pattern = 'bursty'
        else:
            pattern = 'regular'

        return {
            'pattern': pattern,
            'total_invocations': int(total_invocations),
            'active_hours': non_zero_hours,
            'idle_hours': zero_hours,
            'avg_invocations_per_hour': round(avg_invocations, 2),
            'peak_invocations_per_hour': int(peak_invocations),
            'utilization_rate': round(non_zero_hours / len(hourly_invocations), 2)
        }

    def _identify_optimizations(
        self,
        durations: list[float],
        concurrency: list[float],
        memory_util: list[float],
        current_memory: int
    ) -> list[str]:
        """Identify optimization opportunities."""
        optimizations = []

        if durations:
            avg_duration = statistics.mean(durations)
            if avg_duration > 10000:  # > 10 seconds
                optimizations.append('Consider increasing memory to reduce duration')
            elif avg_duration < 1000 and current_memory > 512:  # < 1 second
                optimizations.append('Consider reducing memory allocation')

        if memory_util:
            avg_memory_util = statistics.mean(memory_util)
            if avg_memory_util > 80:
                optimizations.append('High memory utilization - consider increasing memory')
            elif avg_memory_util < 30 and current_memory > 512:
                optimizations.append('Low memory utilization - consider reducing memory')

        if concurrency:
            max_concurrency = max(concurrency)
            if max_concurrency > 50:
                optimizations.append('High concurrency - consider reserved capacity')
            elif max_concurrency < 5:
                optimizations.append('Low concurrency - provisioned concurrency may not be needed')

        return optimizations

    async def _get_cloudwatch_metric(
        self,
        namespace: str,
        metric_name: str,
        dimension_name: str,
        dimension_value: str,
        start_time: datetime,
        end_time: datetime,
        period: int
    ) -> list[dict[str, Any]]:
        """Get CloudWatch metric data."""
        try:
            response = self.cloudwatch.get_metric_statistics(
                Namespace=namespace,
                MetricName=metric_name,
                Dimensions=[
                    {'Name': dimension_name, 'Value': dimension_value}
                ],
                StartTime=start_time,
                EndTime=end_time,
                Period=period,
                Statistics=['Sum', 'Average', 'Maximum']
            )
            return response.get('Datapoints', [])
        except Exception as e:
            logger.warning(f"Failed to get metric {metric_name} for {dimension_value}: {e}")
            return []

    async def _generate_capacity_recommendations(self, analysis: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate capacity planning recommendations based on analysis."""
        recommendations = []

        summary = analysis['summary']
        functions = analysis['functions']

        # Overall cost optimization recommendations
        if summary['total_estimated_cost'] > 100:  # > $100/month
            recommendations.append({
                'category': 'cost_optimization',
                'priority': 'high',
                'title': 'Significant monthly costs detected',
                'description': f"Current estimated cost: ${summary['total_estimated_cost']:.2f}/month",
                'action': 'Review high-cost functions and consider memory optimization'
            })

        # Concurrency recommendations
        if summary['peak_concurrency'] > 100:
            recommendations.append({
                'category': 'capacity_planning',
                'priority': 'medium',
                'title': 'High peak concurrency detected',
                'description': f"Peak concurrency: {summary['peak_concurrency']} executions",
                'action': 'Consider reserved concurrency and DLQ monitoring'
            })

        # Function-specific recommendations
        for func_name, func_data in functions.items():
            if isinstance(func_data, dict) and 'error' not in func_data:
                # Memory optimization recommendations
                if func_data.get('avg_memory_utilization_percent', 0) > 85:
                    recommendations.append({
                        'category': 'performance',
                        'priority': 'medium',
                        'title': f'High memory utilization in {func_name}',
                        'description': (
                            f"Average memory utilization: "
                            f"{func_data['avg_memory_utilization_percent']:.1f}%"
                        ),
                        'action': f'Increase memory from {func_data["current_memory_mb"]}MB'
                    })

                # Duration optimization
                if func_data.get('p95_duration_ms', 0) > 30000:  # > 30 seconds
                    recommendations.append({
                        'category': 'performance',
                        'priority': 'high',
                        'title': f'Slow execution time in {func_name}',
                        'description': f"P95 duration: {func_data['p95_duration_ms']:.0f}ms",
                        'action': 'Investigate performance bottlenecks and consider memory increase'
                    })

                # Usage pattern recommendations
                pattern = func_data.get('usage_patterns', {}).get('pattern', 'unknown')
                if pattern == 'sporadic' and 'api' in func_name:
                    recommendations.append({
                        'category': 'cost_optimization',
                        'priority': 'low',
                        'title': f'Sporadic usage pattern in {func_name}',
                        'description': 'Function has low utilization',
                        'action': 'Consider reducing provisioned concurrency or memory'
                    })

        return recommendations

    async def generate_capacity_report(self, days: int = 30) -> dict[str, Any]:
        """Generate comprehensive capacity planning report.

        Args:
            days: Number of days to analyze

        Returns:
            Comprehensive capacity planning report
        """
        logger.info(f"Generating capacity report for {self.environment} environment")

        # Get usage analysis
        usage_analysis = await self.analyze_lambda_usage_patterns(days)

        # Get current provisioned resources
        provisioned_resources = await self._get_provisioned_resources()

        # Generate cost projections
        cost_projections = self._generate_cost_projections(usage_analysis)

        # Create final report
        report = {
            'report_type': 'capacity_planning',
            'environment': self.environment,
            'analysis_period_days': days,
            'generated_at': datetime.utcnow().isoformat(),
            'usage_analysis': usage_analysis,
            'provisioned_resources': provisioned_resources,
            'cost_projections': cost_projections,
            'executive_summary': self._create_executive_summary(usage_analysis, cost_projections)
        }

        logger.info(f"Capacity report generated with {len(usage_analysis['recommendations'])} recommendations")
        return report

    async def _get_provisioned_resources(self) -> dict[str, Any]:
        """Get information about currently provisioned resources."""
        resources = {
            'lambda_functions': {},
            'dynamodb_tables': {},
            's3_buckets': {}
        }

        # Get Lambda function configurations
        for func_name in self.function_names:
            try:
                config = self.lambda_client.get_function_configuration(FunctionName=func_name)
                resources['lambda_functions'][func_name] = {
                    'memory_mb': config['MemorySize'],
                    'timeout_seconds': config['Timeout'],
                    'runtime': config['Runtime'],
                    'architecture': config.get('Architectures', ['x86_64'])[0],
                    'reserved_concurrency': config.get('ReservedConcurrencyExecutions'),
                    'provisioned_concurrency': None  # Would need additional call to get this
                }
            except ClientError as e:
                logger.warning(f"Could not get config for {func_name}: {e}")

        return resources

    def _generate_cost_projections(self, usage_analysis: dict[str, Any]) -> dict[str, Any]:
        """Generate cost projections based on usage analysis."""
        current_monthly_cost = usage_analysis['summary']['total_estimated_cost']

        # Project costs for different scenarios
        projections = {
            'current_monthly': round(current_monthly_cost, 2),
            'projected_yearly': round(current_monthly_cost * 12, 2),
            'scenarios': {
                'optimized': {
                    'monthly_cost': round(current_monthly_cost * 0.8, 2),  # 20% reduction
                    'savings_monthly': round(current_monthly_cost * 0.2, 2),
                    'description': 'With memory and concurrency optimizations'
                },
                'growth_50_percent': {
                    'monthly_cost': round(current_monthly_cost * 1.5, 2),
                    'additional_monthly': round(current_monthly_cost * 0.5, 2),
                    'description': 'With 50% usage growth'
                },
                'growth_100_percent': {
                    'monthly_cost': round(current_monthly_cost * 2, 2),
                    'additional_monthly': round(current_monthly_cost, 2),
                    'description': 'With 100% usage growth'
                }
            }
        }

        return projections

    def _create_executive_summary(
        self,
        usage_analysis: dict[str, Any],
        cost_projections: dict[str, Any]
    ) -> dict[str, Any]:
        """Create executive summary of the capacity report."""
        summary = usage_analysis['summary']
        high_priority_recs = [
            r for r in usage_analysis['recommendations']
            if r.get('priority') == 'high'
        ]

        return {
            'key_metrics': {
                'total_monthly_invocations': int(summary['avg_daily_invocations'] * 30),
                'current_monthly_cost': cost_projections['current_monthly'],
                'peak_concurrency': summary['peak_concurrency'],
                'total_functions': len([
                    f for f in usage_analysis['functions']
                    if 'error' not in usage_analysis['functions'][f]
                ])
            },
            'critical_findings': {
                'high_priority_issues': len(high_priority_recs),
                'cost_optimization_potential': (
                    f"${cost_projections['scenarios']['optimized']['savings_monthly']:.2f}/month"
                ),
                'performance_issues': len([
                    r for r in usage_analysis['recommendations']
                    if r.get('category') == 'performance'
                ])
            },
            'next_actions': [
                'Review and implement high-priority recommendations',
                'Set up automated monitoring for cost anomalies',
                'Schedule monthly capacity reviews',
                'Consider implementing usage-based scaling'
            ]
        }


# CLI interface for running analysis
async def run_usage_analysis(environment: str, days: int = 30) -> None:
    """Run usage analysis for specified environment.

    Args:
        environment: Environment to analyze
        days: Number of days to analyze
    """
    analyzer = UsageAnalyzer(environment)
    report = await analyzer.generate_capacity_report(days)

    # Output report as JSON
    print(json.dumps(report, indent=2, default=str))


if __name__ == '__main__':
    import asyncio
    import sys

    if len(sys.argv) < 2:
        print("Usage: python usage_analysis.py <environment> [days]")
        sys.exit(1)

    env = sys.argv[1]
    analysis_days = int(sys.argv[2]) if len(sys.argv) > 2 else 30

    asyncio.run(run_usage_analysis(env, analysis_days))
