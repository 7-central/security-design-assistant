"""Analyzer for extracting improvement suggestions from Judge Agent evaluations."""
import logging
from collections import Counter
from typing import Any

logger = logging.getLogger(__name__)


class JudgeFeedbackAnalyzer:
    """Analyzes Judge Agent evaluations to extract actionable improvements."""

    def extract_top_improvements(self, evaluation: dict[str, Any], top_n: int = 2) -> list[str]:
        """Extract top improvement suggestions from a single evaluation.

        Args:
            evaluation: Judge evaluation dictionary
            top_n: Number of top improvements to return

        Returns:
            List of top improvement suggestions
        """
        improvements = evaluation.get("improvement_suggestions", [])

        # Return up to top_n improvements
        return improvements[:top_n]

    def analyze_multiple_evaluations(self, evaluations: list[dict[str, Any]]) -> dict[str, Any]:
        """Analyze multiple evaluations to identify patterns.

        Args:
            evaluations: List of Judge evaluation dictionaries

        Returns:
            Analysis results with patterns and recommendations
        """
        all_suggestions = []
        assessments = []
        issue_categories = {
            "completeness": [],
            "correctness": [],
            "context_usage": [],
            "spatial_understanding": [],
            "false_positives": [],
        }

        for eval_data in evaluations:
            # Collect improvement suggestions
            suggestions = eval_data.get("improvement_suggestions", [])
            all_suggestions.extend(suggestions)

            # Track overall assessments
            assessment = eval_data.get("overall_assessment", "")
            if assessment:
                assessments.append(self._extract_assessment_level(assessment))

            # Collect issues by category
            for category in issue_categories:
                if category in eval_data and eval_data[category]:
                    issue_categories[category].append(eval_data[category])

        # Count suggestion frequency
        suggestion_counter = Counter(all_suggestions)

        # Identify common patterns in suggestions
        patterns = self._identify_patterns(all_suggestions)

        # Calculate assessment distribution
        assessment_distribution = Counter(assessments)

        # Find most problematic categories
        problematic_categories = []
        for category, issues in issue_categories.items():
            if issues and any(
                "miss" in str(issue).lower() or "incorrect" in str(issue).lower() or "wrong" in str(issue).lower()
                for issue in issues
            ):
                problematic_categories.append(category)

        return {
            "total_evaluations": len(evaluations),
            "assessment_distribution": dict(assessment_distribution),
            "top_suggestions": suggestion_counter.most_common(5),
            "recurring_patterns": patterns,
            "problematic_categories": problematic_categories,
            "recommended_improvements": self._generate_recommendations(
                suggestion_counter, patterns, problematic_categories
            ),
        }

    def _extract_assessment_level(self, assessment: str) -> str:
        """Extract assessment level (Good/Fair/Poor) from assessment text.

        Args:
            assessment: Assessment text

        Returns:
            Assessment level
        """
        assessment_lower = assessment.lower()
        if "good" in assessment_lower:
            return "Good"
        elif "fair" in assessment_lower:
            return "Fair"
        elif "poor" in assessment_lower:
            return "Poor"
        else:
            return "Unknown"

    def _identify_patterns(self, suggestions: list[str]) -> list[str]:
        """Identify common patterns in improvement suggestions.

        Args:
            suggestions: List of all improvement suggestions

        Returns:
            List of identified patterns
        """
        if not suggestions:
            return []

        # Common keywords to look for with their pattern descriptions
        pattern_keywords = {
            "emergency exit": "Emergency exit identification issues",
            "reader type": "Reader type classification problems",
            "door": "Door association or identification issues",
            "spatial": "Spatial relationship understanding problems",
            "context": "Context utilization issues",
            "component id": "Component ID pattern recognition issues",
            "false positive": "False positive detection issues",
            "annotation": "Annotation parsing issues",
        }

        # Count occurrences of each pattern efficiently
        pattern_counts = {}
        for keyword, pattern_desc in pattern_keywords.items():
            count = sum(1 for suggestion in suggestions if keyword in suggestion.lower())
            if count > 0:
                pattern_counts[pattern_desc] = count

        # Sort by frequency and return top 3
        if not pattern_counts:
            return []

        sorted_patterns = sorted(pattern_counts.items(), key=lambda x: x[1], reverse=True)
        return [pattern for pattern, _ in sorted_patterns[:3]]

    def _generate_recommendations(
        self, suggestion_counter: Counter, patterns: list[str], problematic_categories: list[str]
    ) -> list[str]:
        """Generate specific recommendations based on analysis.

        Args:
            suggestion_counter: Counter of improvement suggestions
            patterns: Identified patterns
            problematic_categories: Categories with issues

        Returns:
            List of specific recommendations
        """
        recommendations = []

        # Get top 2 most common suggestions
        top_suggestions = suggestion_counter.most_common(2)
        for suggestion, _ in top_suggestions:
            recommendations.append(suggestion)

        # Add recommendations based on patterns if not already covered
        if "Emergency exit identification issues" in patterns:
            rec = "Add explicit instructions for identifying emergency exit doors and buttons"
            if rec not in recommendations:
                recommendations.append(rec)

        if "Reader type classification problems" in patterns:
            rec = "Clarify distinction between reader types (P vs E types)"
            if rec not in recommendations:
                recommendations.append(rec)

        if "Spatial relationship understanding problems" in patterns:
            rec = "Improve instructions for associating components with doors/locations"
            if rec not in recommendations:
                recommendations.append(rec)

        # Add recommendations for problematic categories
        if "completeness" in problematic_categories:
            rec = "Add more comprehensive component search patterns"
            if rec not in recommendations and len(recommendations) < 3:
                recommendations.append(rec)

        if "false_positives" in problematic_categories:
            rec = "Add stricter validation rules to reduce false positives"
            if rec not in recommendations and len(recommendations) < 3:
                recommendations.append(rec)

        return recommendations[:3]  # Return top 3 recommendations

    def format_analysis_report(self, analysis: dict[str, Any]) -> str:
        """Format analysis results into a readable report.

        Args:
            analysis: Analysis results dictionary

        Returns:
            Formatted report string
        """
        report = []
        report.append("=" * 60)
        report.append("JUDGE FEEDBACK ANALYSIS REPORT")
        report.append("=" * 60)
        report.append("")

        # Assessment distribution
        report.append("Assessment Distribution:")
        for level, count in analysis["assessment_distribution"].items():
            percentage = (count / analysis["total_evaluations"]) * 100
            report.append(f"  - {level}: {count} ({percentage:.1f}%)")
        report.append("")

        # Top suggestions
        report.append("Most Common Improvement Suggestions:")
        for i, (suggestion, count) in enumerate(analysis["top_suggestions"], 1):
            report.append(f"  {i}. {suggestion} (mentioned {count} times)")
        report.append("")

        # Recurring patterns
        if analysis["recurring_patterns"]:
            report.append("Recurring Patterns Identified:")
            for pattern in analysis["recurring_patterns"]:
                report.append(f"  - {pattern}")
            report.append("")

        # Problematic categories
        if analysis["problematic_categories"]:
            report.append("Problematic Categories:")
            for category in analysis["problematic_categories"]:
                report.append(f"  - {category}")
            report.append("")

        # Recommendations
        report.append("RECOMMENDED PROMPT IMPROVEMENTS:")
        for i, rec in enumerate(analysis["recommended_improvements"], 1):
            report.append(f"  {i}. {rec}")
        report.append("")
        report.append("=" * 60)

        return "\n".join(report)
