"""
Validation Report Generator

Generates comprehensive reports from validation suite results, analyzing patterns,
identifying performance issues, and creating actionable recommendations.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class ValidationReportGenerator:
    """Generates comprehensive validation reports from test results."""

    def __init__(self):
        self.report_template_path = Path("tests/evaluation/validation_suite/report_template.md")

    def generate_comprehensive_report(self, validation_results: dict[str, Any]) -> dict[str, Any]:
        """Generate a comprehensive analysis report from validation results."""
        logger.info(f"Generating comprehensive report for {validation_results['validation_run_id']}")

        report = {
            "report_id": f"report_{validation_results['validation_run_id']}",
            "generated_at": datetime.utcnow().isoformat(),
            "validation_run_id": validation_results["validation_run_id"],
            "executive_summary": self._generate_executive_summary(validation_results),
            "detailed_analysis": self._analyze_detailed_results(validation_results),
            "pattern_analysis": self._analyze_patterns(validation_results),
            "performance_metrics": self._analyze_performance(validation_results),
            "success_criteria_evaluation": self._evaluate_success_criteria(validation_results),
            "recommendations": self._generate_recommendations(validation_results),
            "appendices": {
                "drawing_by_drawing_breakdown": self._create_drawing_breakdown(validation_results),
                "common_issues_catalog": self._catalog_common_issues(validation_results),
                "context_effectiveness_analysis": self._analyze_context_effectiveness(validation_results),
            },
        }

        return report

    def _generate_executive_summary(self, results: dict[str, Any]) -> dict[str, Any]:
        """Generate executive summary of validation results."""
        assessment_summary = results["assessment_summary"]
        processing_summary = results["processing_summary"]

        total_drawings = assessment_summary.get("total_assessments", 0)
        good_rate = assessment_summary.get("good_rate", 0)

        # Determine overall performance category
        if good_rate >= 0.8:
            performance_category = "Excellent"
        elif good_rate >= 0.6:
            performance_category = "Good"
        elif good_rate >= 0.4:
            performance_category = "Fair"
        else:
            performance_category = "Poor"

        success_criteria = assessment_summary.get("meets_success_criteria", {})
        overall_pass = success_criteria.get("minimum_60_percent_good", False) and success_criteria.get(
            "maximum_20_percent_poor", False
        )

        return {
            "overall_performance": performance_category,
            "success_criteria_met": overall_pass,
            "total_drawings_tested": total_drawings,
            "success_rate_percentage": round(good_rate * 100, 1),
            "average_processing_time_minutes": round(processing_summary.get("average_time_per_drawing", 0) / 60, 1),
            "key_findings": self._extract_key_findings(results),
            "priority_recommendations": self._extract_priority_recommendations(results),
        }

    def _analyze_detailed_results(self, results: dict[str, Any]) -> dict[str, Any]:
        """Analyze detailed results by assessment category."""
        drawing_results = results.get("drawing_results", [])
        completed_results = [r for r in drawing_results if r.get("status") == "completed"]

        # Group by assessment
        by_assessment = {"Good": [], "Fair": [], "Poor": [], "Unknown": []}

        for result in completed_results:
            assessment = result.get("overall_assessment", "Unknown")
            by_assessment[assessment].append(result)

        # Analyze each category
        analysis = {}
        for assessment, drawings in by_assessment.items():
            if drawings:
                analysis[assessment.lower()] = {
                    "count": len(drawings),
                    "drawings": [d["drawing_name"] for d in drawings],
                    "common_characteristics": self._identify_common_characteristics(drawings, results),
                    "average_components": sum(d.get("components_count", 0) for d in drawings) / len(drawings),
                    "average_processing_time": sum(d.get("processing_time_seconds", 0) for d in drawings)
                    / len(drawings),
                }

        return analysis

    def _analyze_patterns(self, results: dict[str, Any]) -> dict[str, Any]:
        """Analyze patterns across all test results."""
        drawing_results = results.get("drawing_results", [])
        completed_results = [r for r in drawing_results if r.get("status") == "completed"]
        test_metadata = results.get("test_metadata", {})

        if not completed_results:
            return {"error": "No completed results to analyze"}

        # Analyze by complexity
        complexity_analysis = self._analyze_by_complexity(completed_results, test_metadata)

        # Analyze by challenge type
        challenge_analysis = self._analyze_by_challenge_type(completed_results, test_metadata)

        # Analyze common strengths and weaknesses
        strengths_weaknesses = self._analyze_strengths_weaknesses(completed_results)

        # Context effectiveness
        context_effectiveness = self._analyze_context_patterns(completed_results)

        return {
            "complexity_patterns": complexity_analysis,
            "challenge_type_patterns": challenge_analysis,
            "common_strengths": strengths_weaknesses["strengths"],
            "common_weaknesses": strengths_weaknesses["weaknesses"],
            "context_effectiveness": context_effectiveness,
            "performance_correlation": self._analyze_performance_correlations(completed_results, test_metadata),
        }

    def _analyze_performance(self, results: dict[str, Any]) -> dict[str, Any]:
        """Analyze performance metrics."""
        drawing_results = results.get("drawing_results", [])
        completed_results = [r for r in drawing_results if r.get("status") == "completed"]
        processing_summary = results.get("processing_summary", {})

        if not completed_results:
            return {"error": "No performance data available"}

        processing_times = [r.get("processing_time_seconds", 0) for r in completed_results]
        component_counts = [r.get("components_count", 0) for r in completed_results]

        return {
            "processing_time_statistics": {
                "mean_seconds": sum(processing_times) / len(processing_times),
                "min_seconds": min(processing_times),
                "max_seconds": max(processing_times),
                "total_seconds": sum(processing_times),
            },
            "component_extraction_statistics": {
                "mean_components": sum(component_counts) / len(component_counts),
                "min_components": min(component_counts),
                "max_components": max(component_counts),
                "total_components": sum(component_counts),
            },
            "throughput_metrics": {
                "drawings_per_hour": 3600 / (sum(processing_times) / len(processing_times)),
                "successful_completion_rate": processing_summary.get("successful_processing", 0)
                / processing_summary.get("total_drawings", 1),
            },
            "cost_analysis": self._analyze_cost_efficiency(results),
        }

    def _evaluate_success_criteria(self, results: dict[str, Any]) -> dict[str, Any]:
        """Evaluate against defined success criteria."""
        assessment_summary = results.get("assessment_summary", {})
        criteria = assessment_summary.get("meets_success_criteria", {})

        evaluation = {
            "criteria_definition": {
                "minimum_good_rate": 0.6,
                "maximum_poor_rate": 0.2,
                "minimum_confidence": 0.7,  # If available in future
            },
            "actual_results": {
                "good_rate": assessment_summary.get("good_rate", 0),
                "poor_rate": assessment_summary.get("poor_rate", 0),
                "total_assessments": assessment_summary.get("total_assessments", 0),
            },
            "criteria_met": {
                "minimum_60_percent_good": criteria.get("minimum_60_percent_good", False),
                "maximum_20_percent_poor": criteria.get("maximum_20_percent_poor", False),
            },
            "overall_pass": criteria.get("minimum_60_percent_good", False)
            and criteria.get("maximum_20_percent_poor", False),
            "gap_analysis": self._analyze_success_criteria_gaps(assessment_summary),
        }

        return evaluation

    def _generate_recommendations(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate prioritized development recommendations."""
        recommendations = []

        # Analyze patterns to identify issues
        drawing_results = results.get("drawing_results", [])
        completed_results = [r for r in drawing_results if r.get("status") == "completed"]
        test_metadata = results.get("test_metadata", {})

        # Group poor and fair assessments by characteristics
        problem_drawings = [r for r in completed_results if r.get("overall_assessment") in ["Poor", "Fair"]]

        if problem_drawings:
            # Analyze what makes these drawings problematic
            issue_patterns = self._identify_issue_patterns(problem_drawings, test_metadata)

            for pattern in issue_patterns:
                priority = self._calculate_recommendation_priority(
                    pattern, len(problem_drawings), len(completed_results)
                )

                recommendations.append(
                    {
                        "priority": priority["level"],
                        "impact_percentage": priority["impact_percentage"],
                        "title": pattern["title"],
                        "description": pattern["description"],
                        "affected_drawings": pattern["affected_drawings"],
                        "suggested_improvements": pattern["improvements"],
                        "estimated_effort": pattern.get("effort", "Medium"),
                        "category": pattern["category"],
                    }
                )

        # Add general recommendations based on overall performance
        overall_recommendations = self._generate_general_recommendations(results)
        recommendations.extend(overall_recommendations)

        # Sort by priority
        priority_order = {"High": 1, "Medium": 2, "Low": 3}
        recommendations.sort(key=lambda x: (priority_order.get(x["priority"], 4), -x["impact_percentage"]))

        return recommendations

    def _identify_common_characteristics(self, drawings: list[dict[str, Any]], results: dict[str, Any]) -> list[str]:
        """Identify common characteristics among a group of drawings."""
        test_metadata = results.get("test_metadata", {})
        drawings_info = test_metadata.get("drawings", {})

        characteristics = []
        drawing_names = [d["drawing_name"] for d in drawings]

        # Analyze common complexity levels
        complexities = []
        for name in drawing_names:
            if name in drawings_info:
                complexities.append(drawings_info[name].get("complexity", "unknown"))

        if complexities and len(set(complexities)) == 1:
            characteristics.append(f"All {complexities[0]} complexity")

        # Analyze common challenge levels
        challenge_levels = []
        for name in drawing_names:
            if name in drawings_info:
                challenge_levels.append(drawings_info[name].get("challenge_level", "unknown"))

        if challenge_levels and len(set(challenge_levels)) == 1:
            characteristics.append(f"All {challenge_levels[0]} challenge level")

        # Analyze component count patterns
        component_counts = [d.get("components_count", 0) for d in drawings]
        if component_counts:
            avg_components = sum(component_counts) / len(component_counts)
            if avg_components < 5:
                characteristics.append("Low component count (< 5 components)")
            elif avg_components > 20:
                characteristics.append("High component count (> 20 components)")

        return characteristics

    def _analyze_by_complexity(
        self, completed_results: list[dict[str, Any]], test_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze performance by drawing complexity."""
        drawings_info = test_metadata.get("drawings", {})
        complexity_results = {}

        for result in completed_results:
            drawing_name = result["drawing_name"]
            if drawing_name in drawings_info:
                complexity = drawings_info[drawing_name].get("complexity", "unknown")
                assessment = result.get("overall_assessment", "Unknown")

                if complexity not in complexity_results:
                    complexity_results[complexity] = {"Good": 0, "Fair": 0, "Poor": 0, "Unknown": 0, "total": 0}

                complexity_results[complexity][assessment] += 1
                complexity_results[complexity]["total"] += 1

        # Calculate success rates
        for _complexity, counts in complexity_results.items():
            total = counts["total"]
            if total > 0:
                counts["good_rate"] = counts["Good"] / total
                counts["poor_rate"] = counts["Poor"] / total

        return complexity_results

    def _analyze_by_challenge_type(
        self, completed_results: list[dict[str, Any]], test_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze performance by challenge type."""
        drawings_info = test_metadata.get("drawings", {})
        challenge_results = {}

        for result in completed_results:
            drawing_name = result["drawing_name"]
            if drawing_name in drawings_info:
                test_focus = drawings_info[drawing_name].get("test_focus", "unknown")
                assessment = result.get("overall_assessment", "Unknown")

                if test_focus not in challenge_results:
                    challenge_results[test_focus] = {"Good": 0, "Fair": 0, "Poor": 0, "Unknown": 0, "total": 0}

                challenge_results[test_focus][assessment] += 1
                challenge_results[test_focus]["total"] += 1

        # Calculate success rates
        for _challenge, counts in challenge_results.items():
            total = counts["total"]
            if total > 0:
                counts["good_rate"] = counts["Good"] / total
                counts["poor_rate"] = counts["Poor"] / total

        return challenge_results

    def _analyze_strengths_weaknesses(self, completed_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze common strengths and weaknesses from judge evaluations."""
        strengths = {}
        weaknesses = {}

        for result in completed_results:
            evaluation_details = result.get("evaluation_details", {})

            # Extract insights from judge feedback
            completeness = evaluation_details.get("completeness", "")
            correctness = evaluation_details.get("correctness", "")
            context_usage = evaluation_details.get("context_usage", "")
            spatial_understanding = evaluation_details.get("spatial_understanding", "")
            false_positives = evaluation_details.get("false_positives", "")

            # Look for positive patterns (strengths)
            if "correctly" in completeness.lower() or "accurate" in completeness.lower():
                strengths["component_identification"] = strengths.get("component_identification", 0) + 1

            if "appropriate" in context_usage.lower() or "well" in context_usage.lower():
                strengths["context_integration"] = strengths.get("context_integration", 0) + 1

            if "correct" in spatial_understanding.lower():
                strengths["spatial_relationships"] = strengths.get("spatial_relationships", 0) + 1

            if "none" in false_positives.lower() or "no false" in false_positives.lower():
                strengths["precision"] = strengths.get("precision", 0) + 1

            # Look for negative patterns (weaknesses)
            if "missing" in completeness.lower() or "incomplete" in completeness.lower():
                weaknesses["incomplete_extraction"] = weaknesses.get("incomplete_extraction", 0) + 1

            if "incorrect" in correctness.lower() or "wrong" in correctness.lower():
                weaknesses["accuracy_issues"] = weaknesses.get("accuracy_issues", 0) + 1

            if "overlapping" in spatial_understanding.lower() or "confusion" in spatial_understanding.lower():
                weaknesses["spatial_confusion"] = weaknesses.get("spatial_confusion", 0) + 1

        # Convert to ranked lists
        total_results = len(completed_results)

        ranked_strengths = [
            {"area": k, "frequency": v, "percentage": round(v / total_results * 100, 1)}
            for k, v in sorted(strengths.items(), key=lambda x: x[1], reverse=True)
        ]

        ranked_weaknesses = [
            {"area": k, "frequency": v, "percentage": round(v / total_results * 100, 1)}
            for k, v in sorted(weaknesses.items(), key=lambda x: x[1], reverse=True)
        ]

        return {"strengths": ranked_strengths, "weaknesses": ranked_weaknesses}

    def _analyze_context_effectiveness(self, completed_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze effectiveness of context usage."""
        context_analysis = {"with_context": [], "without_context": []}

        for result in completed_results:
            # Check if context was used (this would need to be tracked in pipeline)
            pipeline_stages = result.get("pipeline_stages", {})
            has_context = "context_processing" in pipeline_stages

            if has_context:
                context_analysis["with_context"].append(result)
            else:
                context_analysis["without_context"].append(result)

        # Calculate comparative performance
        analysis = {}
        for context_type, results_list in context_analysis.items():
            if results_list:
                assessments = [r.get("overall_assessment", "Unknown") for r in results_list]
                good_count = assessments.count("Good")
                total = len(assessments)

                analysis[context_type] = {
                    "count": total,
                    "good_rate": good_count / total if total > 0 else 0,
                    "average_components": sum(r.get("components_count", 0) for r in results_list) / total
                    if total > 0
                    else 0,
                }

        return analysis

    def _analyze_performance_correlations(
        self, completed_results: list[dict[str, Any]], test_metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """Analyze correlations between drawing characteristics and performance."""
        correlations = {}

        # Component count vs assessment quality
        good_results = [r for r in completed_results if r.get("overall_assessment") == "Good"]
        poor_results = [r for r in completed_results if r.get("overall_assessment") == "Poor"]

        if good_results and poor_results:
            avg_components_good = sum(r.get("components_count", 0) for r in good_results) / len(good_results)
            avg_components_poor = sum(r.get("components_count", 0) for r in poor_results) / len(poor_results)

            correlations["component_count_correlation"] = {
                "good_drawings_avg_components": avg_components_good,
                "poor_drawings_avg_components": avg_components_poor,
                "insight": "Higher component count drawings"
                + (" perform better" if avg_components_good > avg_components_poor else " perform worse"),
            }

        return correlations

    def _extract_key_findings(self, results: dict[str, Any]) -> list[str]:
        """Extract key findings from the analysis."""
        findings = []

        assessment_summary = results.get("assessment_summary", {})
        good_rate = assessment_summary.get("good_rate", 0)
        poor_rate = assessment_summary.get("poor_rate", 0)

        if good_rate >= 0.8:
            findings.append(f"System performs excellently with {good_rate:.1%} good assessments")
        elif good_rate >= 0.6:
            findings.append(f"System meets success criteria with {good_rate:.1%} good assessments")
        else:
            findings.append(f"System below target with only {good_rate:.1%} good assessments")

        if poor_rate > 0.2:
            findings.append(f"Poor assessment rate of {poor_rate:.1%} exceeds acceptable threshold")

        # Add pattern-specific findings
        drawing_results = results.get("drawing_results", [])
        failed_drawings = [r for r in drawing_results if r.get("status") == "failed"]
        if failed_drawings:
            findings.append(f"{len(failed_drawings)} drawings failed processing entirely")

        return findings

    def _extract_priority_recommendations(self, results: dict[str, Any]) -> list[str]:
        """Extract top priority recommendations."""
        # This is a simplified version - the full recommendations are generated separately
        recommendations = []

        assessment_summary = results.get("assessment_summary", {})
        poor_rate = assessment_summary.get("poor_rate", 0)

        if poor_rate > 0.2:
            recommendations.append("Improve recognition accuracy for challenging drawing types")

        processing_summary = results.get("processing_summary", {})
        if processing_summary.get("failed_processing", 0) > 0:
            recommendations.append("Enhance error handling and recovery mechanisms")

        return recommendations

    def _analyze_cost_efficiency(self, results: dict[str, Any]) -> dict[str, Any]:
        """Analyze cost efficiency of the validation run."""
        cost_estimates = results.get("cost_estimates", {})
        assessment_summary = results.get("assessment_summary", {})

        total_cost = cost_estimates.get("total_estimated_cost_usd", 0)
        good_assessments = assessment_summary.get("good_assessments", 0)
        total_assessments = assessment_summary.get("total_assessments", 1)

        return {
            "total_estimated_cost": total_cost,
            "cost_per_drawing": total_cost / total_assessments if total_assessments > 0 else 0,
            "cost_per_good_assessment": total_cost / good_assessments if good_assessments > 0 else float("inf"),
            "efficiency_rating": "High"
            if good_assessments / total_assessments > 0.8
            else "Medium"
            if good_assessments / total_assessments > 0.6
            else "Low",
        }

    def _analyze_success_criteria_gaps(self, assessment_summary: dict[str, Any]) -> dict[str, Any]:
        """Analyze gaps in meeting success criteria."""
        good_rate = assessment_summary.get("good_rate", 0)
        poor_rate = assessment_summary.get("poor_rate", 0)

        gaps = {}

        if good_rate < 0.6:
            gaps["good_rate_shortfall"] = {
                "current": good_rate,
                "target": 0.6,
                "improvement_needed": 0.6 - good_rate,
                "additional_good_assessments_needed": max(
                    0,
                    int(
                        (0.6 * assessment_summary.get("total_assessments", 0))
                        - assessment_summary.get("good_assessments", 0)
                    ),
                ),
            }

        if poor_rate > 0.2:
            gaps["poor_rate_excess"] = {
                "current": poor_rate,
                "target": 0.2,
                "reduction_needed": poor_rate - 0.2,
                "poor_assessments_to_improve": max(
                    0,
                    int(
                        assessment_summary.get("poor_assessments", 0)
                        - (0.2 * assessment_summary.get("total_assessments", 0))
                    ),
                ),
            }

        return gaps

    def _identify_issue_patterns(
        self, problem_drawings: list[dict[str, Any]], test_metadata: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Identify common patterns among problematic drawings."""
        patterns = []
        drawings_info = test_metadata.get("drawings", {})

        # Group by common characteristics
        characteristics_groups = {}
        for drawing in problem_drawings:
            name = drawing["drawing_name"]
            if name in drawings_info:
                characteristics = drawings_info[name].get("characteristics", [])
                test_focus = drawings_info[name].get("test_focus", "")

                key = f"{test_focus}_{characteristics[0] if characteristics else 'unknown'}"
                if key not in characteristics_groups:
                    characteristics_groups[key] = []
                characteristics_groups[key].append(drawing)

        # Convert to patterns
        for key, drawings in characteristics_groups.items():
            if len(drawings) > 1:  # Only report patterns affecting multiple drawings
                patterns.append(
                    {
                        "title": f"Issues with {key.replace('_', ' ').title()}",
                        "description": f"{len(drawings)} drawings showing poor performance in this area",
                        "affected_drawings": [d["drawing_name"] for d in drawings],
                        "category": key.split("_")[0],
                        "improvements": [
                            "Enhance recognition algorithms for this drawing type",
                            "Improve preprocessing for these characteristics",
                            "Add specialized handling logic",
                        ],
                    }
                )

        return patterns

    def _calculate_recommendation_priority(
        self, pattern: dict[str, Any], problem_count: int, total_count: int
    ) -> dict[str, Any]:
        """Calculate priority level for a recommendation."""
        affected_count = len(pattern["affected_drawings"])
        impact_percentage = (affected_count / total_count) * 100

        if impact_percentage > 40:
            priority_level = "High"
        elif impact_percentage > 20:
            priority_level = "Medium"
        else:
            priority_level = "Low"

        return {"level": priority_level, "impact_percentage": impact_percentage}

    def _generate_general_recommendations(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate general recommendations based on overall performance."""
        recommendations = []

        assessment_summary = results.get("assessment_summary", {})
        processing_summary = results.get("processing_summary", {})

        # Performance-based recommendations
        if assessment_summary.get("good_rate", 0) < 0.8:
            recommendations.append(
                {
                    "priority": "Medium",
                    "impact_percentage": 100,
                    "title": "Improve Overall Accuracy",
                    "description": "System accuracy below optimal levels",
                    "affected_drawings": "All",
                    "suggested_improvements": [
                        "Review and enhance core extraction algorithms",
                        "Improve training data quality",
                        "Add validation steps in pipeline",
                    ],
                    "estimated_effort": "High",
                    "category": "accuracy",
                }
            )

        # Reliability recommendations
        if processing_summary.get("failed_processing", 0) > 0:
            recommendations.append(
                {
                    "priority": "High",
                    "impact_percentage": (
                        processing_summary.get("failed_processing", 0) / processing_summary.get("total_drawings", 1)
                    )
                    * 100,
                    "title": "Improve System Reliability",
                    "description": "Some drawings failed to process entirely",
                    "affected_drawings": "Failed processing cases",
                    "suggested_improvements": [
                        "Add comprehensive error handling",
                        "Implement graceful degradation",
                        "Add retry mechanisms for transient failures",
                    ],
                    "estimated_effort": "Medium",
                    "category": "reliability",
                }
            )

        return recommendations

    def _create_drawing_breakdown(self, results: dict[str, Any]) -> list[dict[str, Any]]:
        """Create detailed breakdown for each drawing."""
        drawing_results = results.get("drawing_results", [])
        test_metadata = results.get("test_metadata", {})
        drawings_info = test_metadata.get("drawings", {})

        breakdown = []
        for result in drawing_results:
            name = result["drawing_name"]
            drawing_info = drawings_info.get(name, {})

            breakdown.append(
                {
                    "drawing_name": name,
                    "expected_assessment": drawing_info.get("expected_assessment", "Unknown"),
                    "actual_assessment": result.get("overall_assessment", "Unknown"),
                    "components_found": result.get("components_count", 0),
                    "processing_time": result.get("processing_time_seconds", 0),
                    "test_focus": drawing_info.get("test_focus", "Unknown"),
                    "complexity": drawing_info.get("complexity", "Unknown"),
                    "status": result.get("status", "Unknown"),
                    "key_issues": self._extract_key_issues(result),
                    "performance_met_expectations": drawing_info.get("expected_assessment")
                    == result.get("overall_assessment"),
                }
            )

        return breakdown

    def _catalog_common_issues(self, results: dict[str, Any]) -> dict[str, Any]:
        """Catalog common issues found across drawings."""
        drawing_results = results.get("drawing_results", [])
        completed_results = [r for r in drawing_results if r.get("status") == "completed"]

        issues_catalog = {}

        for result in completed_results:
            evaluation_details = result.get("evaluation_details", {})
            improvement_suggestions = evaluation_details.get("improvement_suggestions", [])

            for suggestion in improvement_suggestions:
                if suggestion not in issues_catalog:
                    issues_catalog[suggestion] = {"frequency": 0, "affected_drawings": []}
                issues_catalog[suggestion]["frequency"] += 1
                issues_catalog[suggestion]["affected_drawings"].append(result["drawing_name"])

        # Sort by frequency
        sorted_issues = sorted(issues_catalog.items(), key=lambda x: x[1]["frequency"], reverse=True)

        return {
            "total_unique_issues": len(issues_catalog),
            "most_common_issues": sorted_issues[:10],  # Top 10 most common issues
            "issue_frequency_distribution": {
                "high_frequency_issues": len(
                    [i for i in issues_catalog.values() if i["frequency"] > len(completed_results) * 0.3]
                ),
                "medium_frequency_issues": len(
                    [i for i in issues_catalog.values() if 0.1 <= i["frequency"] / len(completed_results) <= 0.3]
                ),
                "low_frequency_issues": len(
                    [i for i in issues_catalog.values() if i["frequency"] / len(completed_results) < 0.1]
                ),
            },
        }

    def _analyze_context_patterns(self, completed_results: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze patterns in context usage effectiveness."""
        # Placeholder for context analysis - would need more detailed tracking
        return {
            "effectiveness_summary": "Context analysis requires additional tracking in pipeline",
            "recommendation": "Implement context usage tracking in future validation runs",
        }

    def _extract_key_issues(self, result: dict[str, Any]) -> list[str]:
        """Extract key issues from individual drawing result."""
        issues = []

        if result.get("status") == "failed":
            issues.append(f"Processing failed: {result.get('error', 'Unknown error')}")

        evaluation_details = result.get("evaluation_details", {})
        if "missing" in evaluation_details.get("completeness", "").lower():
            issues.append("Incomplete component extraction")

        if "incorrect" in evaluation_details.get("correctness", "").lower():
            issues.append("Accuracy issues")

        if (
            evaluation_details.get("false_positives", "")
            and "none" not in evaluation_details["false_positives"].lower()
        ):
            issues.append("False positive detections")

        return issues

    def generate_markdown_report(self, report: dict[str, Any]) -> str:
        """Generate a markdown-formatted report."""
        md_lines = [
            f"# Validation Report: {report['validation_run_id']}",
            "",
            f"**Generated:** {report['generated_at']}",
            "",
            "## Executive Summary",
            "",
            f"- **Overall Performance:** {report['executive_summary']['overall_performance']}",
            f"- **Success Criteria Met:** {'✅' if report['executive_summary']['success_criteria_met'] else '❌'}",
            f"- **Total Drawings Tested:** {report['executive_summary']['total_drawings_tested']}",
            f"- **Success Rate:** {report['executive_summary']['success_rate_percentage']}%",
            f"- **Average Processing Time:** {report['executive_summary']['average_processing_time_minutes']} minutes",
            "",
            "### Key Findings",
            "",
        ]

        for finding in report["executive_summary"]["key_findings"]:
            md_lines.append(f"- {finding}")

        md_lines.extend(["", "### Priority Recommendations", ""])

        for rec in report["executive_summary"]["priority_recommendations"]:
            md_lines.append(f"- {rec}")

        # Add detailed sections - extract variables for readability
        criteria_met = report['success_criteria_evaluation']['criteria_met']
        actual_results = report['success_criteria_evaluation']['actual_results']

        md_lines.extend(
            [
                "",
                "## Success Criteria Evaluation",
                "",
                (
                    f"- **Minimum 60% Good:** "
                    f"{'✅' if criteria_met['minimum_60_percent_good'] else '❌'} "
                    f"({actual_results['good_rate']:.1%})"
                ),
                (
                    f"- **Maximum 20% Poor:** "
                    f"{'✅' if criteria_met['maximum_20_percent_poor'] else '❌'} "
                    f"({actual_results['poor_rate']:.1%})"
                ),
                "",
                "## Recommendations",
                "",
            ]
        )

        for i, rec in enumerate(report["recommendations"][:10], 1):  # Top 10 recommendations
            md_lines.extend(
                [
                    f"### {i}. {rec['title']} ({rec['priority']} Priority)",
                    "",
                    f"**Impact:** {rec['impact_percentage']:.1f}% of drawings affected",
                    f"**Description:** {rec['description']}",
                    f"**Category:** {rec['category']}",
                    "",
                    "**Suggested Improvements:**",
                ]
            )

            for improvement in rec["suggested_improvements"]:
                md_lines.append(f"- {improvement}")

            md_lines.append("")

        return "\n".join(md_lines)
