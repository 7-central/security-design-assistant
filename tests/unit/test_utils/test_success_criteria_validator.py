"""
Unit tests for SuccessCriteriaValidator

Tests success criteria validation, trend analysis, and alert generation.
"""

import json
from unittest.mock import Mock, patch

import pytest

from src.utils.success_criteria_validator import SuccessCriteriaValidator


@pytest.fixture
def validator():
    """Create a SuccessCriteriaValidator instance."""
    return SuccessCriteriaValidator()


@pytest.fixture
def sample_validation_results():
    """Sample validation results for testing."""
    return {
        "validation_run_id": "test_validation_001",
        "timestamp": "2025-08-10T10:30:00Z",
        "assessment_summary": {
            "total_assessments": 10,
            "good_assessments": 7,
            "fair_assessments": 2,
            "poor_assessments": 1,
            "good_rate": 0.7,
            "fair_rate": 0.2,
            "poor_rate": 0.1,
            "meets_success_criteria": {
                "minimum_60_percent_good": True,
                "maximum_20_percent_poor": True
            }
        },
        "processing_summary": {
            "total_drawings": 10,
            "successful_processing": 10,
            "failed_processing": 0
        }
    }


@pytest.fixture
def failing_validation_results():
    """Sample validation results that fail criteria."""
    return {
        "validation_run_id": "test_validation_fail",
        "timestamp": "2025-08-10T10:30:00Z",
        "assessment_summary": {
            "total_assessments": 10,
            "good_assessments": 4,  # 40% - below 60% target
            "fair_assessments": 3,
            "poor_assessments": 3,  # 30% - above 20% target
            "good_rate": 0.4,
            "fair_rate": 0.3,
            "poor_rate": 0.3,
            "meets_success_criteria": {
                "minimum_60_percent_good": False,
                "maximum_20_percent_poor": False
            }
        },
        "processing_summary": {
            "total_drawings": 12,
            "successful_processing": 10,
            "failed_processing": 2  # 16.7% failure rate
        }
    }


class TestSuccessCriteriaValidator:
    """Test SuccessCriteriaValidator functionality."""

    def test_init(self, validator):
        """Test initialization."""
        assert validator.criteria["minimum_good_rate"] == 0.6
        assert validator.criteria["maximum_poor_rate"] == 0.2
        assert validator.criteria["minimum_confidence"] == 0.7
        assert validator.criteria["maximum_processing_failures"] == 0.1

        assert validator.results_dir.name == "results"
        assert validator.alerts_dir.name == "alerts"

    @patch('src.utils.success_criteria_validator.SuccessCriteriaValidator._save_validation_results')
    @patch('src.utils.success_criteria_validator.SuccessCriteriaValidator._analyze_trends')
    @pytest.mark.asyncio
    async def test_validate_results_success(self, mock_analyze_trends, mock_save, validator, sample_validation_results):
        """Test successful validation results."""
        mock_analyze_trends.return_value = None
        mock_save.return_value = None

        validation = await validator.validate_results(sample_validation_results)

        assert validation["validation_run_id"] == "test_validation_001"
        assert "validated_at" in validation
        assert "individual_criteria" in validation
        assert "overall_result" in validation
        assert "recommendations" in validation

        # Check that all criteria passed
        overall_result = validation["overall_result"]
        assert overall_result["status"] == "pass"
        assert overall_result["passed_count"] >= 2  # At least good_rate and poor_rate should pass
        assert overall_result["failed_count"] == 0

    @patch('src.utils.success_criteria_validator.SuccessCriteriaValidator._save_validation_results')
    @patch('src.utils.success_criteria_validator.SuccessCriteriaValidator._analyze_trends')
    @pytest.mark.asyncio
    async def test_validate_results_failure(self, mock_analyze_trends, mock_save, validator, failing_validation_results):
        """Test failing validation results."""
        mock_analyze_trends.return_value = None
        mock_save.return_value = None

        validation = await validator.validate_results(failing_validation_results)

        assert validation["validation_run_id"] == "test_validation_fail"

        # Check that criteria failed
        overall_result = validation["overall_result"]
        assert overall_result["status"] == "fail"
        assert overall_result["failed_count"] > 0

        # Should have recommendations
        assert len(validation["recommendations"]) > 0

    def test_validate_good_rate_pass(self, validator):
        """Test good rate validation - passing case."""
        assessment_summary = {
            "good_rate": 0.75,
            "total_assessments": 10,
            "good_assessments": 8
        }

        result = validator._validate_good_rate(assessment_summary)

        assert result["criterion"] == "minimum_good_rate"
        assert result["target_value"] == 0.6
        assert result["actual_value"] == 0.75
        assert result["passed"] is True
        assert result["margin"] == 0.15  # 0.75 - 0.6
        assert result["confidence"] == "high"
        assert "shortfall_assessments" in result["details"]
        assert "improvement_needed" not in result

    def test_validate_good_rate_fail(self, validator):
        """Test good rate validation - failing case."""
        assessment_summary = {
            "good_rate": 0.4,
            "total_assessments": 10,
            "good_assessments": 4
        }

        result = validator._validate_good_rate(assessment_summary)

        assert result["criterion"] == "minimum_good_rate"
        assert result["passed"] is False
        assert result["margin"] == -0.2  # 0.4 - 0.6
        assert result["improvement_needed"] == 0.2
        assert result["priority"] == "medium"  # 40% is above critical threshold of <40%
        assert result["details"]["shortfall_assessments"] == 2  # Need 2 more good assessments

    def test_validate_poor_rate_pass(self, validator):
        """Test poor rate validation - passing case."""
        assessment_summary = {
            "poor_rate": 0.1,
            "total_assessments": 10,
            "poor_assessments": 1
        }

        result = validator._validate_poor_rate(assessment_summary)

        assert result["criterion"] == "maximum_poor_rate"
        assert result["target_value"] == 0.2
        assert result["actual_value"] == 0.1
        assert result["passed"] is True
        assert result["margin"] == 0.1  # 0.2 - 0.1
        assert "reduction_needed" not in result

    def test_validate_poor_rate_fail(self, validator):
        """Test poor rate validation - failing case."""
        assessment_summary = {
            "poor_rate": 0.35,
            "total_assessments": 10,
            "poor_assessments": 4  # Excess of 1 assessment
        }

        result = validator._validate_poor_rate(assessment_summary)

        assert result["passed"] is False
        assert result["reduction_needed"] == 0.15  # 0.35 - 0.2
        assert result["priority"] == "medium"
        assert result["details"]["excess_poor_assessments"] == 2  # 4 - (0.2 * 10)

    def test_validate_failure_rate_pass(self, validator):
        """Test processing failure rate validation - passing case."""
        processing_summary = {
            "total_drawings": 10,
            "failed_processing": 0
        }

        result = validator._validate_failure_rate(processing_summary)

        assert result["criterion"] == "processing_reliability"
        assert result["passed"] is True
        assert result["details"]["failure_rate"] == 0.0
        assert result["details"]["reliability_rate"] == 1.0

    def test_validate_failure_rate_fail(self, validator):
        """Test processing failure rate validation - failing case."""
        processing_summary = {
            "total_drawings": 10,
            "failed_processing": 2  # 20% failure rate
        }

        result = validator._validate_failure_rate(processing_summary)

        assert result["passed"] is False
        assert result["details"]["failure_rate"] == 0.2
        assert result["priority"] == "high"  # 20% > 10% threshold but < 20% critical

    def test_validate_failure_rate_critical(self, validator):
        """Test processing failure rate validation - critical case."""
        processing_summary = {
            "total_drawings": 10,
            "failed_processing": 3  # 30% failure rate
        }

        result = validator._validate_failure_rate(processing_summary)

        assert result["passed"] is False
        assert result["priority"] == "critical"  # 30% > 20% critical threshold

    def test_validate_confidence_score(self, validator):
        """Test confidence score validation (not implemented yet)."""
        result = validator._validate_confidence_score({})

        assert result["criterion"] == "confidence_score"
        assert result["confidence"] == "not_implemented"
        assert result["passed"] is None
        assert "not yet implemented" in result["details"]["note"]

    def test_calculate_overall_result_pass(self, validator):
        """Test overall result calculation - all pass."""
        individual_criteria = {
            "good_rate": {"passed": True, "confidence": "high"},
            "poor_rate": {"passed": True, "confidence": "high"},
            "processing_reliability": {"passed": True, "confidence": "high"}
        }

        result = validator._calculate_overall_result(individual_criteria)

        assert result["status"] == "pass"
        assert result["passed_count"] == 3
        assert result["failed_count"] == 0
        assert result["total_count"] == 3
        assert result["pass_rate"] == 1.0
        assert result["critical_failures"] == 0

    def test_calculate_overall_result_fail(self, validator):
        """Test overall result calculation - some fail."""
        individual_criteria = {
            "good_rate": {"passed": False, "confidence": "high", "priority": "medium"},
            "poor_rate": {"passed": True, "confidence": "high"},
            "processing_reliability": {"passed": False, "confidence": "high", "priority": "critical"}
        }

        result = validator._calculate_overall_result(individual_criteria)

        assert result["status"] == "fail"
        assert result["passed_count"] == 1
        assert result["failed_count"] == 2
        assert result["total_count"] == 3
        assert result["pass_rate"] == 1/3
        assert result["critical_failures"] == 1

    def test_calculate_overall_result_no_data(self, validator):
        """Test overall result calculation - no implemented criteria."""
        individual_criteria = {
            "confidence_score": {"passed": None, "confidence": "not_implemented"}
        }

        result = validator._calculate_overall_result(individual_criteria)

        assert result["status"] == "no_data"
        assert result["passed_count"] == 0
        assert result["failed_count"] == 0
        assert result["total_count"] == 0
        assert result["pass_rate"] == 0

    def test_generate_recommendations(self, validator):
        """Test recommendation generation."""
        individual_criteria = {
            "good_rate": {
                "passed": False,
                "priority": "high",
                "actual_value": 0.4,
                "target_value": 0.6,
                "details": {"shortfall_assessments": 3}
            },
            "poor_rate": {
                "passed": False,
                "priority": "medium",
                "actual_value": 0.3,
                "target_value": 0.2,
                "details": {"excess_poor_assessments": 2}
            },
            "processing_reliability": {
                "passed": False,
                "priority": "critical",
                "details": {"failure_rate": 0.2, "failed_drawings": 2}
            }
        }

        recommendations = validator._generate_recommendations(individual_criteria)

        assert len(recommendations) == 3

        # Should be sorted by priority (critical first)
        assert recommendations[0]["priority"] == "critical"
        assert recommendations[0]["title"] == "Fix Processing Failures"

        # Check recommendation structure
        for rec in recommendations:
            assert "priority" in rec
            assert "title" in rec
            assert "description" in rec
            assert "actions" in rec
            assert "impact" in rec
            assert "effort" in rec

    @pytest.mark.asyncio
    async def test_analyze_trends_insufficient_data(self, validator):
        """Test trend analysis with insufficient historical data."""
        with patch.object(validator, '_load_historical_results', return_value=[]):
            trends = await validator._analyze_trends("current_run")

        assert trends["status"] == "insufficient_data"
        assert "Need at least 2 historical runs" in trends["message"]
        assert trends["available_runs"] == 0

    @pytest.mark.asyncio
    async def test_analyze_trends_success(self, validator):
        """Test successful trend analysis."""
        # Mock historical data
        historical_results = [
            {
                "timestamp": "2025-08-01T10:00:00Z",
                "assessment_summary": {
                    "good_rate": 0.6,
                    "poor_rate": 0.2,
                    "success_rate": 0.6
                }
            },
            {
                "timestamp": "2025-08-05T10:00:00Z",
                "assessment_summary": {
                    "good_rate": 0.65,
                    "poor_rate": 0.15,
                    "success_rate": 0.65
                }
            },
            {
                "timestamp": "2025-08-10T10:00:00Z",
                "assessment_summary": {
                    "good_rate": 0.7,
                    "poor_rate": 0.1,
                    "success_rate": 0.7
                }
            }
        ]

        with patch.object(validator, '_load_historical_results', return_value=historical_results):
            trends = await validator._analyze_trends("current_run")

        assert trends["status"] == "success"
        assert trends["historical_runs_analyzed"] == 3
        assert "trends" in trends
        assert trends["overall_trend"] == "improving"

        # Check specific trend data
        good_rate_trend = trends["trends"]["good_rate"]
        assert good_rate_trend["direction"] == "improving"
        assert good_rate_trend["recent_average"] > good_rate_trend["overall_average"]

    @pytest.mark.asyncio
    async def test_analyze_trends_error(self, validator):
        """Test trend analysis error handling."""
        with patch.object(validator, '_load_historical_results', side_effect=Exception("File error")):
            trends = await validator._analyze_trends("current_run")

        assert trends["status"] == "error"
        assert "Trend analysis failed" in trends["message"]

    @pytest.mark.asyncio
    async def test_load_historical_results(self, validator, tmp_path):
        """Test loading historical results."""
        # Create mock results directory
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create sample result files
        result1 = {"validation_run_id": "run1", "timestamp": "2025-08-01T10:00:00Z"}
        result2 = {"validation_run_id": "run2", "timestamp": "2025-08-05T10:00:00Z"}

        (results_dir / "run1_results.json").write_text(json.dumps(result1))
        (results_dir / "run2_results.json").write_text(json.dumps(result2))
        (results_dir / "not_a_result.txt").write_text("ignore this")

        validator.results_dir = results_dir

        historical_results = await validator._load_historical_results()

        assert len(historical_results) == 2
        assert historical_results[0]["validation_run_id"] == "run1"
        assert historical_results[1]["validation_run_id"] == "run2"

    def test_determine_overall_trend(self, validator):
        """Test overall trend determination."""
        # Test improving trend
        improving_trends = {
            "good_rate": {"direction": "improving"},
            "poor_rate": {"direction": "improving"},
            "success_rate": {"direction": "stable"}
        }
        assert validator._determine_overall_trend(improving_trends) == "improving"

        # Test declining trend
        declining_trends = {
            "good_rate": {"direction": "declining"},
            "poor_rate": {"direction": "declining"},
            "success_rate": {"direction": "improving"}
        }
        assert validator._determine_overall_trend(declining_trends) == "declining"

        # Test stable trend
        stable_trends = {
            "good_rate": {"direction": "stable"},
            "poor_rate": {"direction": "stable"}
        }
        assert validator._determine_overall_trend(stable_trends) == "stable"

    def test_generate_alerts_critical(self, validator):
        """Test alert generation for critical failures."""
        individual_criteria = {
            "processing_reliability": {
                "passed": False,
                "priority": "critical",
                "criterion": "processing_reliability"
            }
        }

        alerts = validator._generate_alerts(individual_criteria, None)

        assert len(alerts) >= 1
        critical_alert = next((a for a in alerts if a["level"] == "critical"), None)
        assert critical_alert is not None
        assert critical_alert["type"] == "criteria_failure"
        assert "Critical Failure" in critical_alert["title"]

    def test_generate_alerts_multiple_failures(self, validator):
        """Test alert generation for multiple failures."""
        individual_criteria = {
            "good_rate": {"passed": False, "criterion": "minimum_good_rate"},
            "poor_rate": {"passed": False, "criterion": "maximum_poor_rate"}
        }

        alerts = validator._generate_alerts(individual_criteria, None)

        # Should have alert for multiple failures
        multiple_failure_alert = next((a for a in alerts if a["type"] == "multiple_failures"), None)
        assert multiple_failure_alert is not None
        assert multiple_failure_alert["level"] == "high"
        assert "Multiple Success Criteria Failed" in multiple_failure_alert["title"]

    def test_generate_alerts_declining_trend(self, validator):
        """Test alert generation for declining trends."""
        trend_analysis = {
            "status": "success",
            "overall_trend": "declining",
            "trends": {"good_rate": {"direction": "declining"}}
        }

        alerts = validator._generate_alerts({}, trend_analysis)

        # Should have trend alert
        trend_alert = next((a for a in alerts if a["type"] == "performance_degradation"), None)
        assert trend_alert is not None
        assert trend_alert["level"] == "medium"
        assert "Performance Degradation" in trend_alert["title"]

    @patch('src.utils.success_criteria_validator.SuccessCriteriaValidator.results_dir')
    @patch('src.utils.success_criteria_validator.SuccessCriteriaValidator.alerts_dir')
    @pytest.mark.asyncio
    async def test_save_validation_results(self, mock_alerts_dir, mock_results_dir, validator, tmp_path):
        """Test saving validation results."""
        mock_results_dir.mkdir = Mock()
        mock_results_dir.__truediv__ = lambda self, other: tmp_path / other
        mock_alerts_dir.mkdir = Mock()
        mock_alerts_dir.__truediv__ = lambda self, other: tmp_path / other

        validation_data = {
            "validation_run_id": "test_save",
            "validated_at": "2025-08-10T10:30:00Z",
            "overall_result": {"status": "pass"},
            "alerts": [
                {"level": "medium", "type": "test_alert", "title": "Test Alert"}
            ]
        }

        await validator._save_validation_results(validation_data)

        # Check validation file was created
        validation_file = tmp_path / "test_save_success_criteria.json"
        assert validation_file.exists()

        with open(validation_file) as f:
            saved_data = json.load(f)
        assert saved_data["validation_run_id"] == "test_save"

        # Check alerts file was created
        alerts_file = tmp_path / "test_save_alerts.json"
        assert alerts_file.exists()

        with open(alerts_file) as f:
            alerts_data = json.load(f)
        assert len(alerts_data["alerts"]) == 1

    def test_generate_pass_fail_summary(self, validator):
        """Test pass/fail summary generation."""
        validation_results = {
            "overall_result": {
                "status": "fail",
                "passed_count": 2,
                "total_count": 4
            },
            "individual_criteria": {
                "good_rate": {
                    "criterion": "minimum_good_rate",
                    "passed": False,
                    "actual_value": 0.4,
                    "target_value": 0.6
                },
                "poor_rate": {
                    "criterion": "maximum_poor_rate",
                    "passed": True,
                    "actual_value": 0.1,
                    "target_value": 0.2
                }
            },
            "recommendations": [
                {"title": "Improve Accuracy", "priority": "high"},
                {"title": "Fix Bugs", "priority": "medium"}
            ]
        }

        summary = validator.generate_pass_fail_summary(validation_results)

        assert "Success Criteria Validation: FAIL" in summary
        assert "Criteria Passed: 2/4" in summary
        assert "Failed Criteria:" in summary
        assert "minimum_good_rate: 40.0% (target: 60.0%)" in summary
        assert "Priority Recommendations: 2" in summary
        assert "Improve Accuracy (high priority)" in summary


class TestSuccessCriteriaValidatorEdgeCases:
    """Test edge cases and error handling."""

    def test_empty_assessment_summary(self, validator):
        """Test handling of empty assessment summary."""
        empty_summary = {}

        result = validator._validate_good_rate(empty_summary)

        # Should handle missing values gracefully
        assert result["actual_value"] == 0
        assert result["passed"] is False
        assert result["details"]["good_assessments"] == 0

    def test_zero_total_assessments(self, validator):
        """Test handling of zero total assessments."""
        zero_summary = {
            "good_rate": 0,
            "total_assessments": 0,
            "good_assessments": 0
        }

        result = validator._validate_good_rate(zero_summary)

        assert result["actual_value"] == 0
        assert result["passed"] is False
        assert result["details"]["shortfall_assessments"] == 0

    def test_negative_values_handling(self, validator):
        """Test handling of negative or invalid values."""
        invalid_summary = {
            "good_rate": -0.1,  # Invalid negative rate
            "poor_rate": 1.5,   # Invalid rate > 1
            "total_assessments": -5  # Invalid negative count
        }

        # Should handle gracefully without crashing
        good_result = validator._validate_good_rate(invalid_summary)
        poor_result = validator._validate_poor_rate(invalid_summary)

        assert isinstance(good_result, dict)
        assert isinstance(poor_result, dict)

    @pytest.mark.asyncio
    async def test_corrupted_historical_results(self, validator, tmp_path):
        """Test handling of corrupted historical result files."""
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        # Create corrupted files
        (results_dir / "corrupted_results.json").write_text("invalid json {")
        (results_dir / "empty_results.json").write_text("")
        (results_dir / "valid_results.json").write_text('{"validation_run_id": "valid"}')

        validator.results_dir = results_dir

        # Should skip corrupted files and return valid ones
        historical_results = await validator._load_historical_results()

        assert len(historical_results) == 1
        assert historical_results[0]["validation_run_id"] == "valid"


@pytest.mark.parametrize("good_rate,poor_rate,expected_overall", [
    (0.8, 0.1, "pass"),    # Both criteria met
    (0.5, 0.1, "fail"),    # Good rate fails
    (0.7, 0.3, "fail"),    # Poor rate fails
    (0.4, 0.4, "fail"),    # Both fail
])
def test_overall_result_scenarios(good_rate, poor_rate, expected_overall):
    """Test various overall result scenarios."""
    validator = SuccessCriteriaValidator()

    assessment_summary = {
        "good_rate": good_rate,
        "poor_rate": poor_rate,
        "total_assessments": 10,
        "good_assessments": int(good_rate * 10),
        "poor_assessments": int(poor_rate * 10)
    }

    good_result = validator._validate_good_rate(assessment_summary)
    poor_result = validator._validate_poor_rate(assessment_summary)

    individual_criteria = {
        "good_rate": good_result,
        "poor_rate": poor_result
    }

    overall_result = validator._calculate_overall_result(individual_criteria)
    assert overall_result["status"] == expected_overall


def test_recommendation_priority_ordering():
    """Test that recommendations are properly ordered by priority."""
    validator = SuccessCriteriaValidator()

    individual_criteria = {
        "good_rate": {"passed": False, "priority": "medium"},
        "poor_rate": {"passed": False, "priority": "high"},
        "processing_reliability": {"passed": False, "priority": "critical"}
    }

    recommendations = validator._generate_recommendations(individual_criteria)

    # Should be ordered: critical, high, medium
    priorities = [rec["priority"] for rec in recommendations]
    expected_order = ["critical", "high", "medium"]
    assert priorities == expected_order
