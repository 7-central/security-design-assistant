"""
Success Criteria Validator

Implements automated success criteria checking for validation suite results,
including threshold validation, trend analysis, and alert generation.
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class SuccessCriteriaValidator:
    """Validates validation suite results against defined success criteria."""

    def __init__(self):
        self.criteria = {
            "minimum_good_rate": 0.6,  # 60% of drawings must receive "Good"
            "maximum_poor_rate": 0.2,  # No more than 20% "Poor"
            "minimum_confidence": 0.7,  # Average confidence above 0.7 (future)
            "maximum_processing_failures": 0.1,  # No more than 10% processing failures
            "minimum_component_accuracy": 0.8,  # Future: component-level accuracy
        }

        self.results_dir = Path("tests/evaluation/validation_suite/results")
        self.alerts_dir = Path("tests/evaluation/validation_suite/alerts")

    async def validate_results(self, validation_results: dict[str, Any]) -> dict[str, Any]:
        """Validate results against success criteria."""
        logger.info(f"Validating success criteria for {validation_results['validation_run_id']}")

        validation = {
            "validation_run_id": validation_results["validation_run_id"],
            "validated_at": datetime.utcnow().isoformat(),
            "criteria_version": "1.0",
            "individual_criteria": {},
            "overall_result": None,
            "recommendations": [],
            "trend_analysis": None,
            "alerts": [],
        }

        # Validate individual criteria
        assessment_summary = validation_results.get("assessment_summary", {})
        processing_summary = validation_results.get("processing_summary", {})

        # 1. Minimum Good Rate
        good_rate_result = self._validate_good_rate(assessment_summary)
        validation["individual_criteria"]["good_rate"] = good_rate_result

        # 2. Maximum Poor Rate
        poor_rate_result = self._validate_poor_rate(assessment_summary)
        validation["individual_criteria"]["poor_rate"] = poor_rate_result

        # 3. Processing Failure Rate
        failure_rate_result = self._validate_failure_rate(processing_summary)
        validation["individual_criteria"]["processing_reliability"] = failure_rate_result

        # 4. Confidence Score (placeholder for future)
        confidence_result = self._validate_confidence_score(validation_results)
        validation["individual_criteria"]["confidence_score"] = confidence_result

        # Calculate overall result
        validation["overall_result"] = self._calculate_overall_result(validation["individual_criteria"])

        # Generate recommendations
        validation["recommendations"] = self._generate_recommendations(validation["individual_criteria"])

        # Perform trend analysis if historical data exists
        validation["trend_analysis"] = await self._analyze_trends(validation_results["validation_run_id"])

        # Generate alerts for significant issues
        validation["alerts"] = self._generate_alerts(validation["individual_criteria"], validation["trend_analysis"])

        # Save validation results
        await self._save_validation_results(validation)

        return validation

    def _validate_good_rate(self, assessment_summary: dict[str, Any]) -> dict[str, Any]:
        """Validate minimum good rate criterion."""
        good_rate = assessment_summary.get("good_rate", 0)
        target = self.criteria["minimum_good_rate"]

        result = {
            "criterion": "minimum_good_rate",
            "target_value": target,
            "actual_value": good_rate,
            "passed": good_rate >= target,
            "margin": good_rate - target,
            "confidence": "high",
            "details": {
                "good_assessments": assessment_summary.get("good_assessments", 0),
                "total_assessments": assessment_summary.get("total_assessments", 0),
                "shortfall_assessments": max(
                    0,
                    int(target * assessment_summary.get("total_assessments", 0))
                    - assessment_summary.get("good_assessments", 0),
                ),
            },
        }

        if not result["passed"]:
            result["improvement_needed"] = target - good_rate
            result["priority"] = "high" if good_rate < 0.4 else "medium"

        return result

    def _validate_poor_rate(self, assessment_summary: dict[str, Any]) -> dict[str, Any]:
        """Validate maximum poor rate criterion."""
        poor_rate = assessment_summary.get("poor_rate", 0)
        target = self.criteria["maximum_poor_rate"]

        result = {
            "criterion": "maximum_poor_rate",
            "target_value": target,
            "actual_value": poor_rate,
            "passed": poor_rate <= target,
            "margin": target - poor_rate,
            "confidence": "high",
            "details": {
                "poor_assessments": assessment_summary.get("poor_assessments", 0),
                "total_assessments": assessment_summary.get("total_assessments", 0),
                "excess_poor_assessments": max(
                    0,
                    assessment_summary.get("poor_assessments", 0)
                    - int(target * assessment_summary.get("total_assessments", 0)),
                ),
            },
        }

        if not result["passed"]:
            result["reduction_needed"] = poor_rate - target
            result["priority"] = "high" if poor_rate > 0.4 else "medium"

        return result

    def _validate_failure_rate(self, processing_summary: dict[str, Any]) -> dict[str, Any]:
        """Validate processing failure rate."""
        total_drawings = processing_summary.get("total_drawings", 1)
        failed_processing = processing_summary.get("failed_processing", 0)
        failure_rate = failed_processing / total_drawings

        target = self.criteria["maximum_processing_failures"]

        result = {
            "criterion": "processing_reliability",
            "target_value": 1 - target,  # Express as reliability %
            "actual_value": 1 - failure_rate,
            "passed": failure_rate <= target,
            "margin": target - failure_rate,
            "confidence": "high",
            "details": {
                "failed_drawings": failed_processing,
                "total_drawings": total_drawings,
                "failure_rate": failure_rate,
                "reliability_rate": 1 - failure_rate,
            },
        }

        if not result["passed"]:
            result["priority"] = "critical" if failure_rate > 0.2 else "high"

        return result

    def _validate_confidence_score(self, validation_results: dict[str, Any]) -> dict[str, Any]:
        """Validate confidence score (placeholder for future implementation)."""
        # This would require confidence scores in judge evaluations
        return {
            "criterion": "confidence_score",
            "target_value": self.criteria["minimum_confidence"],
            "actual_value": None,
            "passed": None,
            "confidence": "not_implemented",
            "details": {"note": "Confidence score validation not yet implemented - requires judge confidence scores"},
        }

    def _calculate_overall_result(self, individual_criteria: dict[str, Any]) -> dict[str, Any]:
        """Calculate overall pass/fail result."""
        implemented_criteria = [
            criteria
            for criteria in individual_criteria.values()
            if criteria.get("confidence") != "not_implemented" and criteria.get("passed") is not None
        ]

        if not implemented_criteria:
            return {"status": "no_data", "passed_count": 0, "failed_count": 0, "total_count": 0, "pass_rate": 0}

        passed_count = sum(1 for criteria in implemented_criteria if criteria["passed"])
        total_count = len(implemented_criteria)

        return {
            "status": "pass" if passed_count == total_count else "fail",
            "passed_count": passed_count,
            "failed_count": total_count - passed_count,
            "total_count": total_count,
            "pass_rate": passed_count / total_count if total_count > 0 else 0,
            "critical_failures": len(
                [c for c in implemented_criteria if not c["passed"] and c.get("priority") == "critical"]
            ),
        }

    def _generate_recommendations(self, individual_criteria: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate recommendations based on failed criteria."""
        recommendations = []

        for criterion_name, criterion in individual_criteria.items():
            if criterion.get("passed") is False:
                if criterion_name == "good_rate":
                    recommendations.append(
                        {
                            "priority": criterion.get("priority", "medium"),
                            "title": "Improve Assessment Quality",
                            "description": (
                                f"Good rate of {criterion['actual_value']:.1%} "
                                f"below target of {criterion['target_value']:.1%}"
                            ),
                            "actions": [
                                "Review and enhance core extraction algorithms",
                                "Improve model training or fine-tuning",
                                "Add validation steps in processing pipeline",
                                (
                                    f"Focus on improving "
                                    f"{criterion['details']['shortfall_assessments']} additional assessments"
                                ),
                            ],
                            "impact": "high",
                            "effort": "high",
                        }
                    )

                elif criterion_name == "poor_rate":
                    recommendations.append(
                        {
                            "priority": criterion.get("priority", "medium"),
                            "title": "Reduce Poor Assessments",
                            "description": (
                                f"Poor rate of {criterion['actual_value']:.1%} "
                                f"exceeds target of {criterion['target_value']:.1%}"
                            ),
                            "actions": [
                                "Identify patterns in poor-performing drawings",
                                "Add specialized handling for challenging drawing types",
                                "Improve error detection and recovery",
                                (
                                    f"Improve {criterion['details']['excess_poor_assessments']} "
                                    "assessments from Poor to Fair/Good"
                                ),
                            ],
                            "impact": "high",
                            "effort": "medium",
                        }
                    )

                elif criterion_name == "processing_reliability":
                    recommendations.append(
                        {
                            "priority": "critical",
                            "title": "Fix Processing Failures",
                            "description": (
                                f"Processing failure rate of " f"{criterion['details']['failure_rate']:.1%} too high"
                            ),
                            "actions": [
                                "Add comprehensive error handling",
                                "Implement retry logic for transient failures",
                                "Add input validation and graceful degradation",
                                "Monitor and fix root causes of processing failures",
                            ],
                            "impact": "critical",
                            "effort": "medium",
                        }
                    )

        # Sort by priority
        priority_order = {"critical": 1, "high": 2, "medium": 3, "low": 4}
        recommendations.sort(key=lambda x: priority_order.get(x["priority"], 5))

        return recommendations

    async def _analyze_trends(self, current_run_id: str) -> dict[str, Any] | None:
        """Analyze trends across multiple validation runs."""
        try:
            # Find historical validation results
            historical_results = await self._load_historical_results()

            if len(historical_results) < 2:
                return {
                    "status": "insufficient_data",
                    "message": "Need at least 2 historical runs for trend analysis",
                    "available_runs": len(historical_results),
                }

            # Calculate trends
            trends = {}
            metrics = ["good_rate", "poor_rate", "success_rate"]

            for metric in metrics:
                values = []
                dates = []

                for result in historical_results:
                    if metric in result.get("assessment_summary", {}):
                        values.append(result["assessment_summary"][metric])
                        dates.append(result["timestamp"])

                if len(values) >= 2:
                    # Simple trend calculation
                    recent_avg = sum(values[-3:]) / min(3, len(values))  # Last 3 runs
                    overall_avg = sum(values) / len(values)
                    trend_direction = (
                        "improving"
                        if recent_avg > overall_avg
                        else "declining"
                        if recent_avg < overall_avg
                        else "stable"
                    )

                    trends[metric] = {
                        "direction": trend_direction,
                        "recent_average": recent_avg,
                        "overall_average": overall_avg,
                        "data_points": len(values),
                        "change_rate": (recent_avg - overall_avg) / overall_avg if overall_avg > 0 else 0,
                    }

            return {
                "status": "success",
                "historical_runs_analyzed": len(historical_results),
                "date_range": {"earliest": min(dates) if dates else None, "latest": max(dates) if dates else None},
                "trends": trends,
                "overall_trend": self._determine_overall_trend(trends),
            }

        except Exception as e:
            logger.error(f"Error analyzing trends: {e}")
            return {"status": "error", "message": f"Trend analysis failed: {e}"}

    async def _load_historical_results(self) -> list[dict[str, Any]]:
        """Load historical validation results for trend analysis."""
        historical_results = []

        if not self.results_dir.exists():
            return historical_results

        # Find all result files
        result_files = list(self.results_dir.glob("*_results.json"))

        for file_path in result_files:
            try:
                with open(file_path) as f:
                    result = json.load(f)
                    historical_results.append(result)
            except Exception as e:
                logger.warning(f"Failed to load {file_path}: {e}")

        # Sort by timestamp
        historical_results.sort(key=lambda x: x.get("timestamp", ""))

        return historical_results

    def _determine_overall_trend(self, trends: dict[str, Any]) -> str:
        """Determine overall system trend from individual metrics."""
        if not trends:
            return "unknown"

        improving_count = sum(1 for trend in trends.values() if trend["direction"] == "improving")
        declining_count = sum(1 for trend in trends.values() if trend["direction"] == "declining")

        if improving_count > declining_count:
            return "improving"
        elif declining_count > improving_count:
            return "declining"
        else:
            return "stable"

    def _generate_alerts(
        self, individual_criteria: dict[str, Any], trend_analysis: dict[str, Any] | None
    ) -> list[dict[str, Any]]:
        """Generate alerts for critical issues or concerning trends."""
        alerts = []

        # Critical failure alerts
        for _criterion_name, criterion in individual_criteria.items():
            if not criterion.get("passed", True) and criterion.get("priority") == "critical":
                alerts.append(
                    {
                        "level": "critical",
                        "type": "criteria_failure",
                        "title": f"Critical Failure: {criterion['criterion']}",
                        "message": "Critical success criterion failed - immediate attention required",
                        "details": criterion,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        # Multiple criteria failure alert
        failed_criteria = [c for c in individual_criteria.values() if not c.get("passed", True)]
        if len(failed_criteria) >= 2:
            alerts.append(
                {
                    "level": "high",
                    "type": "multiple_failures",
                    "title": "Multiple Success Criteria Failed",
                    "message": f"{len(failed_criteria)} success criteria failed simultaneously",
                    "details": {
                        "failed_criteria": [c["criterion"] for c in failed_criteria],
                        "count": len(failed_criteria),
                    },
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        # Trend-based alerts
        if trend_analysis and trend_analysis.get("status") == "success":
            overall_trend = trend_analysis.get("overall_trend", "unknown")

            if overall_trend == "declining":
                alerts.append(
                    {
                        "level": "medium",
                        "type": "performance_degradation",
                        "title": "Performance Degradation Detected",
                        "message": "System performance showing declining trend across multiple metrics",
                        "details": trend_analysis,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

        return alerts

    async def _save_validation_results(self, validation: dict[str, Any]) -> None:
        """Save success criteria validation results."""
        # Ensure directories exist
        self.results_dir.mkdir(parents=True, exist_ok=True)
        if validation.get("alerts"):
            self.alerts_dir.mkdir(parents=True, exist_ok=True)

        # Save validation results
        validation_file = self.results_dir / f"{validation['validation_run_id']}_success_criteria.json"
        with open(validation_file, "w") as f:
            json.dump(validation, f, indent=2, default=str)

        logger.info(f"Success criteria validation saved: {validation_file}")

        # Save alerts separately if any exist
        if validation.get("alerts"):
            alerts_file = self.alerts_dir / f"{validation['validation_run_id']}_alerts.json"
            with open(alerts_file, "w") as f:
                json.dump(
                    {
                        "validation_run_id": validation["validation_run_id"],
                        "generated_at": validation["validated_at"],
                        "alerts": validation["alerts"],
                    },
                    f,
                    indent=2,
                    default=str,
                )

            logger.warning(f"Validation alerts generated: {alerts_file}")

    def generate_pass_fail_summary(self, validation_results: dict[str, Any]) -> str:
        """Generate a concise pass/fail summary."""
        overall_result = validation_results.get("overall_result", {})
        status = overall_result.get("status", "unknown")

        summary_lines = [
            f"Success Criteria Validation: {status.upper()}",
            f"Criteria Passed: {overall_result.get('passed_count', 0)}/{overall_result.get('total_count', 0)}",
        ]

        if status == "fail":
            failed_criteria = []
            for _criterion_name, criterion in validation_results.get("individual_criteria", {}).items():
                if not criterion.get("passed", True):
                    failed_criteria.append(
                        f"  - {criterion['criterion']}: {criterion['actual_value']:.1%} "
                        f"(target: {criterion['target_value']:.1%})"
                    )

            if failed_criteria:
                summary_lines.append("Failed Criteria:")
                summary_lines.extend(failed_criteria)

        recommendations = validation_results.get("recommendations", [])
        if recommendations:
            summary_lines.append(f"Priority Recommendations: {len(recommendations)}")
            for rec in recommendations[:3]:  # Show top 3
                summary_lines.append(f"  - {rec['title']} ({rec['priority']} priority)")

        return "\n".join(summary_lines)
