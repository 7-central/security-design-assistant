#!/usr/bin/env python3
"""
Validation Suite Script

This script runs comprehensive validation testing across multiple test drawings
to evaluate the accuracy and consistency of the security drawing analysis pipeline.

Usage:
    python scripts/validation_suite.py [--dry-run] [--drawings PATTERN] [--context FILE]
"""

import argparse
import asyncio
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agents.context_agent import ContextAgent
from src.agents.excel_generation_agent import ExcelGenerationAgent
from src.agents.judge_agent_v2 import JudgeAgentV2
from src.agents.schedule_agent_v2 import ScheduleAgentV2
from src.models.job import Job, JobStatus
from src.storage.interface import StorageInterface
from src.storage.local_storage import LocalStorage
from src.utils.id_generator import generate_job_id
from src.utils.pdf_processor import PDFProcessor
from src.utils.validators import classify_context

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
VALIDATION_SUITE_DIR = Path("tests/fixtures/validation_suite")
RESULTS_DIR = Path("tests/evaluation/validation_suite/results")
REPORTS_DIR = Path("tests/evaluation/validation_suite/reports")


class ValidationSuite:
    """Main validation suite runner."""

    def __init__(self, storage: StorageInterface | None = None):
        self.storage = storage or LocalStorage()
        self.pdf_processor = PDFProcessor()
        self.validation_run_id = f"validation_{datetime.now().strftime('%Y_%m_%d_%H%M%S')}"

    async def load_test_descriptions(self) -> dict[str, Any]:
        """Load test descriptions metadata."""
        descriptions_file = VALIDATION_SUITE_DIR / "test_descriptions.json"

        if not descriptions_file.exists():
            raise FileNotFoundError(f"Test descriptions not found: {descriptions_file}")

        with open(descriptions_file) as f:
            return json.load(f)

    async def find_test_drawings(self, pattern: str | None = None) -> list[Path]:
        """Find test drawings matching the pattern."""
        drawings = list(VALIDATION_SUITE_DIR.glob(pattern)) if pattern else list(VALIDATION_SUITE_DIR.glob("*.pdf"))

        drawings.sort()  # Ensure consistent ordering
        logger.info(f"Found {len(drawings)} test drawings")
        return drawings

    async def estimate_costs(self, drawings: list[Path], context_file: Path | None = None) -> dict[str, Any]:
        """Estimate processing costs before running actual validation."""
        logger.info("Estimating validation suite costs...")

        # Cost estimates based on Gemini 2.5 pricing
        # Flash: $0.075/1M tokens, Pro: $2.50/1M tokens
        estimates = {
            "drawings_count": len(drawings),
            "estimated_tokens_per_drawing": {
                "context_processing": 5000,  # Flash model
                "schedule_analysis": 25000,  # Pro model
                "excel_generation": 8000,   # Flash model
                "judge_evaluation": 15000   # Pro model
            },
            "estimated_cost_per_drawing": {
                "context": 5000 * 0.000000075,  # $0.000375
                "schedule": 25000 * 0.0000025,  # $0.0625
                "excel": 8000 * 0.000000075,    # $0.0006
                "judge": 15000 * 0.0000025      # $0.0375
            }
        }

        total_tokens = sum(estimates["estimated_tokens_per_drawing"].values()) * len(drawings)
        total_cost = sum(estimates["estimated_cost_per_drawing"].values()) * len(drawings)

        estimates.update({
            "total_estimated_tokens": total_tokens,
            "total_estimated_cost_usd": round(total_cost, 4),
            "processing_time_estimate_minutes": len(drawings) * 3  # ~3 minutes per drawing
        })

        logger.info(f"Estimated cost: ${estimates['total_estimated_cost_usd']:.4f}")
        logger.info(f"Estimated processing time: {estimates['processing_time_estimate_minutes']} minutes")

        return estimates

    async def process_drawing_through_pipeline(
        self,
        drawing_path: Path,
        context_file: Path | None = None
    ) -> dict[str, Any]:
        """Process a single drawing through the full pipeline."""
        logger.info(f"Processing drawing: {drawing_path.name}")

        start_time = datetime.utcnow()
        job_id = generate_job_id()

        # Create job instance
        job = Job(
            job_id=job_id,
            client_name="validation_suite",
            project_name="test_validation",
            status=JobStatus.PROCESSING,
            created_at=start_time,
            updated_at=start_time,
        )

        results = {
            "drawing_name": drawing_path.name,
            "job_id": job_id,
            "start_time": start_time.isoformat(),
            "pipeline_stages": {},
            "error": None
        }

        try:
            # Read drawing file
            with open(drawing_path, 'rb') as f:
                drawing_content = f.read()

            # Process PDF
            metadata = self.pdf_processor.extract_metadata(drawing_path)
            pages, _ = self.pdf_processor.process_pdf(drawing_path)

            job.update_metadata({
                "file_name": drawing_path.name,
                "file_size_mb": round(len(drawing_content) / (1024 * 1024), 2),
                "total_pages": metadata.total_pages,
                "pdf_type": metadata.pdf_type.value,
            })

            processing_results = {
                "pages": [page.to_dict() for page in pages]
            }
            job.update_processing_results(processing_results)

            # Save drawing file
            file_key = f"validation_suite/{job_id}/{drawing_path.name}"
            await self.storage.save_file(file_key, drawing_content, job.metadata)
            job.file_path = file_key

            results["pipeline_stages"]["pdf_processing"] = {
                "status": "completed",
                "pages_count": len(pages),
                "file_size_mb": job.metadata["file_size_mb"]
            }

            # Process context if provided
            context_result = None
            if context_file and context_file.exists():
                logger.info(f"Processing context file: {context_file.name}")

                with open(context_file, 'rb') as f:
                    context_content = f.read()

                context_classification = classify_context(
                    context_file_content=context_content,
                    mime_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                    filename=context_file.name
                )

                if context_classification:
                    context_agent = ContextAgent(storage=self.storage, job=job)
                    context_input = {
                        "context_type": context_classification,
                        "context_file_path": str(context_file)
                    }

                    context_result = await asyncio.wait_for(
                        context_agent.process(context_input),
                        timeout=30.0
                    )

                    job.update_processing_results({"context": context_result})
                    await self.storage.save_job_status(job_id, job.to_dict())

                    results["pipeline_stages"]["context_processing"] = {
                        "status": "completed",
                        "context_type": context_classification.get("type"),
                        "specifications_found": len(context_result.get("context", {}).get("specifications", []))
                    }

            # Run Schedule Agent
            logger.info(f"Running schedule analysis for {drawing_path.name}")
            schedule_agent = ScheduleAgentV2(storage=self.storage, job=job)

            schedule_input = {"pages": processing_results["pages"]}
            agent_result = await schedule_agent.process(schedule_input)

            # Flatten components
            flattened_components = []
            if isinstance(agent_result, dict) and "components" in agent_result:
                components_data = agent_result["components"]
                if isinstance(components_data, dict) and "pages" in components_data:
                    for page in components_data["pages"]:
                        if isinstance(page, dict) and "components" in page:
                            flattened_components.extend(page["components"])
                elif isinstance(components_data, list):
                    flattened_components = components_data

            job.update_processing_results({
                "schedule_agent": {
                    "completed": True,
                    "components": agent_result,
                    "flattened_components": flattened_components
                }
            })
            await self.storage.save_job_status(job_id, job.to_dict())

            results["pipeline_stages"]["schedule_analysis"] = {
                "status": "completed",
                "components_found": len(flattened_components)
            }

            # Run Excel Generation Agent
            logger.info(f"Generating Excel for {drawing_path.name}")
            excel_agent = ExcelGenerationAgent(storage=self.storage, job=job)

            excel_result = await excel_agent.process({
                "components": flattened_components
            })

            job.update_processing_results({
                "excel_generation": {
                    "completed": excel_result.get("status") == "completed",
                    "file_path": excel_result.get("file_path"),
                    "summary": excel_result.get("summary", {})
                }
            })

            excel_file_path = excel_result.get("file_path")
            if excel_file_path:
                job.update_metadata({"excel_file_path": excel_file_path})

            await self.storage.save_job_status(job_id, job.to_dict())

            results["pipeline_stages"]["excel_generation"] = {
                "status": "completed" if excel_result.get("status") == "completed" else "failed",
                "file_path": excel_file_path,
                "summary": excel_result.get("summary", {})
            }

            # Run Judge Agent
            logger.info(f"Running judge evaluation for {drawing_path.name}")
            judge_agent = JudgeAgentV2(storage=self.storage, job=job)

            judge_input = {
                "drawing_file": str(drawing_path),
                "context": context_result.get("context") if context_result else None,
                "components": flattened_components,
                "excel_file": excel_file_path
            }

            judge_result = await judge_agent.process(judge_input)

            job.update_processing_results({
                "evaluation": judge_result.get("evaluation", {}),
                "evaluation_metadata": judge_result.get("metadata", {})
            })

            await self.storage.save_job_status(job_id, job.to_dict())

            evaluation = judge_result.get("evaluation", {})
            results["pipeline_stages"]["judge_evaluation"] = {
                "status": "completed",
                "overall_assessment": evaluation.get("overall_assessment", "Unknown"),
                "evaluation": evaluation
            }

            # Mark job as completed
            end_time = datetime.utcnow()
            processing_time = (end_time - start_time).total_seconds()
            job.mark_completed(processing_time)
            await self.storage.save_job_status(job_id, job.to_dict())

            results.update({
                "end_time": end_time.isoformat(),
                "processing_time_seconds": processing_time,
                "status": "completed",
                "overall_assessment": evaluation.get("overall_assessment", "Unknown"),
                "components_count": len(flattened_components),
                "evaluation_details": evaluation
            })

            logger.info(f"Completed {drawing_path.name}: {evaluation.get('overall_assessment', 'Unknown')} - {len(flattened_components)} components")

        except Exception as e:
            logger.error(f"Error processing {drawing_path.name}: {e}")
            results.update({
                "end_time": datetime.utcnow().isoformat(),
                "status": "failed",
                "error": str(e),
                "error_type": type(e).__name__
            })

        return results

    async def run_validation_suite(
        self,
        drawings_pattern: str | None = None,
        context_file: Path | None = None,
        dry_run: bool = False
    ) -> dict[str, Any]:
        """Run the complete validation suite."""
        logger.info(f"Starting validation suite run: {self.validation_run_id}")

        # Load test descriptions and find drawings
        test_descriptions = await self.load_test_descriptions()
        test_drawings = await self.find_test_drawings(drawings_pattern)

        if not test_drawings:
            raise ValueError("No test drawings found matching pattern")

        # Estimate costs
        cost_estimates = await self.estimate_costs(test_drawings, context_file)

        if dry_run:
            logger.info("Dry run mode - stopping before actual processing")
            return {
                "validation_run_id": self.validation_run_id,
                "dry_run": True,
                "cost_estimates": cost_estimates,
                "test_drawings": [str(d) for d in test_drawings]
            }

        # Confirm processing
        logger.info(f"About to process {len(test_drawings)} drawings")
        logger.info(f"Estimated cost: ${cost_estimates['total_estimated_cost_usd']:.4f}")

        # Process each drawing
        results = []
        start_time = datetime.utcnow()

        for drawing_path in test_drawings:
            try:
                result = await self.process_drawing_through_pipeline(drawing_path, context_file)
                results.append(result)

                # Brief pause between drawings to avoid rate limiting
                await asyncio.sleep(1)

            except Exception as e:
                logger.error(f"Failed to process {drawing_path.name}: {e}")
                results.append({
                    "drawing_name": drawing_path.name,
                    "status": "failed",
                    "error": str(e),
                    "error_type": type(e).__name__
                })

        end_time = datetime.utcnow()
        total_processing_time = (end_time - start_time).total_seconds()

        # Compile final results
        validation_results = {
            "validation_run_id": self.validation_run_id,
            "timestamp": end_time.isoformat(),
            "test_descriptions_version": test_descriptions.get("test_set_version"),
            "processing_summary": {
                "total_drawings": len(test_drawings),
                "successful_processing": len([r for r in results if r.get("status") == "completed"]),
                "failed_processing": len([r for r in results if r.get("status") == "failed"]),
                "total_processing_time_seconds": total_processing_time,
                "average_time_per_drawing": total_processing_time / len(test_drawings) if test_drawings else 0
            },
            "assessment_summary": self._calculate_assessment_summary(results),
            "cost_estimates": cost_estimates,
            "drawing_results": results,
            "test_metadata": test_descriptions
        }

        # Save results
        await self._save_validation_results(validation_results)

        logger.info(f"Validation suite completed: {self.validation_run_id}")
        return validation_results

    def _calculate_assessment_summary(self, results: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate summary statistics from judge assessments."""
        completed_results = [r for r in results if r.get("status") == "completed"]

        if not completed_results:
            return {"error": "No successfully completed assessments"}

        assessments = [r.get("overall_assessment", "Unknown") for r in completed_results]

        good_count = assessments.count("Good")
        fair_count = assessments.count("Fair")
        poor_count = assessments.count("Poor")
        unknown_count = assessments.count("Unknown")

        total = len(assessments)

        return {
            "total_assessments": total,
            "good_assessments": good_count,
            "fair_assessments": fair_count,
            "poor_assessments": poor_count,
            "unknown_assessments": unknown_count,
            "success_rate": round(good_count / total, 3) if total > 0 else 0,
            "good_rate": round(good_count / total, 3) if total > 0 else 0,
            "fair_rate": round(fair_count / total, 3) if total > 0 else 0,
            "poor_rate": round(poor_count / total, 3) if total > 0 else 0,
            "meets_success_criteria": {
                "minimum_60_percent_good": (good_count / total) >= 0.6 if total > 0 else False,
                "maximum_20_percent_poor": (poor_count / total) <= 0.2 if total > 0 else False
            }
        }

    async def _save_validation_results(self, results: dict[str, Any]) -> None:
        """Save validation results to file."""
        # Ensure results directory exists
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)

        # Save detailed results
        results_file = RESULTS_DIR / f"{self.validation_run_id}_results.json"
        with open(results_file, 'w') as f:
            json.dump(results, f, indent=2, default=str)

        logger.info(f"Validation results saved to: {results_file}")


async def main():
    """Main entry point for validation suite."""
    parser = argparse.ArgumentParser(description="Run validation suite for security drawing analysis")
    parser.add_argument("--dry-run", action="store_true", help="Estimate costs without running actual validation")
    parser.add_argument("--drawings", help="Pattern to match specific test drawings (e.g., '01_*.pdf')")
    parser.add_argument("--context", type=Path, help="Context file to use for all tests")

    args = parser.parse_args()

    try:
        suite = ValidationSuite()
        results = await suite.run_validation_suite(
            drawings_pattern=args.drawings,
            context_file=args.context,
            dry_run=args.dry_run
        )

        if args.dry_run:
            print(f"Dry run completed - would process {results['cost_estimates']['drawings_count']} drawings")
            print(f"Estimated cost: ${results['cost_estimates']['total_estimated_cost_usd']:.4f}")
        else:
            summary = results["assessment_summary"]
            print(f"\nValidation Suite Results ({results['validation_run_id']}):")
            print(f"  Total drawings: {summary['total_assessments']}")
            print(f"  Good assessments: {summary['good_assessments']} ({summary['good_rate']:.1%})")
            print(f"  Fair assessments: {summary['fair_assessments']} ({summary['fair_rate']:.1%})")
            print(f"  Poor assessments: {summary['poor_assessments']} ({summary['poor_rate']:.1%})")

            criteria = summary["meets_success_criteria"]
            print("\nSuccess Criteria:")
            print(f"  ✓ Min 60% Good: {criteria['minimum_60_percent_good']}")
            print(f"  ✓ Max 20% Poor: {criteria['maximum_20_percent_poor']}")

            overall_pass = criteria['minimum_60_percent_good'] and criteria['maximum_20_percent_poor']
            print(f"\n  Overall: {'PASS' if overall_pass else 'FAIL'}")

    except Exception as e:
        logger.error(f"Validation suite failed: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
