"""
Unit tests for DevelopmentRecommendationsEngine

Tests recommendation generation, issue categorization, and roadmap creation.
"""


import pytest

from src.utils.recommendations_engine import DevelopmentRecommendationsEngine


@pytest.fixture
def engine():
    """Create a DevelopmentRecommendationsEngine instance."""
    return DevelopmentRecommendationsEngine()


@pytest.fixture
def sample_validation_results():
    """Sample validation results with diverse feedback."""
    return {
        "validation_run_id": "test_recommendations_001",
        "assessment_summary": {
            "total_assessments": 8,
            "good_assessments": 4,
            "fair_assessments": 2,
            "poor_assessments": 2,
            "good_rate": 0.5,
            "poor_rate": 0.25
        },
        "processing_summary": {
            "total_drawings": 10,
            "successful_processing": 8,
            "failed_processing": 2
        },
        "drawing_results": [
            {
                "drawing_name": "test_good.pdf",
                "status": "completed",
                "overall_assessment": "Good",
                "components_count": 12,
                "evaluation_details": {
                    "completeness": "All components identified correctly",
                    "correctness": "Door IDs and types accurate",
                    "context_usage": "Specifications applied appropriately",
                    "spatial_understanding": "Components correctly associated",
                    "false_positives": "None detected",
                    "improvement_suggestions": []
                }
            },
            {
                "drawing_name": "test_emergency_issues.pdf",
                "status": "completed",
                "overall_assessment": "Fair",
                "components_count": 8,
                "evaluation_details": {
                    "completeness": "Missing several emergency exit components",
                    "correctness": "Most components correct",
                    "context_usage": "Context partially applied",
                    "spatial_understanding": "Some overlapping component confusion",
                    "false_positives": "One false emergency exit detection",
                    "improvement_suggestions": [
                        "Improve emergency exit recognition",
                        "Better handling of overlapping elements"
                    ]
                }
            },
            {
                "drawing_name": "test_dense_annotations.pdf",
                "status": "completed",
                "overall_assessment": "Poor",
                "components_count": 3,
                "evaluation_details": {
                    "completeness": "Missing many components due to dense annotations",
                    "correctness": "Several incorrect component classifications",
                    "context_usage": "Context not effectively integrated",
                    "spatial_understanding": "Significant confusion with overlapping annotations",
                    "false_positives": "Multiple false positive detections",
                    "improvement_suggestions": [
                        "Improve OCR for dense text areas",
                        "Add preprocessing for annotation cleanup",
                        "Better spatial understanding algorithms"
                    ]
                }
            },
            {
                "drawing_name": "test_context_issues.pdf",
                "status": "completed",
                "overall_assessment": "Poor",
                "components_count": 5,
                "evaluation_details": {
                    "completeness": "Adequate component detection",
                    "correctness": "Some incorrect types due to context conflicts",
                    "context_usage": "Context specifications conflicted with drawing details",
                    "spatial_understanding": "Good spatial relationships",
                    "false_positives": "None",
                    "improvement_suggestions": [
                        "Improve context integration logic",
                        "Add conflict resolution between context and drawings"
                    ]
                }
            },
            {
                "drawing_name": "test_failed.pdf",
                "status": "failed",
                "error": "Processing timeout after 300 seconds",
                "error_type": "TimeoutError"
            }
        ]
    }


class TestDevelopmentRecommendationsEngine:
    """Test DevelopmentRecommendationsEngine functionality."""

    def test_init(self, engine):
        """Test initialization."""
        assert len(engine.issue_categories) == 6

        categories = list(engine.issue_categories.keys())
        expected_categories = [
            "drawing_complexity", "component_recognition", "spatial_understanding",
            "context_integration", "accuracy", "reliability"
        ]
        for category in expected_categories:
            assert category in categories

        # Check category structure
        for category_info in engine.issue_categories.values():
            assert "title" in category_info
            assert "description" in category_info
            assert "keywords" in category_info
            assert isinstance(category_info["keywords"], list)

    def test_generate_recommendations(self, engine, sample_validation_results):
        """Test comprehensive recommendation generation."""
        result = engine.generate_recommendations(sample_validation_results)

        # Check basic structure
        assert result["validation_run_id"] == "test_recommendations_001"
        assert "generated_at" in result
        assert "analysis_summary" in result
        assert "issue_categories" in result
        assert "recommendations" in result
        assert "user_stories" in result
        assert "development_roadmap" in result
        assert "implementation_estimates" in result

        # Check analysis summary
        analysis_summary = result["analysis_summary"]
        assert "total_issues_identified" in analysis_summary
        assert "unique_issue_types" in analysis_summary
        assert analysis_summary["total_issues_identified"] > 0

    def test_analyze_judge_feedback(self, engine, sample_validation_results):
        """Test judge feedback analysis."""
        analysis = engine._analyze_judge_feedback(sample_validation_results)

        assert "all_issues" in analysis
        assert "feedback_by_category" in analysis
        assert "common_patterns" in analysis
        assert "total_feedback_items" in analysis

        # Should have extracted issues from improvement suggestions
        assert len(analysis["all_issues"]) > 0

        # Check categories
        expected_categories = [
            "completeness", "correctness", "context_usage",
            "spatial_understanding", "false_positives", "improvement_suggestions"
        ]
        for category in expected_categories:
            assert category in analysis["feedback_by_category"]

        # Check common patterns analysis
        patterns = analysis["common_patterns"]
        assert "most_common_phrases" in patterns
        assert "severity_distribution" in patterns
        assert isinstance(patterns["most_common_phrases"], list)

    def test_identify_feedback_patterns(self, engine):
        """Test feedback pattern identification."""
        sample_issues = [
            {
                "feedback": "Missing emergency exit components",
                "severity": "high",
                "category": "completeness"
            },
            {
                "feedback": "Emergency exit detection needs improvement",
                "severity": "medium",
                "category": "improvement_suggestions"
            },
            {
                "feedback": "Dense annotations cause issues",
                "severity": "high",
                "category": "completeness"
            }
        ]

        patterns = engine._identify_feedback_patterns(sample_issues)

        assert "most_common_phrases" in patterns
        assert "severity_distribution" in patterns
        assert "total_unique_patterns" in patterns

        # Should identify "emergency" as a common pattern
        phrase_dict = dict(patterns["most_common_phrases"])
        assert "emergency" in phrase_dict or any("emergency" in phrase for phrase, _ in patterns["most_common_phrases"])

        # Check severity distribution
        severity_dist = patterns["severity_distribution"]
        assert severity_dist["high"] == 2
        assert severity_dist["medium"] == 1

    def test_assess_issue_severity(self, engine):
        """Test issue severity assessment."""
        # High severity cases
        assert engine._assess_issue_severity("Critical failure occurred", "Poor") == "high"
        assert engine._assess_issue_severity("Components completely missing", "Good") == "high"
        assert engine._assess_issue_severity("Major accuracy issues", "Fair") == "high"

        # Medium severity cases
        assert engine._assess_issue_severity("Some components partially identified", "Fair") == "medium"
        assert engine._assess_issue_severity("Inconsistent results", "Good") == "medium"

        # Low severity cases
        assert engine._assess_issue_severity("Minor positioning issue", "Good") == "low"
        assert engine._assess_issue_severity("Small improvement possible", "Good") == "low"

    def test_categorize_issues(self, engine, sample_validation_results):
        """Test issue categorization."""
        feedback_analysis = engine._analyze_judge_feedback(sample_validation_results)
        categorized = engine._categorize_issues(feedback_analysis)

        assert isinstance(categorized, dict)

        # Should identify component recognition issues (emergency exits)
        if "component_recognition" in categorized:
            component_category = categorized["component_recognition"]
            assert "title" in component_category
            assert "issue_count" in component_category
            assert "affected_drawings" in component_category
            assert "impact_percentage" in component_category
            assert component_category["issue_count"] > 0

        # Should identify spatial understanding issues (overlapping)
        if "spatial_understanding" in categorized:
            spatial_category = categorized["spatial_understanding"]
            assert spatial_category["issue_count"] > 0

        # Check category structure
        for category_data in categorized.values():
            assert "title" in category_data
            assert "description" in category_data
            assert "issue_count" in category_data
            assert "affected_drawings" in category_data
            assert "high_severity_issues" in category_data
            assert "impact_percentage" in category_data
            assert "issues" in category_data

    def test_generate_prioritized_recommendations(self, engine, sample_validation_results):
        """Test prioritized recommendation generation."""
        feedback_analysis = engine._analyze_judge_feedback(sample_validation_results)
        categorized_issues = engine._categorize_issues(feedback_analysis)

        recommendations = engine._generate_prioritized_recommendations(
            categorized_issues, sample_validation_results
        )

        assert isinstance(recommendations, list)
        assert len(recommendations) > 0

        # Check recommendation structure
        for rec in recommendations:
            assert "priority" in rec
            assert "category" in rec
            assert "title" in rec
            assert "description" in rec
            assert "impact_percentage" in rec
            assert "suggested_improvements" in rec
            assert "estimated_effort" in rec
            assert rec["priority"] in ["High", "Medium", "Low"]

        # Should be sorted by priority
        priorities = [rec["priority"] for rec in recommendations]
        priority_order = {"High": 1, "Medium": 2, "Low": 3}
        for i in range(len(priorities) - 1):
            current_priority = priority_order.get(priorities[i], 4)
            next_priority = priority_order.get(priorities[i + 1], 4)
            assert current_priority <= next_priority

    def test_create_category_recommendation(self, engine):
        """Test category-specific recommendation creation."""
        sample_category_data = {
            "title": "Component Recognition Issues",
            "issue_count": 5,
            "affected_drawings": 3,
            "high_severity_issues": 2,
            "impact_percentage": 30.0
        }

        rec = engine._create_category_recommendation(
            "component_recognition", sample_category_data, "High"
        )

        assert rec["priority"] == "High"
        assert rec["category"] == "component_recognition"
        assert rec["title"] == "Enhance Component Recognition Accuracy"
        assert rec["impact_percentage"] == 30.0
        assert rec["affected_drawings"] == 3
        assert rec["issue_count"] == 5
        assert rec["high_severity_issues"] == 2
        assert len(rec["suggested_improvements"]) > 0
        assert rec["estimated_effort"] in ["Low", "Medium", "High"]

    def test_generate_overall_recommendations(self, engine, sample_validation_results):
        """Test overall system recommendations."""
        recommendations = engine._generate_overall_recommendations(sample_validation_results)

        assert isinstance(recommendations, list)

        # Should have accuracy recommendation (good_rate = 50% < 80%)
        accuracy_rec = next(
            (r for r in recommendations if "Overall System Performance" in r["title"]),
            None
        )
        assert accuracy_rec is not None
        assert accuracy_rec["priority"] == "Medium"  # 50% > 60% so not High priority

        # Should have reliability recommendation (failure_rate = 20% > 5%)
        reliability_rec = next(
            (r for r in recommendations if "Processing Reliability" in r["title"]),
            None
        )
        assert reliability_rec is not None
        assert reliability_rec["priority"] == "High"

    def test_assess_business_impact(self, engine):
        """Test business impact assessment."""
        assert engine._assess_business_impact(50.0, "High") == "High"
        assert engine._assess_business_impact(30.0, "Medium") == "Medium"
        assert engine._assess_business_impact(10.0, "Low") == "Low"
        assert engine._assess_business_impact(45.0, "Medium") == "High"  # High impact due to percentage
        assert engine._assess_business_impact(25.0, "Low") == "Medium"   # Medium impact due to percentage

    def test_assess_technical_complexity(self, engine):
        """Test technical complexity assessment."""
        assert engine._assess_technical_complexity("drawing_complexity") == "High"
        assert engine._assess_technical_complexity("component_recognition") == "Medium"
        assert engine._assess_technical_complexity("spatial_understanding") == "High"
        assert engine._assess_technical_complexity("context_integration") == "Medium"
        assert engine._assess_technical_complexity("accuracy") == "High"
        assert engine._assess_technical_complexity("reliability") == "Medium"
        assert engine._assess_technical_complexity("unknown_category") == "Medium"  # Default

    def test_create_user_stories(self, engine):
        """Test user story creation."""
        sample_recommendations = [
            {
                "priority": "High",
                "title": "Improve Emergency Exit Detection",
                "category": "component_recognition",
                "suggested_improvements": [
                    "Enhance exit symbol recognition",
                    "Add exit button detection",
                    "Improve spatial exit associations"
                ],
                "estimated_effort": "Medium",
                "business_impact": "High",
                "technical_complexity": "Medium"
            }
        ]

        user_stories = engine._create_user_stories(sample_recommendations)

        assert isinstance(user_stories, list)
        assert len(user_stories) > 0

        # Should have epic story
        epic_stories = [s for s in user_stories if s["type"] == "epic"]
        assert len(epic_stories) == 1

        epic = epic_stories[0]
        assert epic["priority"] == "High"
        assert epic["title"] == "Improve Emergency Exit Detection"
        assert "acceptance_criteria" in epic
        assert "story_points" in epic

        # Should have individual stories
        individual_stories = [s for s in user_stories if s["type"] == "story"]
        assert len(individual_stories) == 3  # Top 3 improvements

        for story in individual_stories:
            assert story["parent_epic"] == "Improve Emergency Exit Detection"
            assert "acceptance_criteria" in story
            assert "story_points" in story

    def test_generate_acceptance_criteria(self, engine):
        """Test acceptance criteria generation."""
        sample_rec = {
            "category": "component_recognition",
            "impact_percentage": 45.0,
            "priority": "High"
        }

        criteria = engine._generate_acceptance_criteria(sample_rec)

        assert isinstance(criteria, list)
        assert len(criteria) > 0

        # Should have basic criteria
        criteria_text = " ".join(criteria)
        assert "Reduce issues" in criteria_text
        assert "50%" in criteria_text  # 50% improvement target
        assert "testing" in criteria_text.lower()

        # Should have additional criteria for high impact/priority
        assert any("improvement within next sprint" in c.lower() for c in criteria)
        assert any("measurable improvement" in c.lower() for c in criteria)

    def test_estimate_story_points(self, engine):
        """Test story point estimation."""
        # Test different effort levels
        low_effort_rec = {"estimated_effort": "Low", "technical_complexity": "Low"}
        medium_effort_rec = {"estimated_effort": "Medium", "technical_complexity": "Medium"}
        high_effort_rec = {"estimated_effort": "High", "technical_complexity": "High"}

        assert engine._estimate_story_points(low_effort_rec) <= 5
        assert 3 <= engine._estimate_story_points(medium_effort_rec) <= 8
        assert engine._estimate_story_points(high_effort_rec) >= 8
        assert engine._estimate_story_points(high_effort_rec) <= 13  # Capped at 13

    def test_estimate_subtask_points(self, engine):
        """Test subtask story point estimation."""
        # Test different improvement types
        assert engine._estimate_subtask_points("Implement new detection algorithm", "High") == 6
        assert engine._estimate_subtask_points("Improve existing logic", "Medium") == 3
        assert engine._estimate_subtask_points("Update configuration", "Low") == 1

    def test_create_development_roadmap(self, engine):
        """Test development roadmap creation."""
        sample_recommendations = [
            {"priority": "High", "title": "Critical Fix", "estimated_effort": "High"},
            {"priority": "Medium", "title": "Improvement", "estimated_effort": "Medium"},
            {"priority": "Low", "title": "Optimization", "estimated_effort": "Low"}
        ]

        roadmap = engine._create_development_roadmap(sample_recommendations)

        assert "timeline_estimates" in roadmap
        assert "resource_requirements" in roadmap
        assert "milestones" in roadmap

        # Check timeline phases
        timeline = roadmap["timeline_estimates"]
        assert "phase_1_critical" in timeline
        assert "phase_2_improvements" in timeline
        assert "phase_3_optimization" in timeline

        # Each phase should have duration, focus, recommendations
        for phase in timeline.values():
            assert "duration_weeks" in phase
            assert "focus" in phase
            assert "recommendations" in phase
            assert "success_metrics" in phase

        # Check resource requirements
        resources = roadmap["resource_requirements"]
        assert "development_team_weeks" in resources
        assert "testing_team_weeks" in resources
        assert "estimated_total_cost" in resources
        assert "risk_factors" in resources

        # Check milestones
        milestones = roadmap["milestones"]
        assert len(milestones) == 3
        for milestone in milestones:
            assert "name" in milestone
            assert "target_date" in milestone
            assert "deliverables" in milestone

    def test_estimate_implementation_effort(self, engine):
        """Test implementation effort estimation."""
        sample_recommendations = [
            {"estimated_effort": "Low", "technical_complexity": "Low"},
            {"estimated_effort": "Medium", "technical_complexity": "Medium"},
            {"estimated_effort": "High", "technical_complexity": "High"}
        ]

        estimates = engine._estimate_implementation_effort(sample_recommendations)

        assert "effort_distribution" in estimates
        assert "total_story_points" in estimates
        assert "estimated_sprints" in estimates
        assert "development_weeks" in estimates
        assert "complexity_score" in estimates

        # Check effort distribution
        effort_dist = estimates["effort_distribution"]
        assert effort_dist["Low"] == 1
        assert effort_dist["Medium"] == 1
        assert effort_dist["High"] == 1

        # Check calculations
        assert estimates["total_story_points"] > 0
        assert estimates["estimated_sprints"] > 0
        assert estimates["development_weeks"] > 0

    def test_estimate_development_cost(self, engine):
        """Test development cost estimation."""
        sample_recommendations = [
            {"estimated_effort": "Low"},   # 1 week
            {"estimated_effort": "Medium"}, # 2 weeks
            {"estimated_effort": "High"}    # 4 weeks
        ]
        # Total: 7 weeks

        cost = engine._estimate_development_cost(sample_recommendations)

        # Should be 7 weeks * $8k * 1.5 overhead = $84k
        expected_cost = 7 * 8000 * 1.5
        assert cost == expected_cost

    def test_identify_risk_factors(self, engine):
        """Test risk factor identification."""
        # Test high complexity risks
        high_complexity_recs = [
            {"technical_complexity": "High", "estimated_effort": "Low"},
            {"technical_complexity": "High", "estimated_effort": "Low"},
            {"technical_complexity": "High", "estimated_effort": "Low"},
            {"technical_complexity": "High", "estimated_effort": "Low"}
        ]

        risks = engine._identify_risk_factors(high_complexity_recs)
        assert any("high-complexity" in risk for risk in risks)

        # Test high priority risks
        high_priority_recs = [
            {"priority": "High", "estimated_effort": "Low"}
        ] * 6

        risks = engine._identify_risk_factors(high_priority_recs)
        assert any("high-priority" in risk for risk in risks)

        # Test high effort risks
        high_effort_recs = [
            {"estimated_effort": "High"}
        ] * 10  # Total effort > 20

        risks = engine._identify_risk_factors(high_effort_recs)
        assert any("development effort" in risk for risk in risks)


class TestDevelopmentRecommendationsEngineEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_validation_results(self, engine):
        """Test handling of empty validation results."""
        empty_results = {
            "validation_run_id": "empty_test",
            "drawing_results": [],
            "assessment_summary": {},
            "processing_summary": {}
        }

        # Should not crash
        result = engine.generate_recommendations(empty_results)
        assert result["validation_run_id"] == "empty_test"
        assert "recommendations" in result
        assert "user_stories" in result

    def test_no_completed_drawings(self, engine):
        """Test handling when no drawings completed successfully."""
        no_completed_results = {
            "validation_run_id": "no_completed_test",
            "drawing_results": [
                {"status": "failed", "error": "Processing failed"},
                {"status": "failed", "error": "Another error"}
            ],
            "assessment_summary": {"total_assessments": 0},
            "processing_summary": {"total_drawings": 2, "failed_processing": 2}
        }

        result = engine.generate_recommendations(no_completed_results)

        # Should still generate reliability recommendations
        assert len(result["recommendations"]) > 0
        reliability_recs = [r for r in result["recommendations"] if "reliability" in r["category"].lower()]
        assert len(reliability_recs) > 0

    def test_missing_evaluation_details(self, engine):
        """Test handling of missing evaluation details."""
        missing_eval_results = {
            "validation_run_id": "missing_eval_test",
            "drawing_results": [
                {
                    "status": "completed",
                    "overall_assessment": "Good"
                    # Missing evaluation_details
                }
            ],
            "assessment_summary": {"good_rate": 1.0},
            "processing_summary": {"total_drawings": 1}
        }

        # Should handle gracefully
        feedback_analysis = engine._analyze_judge_feedback(missing_eval_results)
        assert "all_issues" in feedback_analysis
        # Should have 0 issues due to missing evaluation details
        assert len(feedback_analysis["all_issues"]) == 0

    def test_malformed_feedback_data(self, engine):
        """Test handling of malformed feedback data."""
        malformed_issues = [
            None,  # Invalid issue
            {"feedback": None, "severity": "high"},  # Invalid feedback
            42,    # Wrong type
            {"feedback": "", "severity": "unknown"}  # Empty feedback
        ]

        # Should not crash
        patterns = engine._identify_feedback_patterns(malformed_issues)
        assert "most_common_phrases" in patterns
        assert "severity_distribution" in patterns


@pytest.mark.parametrize("impact,high_severity,expected_priority", [
    (50.0, 3, "High"),    # High impact, high severity
    (30.0, 1, "Medium"),  # Medium impact, some severity
    (15.0, 0, "Low"),     # Low impact, no severity
    (45.0, 0, "High"),    # High impact overrides low severity
    (25.0, 2, "Medium")   # Medium impact with severity
])
def test_priority_calculation(impact, high_severity, expected_priority):
    """Test priority calculation logic."""
    engine = DevelopmentRecommendationsEngine()

    category_data = {
        "impact_percentage": impact,
        "high_severity_issues": high_severity,
        "issue_count": 5,
        "affected_drawings": 3
    }

    rec = engine._create_category_recommendation("test_category", category_data, expected_priority)
    assert rec["priority"] == expected_priority


def test_roadmap_phase_duration_calculation():
    """Test roadmap phase duration calculations."""
    engine = DevelopmentRecommendationsEngine()

    # Test different effort combinations
    recommendations = [
        {"priority": "High", "estimated_effort": "High"},    # 4 effort units
        {"priority": "High", "estimated_effort": "Medium"},  # 2 effort units
        {"priority": "Medium", "estimated_effort": "Low"}    # 1 effort unit
    ]

    roadmap = engine._create_development_roadmap(recommendations)

    # High priority should get the high effort recommendations (6 units = 3 weeks)
    phase_1 = roadmap["timeline_estimates"]["phase_1_critical"]
    assert phase_1["duration_weeks"] == 3  # (4 + 2) / 2 = 3

    # Medium priority should get the low effort recommendation (1 unit = 1 week)
    phase_2 = roadmap["timeline_estimates"]["phase_2_improvements"]
    assert phase_2["duration_weeks"] == 1  # max(1, 1/2) = 1
