#!/usr/bin/env python3
"""Iterative prompt optimization script for testing and improving prompts."""
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# Add src to path
script_dir = Path(__file__).parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

# Import project modules (after path setup)
from src.agents.judge_agent_v2 import JudgeAgentV2  # noqa: E402
from src.agents.schedule_agent_v2 import ScheduleAgentV2  # noqa: E402
from src.config.prompt_version_manager import PromptVersionManager  # noqa: E402
from src.models.job import Job, JobStatus  # noqa: E402
from src.storage.local_storage import LocalStorage  # noqa: E402
from src.utils.judge_feedback_analyzer import JudgeFeedbackAnalyzer  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class PromptOptimizer:
    """Orchestrates prompt optimization iterations."""

    def __init__(self):
        self.storage = LocalStorage()
        self.prompt_manager = PromptVersionManager()
        self.feedback_analyzer = JudgeFeedbackAnalyzer()
        self.results_dir = Path("tests/evaluation/prompt_optimization_results")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        self.test_drawings = self._load_test_drawings_config()

    def _load_test_drawings_config(self) -> list[dict[str, str]]:
        """Load test drawings configuration."""
        return [
            {
                "name": "example_b2_drawing",
                "path": "tests/fixtures/pdfs/example_b2_drawing.pdf",
                "description": "Single page security drawing with standard components"
            },
            {
                "name": "103P3-E34-QCI-40098_Ver1",
                "path": "tests/fixtures/pdfs/103P3-E34-QCI-40098_Ver1.pdf",
                "description": "Multi-page complex drawing with mixed security pages"
            }
        ]

    async def run_optimization_iteration(self, prompt_version: int) -> dict:
        """Run a complete optimization iteration for a specific prompt version.

        Args:
            prompt_version: Prompt version to test

        Returns:
            Dictionary with iteration results
        """
        logger.info(f"Starting optimization iteration for prompt version {prompt_version}")

        iteration_results = {
            "version": prompt_version,
            "timestamp": datetime.utcnow().isoformat(),
            "drawings": {},
            "summary": {}
        }

        evaluations = []

        for drawing_config in self.test_drawings:
            drawing_name = drawing_config["name"]
            drawing_path = Path(drawing_config["path"])

            if not drawing_path.exists():
                logger.warning(f"Test drawing not found: {drawing_path}")
                continue

            logger.info(f"Processing drawing: {drawing_name}")

            try:
                # Process drawing with specific prompt version
                drawing_result = await self._process_drawing(drawing_path, prompt_version)

                # Run judge evaluation
                evaluation = await self._evaluate_extraction(
                    drawing_path, drawing_result
                )

                # Store results
                iteration_results["drawings"][drawing_name] = {
                    "drawing_path": str(drawing_path),
                    "components_found": len(drawing_result.get("components", [])),
                    "evaluation": evaluation
                }

                evaluations.append(evaluation)

            except Exception as e:
                logger.error(f"Failed to process {drawing_name}: {e}")
                iteration_results["drawings"][drawing_name] = {
                    "error": str(e)
                }

        # Analyze all evaluations
        if evaluations:
            analysis = self.feedback_analyzer.analyze_multiple_evaluations(evaluations)
            iteration_results["summary"] = analysis

            # Record performance in prompt manager
            performance_metrics = {
                "total_drawings": len(evaluations),
                "assessment_distribution": analysis["assessment_distribution"],
                "top_issues": [s[0] for s in analysis["top_suggestions"][:3]]
            }
            self.prompt_manager.record_performance(prompt_version, performance_metrics)

        # Save iteration results
        results_file = self.results_dir / f"v{prompt_version}" / "iteration_results.json"
        results_file.parent.mkdir(parents=True, exist_ok=True)
        results_file.write_text(json.dumps(iteration_results, indent=2))

        logger.info(f"Iteration complete for version {prompt_version}. Results saved to {results_file}")

        return iteration_results

    async def _process_drawing(self, drawing_path: Path, prompt_version: int) -> dict:
        """Process a drawing with a specific prompt version.

        Args:
            drawing_path: Path to the drawing PDF
            prompt_version: Version of prompt to use

        Returns:
            Processing results
        """
        # Create job for this processing run
        job = Job(
            job_id=f"optimization_{prompt_version}_{drawing_path.stem}_{int(datetime.utcnow().timestamp())}",
            client_name="PromptOptimization",
            project_name=f"Version{prompt_version}Test",
            status=JobStatus.PROCESSING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Initialize schedule agent with specific prompt version
        schedule_agent = ScheduleAgentV2(self.storage, job, prompt_version=prompt_version)

        # Extract components from drawing using native PDF processing
        result = await schedule_agent._extract_components_native_pdf(str(drawing_path))

        return {
            "job_id": job.job_id,
            "components": result.components if hasattr(result, 'components') else [],
            "pages": result.pages if hasattr(result, 'pages') else []
        }

    async def _evaluate_extraction(self, drawing_path: Path, extraction_result: dict) -> dict:
        """Evaluate extraction results using Judge Agent.

        Args:
            drawing_path: Path to the original drawing
            extraction_result: Results from schedule agent

        Returns:
            Judge evaluation
        """
        # Create job for evaluation
        job = Job(
            job_id=f"evaluation_{int(datetime.utcnow().timestamp())}",
            client_name="PromptOptimization",
            project_name="Evaluation",
            status=JobStatus.PROCESSING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

        # Initialize judge agent
        judge_agent = JudgeAgentV2(self.storage, job)

        # Run evaluation
        evaluation = await judge_agent.evaluate_extraction(
            drawing_path=drawing_path,
            context=None,  # No context for optimization testing
            components=extraction_result["components"],
            excel_path=None  # No Excel generation during optimization
        )

        return evaluation

    def generate_comparison_report(self, version_results: list[dict]) -> str:
        """Generate a comparison report across multiple versions.

        Args:
            version_results: List of iteration results for different versions

        Returns:
            Formatted comparison report
        """
        report = []
        report.append("=" * 80)
        report.append("PROMPT OPTIMIZATION COMPARISON REPORT")
        report.append("=" * 80)
        report.append("")

        # Summary table
        report.append("VERSION PERFORMANCE SUMMARY:")
        report.append("-" * 50)
        report.append(f"{'Version':<8} {'Good':<6} {'Fair':<6} {'Poor':<6} {'Total Drawings':<15}")
        report.append("-" * 50)

        for result in version_results:
            version = result["version"]
            summary = result.get("summary", {})
            dist = summary.get("assessment_distribution", {})
            good = dist.get("Good", 0)
            fair = dist.get("Fair", 0)
            poor = dist.get("Poor", 0)
            total = summary.get("total_evaluations", 0)

            report.append(f"v{version:<7} {good:<6} {fair:<6} {poor:<6} {total:<15}")

        report.append("-" * 50)
        report.append("")

        # Detailed analysis for each version
        for result in version_results:
            version = result["version"]
            summary = result.get("summary", {})

            report.append(f"VERSION {version} DETAILED ANALYSIS:")
            report.append("-" * 30)

            # Top suggestions for this version
            if "top_suggestions" in summary:
                report.append("Top Improvement Suggestions:")
                for i, (suggestion, count) in enumerate(summary["top_suggestions"][:3], 1):
                    report.append(f"  {i}. {suggestion} (mentioned {count} times)")
                report.append("")

            # Recurring patterns
            if "recurring_patterns" in summary:
                report.append("Recurring Patterns:")
                for pattern in summary["recurring_patterns"]:
                    report.append(f"  - {pattern}")
                report.append("")

            # Per-drawing results
            report.append("Per-drawing Results:")
            drawings = result.get("drawings", {})
            for drawing_name, drawing_data in drawings.items():
                if "evaluation" in drawing_data:
                    eval_data = drawing_data["evaluation"]
                    assessment = eval_data.get("overall_assessment", "Unknown")
                    components_count = drawing_data.get("components_found", 0)
                    report.append(f"  - {drawing_name}: {assessment} ({components_count} components)")

            report.append("")
            report.append("-" * 30)
            report.append("")

        report.append("=" * 80)

        return "\n".join(report)

    async def run_batch_optimization(self, versions: list[int]) -> None:
        """Run optimization for multiple prompt versions.

        Args:
            versions: List of prompt versions to test
        """
        logger.info(f"Starting batch optimization for versions: {versions}")

        all_results = []

        for version in versions:
            try:
                result = await self.run_optimization_iteration(version)
                all_results.append(result)

                # Generate individual report
                if result.get("summary"):
                    individual_report = self.feedback_analyzer.format_analysis_report(result["summary"])
                    report_file = self.results_dir / f"v{version}" / "analysis_report.txt"
                    report_file.write_text(individual_report)

            except Exception as e:
                logger.error(f"Failed to process version {version}: {e}")

        # Generate comparison report
        if len(all_results) > 1:
            comparison_report = self.generate_comparison_report(all_results)
            comparison_file = self.results_dir / "comparison_report.txt"
            comparison_file.write_text(comparison_report)
            logger.info(f"Comparison report saved to {comparison_file}")

        logger.info("Batch optimization complete!")


async def main():
    """Main entry point for prompt optimization script."""
    import argparse

    parser = argparse.ArgumentParser(description="Prompt optimization for schedule extraction")
    parser.add_argument("--version", "-v", type=int, help="Test specific prompt version")
    parser.add_argument("--versions", "-vs", nargs="+", type=int, help="Test multiple versions")
    parser.add_argument("--all", action="store_true", help="Test all available versions")

    args = parser.parse_args()

    optimizer = PromptOptimizer()

    if args.version:
        # Test single version
        await optimizer.run_optimization_iteration(args.version)
    elif args.versions:
        # Test multiple specific versions
        await optimizer.run_batch_optimization(args.versions)
    elif args.all:
        # Test all available versions
        manager = PromptVersionManager()
        history = manager.get_version_history()
        all_versions = [int(v) for v in history["versions"]]
        await optimizer.run_batch_optimization(sorted(all_versions))
    else:
        # Default: test current version
        manager = PromptVersionManager()
        current_version = manager.get_current_version()
        await optimizer.run_optimization_iteration(current_version)


if __name__ == "__main__":
    asyncio.run(main())
