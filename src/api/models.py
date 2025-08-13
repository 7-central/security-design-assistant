from typing import Any

from pydantic import BaseModel, Field

from src.models.job import JobStatus


class HealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Health status of the service")
    version: str = Field(default="1.0.0", description="Version of the service")


class DetailedHealthResponse(BaseModel):
    status: str = Field(default="healthy", description="Health status of the service")
    version: str = Field(default="1.0.0", description="Version of the service")
    environment: str = Field(..., description="Current environment (dev/staging/prod)")
    storage_mode: str = Field(..., description="Storage mode (local/aws)")
    timestamp: str = Field(..., description="Current timestamp")
    uptime: str = Field(default="unknown", description="Service uptime")
    dependencies: dict[str, str] = Field(default_factory=dict, description="Status of external dependencies")


class ProcessDrawingRequest(BaseModel):
    client_name: str = Field(..., description="Name of the client")
    project_name: str = Field(..., description="Name of the project")
    context_text: str | None = Field(default=None, description="Optional context text")


class ProcessDrawingResponse(BaseModel):
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(..., description="Current job status")
    estimated_time_seconds: int | None = Field(default=300, description="Estimated processing time in seconds")
    metadata: dict[str, Any] | None = Field(default=None, description="PDF metadata information")
    file_path: str | None = Field(default=None, description="Path to generated Excel file")
    summary: dict[str, Any] | None = Field(default=None, description="Summary statistics")


class ErrorResponse(BaseModel):
    detail: str = Field(..., description="Error message")
    status_code: int = Field(..., description="HTTP status code")
