"""Unit tests for JudgeFeedbackAnalyzer."""
import pytest

from src.utils.judge_feedback_analyzer import JudgeFeedbackAnalyzer


class TestJudgeFeedbackAnalyzer:
    """Test cases for JudgeFeedbackAnalyzer functionality."""

    @pytest.fixture
    def analyzer(self):
        """Create analyzer instance."""
        return JudgeFeedbackAnalyzer()

    @pytest.fixture
    def sample_evaluation(self):
        """Sample judge evaluation for testing."""
        return {
            "overall_assessment": "Fair performance with moderate accuracy",
            "completeness": "System found most components but missed emergency exits",
            "correctness": "Most components correctly identified",
            "context_usage": "Context used appropriately",
            "spatial_understanding": "Good associations",
            "false_positives": "Few false positives",
            "improvement_suggestions": [
                "Focus on emergency exit door patterns",
                "Clarify reader type distinctions"
            ]
        }

    @pytest.fixture
    def sample_evaluations(self):
        """Multiple sample evaluations for testing."""
        return [
            {
                "overall_assessment": "Fair performance with completeness issues",
                "completeness": "Missed several emergency exit components",
                "correctness": "Good accuracy for detected components",
                "context_usage": "Context usage adequate",
                "spatial_understanding": "Spatial relationships need improvement",
                "false_positives": "Minimal false positives",
                "improvement_suggestions": [
                    "Focus on emergency exit door patterns",
                    "Improve spatial relationship instructions"
                ]
            },
            {
                "overall_assessment": "Good performance with minor issues",
                "completeness": "Found most components including exits",
                "correctness": "High accuracy in identification",
                "context_usage": "Good context utilization",
                "spatial_understanding": "Clear spatial associations",
                "false_positives": "No false positives detected",
                "improvement_suggestions": [
                    "Clarify reader type distinctions",
                    "Add component ID pattern examples"
                ]
            }
        ]

    def test_extract_top_improvements_single(self, analyzer, sample_evaluation):
        """Test extracting improvements from single evaluation."""
        improvements = analyzer.extract_top_improvements(sample_evaluation, top_n=2)

        assert len(improvements) == 2
        assert "Focus on emergency exit door patterns" in improvements
        assert "Clarify reader type distinctions" in improvements

    def test_extract_top_improvements_empty_suggestions(self, analyzer):
        """Test handling evaluation with no improvement suggestions."""
        evaluation = {
            "overall_assessment": "Good performance",
            "improvement_suggestions": []
        }

        improvements = analyzer.extract_top_improvements(evaluation, top_n=2)
        assert improvements == []

    def test_extract_top_improvements_fewer_than_requested(self, analyzer):
        """Test when there are fewer suggestions than requested."""
        evaluation = {
            "improvement_suggestions": ["Only one suggestion"]
        }

        improvements = analyzer.extract_top_improvements(evaluation, top_n=3)
        assert len(improvements) == 1
        assert improvements[0] == "Only one suggestion"

    def test_analyze_multiple_evaluations(self, analyzer, sample_evaluations):
        """Test analysis of multiple evaluations."""
        analysis = analyzer.analyze_multiple_evaluations(sample_evaluations)

        # Check basic structure
        assert "total_evaluations" in analysis
        assert "assessment_distribution" in analysis
        assert "top_suggestions" in analysis
        assert "recurring_patterns" in analysis
        assert "recommended_improvements" in analysis

        # Check values
        assert analysis["total_evaluations"] == 2
        assert "Fair" in analysis["assessment_distribution"]
        assert "Good" in analysis["assessment_distribution"]

        # Check that emergency exit pattern is identified
        patterns = analysis["recurring_patterns"]
        assert any("emergency exit" in pattern.lower() for pattern in patterns)

    def test_extract_assessment_level(self, analyzer):
        """Test assessment level extraction."""
        assert analyzer._extract_assessment_level("Good performance with minor issues") == "Good"
        assert analyzer._extract_assessment_level("Fair performance moderate") == "Fair"
        assert analyzer._extract_assessment_level("Poor performance many issues") == "Poor"
        assert analyzer._extract_assessment_level("Unclear assessment") == "Unknown"

    def test_identify_patterns(self, analyzer):
        """Test pattern identification in suggestions."""
        suggestions = [
            "Focus on emergency exit door patterns",
            "Emergency exit buttons need attention",
            "Improve reader type classification",
            "Reader type P vs E confusion",
            "Spatial relationships unclear"
        ]

        patterns = analyzer._identify_patterns(suggestions)

        # Should identify emergency exit and reader type patterns
        assert any("emergency exit" in pattern.lower() for pattern in patterns)
        assert any("reader type" in pattern.lower() for pattern in patterns)

    def test_generate_recommendations(self, analyzer):
        """Test recommendation generation."""
        from collections import Counter

        suggestion_counter = Counter([
            "Focus on emergency exit patterns",
            "Focus on emergency exit patterns",
            "Clarify reader types"
        ])

        patterns = ["Emergency exit identification issues"]
        problematic_categories = ["completeness"]

        recommendations = analyzer._generate_recommendations(
            suggestion_counter, patterns, problematic_categories
        )

        assert len(recommendations) <= 3
        assert "Focus on emergency exit patterns" in recommendations

    def test_format_analysis_report(self, analyzer, sample_evaluations):
        """Test report formatting."""
        analysis = analyzer.analyze_multiple_evaluations(sample_evaluations)
        report = analyzer.format_analysis_report(analysis)

        assert isinstance(report, str)
        assert "JUDGE FEEDBACK ANALYSIS REPORT" in report
        assert "Assessment Distribution:" in report
        assert "RECOMMENDED PROMPT IMPROVEMENTS:" in report
        assert len(report) > 100  # Should be a substantial report

    def test_empty_evaluations_list(self, analyzer):
        """Test handling of empty evaluations list."""
        analysis = analyzer.analyze_multiple_evaluations([])

        assert analysis["total_evaluations"] == 0
        assert analysis["assessment_distribution"] == {}
        assert analysis["top_suggestions"] == []
        assert analysis["recurring_patterns"] == []

    def test_malformed_evaluation(self, analyzer):
        """Test handling of malformed evaluation data."""
        malformed = {
            "overall_assessment": "Fair performance",
            # Missing improvement_suggestions
        }

        improvements = analyzer.extract_top_improvements(malformed)
        assert improvements == []  # Should handle gracefully

    def test_consistent_recommendation_count(self, analyzer, sample_evaluations):
        """Test that recommendations are consistently limited."""
        analysis = analyzer.analyze_multiple_evaluations(sample_evaluations)
        recommendations = analysis["recommended_improvements"]

        # Should not exceed 3 recommendations
        assert len(recommendations) <= 3

        # All recommendations should be strings
        assert all(isinstance(rec, str) for rec in recommendations)

    @pytest.mark.parametrize("assessment_text,expected", [
        ("Good performance overall", "Good"),
        ("Fair quality with issues", "Fair"),
        ("Poor extraction results", "Poor"),
        ("Good work done excellently", "Good"),  # Contains "good" explicitly
        ("Moderate fair quality", "Fair"),
        ("Really poor implementation", "Poor"),
    ])
    def test_assessment_extraction_variations(self, analyzer, assessment_text, expected):
        """Test assessment extraction with various text formats."""
        result = analyzer._extract_assessment_level(assessment_text)
        assert result == expected
