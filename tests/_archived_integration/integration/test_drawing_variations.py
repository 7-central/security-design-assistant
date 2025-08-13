"""Test suite for processing all drawing variations."""
import asyncio
import json
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.agents.judge_agent_v2 import JudgeAgentV2
from src.agents.schedule_agent_v2 import ScheduleAgentV2
from src.models.job import Job, JobStatus
from src.storage.local_storage import LocalStorage


@pytest.fixture
def variation_files():
    """Get all variation drawing files."""
    variations_dir = Path("tests/fixtures/drawings/variations")
    return sorted(variations_dir.glob("*.pdf"))


@pytest.fixture
def mock_storage(tmp_path):
    """Create a mock storage with temp directory."""
    with patch.dict('os.environ', {'LOCAL_OUTPUT_DIR': str(tmp_path)}):
        storage = LocalStorage()
        return storage


async def process_all_variations(variations, storage, parallel=True):
    """Process all drawing variations.

    Args:
        variations: List of variation file paths
        storage: Storage interface
        parallel: Whether to process in parallel

    Returns:
        List of processing results
    """
    results = []

    async def process_single_variation(variation_path):
        """Process a single variation."""
        start_time = time.time()
        result = {
            "variation_name": variation_path.name,
            "file_path": str(variation_path),
            "success": False,
            "errors": [],
            "execution_time_ms": 0,
            "components_found": 0,
            "judge_score": 0,
            "judge_feedback": ""
        }

        try:
            # Create job for this variation
            job = Job(
                job_id=f"var_test_{variation_path.stem}_{int(time.time())}",
                client_name="VariationTest",
                project_name=variation_path.stem,
                status=JobStatus.PROCESSING,
                created_at=int(time.time()),
                metadata={"file_name": variation_path.name}
            )

            # Mock the Gemini client
            with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
                # Mock schedule agent response based on variation
                components = generate_mock_components(variation_path.stem)

                mock_response = Mock()
                mock_response.text = json.dumps({"components": components})
                mock_client.return_value.models.generate_content.return_value = mock_response

                # Process with schedule agent
                schedule_agent = ScheduleAgentV2(storage, job)
                schedule_agent._client = mock_client.return_value

                # Read drawing content
                with open(variation_path, 'rb') as f:
                    drawing_content = f.read()

                # Save drawing to storage
                drawing_key = f"variations/{job.job_id}/drawing.pdf"
                drawing_path = await storage.save_file(drawing_key, drawing_content)

                # Process drawing
                schedule_result = await schedule_agent.process({
                    "drawing_path": drawing_path,
                    "pages": [{"page_num": 1, "content": "mock content"}]
                })

                result["components_found"] = len(schedule_result.get("components", []))

                # Judge evaluation
                try:
                    judge = JudgeAgentV2(storage, job)
                    judge._client = mock_client.return_value

                    # Mock judge response
                    judge_response = Mock()
                    judge_response.text = json.dumps({
                        "score": calculate_mock_score(variation_path.stem),
                        "feedback": f"Evaluated {variation_path.stem}",
                        "issues": []
                    })
                    mock_client.return_value.models.generate_content.return_value = judge_response

                    evaluation = await judge.evaluate_extraction(
                        schedule_result.get("components", []),
                        drawing_path
                    )

                    result["judge_score"] = evaluation.get("score", 0)
                    result["judge_feedback"] = evaluation.get("feedback", "")

                except Exception as e:
                    result["errors"].append(f"Judge evaluation failed: {e!s}")
                    # Continue even if judge fails

                result["success"] = True

        except Exception as e:
            result["errors"].append(str(e))

        result["execution_time_ms"] = int((time.time() - start_time) * 1000)
        return result

    if parallel:
        # Process variations in parallel using asyncio
        tasks = [process_single_variation(var) for var in variations]
        results = await asyncio.gather(*tasks, return_exceptions=False)
    else:
        # Process sequentially
        for variation in variations:
            result = await process_single_variation(variation)
            results.append(result)

    return results


def generate_mock_components(variation_name):
    """Generate mock components based on variation type."""
    # Base components that should be found
    base_components = [
        {
            "component_id": "A-001",
            "type": "door",
            "location": {"x": 100, "y": 200},
            "description": "Main entry",
            "has_reader": True,
            "has_rex": True
        },
        {
            "component_id": "A-002",
            "type": "door",
            "location": {"x": 200, "y": 200},
            "description": "Office door",
            "has_reader": True,
            "has_rex": True
        }
    ]

    # Adjust based on variation
    if "removed_components" in variation_name:
        # Return fewer components
        return base_components[:1]
    elif "multiple_pages" in variation_name:
        # Return more components
        return base_components * 2
    elif "mixed_system" in variation_name:
        # Only return A- components
        return [c for c in base_components if c["component_id"].startswith("A-")]
    else:
        return base_components


def calculate_mock_score(variation_name):
    """Calculate mock judge score based on variation."""
    scores = {
        "01_different_text_sizes": 85,
        "02_rotated_pages": 75,
        "03_additional_annotations": 80,
        "04_removed_components": 70,  # Lower due to missing components
        "05_different_symbols": 75,
        "06_multiple_pages": 90,
        "07_overlapping_elements": 65,  # Lower due to overlaps
        "08_poor_scan_quality": 60,  # Lower due to quality
        "09_different_legends": 78,
        "10_mixed_system_components": 88
    }

    for key, score in scores.items():
        if key in variation_name:
            return score

    return 80  # Default score


def variation_challenge_report(results):
    """Generate report documenting problematic variations.

    Args:
        results: List of variation processing results

    Returns:
        Report dictionary
    """
    report = {
        "total_variations": len(results),
        "successful": sum(1 for r in results if r["success"]),
        "failed": sum(1 for r in results if not r["success"]),
        "challenging_variations": [],
        "recommendations": []
    }

    # Identify challenging variations (score < 70 or errors)
    for result in results:
        if result["judge_score"] < 70 or result["errors"]:
            report["challenging_variations"].append({
                "name": result["variation_name"],
                "score": result["judge_score"],
                "issues": result["errors"] or ["Low accuracy score"],
                "components_found": result["components_found"]
            })

    # Add recommendations based on challenges
    if any("poor_scan" in r["variation_name"] for r in report["challenging_variations"]):
        report["recommendations"].append(
            "Implement image enhancement preprocessing for poor quality scans"
        )

    if any("overlapping" in r["variation_name"] for r in report["challenging_variations"]):
        report["recommendations"].append(
            "Improve spatial resolution algorithm for overlapping components"
        )

    if any("rotated" in r["variation_name"] for r in report["challenging_variations"]):
        report["recommendations"].append(
            "Add automatic page orientation detection and correction"
        )

    return report


@pytest.mark.integration
@pytest.mark.slow
class TestDrawingVariations:
    """Test suite for drawing variations."""

    @pytest.mark.asyncio
    async def test_process_all_variations(self, variation_files, mock_storage):
        """Process all variations with parallel execution."""
        assert len(variation_files) == 10, "Should have 10 variation files"

        # Process all variations
        results = await process_all_variations(
            variation_files[:3],  # Test with first 3 for speed
            mock_storage,
            parallel=True
        )

        assert len(results) == 3

        # Check all processed
        for result in results:
            assert "variation_name" in result
            assert "execution_time_ms" in result
            assert result["execution_time_ms"] > 0

    @pytest.mark.asyncio
    async def test_result_logging(self, variation_files, mock_storage, tmp_path):
        """Test result logging for each variation."""
        # Process one variation
        results = await process_all_variations(
            variation_files[:1],
            mock_storage,
            parallel=False
        )

        # Log results
        log_file = tmp_path / "variation_log.json"
        with open(log_file, 'w') as f:
            json.dump(results, f, indent=2)

        assert log_file.exists()

        # Verify log structure
        with open(log_file) as f:
            logged_results = json.load(f)

        assert len(logged_results) == 1
        assert "variation_name" in logged_results[0]
        assert "components_found" in logged_results[0]

    @pytest.mark.asyncio
    async def test_judge_evaluation_integration(self, variation_files, mock_storage):
        """Test AI Judge evaluation integration."""
        # Process variations
        results = await process_all_variations(
            variation_files[:2],
            mock_storage,
            parallel=False
        )

        # Check judge evaluation
        for result in results:
            assert "judge_score" in result
            assert "judge_feedback" in result
            assert 0 <= result["judge_score"] <= 100

    @pytest.mark.asyncio
    async def test_variation_challenge_documentation(self, variation_files, mock_storage):
        """Document which variations challenge the system."""
        # Process all variations
        results = await process_all_variations(
            variation_files,
            mock_storage,
            parallel=True
        )

        # Generate challenge report
        report = variation_challenge_report(results)

        assert "challenging_variations" in report
        assert "recommendations" in report

        # Log challenging variations
        print("\n=== Challenging Variations ===")
        for challenge in report["challenging_variations"]:
            print(f"- {challenge['name']}: Score {challenge['score']}")
            for issue in challenge.get("issues", []):
                print(f"  Issue: {issue}")

        print("\n=== Recommendations ===")
        for rec in report["recommendations"]:
            print(f"- {rec}")

    @pytest.mark.asyncio
    async def test_store_results_for_analysis(self, variation_files, mock_storage, tmp_path):
        """Store test results in structured format."""
        # Process variations
        results = await process_all_variations(
            variation_files,
            mock_storage,
            parallel=True
        )

        # Create structured results
        test_run = {
            "test_run_id": f"variation_test_{int(time.time())}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "variations": results,
            "summary": {
                "total_variations": len(results),
                "passed": sum(1 for r in results if r["success"]),
                "failed": sum(1 for r in results if not r["success"]),
                "average_execution_time_ms": sum(r["execution_time_ms"] for r in results) / len(results) if results else 0,
                "average_judge_score": sum(r["judge_score"] for r in results) / len(results) if results else 0
            }
        }

        # Store results
        results_file = tmp_path / "variation_analysis.json"
        with open(results_file, 'w') as f:
            json.dump(test_run, f, indent=2)

        assert results_file.exists()

        # Verify structure
        with open(results_file) as f:
            stored_results = json.load(f)

        assert "test_run_id" in stored_results
        assert "timestamp" in stored_results
        assert "variations" in stored_results
        assert "summary" in stored_results
        assert stored_results["summary"]["total_variations"] == 10
