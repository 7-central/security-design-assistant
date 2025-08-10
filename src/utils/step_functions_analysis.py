"""
Step Functions evaluation utility for analyzing processing workflows.
Provides analysis and recommendations for breaking complex processing into steps.
"""

import json
import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class ProcessingStageAnalysis:
    """Analysis data for a single processing stage."""
    name: str
    average_duration: float
    max_duration: float
    min_duration: float
    success_rate: float
    memory_usage_mb: Optional[int]
    timeout_risk: str  # 'low', 'medium', 'high'
    complexity: str    # 'simple', 'moderate', 'complex'


@dataclass
class WorkflowRecommendation:
    """Recommendation for workflow optimization."""
    current_architecture: str
    recommended_architecture: str
    reasoning: str
    estimated_cost_impact: str
    implementation_complexity: str
    benefits: List[str]
    trade_offs: List[str]


class StepFunctionsAnalyzer:
    """Analyzer for evaluating Step Functions migration recommendations."""
    
    # Processing stage timing thresholds (seconds)
    STAGE_TIMEOUT_THRESHOLDS = {
        'pdf_processing': 120,        # 2 minutes
        'context_processing': 180,    # 3 minutes  
        'drawing_analysis': 600,      # 10 minutes
        'excel_generation': 300,      # 5 minutes
        'evaluation': 240            # 4 minutes
    }
    
    # Lambda timeout limit
    LAMBDA_TIMEOUT_LIMIT = 900  # 15 minutes
    SAFE_TIMEOUT_THRESHOLD = 720  # 12 minutes (80% of limit)
    
    def __init__(self):
        """Initialize the analyzer."""
        self.stage_analyses: Dict[str, ProcessingStageAnalysis] = {}
        
    def analyze_processing_stages(self, job_history: List[Dict]) -> Dict[str, ProcessingStageAnalysis]:
        """
        Analyze processing stages from historical job data.
        
        Args:
            job_history: List of completed job records with timing data
            
        Returns:
            Dictionary mapping stage names to analysis results
        """
        
        # Group timing data by stage
        stage_timings = {
            'pdf_processing': [],
            'context_processing': [],  
            'drawing_analysis': [],
            'excel_generation': [],
            'evaluation': []
        }
        
        stage_success_rates = {stage: {'success': 0, 'total': 0} for stage in stage_timings.keys()}
        
        # Extract timing data from job history
        for job in job_history:
            processing_results = job.get('processing_results', {})
            
            # PDF processing timing
            if 'pdf_processing_time_seconds' in job.get('metadata', {}):
                pdf_time = job['metadata']['pdf_processing_time_seconds']
                stage_timings['pdf_processing'].append(pdf_time)
                stage_success_rates['pdf_processing']['total'] += 1
                if job.get('status') != 'failed':
                    stage_success_rates['pdf_processing']['success'] += 1
            
            # Other stage timings (would need to be extracted from logs in real implementation)
            # This is a simplified version for demonstration
            total_time = job.get('total_processing_time_seconds', 0)
            if total_time > 0:
                # Estimate stage times based on typical distributions
                estimated_timings = self._estimate_stage_timings(total_time, processing_results)
                
                for stage, estimated_time in estimated_timings.items():
                    if stage in stage_timings:
                        stage_timings[stage].append(estimated_time)
                        stage_success_rates[stage]['total'] += 1
                        if job.get('status') != 'failed':
                            stage_success_rates[stage]['success'] += 1
        
        # Analyze each stage
        analyses = {}
        for stage, timings in stage_timings.items():
            if timings:  # Only analyze stages with data
                analyses[stage] = self._analyze_stage(stage, timings, stage_success_rates[stage])
        
        self.stage_analyses = analyses
        return analyses
    
    def _estimate_stage_timings(self, total_time: float, processing_results: Dict) -> Dict[str, float]:
        """Estimate individual stage timings from total processing time."""
        
        # Typical time distribution percentages based on pipeline analysis
        distributions = {
            'pdf_processing': 0.15,      # 15% - PDF extraction
            'context_processing': 0.10,  # 10% - Context analysis
            'drawing_analysis': 0.50,    # 50% - Main AI processing
            'excel_generation': 0.20,    # 20% - Excel creation  
            'evaluation': 0.05           # 5% - Quality evaluation
        }
        
        # Adjust based on actual results if available
        if 'context' not in processing_results:
            # No context processing, redistribute time
            distributions['context_processing'] = 0.0
            distributions['drawing_analysis'] += 0.05
            distributions['excel_generation'] += 0.05
        
        return {stage: total_time * percentage for stage, percentage in distributions.items()}
    
    def _analyze_stage(
        self, 
        stage_name: str, 
        timings: List[float], 
        success_data: Dict[str, int]
    ) -> ProcessingStageAnalysis:
        """Analyze a single processing stage."""
        
        avg_duration = sum(timings) / len(timings)
        max_duration = max(timings)
        min_duration = min(timings)
        
        # Calculate success rate
        success_rate = (success_data['success'] / success_data['total']) if success_data['total'] > 0 else 1.0
        
        # Determine timeout risk
        timeout_threshold = self.STAGE_TIMEOUT_THRESHOLDS.get(stage_name, 300)
        if max_duration > timeout_threshold * 1.5:
            timeout_risk = 'high'
        elif avg_duration > timeout_threshold:
            timeout_risk = 'medium'
        else:
            timeout_risk = 'low'
        
        # Determine complexity
        if stage_name in ['drawing_analysis', 'excel_generation']:
            complexity = 'complex'
        elif stage_name in ['context_processing', 'evaluation']:
            complexity = 'moderate'  
        else:
            complexity = 'simple'
        
        # Estimate memory usage (simplified)
        memory_estimates = {
            'pdf_processing': 512,
            'context_processing': 256,
            'drawing_analysis': 2048,
            'excel_generation': 1024,
            'evaluation': 512
        }
        
        return ProcessingStageAnalysis(
            name=stage_name,
            average_duration=avg_duration,
            max_duration=max_duration,
            min_duration=min_duration,
            success_rate=success_rate,
            memory_usage_mb=memory_estimates.get(stage_name, 512),
            timeout_risk=timeout_risk,
            complexity=complexity
        )
    
    def generate_recommendations(self) -> List[WorkflowRecommendation]:
        """Generate workflow architecture recommendations."""
        
        recommendations = []
        
        # Calculate total processing characteristics
        total_avg_time = sum(stage.average_duration for stage in self.stage_analyses.values())
        total_max_time = sum(stage.max_duration for stage in self.stage_analyses.values())
        
        # High-risk stages (long duration or high failure rate)
        high_risk_stages = [
            stage for stage in self.stage_analyses.values()
            if stage.timeout_risk == 'high' or stage.success_rate < 0.9 or stage.average_duration > 300
        ]
        
        # Recommendation 1: Current architecture assessment
        if total_max_time < self.SAFE_TIMEOUT_THRESHOLD and len(high_risk_stages) == 0:
            recommendations.append(WorkflowRecommendation(
                current_architecture="Single Lambda Function",
                recommended_architecture="Single Lambda Function (Keep Current)",
                reasoning="Processing times are within safe Lambda limits and success rates are high",
                estimated_cost_impact="Neutral (no change)",
                implementation_complexity="None",
                benefits=[
                    "Simple architecture",
                    "Lower latency (no state transitions)",
                    "Easier debugging and monitoring",
                    "Lower operational complexity"
                ],
                trade_offs=[
                    "All-or-nothing processing (no partial recovery)",
                    "Limited ability to scale individual stages",
                    "Potential for timeout on complex documents"
                ]
            ))
        
        # Recommendation 2: Step Functions for timeout mitigation
        elif total_max_time > self.SAFE_TIMEOUT_THRESHOLD:
            recommendations.append(WorkflowRecommendation(
                current_architecture="Single Lambda Function",
                recommended_architecture="Step Functions with Multiple Lambda Steps",
                reasoning=f"Maximum processing time ({total_max_time:.1f}s) approaches Lambda timeout limit",
                estimated_cost_impact="Slight increase (~10-20% due to state transitions)",
                implementation_complexity="Medium",
                benefits=[
                    "No timeout risk (each step has independent timeout)",
                    "Partial recovery from failures",
                    "Better observability of processing stages",
                    "Ability to retry specific stages",
                    "Independent scaling of each processing stage"
                ],
                trade_offs=[
                    "Increased architectural complexity",
                    "Higher latency due to state transitions",
                    "More complex error handling",
                    "Additional AWS service dependencies"
                ]
            ))
        
        # Recommendation 3: Hybrid approach for high-risk stages
        if len(high_risk_stages) > 0 and total_avg_time < self.SAFE_TIMEOUT_THRESHOLD:
            high_risk_names = [stage.name for stage in high_risk_stages]
            recommendations.append(WorkflowRecommendation(
                current_architecture="Single Lambda Function",
                recommended_architecture="Hybrid: Step Functions for High-Risk Stages",
                reasoning=f"Stages {high_risk_names} show high failure risk or long duration",
                estimated_cost_impact="Minimal increase (~5-10%)",
                implementation_complexity="Medium",
                benefits=[
                    f"Isolated retry logic for problematic stages: {', '.join(high_risk_names)}",
                    "Improved success rates through targeted recovery",
                    "Maintains simplicity for successful stages",
                    "Better monitoring of failure points"
                ],
                trade_offs=[
                    "Mixed architecture complexity",
                    "Selective state management required",
                    "More complex deployment and testing"
                ]
            ))
        
        # Recommendation 4: Performance optimization
        if any(stage.complexity == 'complex' for stage in self.stage_analyses.values()):
            complex_stages = [stage.name for stage in self.stage_analyses.values() if stage.complexity == 'complex']
            recommendations.append(WorkflowRecommendation(
                current_architecture="Single Lambda Function",
                recommended_architecture="Step Functions with Optimized Memory Allocation",
                reasoning=f"Complex stages ({', '.join(complex_stages)}) could benefit from dedicated resources",
                estimated_cost_impact="Optimized (potential savings through right-sizing)",
                implementation_complexity="High",
                benefits=[
                    "Right-sized memory allocation per stage",
                    "Parallel processing of independent stages",
                    "Cost optimization through efficient resource usage",
                    "Better performance isolation"
                ],
                trade_offs=[
                    "Significant architectural changes required",
                    "Complex resource management",
                    "Longer development and testing cycle"
                ]
            ))
        
        return recommendations
    
    def create_step_functions_state_machine(self) -> Dict:
        """Create a sample Step Functions state machine definition."""
        
        state_machine = {
            "Comment": "Security Design Assistant Processing Pipeline",
            "StartAt": "PDFProcessing",
            "States": {
                "PDFProcessing": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:security-assistant-pdf-processor-${Environment}",
                    "TimeoutSeconds": 300,
                    "Retry": [
                        {
                            "ErrorEquals": ["States.TaskFailed"],
                            "IntervalSeconds": 2,
                            "MaxAttempts": 3,
                            "BackoffRate": 2.0
                        }
                    ],
                    "Catch": [
                        {
                            "ErrorEquals": ["States.ALL"],
                            "Next": "ProcessingFailed",
                            "ResultPath": "$.error"
                        }
                    ],
                    "Next": "CheckContextRequired"
                },
                
                "CheckContextRequired": {
                    "Type": "Choice",
                    "Choices": [
                        {
                            "Variable": "$.context_s3_key",
                            "IsPresent": True,
                            "Next": "ContextProcessing"
                        },
                        {
                            "Variable": "$.context_text",
                            "IsPresent": True,
                            "Next": "ContextProcessing"
                        }
                    ],
                    "Default": "DrawingAnalysis"
                },
                
                "ContextProcessing": {
                    "Type": "Task", 
                    "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:security-assistant-context-processor-${Environment}",
                    "TimeoutSeconds": 300,
                    "Retry": [
                        {
                            "ErrorEquals": ["States.TaskFailed"],
                            "IntervalSeconds": 2,
                            "MaxAttempts": 2,
                            "BackoffRate": 2.0
                        }
                    ],
                    "Catch": [
                        {
                            "ErrorEquals": ["States.ALL"],
                            "Next": "DrawingAnalysis",
                            "ResultPath": "$.context_error"
                        }
                    ],
                    "Next": "DrawingAnalysis"
                },
                
                "DrawingAnalysis": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:security-assistant-drawing-analyzer-${Environment}",
                    "TimeoutSeconds": 900,
                    "Retry": [
                        {
                            "ErrorEquals": ["Lambda.ServiceException", "Lambda.AWSLambdaException"],
                            "IntervalSeconds": 2,
                            "MaxAttempts": 2,
                            "BackoffRate": 2.0
                        }
                    ],
                    "Catch": [
                        {
                            "ErrorEquals": ["States.ALL"],
                            "Next": "ProcessingFailed",
                            "ResultPath": "$.error"
                        }
                    ],
                    "Next": "ParallelGeneration"
                },
                
                "ParallelGeneration": {
                    "Type": "Parallel",
                    "Branches": [
                        {
                            "StartAt": "ExcelGeneration",
                            "States": {
                                "ExcelGeneration": {
                                    "Type": "Task",
                                    "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:security-assistant-excel-generator-${Environment}",
                                    "TimeoutSeconds": 600,
                                    "End": True
                                }
                            }
                        },
                        {
                            "StartAt": "QualityEvaluation", 
                            "States": {
                                "QualityEvaluation": {
                                    "Type": "Task",
                                    "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:security-assistant-evaluator-${Environment}",
                                    "TimeoutSeconds": 400,
                                    "End": True
                                }
                            }
                        }
                    ],
                    "Catch": [
                        {
                            "ErrorEquals": ["States.ALL"],
                            "Next": "ProcessingFailed",
                            "ResultPath": "$.error"
                        }
                    ],
                    "Next": "ProcessingComplete"
                },
                
                "ProcessingComplete": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:security-assistant-finalizer-${Environment}",
                    "TimeoutSeconds": 60,
                    "End": True
                },
                
                "ProcessingFailed": {
                    "Type": "Task",
                    "Resource": "arn:aws:lambda:${AWS::Region}:${AWS::AccountId}:function:security-assistant-failure-handler-${Environment}",
                    "TimeoutSeconds": 60,
                    "End": True
                }
            }
        }
        
        return state_machine
    
    def generate_analysis_report(self, job_history: List[Dict]) -> Dict:
        """Generate comprehensive analysis report."""
        
        # Analyze stages
        stage_analyses = self.analyze_processing_stages(job_history)
        
        # Generate recommendations  
        recommendations = self.generate_recommendations()
        
        # Create state machine definition
        state_machine = self.create_step_functions_state_machine()
        
        # Summary statistics
        total_jobs = len(job_history)
        successful_jobs = len([job for job in job_history if job.get('status') == 'completed'])
        success_rate = (successful_jobs / total_jobs) if total_jobs > 0 else 0
        
        avg_processing_time = sum(
            job.get('total_processing_time_seconds', 0) for job in job_history
        ) / total_jobs if total_jobs > 0 else 0
        
        report = {
            "analysis_timestamp": int(time.time()),
            "summary": {
                "total_jobs_analyzed": total_jobs,
                "overall_success_rate": success_rate,
                "average_processing_time_seconds": avg_processing_time,
                "recommendation_count": len(recommendations)
            },
            "stage_analyses": {name: {
                "average_duration": analysis.average_duration,
                "max_duration": analysis.max_duration,
                "success_rate": analysis.success_rate,
                "timeout_risk": analysis.timeout_risk,
                "complexity": analysis.complexity,
                "memory_usage_mb": analysis.memory_usage_mb
            } for name, analysis in stage_analyses.items()},
            "recommendations": [{
                "current_architecture": rec.current_architecture,
                "recommended_architecture": rec.recommended_architecture,
                "reasoning": rec.reasoning,
                "cost_impact": rec.estimated_cost_impact,
                "implementation_complexity": rec.implementation_complexity,
                "benefits": rec.benefits,
                "trade_offs": rec.trade_offs
            } for rec in recommendations],
            "sample_state_machine": state_machine
        }
        
        return report


def run_step_functions_analysis(job_history_file: str) -> Dict:
    """
    Run Step Functions analysis on historical job data.
    
    Args:
        job_history_file: Path to file containing job history data
        
    Returns:
        Analysis report
    """
    
    try:
        # Load job history (in real implementation, this would come from DynamoDB)
        with open(job_history_file, 'r') as f:
            job_history = json.load(f)
        
        analyzer = StepFunctionsAnalyzer()
        report = analyzer.generate_analysis_report(job_history)
        
        logger.info(f"Generated Step Functions analysis for {len(job_history)} jobs")
        return report
        
    except Exception as e:
        logger.error(f"Error running Step Functions analysis: {e}")
        raise


if __name__ == "__main__":
    # Example usage
    import time
    
    # Sample job history for testing
    sample_jobs = [
        {
            "job_id": "job_001",
            "status": "completed",
            "total_processing_time_seconds": 450,
            "metadata": {"pdf_processing_time_seconds": 67.5},
            "processing_results": {"context": {"completed": True}}
        },
        {
            "job_id": "job_002", 
            "status": "completed",
            "total_processing_time_seconds": 780,
            "metadata": {"pdf_processing_time_seconds": 120.0},
            "processing_results": {"context": {"completed": True}}
        },
        {
            "job_id": "job_003",
            "status": "failed",
            "total_processing_time_seconds": 300,
            "metadata": {"pdf_processing_time_seconds": 45.0},
            "processing_results": {}
        }
    ]
    
    analyzer = StepFunctionsAnalyzer()
    report = analyzer.generate_analysis_report(sample_jobs)
    
    print(json.dumps(report, indent=2))