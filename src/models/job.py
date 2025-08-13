"""Job model for tracking drawing processing jobs."""
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


class JobStatus(str, Enum):
    """Job processing status."""

    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class Job:
    """Job model for tracking PDF processing tasks."""

    job_id: str
    client_name: str
    project_name: str
    status: JobStatus
    created_at: datetime
    updated_at: datetime

    # PDF processing fields
    metadata: dict[str, Any] = field(default_factory=dict)
    processing_results: dict[str, Any] = field(default_factory=dict)

    # Optional fields
    file_path: str | None = None
    error_message: str | None = None
    processing_time_seconds: float | None = None

    def update_metadata(self, pdf_metadata: dict[str, Any]) -> None:
        """Update job metadata with PDF information.

        Args:
            pdf_metadata: Dictionary containing PDF metadata
        """
        self.metadata.update(pdf_metadata)
        self.updated_at = datetime.utcnow()

    def update_processing_results(self, results: dict[str, Any]) -> None:
        """Update processing results.

        Args:
            results: Processing results to store
        """
        self.processing_results.update(results)
        self.updated_at = datetime.utcnow()

    def mark_completed(self, processing_time: float) -> None:
        """Mark job as completed.

        Args:
            processing_time: Total processing time in seconds
        """
        self.status = JobStatus.COMPLETED
        self.processing_time_seconds = processing_time
        self.updated_at = datetime.utcnow()

    def mark_failed(self, error: str) -> None:
        """Mark job as failed with error message.

        Args:
            error: Error message
        """
        self.status = JobStatus.FAILED
        self.error_message = error
        self.updated_at = datetime.utcnow()

    def to_dict(self) -> dict[str, Any]:
        """Convert job to dictionary representation."""
        return {
            "job_id": self.job_id,
            "client_name": self.client_name,
            "project_name": self.project_name,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "processing_results": self.processing_results,
            "file_path": self.file_path,
            "error_message": self.error_message,
            "processing_time_seconds": self.processing_time_seconds,
        }
