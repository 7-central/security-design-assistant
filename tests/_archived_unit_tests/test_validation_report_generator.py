"""
Unit tests for ValidationReportGenerator

Tests report generation, analysis, and pattern recognition functionality.
"""


import pytest

from src.utils.validation_report_generator import ValidationReportGenerator


@pytest.fixture
def report_generator():
    """Create a ValidationReportGenerator instance."""
    return ValidationReportGenerator()


@pytest.fixture
def sample_validation_data():
    """Sample validation data for testing."""
    return {
        "validation_run_id": "test_run_123",
        "timestamp": "2025-08-10T10:30:00Z",
        "test_descriptions_version": "1.0",
        "processing_summary": {
            "total_drawings": 10,
            "successful_processing": 8,
            "failed_processing": 2,
            "total_processing_time_seconds": 1200.0,
            "average_time_per_drawing": 120.0
        },
        "assessment_summary": {
            "total_assessments": 8,
            "good_assessments": 5,
            "fair_assessments": 2,
            "poor_assessments": 1,
            "unknown_assessments": 0,
            "success_rate": 0.625,
            "good_rate": 0.625,
            "fair_rate": 0.25,
            "poor_rate": 0.125,
            "meets_success_criteria": {
                "minimum_60_percent_good": True,
                "maximum_20_percent_poor": True
            }
        },
        "cost_estimates": {
            "drawings_count": 10,
            "total_estimated_cost_usd": 0.8500,
            "processing_time_estimate_minutes": 30
        },
        "drawing_results": [
            {
                "drawing_name": "test_good_1.pdf",
                "status": "completed",
                "overall_assessment": "Good",
                "components_count": 12,
                "processing_time_seconds": 90.0,
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
                "drawing_name": "test_fair_1.pdf",
                "status": "completed",
                "overall_assessment": "Fair",
                "components_count": 8,
                "processing_time_seconds": 150.0,
                "evaluation_details": {
                    "completeness": "Most components found, missing some emergency exits",
                    "correctness": "Generally accurate with minor issues",
                    "context_usage": "Context partially applied",
                    "spatial_understanding": "Some confusion with overlapping elements",
                    "false_positives": "One false detection",
                    "improvement_suggestions": ["Improve emergency exit detection"]
                }
            },
            {
                "drawing_name": "test_poor_1.pdf",
                "status": "completed",
                "overall_assessment": "Poor",
                "components_count": 3,
                "processing_time_seconds": 200.0,
                "evaluation_details": {
                    "completeness": "Missing many components",
                    "correctness": "Several incorrect classifications",
                    "context_usage": "Context not effectively used",
                    "spatial_understanding": "Significant spatial confusion",
                    "false_positives": "Multiple false detections",
                    "improvement_suggestions": [
                        "Improve component detection accuracy",
                        "Better spatial relationship understanding"
                    ]
                }
            }
        ],
        "test_metadata": {
            "drawings": {
                "test_good_1.pdf": {
                    "complexity": "standard",
                    "expected_assessment": "Good",
                    "test_focus": "Basic functionality"
                },
                "test_fair_1.pdf": {
                    "complexity": "complex",
                    "expected_assessment": "Fair",
                    "test_focus": "Emergency exit recognition"
                },
                "test_poor_1.pdf": {
                    "complexity": "complex",
                    "expected_assessment": "Poor",
                    "test_focus": "Dense annotations"
                }
            }
        }
    }


class TestValidationReportGenerator:
    """Test ValidationReportGenerator functionality."""

    def test_init(self, report_generator):
        """Test initialization."""
        assert report_generator.report_template_path.name == "report_template.md"

    def test_generate_comprehensive_report(self, report_generator, sample_validation_data):
        """Test comprehensive report generation."""
        report = report_generator.generate_comprehensive_report(sample_validation_data)

        # Check basic structure
        assert "report_id" in report
        assert report["validation_run_id"] == "test_run_123"
        assert "generated_at" in report

        # Check all major sections exist
        required_sections = [
            "executive_summary",
            "detailed_analysis",
            "pattern_analysis",
            "performance_metrics",
            "success_criteria_evaluation",
            "recommendations",
            "appendices"
        ]

        for section in required_sections:
            assert section in report, f"Missing section: {section}"

    def test_generate_executive_summary(self, report_generator, sample_validation_data):
        """Test executive summary generation."""
        summary = report_generator._generate_executive_summary(sample_validation_data)

        assert summary["overall_performance"] == "Good"  # 62.5% good rate
        assert summary["success_criteria_met"] is True
        assert summary["total_drawings_tested"] == 8  # Completed drawings
        assert summary["success_rate_percentage"] == 62.5

        assert "key_findings" in summary
        assert "priority_recommendations" in summary
        assert isinstance(summary["key_findings"], list)
        assert isinstance(summary["priority_recommendations"], list)

    def test_analyze_detailed_results(self, report_generator, sample_validation_data):
        """Test detailed results analysis."""
        analysis = report_generator._analyze_detailed_results(sample_validation_data)

        # Check structure
        assert "good" in analysis
        assert "fair" in analysis
        assert "poor" in analysis

        # Check counts
        assert analysis["good"]["count"] == 1  # From sample data
        assert analysis["fair"]["count"] == 1
        assert analysis["poor"]["count"] == 1

        # Check drawing names
        assert "test_good_1.pdf" in analysis["good"]["drawings"]
        assert "test_fair_1.pdf" in analysis["fair"]["drawings"]
        assert "test_poor_1.pdf" in analysis["poor"]["drawings"]

    def test_analyze_patterns(self, report_generator, sample_validation_data):
        """Test pattern analysis."""
        patterns = report_generator._analyze_patterns(sample_validation_data)

        required_pattern_keys = [
            "complexity_patterns",
            "challenge_type_patterns",
            "common_strengths",
            "common_weaknesses",
            "context_effectiveness",
            "performance_correlation"
        ]

        for key in required_pattern_keys:
            assert key in patterns

    def test_analyze_by_complexity(self, report_generator, sample_validation_data):
        """Test complexity analysis."""
        completed_results = [
            r for r in sample_validation_data["drawing_results"]
            if r.get("status") == "completed"
        ]

        analysis = report_generator._analyze_by_complexity(
            completed_results,
            sample_validation_data["test_metadata"]
        )

        # Should have complexity categories
        assert "standard" in analysis
        assert "complex" in analysis

        # Check calculation
        for _complexity, data in analysis.items():
            assert "total" in data
            assert "good_rate" in data
            assert "poor_rate" in data

    def test_analyze_strengths_weaknesses(self, report_generator, sample_validation_data):
        """Test strengths and weaknesses analysis."""
        completed_results = [
            r for r in sample_validation_data["drawing_results"]
            if r.get("status") == "completed"
        ]

        analysis = report_generator._analyze_strengths_weaknesses(completed_results)

        assert "strengths" in analysis
        assert "weaknesses" in analysis
        assert isinstance(analysis["strengths"], list)
        assert isinstance(analysis["weaknesses"], list)

        # Check structure of strength/weakness items
        if analysis["strengths"]:
            strength = analysis["strengths"][0]
            assert "area" in strength
            assert "frequency" in strength
            assert "percentage" in strength

    def test_analyze_performance(self, report_generator, sample_validation_data):
        """Test performance metrics analysis."""
        performance = report_generator._analyze_performance(sample_validation_data)

        assert "processing_time_statistics" in performance
        assert "component_extraction_statistics" in performance
        assert "throughput_metrics" in performance
        assert "cost_analysis" in performance

        # Check processing time stats
        time_stats = performance["processing_time_statistics"]
        assert "mean_seconds" in time_stats
        assert "min_seconds" in time_stats
        assert "max_seconds" in time_stats

        # Verify calculations
        assert time_stats["min_seconds"] == 90.0  # From sample data
        assert time_stats["max_seconds"] == 200.0

    def test_evaluate_success_criteria(self, report_generator, sample_validation_data):
        """Test success criteria evaluation."""
        evaluation = report_generator._evaluate_success_criteria(sample_validation_data)

        assert "criteria_definition" in evaluation
        assert "actual_results" in evaluation
        assert "criteria_met" in evaluation
        assert "overall_pass" in evaluation
        assert "gap_analysis" in evaluation

        # Check specific values from sample data
        assert evaluation["overall_pass"] is True
        assert evaluation["actual_results"]["good_rate"] == 0.625
        assert evaluation["criteria_met"]["minimum_60_percent_good"] is True

    def test_generate_recommendations(self, report_generator, sample_validation_data):
        """Test recommendation generation."""
        recommendations = report_generator._generate_recommendations(sample_validation_data)

        assert isinstance(recommendations, list)

        # Check recommendation structure if any exist
        if recommendations:
            rec = recommendations[0]
            required_keys = [
                "priority", "title", "description", "suggested_improvements",
                "category", "estimated_effort"
            ]
            for key in required_keys:
                assert key in rec

            assert rec["priority"] in ["High", "Medium", "Low"]
            assert isinstance(rec["suggested_improvements"], list)

    def test_extract_key_findings(self, report_generator, sample_validation_data):
        """Test key findings extraction."""
        findings = report_generator._extract_key_findings(sample_validation_data)

        assert isinstance(findings, list)
        assert len(findings) > 0

        # Should mention success criteria being met
        findings_text = " ".join(findings).lower()
        assert "criteria" in findings_text or "success" in findings_text

    def test_analyze_cost_efficiency(self, report_generator, sample_validation_data):
        """Test cost efficiency analysis."""
        cost_analysis = report_generator._analyze_cost_efficiency(sample_validation_data)

        assert "total_estimated_cost" in cost_analysis
        assert "cost_per_drawing" in cost_analysis
        assert "cost_per_good_assessment" in cost_analysis
        assert "efficiency_rating" in cost_analysis

        # Verify calculations
        total_cost = cost_analysis["total_estimated_cost"]
        assert total_cost == 0.8500  # From sample data

        cost_per_drawing = cost_analysis["cost_per_drawing"]
        assert cost_per_drawing == total_cost / 8  # 8 completed drawings

    def test_create_drawing_breakdown(self, report_generator, sample_validation_data):
        """Test drawing breakdown creation."""
        breakdown = report_generator._create_drawing_breakdown(sample_validation_data)

        assert isinstance(breakdown, list)
        assert len(breakdown) == 3  # 3 completed drawings in sample

        # Check structure
        if breakdown:
            drawing = breakdown[0]
            required_keys = [
                "drawing_name", "expected_assessment", "actual_assessment",
                "components_found", "processing_time", "test_focus",
                "complexity", "status", "key_issues", "performance_met_expectations"
            ]
            for key in required_keys:
                assert key in drawing

    def test_catalog_common_issues(self, report_generator, sample_validation_data):
        """Test common issues cataloging."""
        catalog = report_generator._catalog_common_issues(sample_validation_data)

        assert "total_unique_issues" in catalog
        assert "most_common_issues" in catalog
        assert "issue_frequency_distribution" in catalog

        # Check frequency distribution structure
        freq_dist = catalog["issue_frequency_distribution"]
        assert "high_frequency_issues" in freq_dist
        assert "medium_frequency_issues" in freq_dist
        assert "low_frequency_issues" in freq_dist

    def test_generate_markdown_report(self, report_generator, sample_validation_data):
        """Test markdown report generation."""
        # First generate comprehensive report
        report = report_generator.generate_comprehensive_report(sample_validation_data)

        # Then generate markdown
        markdown = report_generator.generate_markdown_report(report)

        assert isinstance(markdown, str)
        assert len(markdown) > 0

        # Check for key markdown elements
        assert "# Validation Report:" in markdown
        assert "## Executive Summary" in markdown
        assert "## Success Criteria Evaluation" in markdown
        assert "## Recommendations" in markdown

        # Check for data substitution
        assert "test_run_123" in markdown  # validation_run_id
        assert "62.5%" in markdown  # success rate

    def test_assess_issue_severity(self, report_generator):
        """Test issue severity assessment."""
        # Test high severity
        assert report_generator._assess_issue_severity("Critical failure", "Poor") == "high"
        assert report_generator._assess_issue_severity("Completely missing", "Good") == "high"

        # Test medium severity
        assert report_generator._assess_issue_severity("Some issues", "Fair") == "medium"
        assert report_generator._assess_issue_severity("Partially correct", "Good") == "medium"

        # Test low severity
        assert report_generator._assess_issue_severity("Minor issue", "Good") == "low"

    def test_identify_common_characteristics(self, report_generator, sample_validation_data):
        """Test common characteristics identification."""
        # Test with drawings having same complexity
        same_complexity_drawings = [
            {"drawing_name": "test_fair_1.pdf", "components_count": 8},
            {"drawing_name": "test_poor_1.pdf", "components_count": 3}
        ]

        characteristics = report_generator._identify_common_characteristics(
            same_complexity_drawings,
            sample_validation_data
        )

        assert isinstance(characteristics, list)
        # Should identify that both are complex complexity
        characteristics_text = " ".join(characteristics).lower()
        assert "complex" in characteristics_text

    def test_analyze_success_criteria_gaps(self, report_generator):
        """Test success criteria gap analysis."""
        # Test with failing criteria
        failing_summary = {
            "good_rate": 0.4,  # Below 60%
            "poor_rate": 0.3,  # Above 20%
            "total_assessments": 10,
            "good_assessments": 4,
            "poor_assessments": 3
        }

        gaps = report_generator._analyze_success_criteria_gaps(failing_summary)

        assert "good_rate_shortfall" in gaps
        assert "poor_rate_excess" in gaps

        # Check calculations
        good_gap = gaps["good_rate_shortfall"]
        assert good_gap["current"] == 0.4
        assert good_gap["target"] == 0.6
        assert good_gap["improvement_needed"] == 0.2

    def test_extract_key_issues(self, report_generator):
        """Test key issue extraction from individual results."""
        # Test failed result
        failed_result = {
            "status": "failed",
            "error": "Processing timeout"
        }
        issues = report_generator._extract_key_issues(failed_result)
        assert len(issues) > 0
        assert "Processing failed" in issues[0]

        # Test result with evaluation issues
        problematic_result = {
            "status": "completed",
            "evaluation_details": {
                "completeness": "Missing components",
                "correctness": "Incorrect classifications",
                "false_positives": "Several false detections"
            }
        }
        issues = report_generator._extract_key_issues(problematic_result)
        assert "Incomplete component extraction" in issues
        assert "Accuracy issues" in issues
        assert "False positive detections" in issues


class TestValidationReportGeneratorEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_validation_data(self, report_generator):
        """Test handling of empty validation data."""
        empty_data = {
            "validation_run_id": "empty_test",
            "drawing_results": [],
            "assessment_summary": {},
            "processing_summary": {},
            "test_metadata": {}
        }

        # Should not crash, should handle gracefully
        report = report_generator.generate_comprehensive_report(empty_data)
        assert "report_id" in report
        assert report["validation_run_id"] == "empty_test"

    def test_malformed_drawing_results(self, report_generator):
        """Test handling of malformed drawing results."""
        malformed_data = {
            "validation_run_id": "malformed_test",
            "drawing_results": [
                {"drawing_name": "test.pdf"},  # Missing required fields
                {"status": "completed"},        # Missing drawing_name
                None,                          # Invalid entry
                42                             # Invalid type
            ],
            "assessment_summary": {"total_assessments": 0},
            "processing_summary": {"total_drawings": 0},
            "test_metadata": {"drawings": {}}
        }

        # Should handle gracefully without crashing
        report = report_generator.generate_comprehensive_report(malformed_data)
        assert "report_id" in report

    def test_missing_evaluation_details(self, report_generator):
        """Test handling of missing evaluation details."""
        data_missing_eval = {
            "validation_run_id": "missing_eval_test",
            "drawing_results": [
                {
                    "drawing_name": "test.pdf",
                    "status": "completed",
                    "overall_assessment": "Good"
                    # Missing evaluation_details
                }
            ],
            "assessment_summary": {
                "total_assessments": 1,
                "good_assessments": 1,
                "good_rate": 1.0
            },
            "processing_summary": {"total_drawings": 1},
            "test_metadata": {"drawings": {}}
        }

        # Should handle gracefully
        analysis = report_generator._analyze_strengths_weaknesses(data_missing_eval["drawing_results"])
        assert "strengths" in analysis
        assert "weaknesses" in analysis


@pytest.mark.parametrize("good_rate,expected_performance", [
    (0.9, "Excellent"),
    (0.75, "Good"),
    (0.5, "Fair"),
    (0.3, "Poor")
])
def test_performance_categorization(good_rate, expected_performance):
    """Test performance category assignment."""
    generator = ValidationReportGenerator()

    mock_results = {
        "assessment_summary": {"good_rate": good_rate, "poor_rate": 0.1},
        "processing_summary": {"average_time_per_drawing": 120}
    }

    summary = generator._generate_executive_summary(mock_results)
    assert summary["overall_performance"] == expected_performance
