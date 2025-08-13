"""Consistency validation tests for the pipeline."""
import json
import statistics
import time
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from src.agents.schedule_agent_v2 import ScheduleAgentV2
from src.models.job import Job, JobStatus
from src.storage.local_storage import LocalStorage


@pytest.fixture
def base_drawing_path():
    """Get path to base drawing for consistency testing."""
    # Use the first variation as base
    return Path("tests/fixtures/drawings/variations/01_different_text_sizes.pdf")


@pytest.fixture
def mock_storage(tmp_path):
    """Create a mock storage with temp directory."""
    with patch.dict('os.environ', {'LOCAL_OUTPUT_DIR': str(tmp_path)}):
        storage = LocalStorage()
        return storage


async def run_consistency_test(drawing_path, storage, num_runs=5):
    """Run the same drawing multiple times.

    Args:
        drawing_path: Path to drawing file
        storage: Storage interface
        num_runs: Number of times to process

    Returns:
        List of processing results
    """
    results = []

    # Read drawing once
    with open(drawing_path, 'rb') as f:
        drawing_content = f.read()

    for run_idx in range(num_runs):
        start_time = time.time()

        # Create job for this run
        job = Job(
            job_id=f"consistency_test_run_{run_idx}_{int(time.time())}",
            client_name="ConsistencyTest",
            project_name=f"Run_{run_idx}",
            status=JobStatus.PROCESSING,
            created_at=int(time.time()),
            metadata={"file_name": drawing_path.name, "run_number": run_idx}
        )

        # Mock consistent Gemini responses
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            # Use same mock components but with slight variations to simulate real behavior
            components = generate_consistent_components(run_idx)

            mock_response = Mock()
            mock_response.text = json.dumps({"components": components})
            mock_client.return_value.models.generate_content.return_value = mock_response

            # Process with schedule agent
            schedule_agent = ScheduleAgentV2(storage, job)
            schedule_agent._client = mock_client.return_value

            # Save drawing to storage
            drawing_key = f"consistency/{job.job_id}/drawing.pdf"
            saved_path = await storage.save_file(drawing_key, drawing_content)

            # Process drawing
            schedule_result = await schedule_agent.process({
                "drawing_path": saved_path,
                "pages": [{"page_num": 1, "content": "consistent content"}]
            })

            execution_time = time.time() - start_time

            results.append({
                "run_number": run_idx,
                "job_id": job.job_id,
                "components": schedule_result.get("components", []),
                "component_count": len(schedule_result.get("components", [])),
                "execution_time": execution_time,
                "timestamp": int(time.time())
            })

    return results


def generate_consistent_components(run_idx):
    """Generate consistent components with minor acceptable variations.

    This simulates real AI responses which may have slight variations
    but should be fundamentally consistent.
    """
    # Base components that should always be found
    base_components = [
        {
            "component_id": "A-200",
            "type": "door",
            "location": {"x": 100 + run_idx % 2, "y": 200},  # ±1 pixel variance
            "description": "Door with 8pt text",
            "has_reader": True,
            "has_rex": True
        },
        {
            "component_id": "A-201",
            "type": "door",
            "location": {"x": 200, "y": 200 + run_idx % 2},  # ±1 pixel variance
            "description": "Door with 10pt text",
            "has_reader": True,
            "has_rex": True
        },
        {
            "component_id": "A-202",
            "type": "door",
            "location": {"x": 300, "y": 200},
            "description": "Door with 12pt text",
            "has_reader": True,
            "has_rex": True
        }
    ]

    # Occasionally miss a component (5% chance) to simulate real variance
    import random
    random.seed(42 + run_idx)  # Deterministic for testing
    if random.random() > 0.95:
        return base_components[:-1]  # Miss last component

    return base_components


def result_comparison(results):
    """Compare results to verify consistency.

    Args:
        results: List of processing results

    Returns:
        Dictionary with comparison metrics
    """
    comparison = {
        "total_runs": len(results),
        "component_counts": [],
        "execution_times": [],
        "variations": [],
        "consistency_score": 100.0
    }

    # Extract metrics
    for result in results:
        comparison["component_counts"].append(result["component_count"])
        comparison["execution_times"].append(result["execution_time"])

    # Calculate statistics
    if len(comparison["component_counts"]) > 1:
        # Component count variance
        count_mean = statistics.mean(comparison["component_counts"])
        count_stdev = statistics.stdev(comparison["component_counts"]) if len(comparison["component_counts"]) > 1 else 0
        count_variance_pct = (count_stdev / count_mean * 100) if count_mean > 0 else 0

        comparison["component_count_stats"] = {
            "mean": count_mean,
            "stdev": count_stdev,
            "variance_pct": count_variance_pct,
            "min": min(comparison["component_counts"]),
            "max": max(comparison["component_counts"])
        }

        # Execution time variance
        time_mean = statistics.mean(comparison["execution_times"])
        time_stdev = statistics.stdev(comparison["execution_times"]) if len(comparison["execution_times"]) > 1 else 0

        comparison["execution_time_stats"] = {
            "mean": time_mean,
            "stdev": time_stdev,
            "min": min(comparison["execution_times"]),
            "max": max(comparison["execution_times"])
        }

        # Check component ID consistency
        all_component_ids = []
        for result in results:
            ids = [c["component_id"] for c in result["components"]]
            all_component_ids.append(set(ids))

        # Find common components across all runs
        if all_component_ids:
            common_ids = set.intersection(*all_component_ids)
            all_ids = set.union(*all_component_ids)

            comparison["component_id_consistency"] = {
                "common_across_all_runs": list(common_ids),
                "total_unique_ids": len(all_ids),
                "consistency_ratio": len(common_ids) / len(all_ids) if all_ids else 0
            }

        # Calculate overall consistency score
        penalties = 0

        # Penalize for component count variance > 5%
        if count_variance_pct > 5:
            penalties += (count_variance_pct - 5) * 2

        # Penalize for missing common components
        if comparison.get("component_id_consistency", {}).get("consistency_ratio", 1) < 0.9:
            penalties += (1 - comparison["component_id_consistency"]["consistency_ratio"]) * 50

        comparison["consistency_score"] = max(0, 100 - penalties)

    return comparison


def calculate_variance_metrics(results):
    """Calculate variance metrics for components.

    Args:
        results: List of processing results

    Returns:
        Dictionary with variance metrics
    """
    metrics = {
        "location_variance": [],
        "attribute_variance": []
    }

    # Group components by ID across runs
    components_by_id = {}
    for result in results:
        for component in result["components"]:
            comp_id = component["component_id"]
            if comp_id not in components_by_id:
                components_by_id[comp_id] = []
            components_by_id[comp_id].append(component)

    # Calculate location variance for each component
    for comp_id, components in components_by_id.items():
        if len(components) > 1:
            x_values = [c["location"]["x"] for c in components]
            y_values = [c["location"]["y"] for c in components]

            x_variance = statistics.variance(x_values) if len(x_values) > 1 else 0
            y_variance = statistics.variance(y_values) if len(y_values) > 1 else 0

            metrics["location_variance"].append({
                "component_id": comp_id,
                "x_variance": x_variance,
                "y_variance": y_variance,
                "max_deviation": max(
                    max(x_values) - min(x_values),
                    max(y_values) - min(y_values)
                )
            })

    return metrics


@pytest.mark.integration
@pytest.mark.slow
class TestConsistency:
    """Test consistency of pipeline processing."""

    @pytest.mark.asyncio
    async def test_run_consistency_test(self, base_drawing_path, mock_storage):
        """Process base drawing 5 times."""
        results = await run_consistency_test(
            base_drawing_path,
            mock_storage,
            num_runs=5
        )

        assert len(results) == 5

        # Check all runs completed
        for i, result in enumerate(results):
            assert result["run_number"] == i
            assert result["component_count"] > 0
            assert result["execution_time"] > 0

    @pytest.mark.asyncio
    async def test_verify_consistent_outputs(self, base_drawing_path, mock_storage):
        """Verify outputs are consistent across runs."""
        results = await run_consistency_test(
            base_drawing_path,
            mock_storage,
            num_runs=5
        )

        comparison = result_comparison(results)

        # Check consistency
        assert comparison["consistency_score"] > 95, f"Consistency score too low: {comparison['consistency_score']}"

        # Check component count variance
        stats = comparison.get("component_count_stats", {})
        assert stats.get("variance_pct", 100) < 5, f"Component count variance too high: {stats.get('variance_pct')}%"

        # Check component ID consistency
        id_consistency = comparison.get("component_id_consistency", {})
        assert id_consistency.get("consistency_ratio", 0) > 0.9, "Component IDs not consistent across runs"

    @pytest.mark.asyncio
    async def test_variance_metrics(self, base_drawing_path, mock_storage):
        """Calculate variance metrics for component locations."""
        results = await run_consistency_test(
            base_drawing_path,
            mock_storage,
            num_runs=5
        )

        metrics = calculate_variance_metrics(results)

        # Check location variance is acceptable (< 2 pixels)
        for location_var in metrics["location_variance"]:
            assert location_var["max_deviation"] <= 2, \
                f"Component {location_var['component_id']} location varies too much: {location_var['max_deviation']} pixels"

    @pytest.mark.asyncio
    async def test_document_inconsistencies(self, base_drawing_path, mock_storage, tmp_path):
        """Document any inconsistencies found."""
        results = await run_consistency_test(
            base_drawing_path,
            mock_storage,
            num_runs=10  # More runs for better statistics
        )

        comparison = result_comparison(results)
        variance_metrics = calculate_variance_metrics(results)

        # Create inconsistency report
        report = {
            "test_date": time.strftime("%Y-%m-%d %H:%M:%S"),
            "drawing": str(base_drawing_path),
            "num_runs": len(results),
            "consistency_score": comparison["consistency_score"],
            "component_count_variance": comparison.get("component_count_stats", {}).get("variance_pct", 0),
            "inconsistencies": []
        }

        # Document component count inconsistencies
        if comparison.get("component_count_stats", {}).get("variance_pct", 0) > 5:
            report["inconsistencies"].append({
                "type": "component_count_variance",
                "description": f"Component count varies by {comparison['component_count_stats']['variance_pct']:.1f}%",
                "details": comparison["component_count_stats"]
            })

        # Document location inconsistencies
        for loc_var in variance_metrics["location_variance"]:
            if loc_var["max_deviation"] > 2:
                report["inconsistencies"].append({
                    "type": "location_variance",
                    "component_id": loc_var["component_id"],
                    "description": f"Location varies by up to {loc_var['max_deviation']} pixels",
                    "details": loc_var
                })

        # Save report
        report_file = tmp_path / "consistency_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"\nConsistency Report saved to: {report_file}")
        print(f"Consistency Score: {report['consistency_score']:.1f}%")
        print(f"Inconsistencies found: {len(report['inconsistencies'])}")

        # Assert acceptable consistency
        assert report["consistency_score"] > 90, f"Overall consistency below threshold: {report['consistency_score']}%"
