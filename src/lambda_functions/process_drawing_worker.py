import json
import logging
import os
import tempfile
import time
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Any

from src.agents.context_agent import ContextAgent
from src.agents.excel_generation_agent import ExcelGenerationAgent
from src.agents.judge_agent_v2 import JudgeAgentV2
from src.agents.schedule_agent_v2 import ScheduleAgentError, ScheduleAgentV2
from src.models.job import Job, JobStatus
from src.utils.cloudwatch_metrics import get_metrics_client
from src.utils.error_handlers import (
    TimeoutApproachingError,
    check_lambda_timeout,
    check_memory_usage,
    create_correlation_id,
    handle_processing_stage,
    log_lambda_metrics,
    log_structured_error,
)
from src.utils.pdf_processor import (
    CorruptedPDFError,
    MissingDependencyError,
    PasswordProtectedPDFError,
    PDFProcessor,
)
from src.utils.retry_logic import RateLimitExceededException, retry_with_exponential_backoff
from src.utils.storage_manager import StorageManager
from src.utils.validators import classify_context

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def handle_stage_with_metrics(
    stage_name: str,
    stage_func: callable,
    job_id: str,
    storage,
    context: Any,
    start_time: float,
    client_name: str,
    project_name: str,
    *args,
    **kwargs
) -> Any:
    """
    Handle a processing stage with both error handling and metrics tracking.

    Args:
        stage_name: Name of the processing stage
        stage_func: Function to execute for this stage
        job_id: Job ID for tracking
        storage: Storage interface
        context: Lambda context
        start_time: Processing start time
        client_name: Client name for metrics segmentation
        project_name: Project name for metrics segmentation
        *args: Arguments for stage function
        **kwargs: Keyword arguments for stage function

    Returns:
        Stage function result
    """
    metrics = get_metrics_client(os.getenv('ENVIRONMENT', 'dev'))
    stage_start_time = time.time()

    try:
        # Execute stage with error handling
        result = await handle_processing_stage(
            stage_name,
            stage_func,
            job_id,
            storage,
            context,
            start_time,
            *args,
            **kwargs
        )

        # Track successful completion
        stage_duration = time.time() - stage_start_time
        metrics.track_job_processing_duration(
            job_id, stage_name, stage_duration, "completed", client_name, project_name
        )
        metrics.track_stage_success_failure(job_id, stage_name, True)

        return result

    except Exception as e:
        # Track failure
        stage_duration = time.time() - stage_start_time
        error_type = type(e).__name__
        metrics.track_job_processing_duration(
            job_id, stage_name, stage_duration, "failed", client_name, project_name
        )
        metrics.track_stage_success_failure(job_id, stage_name, False, error_type)
        raise

# Lambda timeout detection (15 minutes = 900 seconds)
LAMBDA_TIMEOUT = 900
TIMEOUT_BUFFER = 60  # Stop processing 1 minute before timeout


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    """
    AWS Lambda handler for processing drawing analysis jobs from SQS.

    This function processes one drawing at a time with the full pipeline:
    1. Context processing (if context provided)
    2. Schedule agent (component extraction)
    3. Excel generation
    4. Judge evaluation

    Args:
        event: Lambda event containing SQS messages
        context: Lambda context object

    Returns:
        Processing results
    """

    # Track start time for timeout detection
    start_time = time.time()
    function_name = context.function_name if context else "process_drawing_worker"

    remaining_time = context.get_remaining_time_in_millis() / 1000 if context else LAMBDA_TIMEOUT
    logger.info(f"Starting processing worker with {remaining_time:.1f}s remaining")

    # Initialize storage and metrics
    storage = StorageManager.get_storage()
    get_metrics_client(os.getenv('ENVIRONMENT', 'dev'))
    processed_records = []
    error_count = 0

    try:
        for record in event.get('Records', []):
            job_id = "unknown"
            correlation_id = create_correlation_id()

            try:
                # Parse SQS message
                message_body = json.loads(record['body'])
                job_id = message_body['job_id']
                correlation_id = create_correlation_id(job_id)

                logger.info(f"Processing job {job_id} with correlation ID {correlation_id}")

                # Enhanced timeout checking
                try:
                    check_lambda_timeout(context, start_time, TIMEOUT_BUFFER, job_id)
                except TimeoutApproachingError:
                    logger.warning(f"Approaching timeout for job {job_id}, saving progress and exiting")
                    await_sync(update_job_status(
                        storage, job_id,
                        JobStatus.PROCESSING.value,
                        {"timeout_detected": True, "processing_interrupted": True, "correlation_id": correlation_id}
                    ))
                    break

                # Check memory usage
                check_memory_usage(85.0, job_id)

                # Process the job with enhanced error handling
                result = await_sync(process_job_with_enhanced_handling(
                    storage, message_body, context, start_time, correlation_id
                ))

                processed_records.append({
                    'job_id': job_id,
                    'status': result.get('status', 'completed'),
                    'message': result.get('message', 'Processing completed'),
                    'correlation_id': correlation_id
                })

            except Exception as e:
                error_count += 1

                # Enhanced error logging
                log_structured_error(
                    e,
                    {
                        "sqs_record": record,
                        "processing_stage": "message_parsing",
                        "function_name": function_name
                    },
                    correlation_id,
                    job_id
                )

                processed_records.append({
                    'job_id': job_id,
                    'status': 'failed',
                    'error': str(e),
                    'correlation_id': correlation_id
                })

        # Log execution metrics
        execution_time = time.time() - start_time
        success = error_count == 0

        log_lambda_metrics(
            function_name,
            execution_time,
            success=success,
            error_count=error_count
        )

        return {
            'statusCode': 200,
            'body': json.dumps({
                'processed_records': len(processed_records),
                'results': processed_records,
                'execution_time': execution_time,
                'success': success
            })
        }

    except Exception as e:
        # Catch-all error handler
        execution_time = time.time() - start_time

        log_structured_error(
            e,
            {
                "event": event,
                "function_name": function_name,
                "execution_time": execution_time
            }
        )

        log_lambda_metrics(
            function_name,
            execution_time,
            success=False,
            error_count=1
        )

        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': 'Internal processing error',
                'execution_time': execution_time
            })
        }


async def process_job_with_enhanced_handling(
    storage,
    message_body: dict[str, Any],
    context: Any,
    start_time: float,
    correlation_id: str
) -> dict[str, Any]:
    """
    Process a single drawing analysis job with enhanced error handling.

    Args:
        storage: Storage interface
        message_body: SQS message containing job details
        context: Lambda context
        start_time: Processing start time
        correlation_id: Correlation ID for tracing

    Returns:
        Processing results
    """
    job_id = message_body['job_id']

    try:
        # Use the stage-based processing approach
        return await process_job_stages(storage, message_body, context, start_time, correlation_id)

    except Exception as e:
        # Log final error
        log_structured_error(
            e,
            {
                "job_id": job_id,
                "message_body": message_body,
                "processing_stage": "job_processing"
            },
            correlation_id,
            job_id
        )
        raise


async def process_job_stages(
    storage,
    message_body: dict[str, Any],
    context: Any,
    start_time: float,
    correlation_id: str
) -> dict[str, Any]:
    """
    Process job using stage-based approach with comprehensive error handling.

    Args:
        storage: Storage interface
        message_body: SQS message containing job details
        context: Lambda context
        start_time: Processing start time
        correlation_id: Correlation ID for tracing

    Returns:
        Processing results
    """
    job_id = message_body['job_id']
    client_name = message_body['client_name']
    project_name = message_body['project_name']

    # Stage 1: PDF Processing
    pdf_result = await handle_stage_with_metrics(
        "pdf_processing",
        process_pdf_stage,
        job_id,
        storage,
        context,
        start_time,
        client_name,
        project_name,
        message_body
    )

    # Stage 2: Context Processing (if needed)
    context_result = None
    if message_body.get('context_s3_key') or message_body.get('context_text'):
        context_result = await handle_stage_with_metrics(
            "context_processing",
            process_context_stage,
            job_id,
            storage,
            context,
            start_time,
            client_name,
            project_name,
            message_body,
            pdf_result['job']
        )

    # Stage 3: Component Extraction (Schedule Agent)
    schedule_result = await handle_stage_with_metrics(
        "drawing_analysis",
        process_schedule_agent_stage,
        job_id,
        storage,
        context,
        start_time,
        client_name,
        project_name,
        pdf_result['job'],
        pdf_result['pages']
    )

    # Stage 4: Excel Generation
    excel_result = await handle_stage_with_metrics(
        "excel_generation",
        process_excel_generation_stage,
        job_id,
        storage,
        context,
        start_time,
        client_name,
        project_name,
        pdf_result['job'],
        schedule_result['flattened_components']
    )

    # Stage 5: Judge Evaluation
    await handle_stage_with_metrics(
        "evaluation",
        process_judge_evaluation_stage,
        job_id,
        storage,
        context,
        start_time,
        client_name,
        project_name,
        pdf_result['job'],
        {
            'context_result': context_result,
            'flattened_components': schedule_result['flattened_components'],
            'excel_file_path': excel_result.get('file_path'),
            'pdf_file_path': pdf_result['tmp_file_path']
        }
    )

    # Finalize job
    total_processing_time = time.time() - start_time
    job = pdf_result['job']
    job.mark_completed(processing_time=total_processing_time)

    final_job_data = job.to_dict()
    final_job_data.update({
        "current_stage": "completed",
        "stages_completed": ["pdf_processing", "context_processing", "drawing_analysis", "excel_generation", "evaluation"],
        "completed_at": int(time.time()),
        "total_processing_time_seconds": round(total_processing_time, 2),
        "correlation_id": correlation_id
    })

    await storage.save_job_status(job_id, final_job_data)

    logger.info(f"Job {job_id} completed successfully in {total_processing_time:.2f}s")

    return {
        "status": "completed",
        "processing_time": total_processing_time,
        "components_found": len(schedule_result['flattened_components']),
        "excel_generated": excel_result.get('status') == 'completed'
    }


async def process_pdf_stage(message_body: dict[str, Any]) -> dict[str, Any]:
    """Process PDF extraction stage."""
    job_id = message_body['job_id']
    drawing_s3_key = message_body['drawing_s3_key']
    client_name = message_body['client_name']
    project_name = message_body['project_name']

    # Get storage from global (set in handler)
    storage = StorageManager.get_storage()

    # Download drawing file
    drawing_content = await storage.get_file(drawing_s3_key)

    # Save to temporary file for processing
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
        tmp_file.write(drawing_content)
        tmp_file_path = Path(tmp_file.name)

    try:
        # Initialize PDF processor
        pdf_processor = PDFProcessor()

        # Extract metadata and process PDF
        pdf_start_time = datetime.utcnow()
        metadata = pdf_processor.extract_metadata(tmp_file_path)
        pages, _ = pdf_processor.process_pdf(tmp_file_path)
        pdf_end_time = datetime.utcnow()
        pdf_processing_time = (pdf_end_time - pdf_start_time).total_seconds()

        # Create Job instance for agent coordination
        job = Job(
            job_id=job_id,
            client_name=client_name,
            project_name=project_name,
            status=JobStatus.PROCESSING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        job.update_metadata({
            "file_name": drawing_s3_key.split('/')[-1],
            "file_size_mb": round(len(drawing_content) / (1024 * 1024), 2),
            "total_pages": metadata.total_pages,
            "pdf_type": metadata.pdf_type.value,
            "pdf_processing_time_seconds": round(pdf_processing_time, 2),
        })

        job.update_processing_results({"pages": [page.to_dict() for page in pages]})

        return {
            'job': job,
            'pages': [page.to_dict() for page in pages],
            'tmp_file_path': tmp_file_path
        }

    except Exception:
        # Clean up temp file on error
        if tmp_file_path and tmp_file_path.exists():
            tmp_file_path.unlink()
        raise


async def process_context_stage(message_body: dict[str, Any], job: Job) -> dict[str, Any]:
    """Process context analysis stage."""
    context_s3_key = message_body.get('context_s3_key')
    context_text = message_body.get('context_text')

    storage = StorageManager.get_storage()

    context_file_content = None
    context_filename = None
    context_mime_type = None

    if context_s3_key:
        context_file_content = await storage.get_file(context_s3_key)
        context_filename = context_s3_key.split('/')[-1]

        # Determine mime type from filename
        if context_filename.lower().endswith('.docx'):
            context_mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
        elif context_filename.lower().endswith('.pdf'):
            context_mime_type = 'application/pdf'
        else:
            context_mime_type = 'text/plain'

    # Classify context type
    context_classification = classify_context(
        context_file_content=context_file_content,
        context_text=context_text,
        mime_type=context_mime_type,
        filename=context_filename
    )

    if not context_classification:
        return {"status": "skipped", "reason": "context_classification_failed"}

    logger.info(f"Context classified as: {context_classification}")

    # Initialize Context Agent
    context_agent = ContextAgent(storage=storage, job=job)

    # Prepare input data for context agent
    context_input = {"context_type": context_classification}

    if context_file_content:
        # Save context file temporarily
        with tempfile.NamedTemporaryFile(
            suffix=f".{context_classification['type']}",
            delete=False
        ) as tmp_context:
            tmp_context.write(context_file_content)
            context_input["context_file_path"] = tmp_context.name
    else:
        context_input["context_text"] = context_text

    try:
        # Process context with timeout and retry logic
        context_result = await retry_with_exponential_backoff(
            context_agent.process,
            context_input,
            max_retries=2,
            base_delay=5.0
        )

        # Update job with context results
        job.update_processing_results({
            "context": context_result
        })

        logger.info(f"Context processing completed for job {job.job_id}")
        return context_result

    except (RateLimitExceededException, TimeoutApproachingError) as e:
        logger.warning(f"Context processing failed due to {type(e).__name__}: {e}")
        return {"status": "skipped", "reason": str(e)}

    finally:
        # Clean up temp file if created
        if context_file_content and "context_file_path" in context_input:
            with suppress(Exception):
                Path(context_input["context_file_path"]).unlink()


async def process_schedule_agent_stage(job: Job, pages: list) -> dict[str, Any]:
    """Process component extraction using Schedule Agent."""
    storage = StorageManager.get_storage()

    try:
        schedule_agent = ScheduleAgentV2(storage=storage, job=job)

        # Process with Schedule Agent using retry logic
        schedule_input = {"pages": pages}
        agent_result = await retry_with_exponential_backoff(
            schedule_agent.process,
            schedule_input,
            max_retries=3,
            base_delay=10.0
        )

        # Flatten components from pages structure
        flattened_components = []

        if isinstance(agent_result, dict) and "components" in agent_result:
            components_data = agent_result["components"]

            if isinstance(components_data, dict) and "pages" in components_data:
                # Extract components from each page
                for page in components_data["pages"]:
                    if isinstance(page, dict) and "components" in page:
                        flattened_components.extend(page["components"])
            elif isinstance(components_data, list):
                # Already a flat list of components
                flattened_components = components_data
        elif isinstance(agent_result, dict) and "pages" in agent_result:
            # Fallback for direct pages structure
            for page in agent_result["pages"]:
                if isinstance(page, dict) and "components" in page:
                    flattened_components.extend(page["components"])

        # Update job status after schedule agent
        job.update_processing_results({
            "schedule_agent": {
                "completed": True,
                "components": agent_result,
                "flattened_components": flattened_components
            }
        })

        logger.info(f"Schedule agent completed for job {job.job_id}, found {len(flattened_components)} components")

        return {
            "agent_result": agent_result,
            "flattened_components": flattened_components
        }

    except ScheduleAgentError as e:
        logger.error(f"Schedule agent error for job {job.job_id}: {e}")
        raise
    except RateLimitExceededException as e:
        logger.error(f"Rate limit exceeded in schedule agent for job {job.job_id}: {e}")
        raise


async def process_excel_generation_stage(job: Job, flattened_components: list) -> dict[str, Any]:
    """Process Excel generation stage."""
    storage = StorageManager.get_storage()

    excel_agent = ExcelGenerationAgent(storage=storage, job=job)

    # Process with Excel Generation Agent using retry logic
    excel_result = await retry_with_exponential_backoff(
        excel_agent.process,
        {"components": flattened_components},
        max_retries=2,
        base_delay=5.0
    )

    # Update job with Excel generation results
    job.update_processing_results({
        "excel_generation": {
            "completed": excel_result.get("status") == "completed",
            "file_path": excel_result.get("file_path"),
            "summary": excel_result.get("summary", {})
        }
    })

    # Update job metadata with Excel file path
    if excel_result.get("file_path"):
        job.update_metadata({
            "excel_file_path": excel_result.get("file_path")
        })

    logger.info(f"Excel generation completed for job {job.job_id}")
    return excel_result


async def process_judge_evaluation_stage(job: Job, inputs: dict) -> dict[str, Any]:
    """Process judge evaluation stage."""
    storage = StorageManager.get_storage()

    try:
        judge_agent = JudgeAgentV2(storage=storage, job=job)

        # Prepare inputs for judge
        judge_input = {
            "drawing_file": str(inputs['pdf_file_path']) if inputs['pdf_file_path'] and inputs['pdf_file_path'].exists() else None,
            "context": inputs['context_result'].get("context") if inputs['context_result'] else None,
            "components": inputs['flattened_components'],
            "excel_file": inputs['excel_file_path']
        }

        # Run evaluation with retry logic
        judge_result = await retry_with_exponential_backoff(
            judge_agent.process,
            judge_input,
            max_retries=2,
            base_delay=5.0
        )

        # Update job with evaluation results
        job.update_processing_results({
            "evaluation": judge_result.get("evaluation", {}),
            "evaluation_metadata": judge_result.get("metadata", {})
        })

        # Log evaluation summary
        evaluation = judge_result.get("evaluation", {})
        overall_assessment = evaluation.get("overall_assessment", "Unknown")
        logger.info(f"Judge evaluation complete for job {job.job_id}: {overall_assessment}")

        return judge_result

    except Exception as e:
        # Log but don't fail the job if judge evaluation fails
        logger.error(f"Judge evaluation failed for job {job.job_id}: {e}")
        job.update_processing_results({
            "evaluation": {
                "overall_assessment": "Evaluation failed",
                "error": str(e)
            }
        })
        return {"evaluation": {"overall_assessment": "Evaluation failed", "error": str(e)}}
    finally:
        # Clean up PDF temp file
        if inputs['pdf_file_path'] and inputs['pdf_file_path'].exists():
            inputs['pdf_file_path'].unlink()


async def process_job(storage, message_body: dict[str, Any], context: Any, start_time: float) -> dict[str, Any]:
    """
    Process a single drawing analysis job through the full pipeline.

    Args:
        storage: Storage interface
        message_body: SQS message containing job details
        context: Lambda context
        start_time: Processing start time

    Returns:
        Processing results
    """
    job_id = message_body['job_id']
    message_body['company_client_job']
    drawing_s3_key = message_body['drawing_s3_key']
    context_s3_key = message_body.get('context_s3_key')
    context_text = message_body.get('context_text')
    client_name = message_body['client_name']
    project_name = message_body['project_name']

    try:
        # Update job status to processing
        await update_job_status(
            storage, job_id,
            JobStatus.PROCESSING.value,
            {
                "current_stage": "pdf_processing",
                "processing_started_at": int(time.time())
            }
        )

        # Step 1: Download and process PDF
        logger.info(f"Processing PDF for job {job_id}")

        # Download drawing file
        drawing_content = await storage.get_file(drawing_s3_key)

        # Save to temporary file for processing
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
            tmp_file.write(drawing_content)
            tmp_file_path = Path(tmp_file.name)

        try:
            # Initialize PDF processor
            pdf_processor = PDFProcessor()

            # Extract metadata and process PDF
            pdf_start_time = datetime.utcnow()
            metadata = pdf_processor.extract_metadata(tmp_file_path)
            pages, _ = pdf_processor.process_pdf(tmp_file_path)
            pdf_end_time = datetime.utcnow()
            pdf_processing_time = (pdf_end_time - pdf_start_time).total_seconds()

            # Update job with PDF processing results
            pdf_results = {
                "total_pages": metadata.total_pages,
                "pdf_type": metadata.pdf_type.value,
                "pdf_processing_time_seconds": round(pdf_processing_time, 2),
                "pages": [page.to_dict() for page in pages]
            }

            # Create Job instance for agent coordination
            job = Job(
                job_id=job_id,
                client_name=client_name,
                project_name=project_name,
                status=JobStatus.PROCESSING,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )

            job.update_metadata({
                "file_name": drawing_s3_key.split('/')[-1],
                "file_size_mb": round(len(drawing_content) / (1024 * 1024), 2),
                **{k: v for k, v in pdf_results.items() if k != "pages"}
            })

            job.update_processing_results({"pages": pdf_results["pages"]})

            # Save checkpoint after PDF processing
            await storage.save_job_status(job_id, job.to_dict())

            logger.info(f"PDF processing completed for job {job_id}: {job.metadata}")

            # Step 2: Process context if provided
            context_result = None
            if context_s3_key or context_text:
                logger.info(f"Processing context for job {job_id}")

                await update_job_status(
                    storage, job_id, JobStatus.PROCESSING.value,
                    {"current_stage": "context_processing"}
                )

                try:
                    context_file_content = None
                    context_filename = None
                    context_mime_type = None

                    if context_s3_key:
                        context_file_content = await storage.get_file(context_s3_key)
                        context_filename = context_s3_key.split('/')[-1]

                        # Determine mime type from filename
                        if context_filename.lower().endswith('.docx'):
                            context_mime_type = 'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
                        elif context_filename.lower().endswith('.pdf'):
                            context_mime_type = 'application/pdf'
                        else:
                            context_mime_type = 'text/plain'

                    # Classify context type
                    context_classification = classify_context(
                        context_file_content=context_file_content,
                        context_text=context_text,
                        mime_type=context_mime_type,
                        filename=context_filename
                    )

                    if context_classification:
                        logger.info(f"Context classified as: {context_classification}")

                        # Initialize Context Agent
                        context_agent = ContextAgent(storage=storage, job=job)

                        # Prepare input data for context agent
                        context_input = {"context_type": context_classification}

                        if context_file_content:
                            # Save context file temporarily
                            with tempfile.NamedTemporaryFile(
                                suffix=f".{context_classification['type']}",
                                delete=False
                            ) as tmp_context:
                                tmp_context.write(context_file_content)
                                context_input["context_file_path"] = tmp_context.name
                        else:
                            context_input["context_text"] = context_text

                        # Process context with timeout
                        import asyncio
                        try:
                            context_result = await asyncio.wait_for(
                                context_agent.process(context_input),
                                timeout=120.0  # 2 minute timeout for context
                            )

                            # Update job with context results
                            job.update_processing_results({
                                "context": context_result
                            })

                            # Save checkpoint
                            await storage.save_job_status(job_id, job.to_dict())
                            logger.info(f"Context processing completed for job {job_id}")

                        except asyncio.TimeoutError:
                            logger.warning(f"Context processing timed out for job {job_id}")
                            # Continue without context

                        finally:
                            # Clean up temp file if created
                            if context_file_content and "context_file_path" in context_input:
                                with suppress(Exception):
                                    Path(context_input["context_file_path"]).unlink()

                except Exception as e:
                    logger.error(f"Context processing failed for job {job_id}: {e}")
                    # Continue without context on failure

            # Check timeout before continuing
            elapsed_time = time.time() - start_time
            remaining_time = (context.get_remaining_time_in_millis() / 1000) if context else (LAMBDA_TIMEOUT - elapsed_time)

            if remaining_time < TIMEOUT_BUFFER:
                logger.warning(f"Timeout approaching for job {job_id}, saving progress")
                await update_job_status(
                    storage, job_id, JobStatus.PROCESSING.value,
                    {"timeout_detected": True, "stages_completed": ["pdf_processing", "context_processing"]}
                )
                return {"status": "timeout", "message": "Processing interrupted due to timeout"}

            # Step 3: Schedule Agent (Component Extraction)
            logger.info(f"Running Schedule Agent for job {job_id}")

            await update_job_status(
                storage, job_id, JobStatus.PROCESSING.value,
                {"current_stage": "component_extraction"}
            )

            try:
                schedule_agent = ScheduleAgentV2(storage=storage, job=job)

                # Process with Schedule Agent
                schedule_input = {"pages": pdf_results["pages"]}
                agent_result = await schedule_agent.process(schedule_input)

                # Flatten components from pages structure
                flattened_components = []

                if isinstance(agent_result, dict) and "components" in agent_result:
                    components_data = agent_result["components"]

                    if isinstance(components_data, dict) and "pages" in components_data:
                        # Extract components from each page
                        for page in components_data["pages"]:
                            if isinstance(page, dict) and "components" in page:
                                flattened_components.extend(page["components"])
                    elif isinstance(components_data, list):
                        # Already a flat list of components
                        flattened_components = components_data
                elif isinstance(agent_result, dict) and "pages" in agent_result:
                    # Fallback for direct pages structure
                    for page in agent_result["pages"]:
                        if isinstance(page, dict) and "components" in page:
                            flattened_components.extend(page["components"])

                # Update job status after schedule agent
                job.update_processing_results({
                    "schedule_agent": {
                        "completed": True,
                        "components": agent_result,
                        "flattened_components": flattened_components
                    }
                })

                # Save checkpoint
                await storage.save_job_status(job_id, job.to_dict())
                logger.info(f"Schedule agent completed for job {job_id}, found {len(flattened_components)} components")

            except ScheduleAgentError as e:
                logger.error(f"Schedule agent error for job {job_id}: {e}")
                await update_job_status(
                    storage, job_id, JobStatus.FAILED.value,
                    {"error": f"Schedule agent failed: {e!s}", "failed_at": int(time.time())}
                )
                return {"status": "failed", "error": str(e)}

            # Check timeout before Excel generation
            elapsed_time = time.time() - start_time
            remaining_time = (context.get_remaining_time_in_millis() / 1000) if context else (LAMBDA_TIMEOUT - elapsed_time)

            if remaining_time < TIMEOUT_BUFFER:
                logger.warning(f"Timeout approaching for job {job_id}, saving progress")
                await update_job_status(
                    storage, job_id, JobStatus.PROCESSING.value,
                    {"timeout_detected": True, "stages_completed": ["pdf_processing", "context_processing", "component_extraction"]}
                )
                return {"status": "timeout", "message": "Processing interrupted due to timeout"}

            # Step 4: Excel Generation Agent
            logger.info(f"Running Excel Generation Agent for job {job_id}")

            await update_job_status(
                storage, job_id, JobStatus.PROCESSING.value,
                {"current_stage": "excel_generation"}
            )

            excel_agent = ExcelGenerationAgent(storage=storage, job=job)

            # Process with Excel Generation Agent
            excel_result = await excel_agent.process({
                "components": flattened_components
            })

            # Update job with Excel generation results
            job.update_processing_results({
                "excel_generation": {
                    "completed": excel_result.get("status") == "completed",
                    "file_path": excel_result.get("file_path"),
                    "summary": excel_result.get("summary", {})
                }
            })

            # Update job metadata with Excel file path
            excel_file_path = None
            if excel_result.get("file_path"):
                excel_file_path = excel_result.get("file_path")
                job.update_metadata({
                    "excel_file_path": excel_file_path
                })

            # Save checkpoint before judge evaluation
            await storage.save_job_status(job_id, job.to_dict())
            logger.info(f"Excel generation completed for job {job_id}")

            # Step 5: Judge Agent Evaluation
            logger.info(f"Running Judge Agent for job {job_id}")

            await update_job_status(
                storage, job_id, JobStatus.PROCESSING.value,
                {"current_stage": "evaluation"}
            )

            try:
                judge_agent = JudgeAgentV2(storage=storage, job=job)

                # Prepare inputs for judge
                judge_input = {
                    "drawing_file": str(tmp_file_path) if tmp_file_path.exists() else None,
                    "context": context_result.get("context") if context_result else None,
                    "components": flattened_components,
                    "excel_file": excel_file_path
                }

                # Run evaluation
                judge_result = await judge_agent.process(judge_input)

                # Update job with evaluation results
                job.update_processing_results({
                    "evaluation": judge_result.get("evaluation", {}),
                    "evaluation_metadata": judge_result.get("metadata", {})
                })

                # Log evaluation summary
                evaluation = judge_result.get("evaluation", {})
                overall_assessment = evaluation.get("overall_assessment", "Unknown")
                logger.info(f"Judge evaluation complete for job {job_id}: {overall_assessment}")

            except Exception as e:
                # Log but don't fail the job if judge evaluation fails
                logger.error(f"Judge evaluation failed for job {job_id}: {e}")
                job.update_processing_results({
                    "evaluation": {
                        "overall_assessment": "Evaluation failed",
                        "error": str(e)
                    }
                })

            # Mark job as completed
            total_processing_time = time.time() - start_time
            job.mark_completed(processing_time=total_processing_time)

            # Final status update
            final_job_data = job.to_dict()
            final_job_data.update({
                "current_stage": "completed",
                "stages_completed": ["pdf_processing", "context_processing", "component_extraction", "excel_generation", "evaluation"],
                "completed_at": int(time.time()),
                "total_processing_time_seconds": round(total_processing_time, 2)
            })

            await storage.save_job_status(job_id, final_job_data)

            logger.info(f"Job {job_id} completed successfully in {total_processing_time:.2f}s")

            return {
                "status": "completed",
                "processing_time": total_processing_time,
                "components_found": len(flattened_components),
                "excel_generated": excel_result.get("status") == "completed"
            }

        finally:
            # Clean up temporary PDF file
            if tmp_file_path.exists():
                tmp_file_path.unlink()

    except PasswordProtectedPDFError as e:
        logger.error(f"Password protected PDF for job {job_id}: {e}")
        await update_job_status(
            storage, job_id, JobStatus.FAILED.value,
            {"error": "PDF is password protected", "failed_at": int(time.time())}
        )
        return {"status": "failed", "error": "PDF is password protected"}

    except CorruptedPDFError as e:
        logger.error(f"Corrupted PDF for job {job_id}: {e}")
        await update_job_status(
            storage, job_id, JobStatus.FAILED.value,
            {"error": "PDF file is corrupted or invalid", "failed_at": int(time.time())}
        )
        return {"status": "failed", "error": "PDF file is corrupted or invalid"}

    except MissingDependencyError as e:
        logger.error(f"Missing dependency for job {job_id}: {e}")
        await update_job_status(
            storage, job_id, JobStatus.FAILED.value,
            {"error": "System dependency missing: poppler-utils", "failed_at": int(time.time())}
        )
        return {"status": "failed", "error": "System dependency missing"}

    except Exception as e:
        logger.error(f"Unexpected error processing job {job_id}: {e}", exc_info=True)
        await update_job_status(
            storage, job_id, JobStatus.FAILED.value,
            {"error": f"Unexpected error: {type(e).__name__}", "failed_at": int(time.time())}
        )
        return {"status": "failed", "error": str(e)}


async def update_job_status(storage, job_id: str, status: str, additional_data: dict[str, Any]) -> None:
    """Update job status in storage with additional data."""
    try:
        # Get current job data
        current_job = await storage.get_job_status(job_id)
        if current_job:
            current_job.update({
                "status": status,
                "updated_at": int(time.time()),
                **additional_data
            })
            await storage.save_job_status(job_id, current_job)
        else:
            logger.warning(f"Job {job_id} not found when updating status")
    except Exception as e:
        logger.error(f"Failed to update job status for {job_id}: {e}")


def await_sync(coro):
    """
    Helper function to run async code in sync context.
    This is needed because Lambda handlers are sync by default.
    """
    import asyncio

    try:
        # Try to get existing event loop
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # If loop is running, create a new task
            import concurrent.futures
            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(asyncio.run, coro)
                return future.result()
        else:
            return loop.run_until_complete(coro)
    except RuntimeError:
        # No event loop, create a new one
        return asyncio.run(coro)
