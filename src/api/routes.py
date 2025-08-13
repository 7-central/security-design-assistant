import logging
import tempfile
from contextlib import suppress
from datetime import datetime
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse, RedirectResponse

from src.agents.context_agent import ContextAgent
from src.agents.excel_generation_agent import ExcelGenerationAgent
from src.agents.judge_agent_v2 import JudgeAgentV2
from src.agents.schedule_agent_v2 import ScheduleAgentError, ScheduleAgentV2
from src.api.models import (
    HealthResponse,
    ProcessDrawingResponse,
)
from src.models.job import Job, JobStatus
from src.storage.interface import StorageInterface
from src.storage.local_storage import LocalStorage
from src.utils.id_generator import generate_job_id
from src.utils.pdf_processor import (
    CorruptedPDFError,
    MissingDependencyError,
    PasswordProtectedPDFError,
    PDFProcessor,
)
from src.utils.validators import classify_context, validate_file_size, validate_pdf_file

router = APIRouter()
logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 100 * 1024 * 1024  # 100MB in bytes

# Initialize storage
storage: StorageInterface = LocalStorage()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="healthy", version="1.0.0")


@router.post(
    "/process-drawing",
    response_model=ProcessDrawingResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Password protected PDF"},
        413: {"description": "File too large"},
        422: {"description": "Invalid file format or missing dependencies"},
    },
)
async def process_drawing(
    drawing_file: Annotated[UploadFile, File(description="PDF drawing file")],
    client_name: Annotated[str, Form(description="Client name")],
    project_name: Annotated[str, Form(description="Project name")],
    context_file: Annotated[UploadFile | None, File(description="Optional context file (DOCX/PDF/TXT)")] = None,
    context_text: Annotated[str | None, Form(description="Optional context text")] = None,
) -> ProcessDrawingResponse:
    if not drawing_file:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="No file provided",
        )

    if drawing_file.content_type != "application/pdf":
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="File must be a PDF",
        )

    contents = await drawing_file.read()
    file_size = len(contents)
    file_size_mb = file_size / (1024 * 1024)

    size_valid, size_error = validate_file_size(file_size, MAX_FILE_SIZE)
    if not size_valid:
        if "exceeds" in size_error:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=size_error,
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=size_error,
            )

    pdf_valid, pdf_error = validate_pdf_file(contents)
    if not pdf_valid:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=pdf_error,
        )

    job_id = generate_job_id()

    # Create job instance
    job = Job(
        job_id=job_id,
        client_name=client_name,
        project_name=project_name,
        status=JobStatus.PROCESSING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
    )

    # Save file to temporary location for processing
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp_file:
        tmp_file.write(contents)
        tmp_file_path = Path(tmp_file.name)

    try:
        # Initialize PDF processor
        pdf_processor = PDFProcessor()

        # Extract metadata and process PDF
        start_time = datetime.utcnow()
        metadata = pdf_processor.extract_metadata(tmp_file_path)
        pages, _ = pdf_processor.process_pdf(tmp_file_path)
        end_time = datetime.utcnow()
        processing_time = (end_time - start_time).total_seconds()

        # Update job with metadata
        job.update_metadata({
            "file_name": drawing_file.filename,
            "file_size_mb": round(file_size_mb, 2),
            "total_pages": metadata.total_pages,
            "pdf_type": metadata.pdf_type.value,
            "processing_time_seconds": round(processing_time, 2)
        })

        # Store extracted content in memory structure
        processing_results = {
            "pages": [page.to_dict() for page in pages]
        }
        job.update_processing_results(processing_results)

        # Save file to storage
        file_key = f"{client_name}/{project_name}/{job_id}/{drawing_file.filename}"
        file_path = await storage.save_file(file_key, contents, job.metadata)
        job.file_path = file_path

        # Save job status after PDF processing
        await storage.save_job_status(job_id, job.to_dict())

        logger.info(f"PDF processed successfully: {job.metadata}")

        # Process context if provided
        context_result = None
        if context_file or context_text:
            try:
                # Classify context type
                context_file_content = None
                context_filename = None
                context_mime_type = None

                if context_file:
                    context_file_content = await context_file.read()
                    context_filename = context_file.filename
                    context_mime_type = context_file.content_type

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

                    if context_file:
                        # Save context file temporarily
                        with tempfile.NamedTemporaryFile(
                            suffix=f".{context_classification['type']}",
                            delete=False
                        ) as tmp_context:
                            tmp_context.write(context_file_content)
                            context_input["context_file_path"] = tmp_context.name

                        # Also save to storage for record keeping
                        context_key = f"{client_name}/{project_name}/{job_id}/context.{context_classification['type']}"
                        await storage.save_file(context_key, context_file_content)
                    else:
                        context_input["context_text"] = context_text

                    # Process context with timeout
                    import asyncio
                    try:
                        context_result = await asyncio.wait_for(
                            context_agent.process(context_input),
                            timeout=30.0  # 30 second timeout
                        )

                        # Update job with context results
                        job.update_processing_results({
                            "context": context_result
                        })

                        # Save checkpoint
                        await storage.save_job_status(job_id, job.to_dict())

                    except asyncio.TimeoutError:
                        logger.warning(f"Context processing timed out for job {job_id}")
                        # Continue without context

                    finally:
                        # Clean up temp file if created
                        if context_file and "context_file_path" in context_input:
                            with suppress(Exception):
                                Path(context_input["context_file_path"]).unlink()

            except Exception as e:
                logger.error(f"Context processing failed for job {job_id}: {e}")
                # Continue without context on failure

        # Initialize and run Schedule Agent
        try:
            schedule_agent = ScheduleAgentV2(storage=storage, job=job)

            # Process with Schedule Agent
            # Note: Context is loaded from checkpoint by the agent internally
            schedule_input = {
                "pages": processing_results["pages"],
                "pdf_path": str(tmp_file_path) if tmp_file_path.exists() else None
            }

            agent_result = await schedule_agent.process(schedule_input)

            # Flatten components from pages structure
            flattened_components = []

            # Debug logging
            logger.info(f"agent_result type: {type(agent_result)}")
            logger.info(f"agent_result keys: {agent_result.keys() if isinstance(agent_result, dict) else 'not a dict'}")

            # The Schedule Agent returns {"components": extraction_result.model_dump(), ...}
            # So we need to look inside agent_result["components"] for the pages
            if isinstance(agent_result, dict) and "components" in agent_result:
                components_data = agent_result["components"]

                logger.info(f"components_data type: {type(components_data)}")
                if isinstance(components_data, dict):
                    logger.info(f"components_data keys: {components_data.keys()}")

                # Check if components_data has pages structure
                if isinstance(components_data, dict) and "pages" in components_data:
                    # Extract components from each page
                    for page in components_data["pages"]:
                        if isinstance(page, dict) and "components" in page:
                            flattened_components.extend(page["components"])
                    logger.info(f"Flattened {len(flattened_components)} components from pages")
                elif isinstance(components_data, list):
                    # Already a flat list of components
                    flattened_components = components_data
                    logger.info(f"Using {len(flattened_components)} components (already flat)")
            elif isinstance(agent_result, dict) and "pages" in agent_result:
                # Fallback for direct pages structure
                for page in agent_result["pages"]:
                    if isinstance(page, dict) and "components" in page:
                        flattened_components.extend(page["components"])

            # Update job status after schedule agent
            job.update_processing_results({
                "schedule_agent": {
                    "completed": True,
                    "components": agent_result,  # Store the full result
                    "flattened_components": flattened_components  # Store flattened for Excel
                }
            })

            # Save intermediate state
            await storage.save_job_status(job_id, job.to_dict())

            # Initialize Excel Generation Agent
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

            # Run Judge Agent for evaluation
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
            job.mark_completed(processing_time=(datetime.utcnow() - start_time).total_seconds())
            await storage.save_job_status(job_id, job.to_dict())

            # Prepare response with file paths and summary
            response_data = {
                "job_id": job_id,
                "status": job.status,
                "estimated_time_seconds": 300,
                "metadata": job.metadata
            }

            # Add file path and summary if Excel was generated
            if excel_result.get("status") == "completed":
                response_data["file_path"] = excel_result.get("file_path")
                response_data["summary"] = excel_result.get("summary", {})

            return ProcessDrawingResponse(**response_data)

        except ScheduleAgentError as e:
            logger.error(f"Schedule agent error for job {job_id}: {e}")
            job.mark_failed(f"Schedule agent failed: {e!s}")
            await storage.save_job_status(job_id, job.to_dict())

            # Map different error types based on error message
            if "API_KEY_INVALID" in str(e) or "Invalid API key" in str(e):
                status_code = status.HTTP_401_UNAUTHORIZED
            elif "RATE_LIMIT_EXCEEDED" in str(e) or "Rate limit exceeded" in str(e):
                status_code = status.HTTP_429_TOO_MANY_REQUESTS
            elif "RESOURCE_EXHAUSTED" in str(e) or "Token limit exceeded" in str(e):
                status_code = status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
            else:
                status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

            raise HTTPException(status_code=status_code, detail=str(e)) from e
        except Exception as e:
            logger.error(f"Schedule Agent error for job {job_id}: {e}", exc_info=True)
            job.mark_failed(f"Schedule Agent error: {type(e).__name__}")
            await storage.save_job_status(job_id, job.to_dict())
            # Let the outer exception handler deal with it
            raise

    except PasswordProtectedPDFError as e:
        logger.error(f"Password protected PDF for job {job_id}: {e}")
        job.mark_failed("PDF is password protected")
        await storage.save_job_status(job_id, job.to_dict())
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e)
        ) from e
    except CorruptedPDFError as e:
        logger.error(f"Corrupted PDF for job {job_id}: {e}")
        job.mark_failed("PDF file is corrupted or invalid")
        await storage.save_job_status(job_id, job.to_dict())
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except MissingDependencyError as e:
        logger.error(f"Missing dependency for job {job_id}: {e}")
        job.mark_failed("System dependency missing: poppler-utils")
        await storage.save_job_status(job_id, job.to_dict())
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error(f"Unexpected error processing PDF for job {job_id}: {e}", exc_info=True)
        job.mark_failed(f"Unexpected error: {type(e).__name__}")
        await storage.save_job_status(job_id, job.to_dict())
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process PDF file"
        ) from e
    finally:
        # Clean up temporary file
        if tmp_file_path.exists():
            tmp_file_path.unlink()


@router.get("/status/{job_id}")
async def get_job_status(job_id: str):
    """Get the status of a processing job.

    Args:
        job_id: The job ID to check

    Returns:
        Job status with details

    Raises:
        404: Job not found
    """
    job_data = await storage.get_job_status(job_id)

    if not job_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Job {job_id} not found"
        )

    # Build response with all relevant information
    response = {
        "job_id": job_id,
        "status": job_data.get("status", "unknown"),
        "created_at": job_data.get("created_at"),
        "updated_at": job_data.get("updated_at"),
        "processing_time": job_data.get("processing_time"),
        "metadata": job_data.get("metadata", {}),
    }

    # Add file path if Excel was generated (or bypassed)
    processing_results = job_data.get("processing_results", {})
    excel_generation = processing_results.get("excel_generation", {})

    if excel_generation.get("bypassed"):
        response["file_path"] = None
        response["summary"] = excel_generation.get("summary", {})
        response["message"] = "Excel generation bypassed for testing"
    elif excel_generation.get("completed"):
        response["file_path"] = excel_generation.get("file_path")
        response["summary"] = excel_generation.get("summary", {})
    else:
        # Check for Excel file path in metadata (legacy)
        excel_path = job_data.get("metadata", {}).get("excel_file_path")
        if excel_path:
            response["file_path"] = excel_path

        # Add summary from Schedule Agent if available
        schedule_results = processing_results.get("schedule_agent", {})
        if schedule_results:
            component_count = len(schedule_results.get("flattened_components", []))
            response["summary"] = {
                "doors_found": component_count,
                "processing_time_seconds": job_data.get("processing_time")
            }

    # Add evaluation results if available
    evaluation = processing_results.get("evaluation")
    if evaluation:
        response["evaluation"] = {
            "overall_assessment": evaluation.get("overall_assessment"),
            "completeness": evaluation.get("completeness"),
            "correctness": evaluation.get("correctness"),
            "improvement_suggestions": evaluation.get("improvement_suggestions", [])
        }

    # Add download links if files exist
    response["files"] = {}
    if response.get("file_path"):
        response["files"]["excel"] = f"/download/{job_id}/excel"
    response["files"]["components"] = f"/download/{job_id}/components"

    return response


@router.get("/download/{job_id}/excel")
async def download_excel(job_id: str):
    """Download the generated Excel file for a job.

    Args:
        job_id: Job identifier

    Returns:
        Excel file download or redirect to presigned URL

    Raises:
        404: Job or file not found
        500: Error generating download URL
    """
    try:
        # Get job status
        job_data = await storage.get_job_status(job_id)

        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        # Check if Excel file was generated
        excel_path = job_data.get("metadata", {}).get("excel_file_path")
        if not excel_path:
            processing_results = job_data.get("processing_results", {})
            excel_generation = processing_results.get("excel_generation", {})
            excel_path = excel_generation.get("file_path")

        if not excel_path:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Excel file not found for job {job_id}"
            )

        # Check if file exists
        if not await storage.file_exists(excel_path):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Excel file no longer exists for job {job_id}"
            )

        # For AWS storage, generate presigned URL
        if hasattr(storage, 'generate_presigned_url'):
            presigned_url = await storage.generate_presigned_url(excel_path)
            return RedirectResponse(url=presigned_url)
        else:
            # For local storage, return file directly
            file_content = await storage.get_file(excel_path)

            # Save to temp file for FileResponse
            with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp_file:
                tmp_file.write(file_content)
                tmp_path = tmp_file.name

            return FileResponse(
                path=tmp_path,
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                filename=f"schedule_{job_id}.xlsx"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading Excel for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to generate download URL"
        ) from e


@router.get("/download/{job_id}/components")
async def download_components(job_id: str):
    """Download the extracted components JSON for a job.

    Args:
        job_id: Job identifier

    Returns:
        Components JSON file download

    Raises:
        404: Job or components not found
    """
    try:
        # Get job status
        job_data = await storage.get_job_status(job_id)

        if not job_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )

        # Get components from processing results
        processing_results = job_data.get("processing_results", {})
        schedule_agent_results = processing_results.get("schedule_agent", {})
        components = schedule_agent_results.get("components", [])

        if not components:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"No components found for job {job_id}"
            )

        # Convert to JSON
        import json
        components_json = json.dumps(components, indent=2)

        # Save to temp file for FileResponse
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False, mode='w') as tmp_file:
            tmp_file.write(components_json)
            tmp_path = tmp_file.name

        return FileResponse(
            path=tmp_path,
            media_type="application/json",
            filename=f"components_{job_id}.json"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error downloading components for job {job_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to download components"
        ) from e
