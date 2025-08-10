"""
Development Recommendations Engine

Analyzes validation suite results to generate prioritized development recommendations
and actionable user stories for the backlog.
"""

import logging
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)


class DevelopmentRecommendationsEngine:
    """Generates development recommendations from validation analysis."""

    def __init__(self):
        self.issue_categories = {
            "drawing_complexity": {
                "title": "Drawing Complexity Issues",
                "description": "Problems with complex drawings, dense annotations, or poor quality scans",
                "keywords": ["dense", "overlapping", "complex", "quality", "resolution", "grainy"]
            },
            "component_recognition": {
                "title": "Component Recognition Issues",
                "description": "Problems identifying specific component types",
                "keywords": ["emergency", "exit", "button", "reader", "door", "component"]
            },
            "spatial_understanding": {
                "title": "Spatial Understanding Issues",
                "description": "Problems with spatial relationships and component associations",
                "keywords": ["overlapping", "spatial", "association", "relationship", "position"]
            },
            "context_integration": {
                "title": "Context Integration Issues",
                "description": "Problems using context documents effectively",
                "keywords": ["context", "specification", "conflict", "integration"]
            },
            "accuracy": {
                "title": "Accuracy Issues",
                "description": "General accuracy problems with extraction or classification",
                "keywords": ["incorrect", "wrong", "inaccurate", "false", "missing"]
            },
            "reliability": {
                "title": "System Reliability Issues",
                "description": "Processing failures, errors, or system stability issues",
                "keywords": ["failed", "error", "timeout", "crash", "exception"]
            }
        }

    def generate_recommendations(self, validation_results: dict[str, Any]) -> dict[str, Any]:
        """Generate comprehensive development recommendations."""
        logger.info(f"Generating development recommendations for {validation_results['validation_run_id']}")

        # Analyze judge feedback patterns
        feedback_analysis = self._analyze_judge_feedback(validation_results)

        # Categorize issues by type
        categorized_issues = self._categorize_issues(feedback_analysis)

        # Generate prioritized recommendations
        recommendations = self._generate_prioritized_recommendations(categorized_issues, validation_results)

        # Create actionable user stories
        user_stories = self._create_user_stories(recommendations)

        # Generate development roadmap
        roadmap = self._create_development_roadmap(recommendations)

        return {
            "validation_run_id": validation_results["validation_run_id"],
            "generated_at": datetime.utcnow().isoformat(),
            "analysis_summary": {
                "total_issues_identified": len(feedback_analysis["all_issues"]),
                "unique_issue_types": len(categorized_issues),
                "high_priority_recommendations": len([r for r in recommendations if r["priority"] == "High"]),
                "medium_priority_recommendations": len([r for r in recommendations if r["priority"] == "Medium"]),
                "low_priority_recommendations": len([r for r in recommendations if r["priority"] == "Low"])
            },
            "issue_categories": categorized_issues,
            "recommendations": recommendations,
            "user_stories": user_stories,
            "development_roadmap": roadmap,
            "implementation_estimates": self._estimate_implementation_effort(recommendations)
        }

    def _analyze_judge_feedback(self, validation_results: dict[str, Any]) -> dict[str, Any]:
        """Analyze judge feedback across all drawings to identify patterns."""
        drawing_results = validation_results.get("drawing_results", [])
        completed_results = [r for r in drawing_results if r.get("status") == "completed"]

        all_issues = []
        feedback_by_category = {
            "completeness": [],
            "correctness": [],
            "context_usage": [],
            "spatial_understanding": [],
            "false_positives": [],
            "improvement_suggestions": []
        }

        # Extract all feedback
        for result in completed_results:
            evaluation_details = result.get("evaluation_details", {})

            for category, feedback_list in feedback_by_category.items():
                feedback = evaluation_details.get(category, "")
                if feedback and feedback.lower() not in ["none", "n/a", "good", "excellent"]:
                    feedback_list.append({
                        "drawing": result["drawing_name"],
                        "assessment": result.get("overall_assessment", "Unknown"),
                        "feedback": feedback,
                        "components_count": result.get("components_count", 0)
                    })

                    # Add to all issues for pattern analysis
                    all_issues.append({
                        "category": category,
                        "drawing": result["drawing_name"],
                        "feedback": feedback,
                        "severity": self._assess_issue_severity(feedback, result.get("overall_assessment", "Unknown"))
                    })

        # Identify common phrases and patterns
        common_patterns = self._identify_feedback_patterns(all_issues)

        return {
            "all_issues": all_issues,
            "feedback_by_category": feedback_by_category,
            "common_patterns": common_patterns,
            "total_feedback_items": len(all_issues)
        }

    def _identify_feedback_patterns(self, all_issues: list[dict[str, Any]]) -> dict[str, Any]:
        """Identify common patterns in judge feedback."""
        # Count phrase frequencies
        phrase_counts = {}
        severity_distribution = {"high": 0, "medium": 0, "low": 0}

        for issue in all_issues:
            feedback_lower = issue["feedback"].lower()
            severity = issue["severity"]
            severity_distribution[severity] += 1

            # Extract key phrases (simplified approach)
            words = feedback_lower.split()
            for i in range(len(words)):
                # Single words
                word = words[i].strip('.,!?;:')
                if len(word) > 3 and word not in ["the", "and", "but", "for", "are", "with", "this", "that", "have"]:
                    phrase_counts[word] = phrase_counts.get(word, 0) + 1

                # Two-word phrases
                if i < len(words) - 1:
                    phrase = f"{words[i]} {words[i+1]}".strip('.,!?;:')
                    if len(phrase) > 6:
                        phrase_counts[phrase] = phrase_counts.get(phrase, 0) + 1

        # Get most common patterns
        sorted_patterns = sorted(phrase_counts.items(), key=lambda x: x[1], reverse=True)

        return {
            "most_common_phrases": sorted_patterns[:20],
            "severity_distribution": severity_distribution,
            "total_unique_patterns": len(phrase_counts)
        }

    def _assess_issue_severity(self, feedback: str, assessment: str) -> str:
        """Assess severity of an issue based on feedback and assessment."""
        feedback_lower = feedback.lower()

        # High severity indicators
        if assessment == "Poor" or any(word in feedback_lower for word in ["critical", "major", "completely", "entirely", "failed", "missing"]):
            return "high"

        # Medium severity indicators
        if assessment == "Fair" or any(word in feedback_lower for word in ["some", "partially", "inconsistent", "unclear"]):
            return "medium"

        # Default to low severity
        return "low"

    def _categorize_issues(self, feedback_analysis: dict[str, Any]) -> dict[str, Any]:
        """Categorize issues by type using keyword matching."""
        categorized = {}
        all_issues = feedback_analysis["all_issues"]

        for category_key, category_info in self.issue_categories.items():
            matching_issues = []

            for issue in all_issues:
                feedback_lower = issue["feedback"].lower()
                if any(keyword in feedback_lower for keyword in category_info["keywords"]):
                    matching_issues.append(issue)

            if matching_issues:
                # Calculate impact metrics
                affected_drawings = len({issue["drawing"] for issue in matching_issues})
                high_severity_count = len([i for i in matching_issues if i["severity"] == "high"])

                categorized[category_key] = {
                    "title": category_info["title"],
                    "description": category_info["description"],
                    "issue_count": len(matching_issues),
                    "affected_drawings": affected_drawings,
                    "high_severity_issues": high_severity_count,
                    "impact_percentage": (affected_drawings / len({i["drawing"] for i in all_issues})) * 100 if all_issues else 0,
                    "issues": matching_issues
                }

        return categorized

    def _generate_prioritized_recommendations(self, categorized_issues: dict[str, Any], validation_results: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate prioritized recommendations based on categorized issues."""
        recommendations = []

        for category_key, category_data in categorized_issues.items():
            impact_percentage = category_data["impact_percentage"]
            high_severity_issues = category_data["high_severity_issues"]

            # Determine priority
            if impact_percentage > 40 or high_severity_issues > 2:
                priority = "High"
            elif impact_percentage > 20 or high_severity_issues > 0:
                priority = "Medium"
            else:
                priority = "Low"

            # Generate specific recommendations based on category
            recommendation = self._create_category_recommendation(category_key, category_data, priority)
            recommendations.append(recommendation)

        # Add general recommendations based on overall performance
        overall_recommendations = self._generate_overall_recommendations(validation_results)
        recommendations.extend(overall_recommendations)

        # Sort by priority and impact
        priority_order = {"High": 1, "Medium": 2, "Low": 3}
        recommendations.sort(key=lambda x: (priority_order.get(x["priority"], 4), -x["impact_percentage"]))

        return recommendations

    def _create_category_recommendation(self, category_key: str, category_data: dict[str, Any], priority: str) -> dict[str, Any]:
        """Create a specific recommendation for a category of issues."""

        recommendation_templates = {
            "drawing_complexity": {
                "title": "Improve Complex Drawing Processing",
                "improvements": [
                    "Implement preprocessing for image quality enhancement",
                    "Add specialized OCR handling for dense annotations",
                    "Create multi-scale analysis for complex layouts",
                    "Add rotation and skew correction algorithms"
                ],
                "effort": "High"
            },
            "component_recognition": {
                "title": "Enhance Component Recognition Accuracy",
                "improvements": [
                    "Expand training data for emergency exit components",
                    "Improve symbol recognition algorithms",
                    "Add component type confidence scoring",
                    "Create specialized detection for button/reader types"
                ],
                "effort": "Medium"
            },
            "spatial_understanding": {
                "title": "Improve Spatial Relationship Detection",
                "improvements": [
                    "Enhance spatial association algorithms",
                    "Add overlapping component resolution logic",
                    "Improve distance-based component grouping",
                    "Add spatial context validation"
                ],
                "effort": "High"
            },
            "context_integration": {
                "title": "Enhance Context Document Integration",
                "improvements": [
                    "Improve context parsing and extraction",
                    "Add conflict resolution between context and drawings",
                    "Enhance specification matching algorithms",
                    "Add context validation feedback"
                ],
                "effort": "Medium"
            },
            "accuracy": {
                "title": "Improve Overall System Accuracy",
                "improvements": [
                    "Review and retrain core models",
                    "Add validation checkpoints in pipeline",
                    "Implement confidence scoring throughout",
                    "Add human-in-the-loop validation for low confidence"
                ],
                "effort": "High"
            },
            "reliability": {
                "title": "Enhance System Reliability",
                "improvements": [
                    "Add comprehensive error handling and recovery",
                    "Implement graceful degradation for failures",
                    "Add retry logic with exponential backoff",
                    "Improve input validation and sanitization"
                ],
                "effort": "Medium"
            }
        }

        template = recommendation_templates.get(category_key, {
            "title": f"Address {category_data['title']}",
            "improvements": ["Analyze specific issues and implement targeted fixes"],
            "effort": "Medium"
        })

        return {
            "priority": priority,
            "category": category_key,
            "title": template["title"],
            "description": f"Address {category_data['issue_count']} issues affecting {category_data['affected_drawings']} drawings",
            "impact_percentage": category_data["impact_percentage"],
            "affected_drawings": category_data["affected_drawings"],
            "issue_count": category_data["issue_count"],
            "high_severity_issues": category_data["high_severity_issues"],
            "suggested_improvements": template["improvements"],
            "estimated_effort": template["effort"],
            "business_impact": self._assess_business_impact(category_data["impact_percentage"], priority),
            "technical_complexity": self._assess_technical_complexity(category_key)
        }

    def _generate_overall_recommendations(self, validation_results: dict[str, Any]) -> list[dict[str, Any]]:
        """Generate overall system recommendations."""
        recommendations = []

        assessment_summary = validation_results.get("assessment_summary", {})
        processing_summary = validation_results.get("processing_summary", {})

        good_rate = assessment_summary.get("good_rate", 0)
        failure_rate = processing_summary.get("failed_processing", 0) / max(processing_summary.get("total_drawings", 1), 1)

        # Overall accuracy recommendation
        if good_rate < 0.8:
            recommendations.append({
                "priority": "High" if good_rate < 0.6 else "Medium",
                "category": "overall_performance",
                "title": "Improve Overall System Performance",
                "description": f"System achieving only {good_rate:.1%} good assessments",
                "impact_percentage": 100,
                "affected_drawings": assessment_summary.get("total_assessments", 0),
                "suggested_improvements": [
                    "Conduct comprehensive system accuracy review",
                    "Implement end-to-end testing and validation",
                    "Add performance monitoring and alerting",
                    "Create feedback loop for continuous improvement"
                ],
                "estimated_effort": "High",
                "business_impact": "High",
                "technical_complexity": "High"
            })

        # Reliability recommendation
        if failure_rate > 0.05:  # More than 5% failure rate
            recommendations.append({
                "priority": "High",
                "category": "system_reliability",
                "title": "Address Processing Reliability Issues",
                "description": f"System has {failure_rate:.1%} processing failure rate",
                "impact_percentage": failure_rate * 100,
                "affected_drawings": processing_summary.get("failed_processing", 0),
                "suggested_improvements": [
                    "Implement robust error handling throughout pipeline",
                    "Add comprehensive input validation",
                    "Create monitoring and alerting for failures",
                    "Add automated retry and recovery mechanisms"
                ],
                "estimated_effort": "Medium",
                "business_impact": "High",
                "technical_complexity": "Medium"
            })

        return recommendations

    def _assess_business_impact(self, impact_percentage: float, priority: str) -> str:
        """Assess business impact level."""
        if priority == "High" or impact_percentage > 40:
            return "High"
        elif priority == "Medium" or impact_percentage > 20:
            return "Medium"
        else:
            return "Low"

    def _assess_technical_complexity(self, category: str) -> str:
        """Assess technical complexity of addressing a category."""
        complexity_map = {
            "drawing_complexity": "High",
            "component_recognition": "Medium",
            "spatial_understanding": "High",
            "context_integration": "Medium",
            "accuracy": "High",
            "reliability": "Medium"
        }
        return complexity_map.get(category, "Medium")

    def _create_user_stories(self, recommendations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Create actionable user stories for the backlog."""
        user_stories = []

        for rec in recommendations[:10]:  # Top 10 recommendations
            # Main epic story
            epic_story = {
                "type": "epic",
                "priority": rec["priority"],
                "title": rec["title"],
                "description": f"As a system user, I want {rec['title'].lower()}, so that the system performs more reliably and accurately.",
                "acceptance_criteria": self._generate_acceptance_criteria(rec),
                "story_points": self._estimate_story_points(rec),
                "category": rec["category"],
                "business_value": rec.get("business_impact", "Medium")
            }
            user_stories.append(epic_story)

            # Break down into smaller stories
            for _i, improvement in enumerate(rec["suggested_improvements"][:3], 1):  # Top 3 improvements
                story = {
                    "type": "story",
                    "priority": rec["priority"],
                    "title": f"{rec['title']} - {improvement}",
                    "description": f"As a developer, I want to implement {improvement.lower()}, so that we can address {rec['category']} issues.",
                    "acceptance_criteria": [
                        f"Implement {improvement.lower()}",
                        "Add appropriate tests for the implementation",
                        "Validate improvement with test drawings",
                        "Update documentation"
                    ],
                    "story_points": self._estimate_subtask_points(improvement, rec["estimated_effort"]),
                    "parent_epic": rec["title"],
                    "category": rec["category"]
                }
                user_stories.append(story)

        return user_stories

    def _generate_acceptance_criteria(self, recommendation: dict[str, Any]) -> list[str]:
        """Generate acceptance criteria for a recommendation."""
        base_criteria = [
            f"Reduce issues in {recommendation['category']} by at least 50%",
            "Implement all suggested improvements with appropriate testing",
            "Validate improvements with validation suite",
            "Update system documentation"
        ]

        # Add specific criteria based on impact
        if recommendation["impact_percentage"] > 40:
            base_criteria.append("Show measurable improvement in affected drawings within one validation cycle")

        if recommendation["priority"] == "High":
            base_criteria.append("Achieve improvement within next sprint cycle")

        return base_criteria

    def _estimate_story_points(self, recommendation: dict[str, Any]) -> int:
        """Estimate story points for a recommendation."""
        effort = recommendation.get("estimated_effort", "Medium")
        complexity = recommendation.get("technical_complexity", "Medium")

        # Base points by effort
        effort_points = {"Low": 3, "Medium": 5, "High": 8}
        base_points = effort_points.get(effort, 5)

        # Adjust for complexity
        if complexity == "High":
            base_points += 3
        elif complexity == "Low":
            base_points = max(1, base_points - 2)

        return min(base_points, 13)  # Cap at 13 points

    def _estimate_subtask_points(self, improvement: str, effort: str) -> int:
        """Estimate story points for individual improvements."""
        base_points = {"Low": 2, "Medium": 3, "High": 5}.get(effort, 3)

        # Adjust based on improvement type
        if any(word in improvement.lower() for word in ["implement", "create", "add"]):
            return base_points + 1
        elif any(word in improvement.lower() for word in ["improve", "enhance", "update"]):
            return base_points
        else:
            return max(1, base_points - 1)

    def _create_development_roadmap(self, recommendations: list[dict[str, Any]]) -> dict[str, Any]:
        """Create a development roadmap based on recommendations."""
        # Group by priority and estimate timeline
        high_priority = [r for r in recommendations if r["priority"] == "High"]
        medium_priority = [r for r in recommendations if r["priority"] == "Medium"]
        low_priority = [r for r in recommendations if r["priority"] == "Low"]

        # Estimate timeline based on effort
        def estimate_weeks(recs):
            total_effort = sum({"Low": 1, "Medium": 2, "High": 4}.get(r.get("estimated_effort", "Medium"), 2) for r in recs)
            return max(1, total_effort // 2)  # Assuming 2 effort units per week

        roadmap = {
            "timeline_estimates": {
                "phase_1_critical": {
                    "duration_weeks": estimate_weeks(high_priority),
                    "focus": "Critical issues affecting system reliability and accuracy",
                    "recommendations": [r["title"] for r in high_priority],
                    "success_metrics": ["Achieve minimum success criteria", "Reduce processing failures"]
                },
                "phase_2_improvements": {
                    "duration_weeks": estimate_weeks(medium_priority),
                    "focus": "Performance improvements and feature enhancements",
                    "recommendations": [r["title"] for r in medium_priority],
                    "success_metrics": ["Improve overall accuracy", "Enhance user experience"]
                },
                "phase_3_optimization": {
                    "duration_weeks": estimate_weeks(low_priority),
                    "focus": "System optimization and edge case handling",
                    "recommendations": [r["title"] for r in low_priority],
                    "success_metrics": ["Optimize performance", "Handle edge cases"]
                }
            },
            "resource_requirements": {
                "development_team_weeks": estimate_weeks(recommendations),
                "testing_team_weeks": estimate_weeks(recommendations) // 2,
                "estimated_total_cost": self._estimate_development_cost(recommendations),
                "risk_factors": self._identify_risk_factors(recommendations)
            },
            "milestones": [
                {"name": "Critical Issues Resolved", "target_date": "+4 weeks", "deliverables": high_priority[:3]},
                {"name": "Core Improvements Complete", "target_date": "+8 weeks", "deliverables": medium_priority[:3]},
                {"name": "System Optimization Complete", "target_date": "+12 weeks", "deliverables": low_priority[:2]}
            ]
        }

        return roadmap

    def _estimate_implementation_effort(self, recommendations: list[dict[str, Any]]) -> dict[str, Any]:
        """Estimate overall implementation effort."""
        effort_distribution = {"Low": 0, "Medium": 0, "High": 0}
        total_story_points = 0

        for rec in recommendations:
            effort = rec.get("estimated_effort", "Medium")
            effort_distribution[effort] += 1

            # Estimate story points (rough approximation)
            points = {"Low": 3, "Medium": 5, "High": 8}.get(effort, 5)
            total_story_points += points

        return {
            "effort_distribution": effort_distribution,
            "total_story_points": total_story_points,
            "estimated_sprints": (total_story_points // 30) + 1,  # Assuming 30 points per sprint
            "development_weeks": (total_story_points // 15) + 1,   # Assuming 15 points per week
            "complexity_score": sum({"Low": 1, "Medium": 2, "High": 3}.get(r.get("technical_complexity", "Medium"), 2) for r in recommendations)
        }

    def _estimate_development_cost(self, recommendations: list[dict[str, Any]]) -> float:
        """Estimate development cost (rough approximation)."""
        total_weeks = sum({"Low": 1, "Medium": 2, "High": 4}.get(r.get("estimated_effort", "Medium"), 2) for r in recommendations)

        # Rough cost estimates (developer week rates)
        dev_week_cost = 8000  # $8k per developer week
        total_cost = total_weeks * dev_week_cost

        # Add overhead for testing, project management, etc.
        total_cost *= 1.5

        return round(total_cost, -3)  # Round to nearest thousand

    def _identify_risk_factors(self, recommendations: list[dict[str, Any]]) -> list[str]:
        """Identify potential risk factors for implementation."""
        risks = []

        high_complexity_count = len([r for r in recommendations if r.get("technical_complexity") == "High"])
        if high_complexity_count > 3:
            risks.append("Multiple high-complexity implementations may cause delays")

        high_priority_count = len([r for r in recommendations if r["priority"] == "High"])
        if high_priority_count > 5:
            risks.append("Large number of high-priority items may indicate systemic issues")

        total_effort = sum({"Low": 1, "Medium": 2, "High": 4}.get(r.get("estimated_effort", "Medium"), 2) for r in recommendations)
        if total_effort > 20:
            risks.append("Significant development effort required - consider phased approach")

        return risks
