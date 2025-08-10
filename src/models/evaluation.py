"""Data models for Judge Agent evaluation results."""
from typing import ClassVar, Literal

from pydantic import BaseModel, Field


class JudgeEvaluation(BaseModel):
    """Model for Judge Agent evaluation results."""

    overall_assessment: str = Field(
        ...,
        description="Overall assessment with Good/Fair/Poor rating and reasoning"
    )

    completeness: str = Field(
        ...,
        description="Description of what components were found vs missed"
    )

    correctness: str = Field(
        ...,
        description="Assessment of accuracy in identification and classification"
    )

    context_usage: str = Field(
        ...,
        description="How well the provided context was applied"
    )

    spatial_understanding: str = Field(
        ...,
        description="Quality of spatial relationship understanding"
    )

    false_positives: str = Field(
        ...,
        description="Any incorrectly identified components"
    )

    improvement_suggestions: list[str] = Field(
        default_factory=list,
        description="Specific actionable suggestions for improvement"
    )

    error: str | None = Field(
        None,
        description="Error message if evaluation failed"
    )

    class Config:
        """Pydantic configuration."""
        json_schema_extra: ClassVar = {
            "example": {
                "overall_assessment": "Good performance - extracted 92% of visible components with high accuracy",
                "completeness": "Found all main door readers and exit buttons, missed 2 emergency exit sensors",
                "correctness": "Door IDs accurate, component types correctly classified",
                "context_usage": "Successfully applied lock type specifications from context document",
                "spatial_understanding": "Excellent door-reader associations, proper floor assignments",
                "false_positives": "None detected",
                "improvement_suggestions": [
                    "Focus on identifying emergency exit door sensors",
                    "Improve detection of components in crowded annotation areas"
                ]
            }
        }


class EvaluationMetadata(BaseModel):
    """Metadata for evaluation results."""

    timestamp: str = Field(
        ...,
        description="ISO timestamp of evaluation"
    )

    model_used: str = Field(
        default="gemini-2.0-flash-exp",
        description="AI model used for evaluation"
    )

    components_evaluated: int = Field(
        ...,
        description="Number of components evaluated"
    )

    assessment_category: Literal["Good", "Fair", "Poor", "Unknown"] = Field(
        ...,
        description="Categorized assessment level"
    )

    has_context: bool = Field(
        ...,
        description="Whether context was provided for evaluation"
    )

    has_drawing: bool = Field(
        ...,
        description="Whether original drawing was provided"
    )

    has_excel: bool = Field(
        ...,
        description="Whether Excel file was generated"
    )


class EvaluationCheckpoint(BaseModel):
    """Complete evaluation checkpoint data."""

    evaluation: JudgeEvaluation = Field(
        ...,
        description="Judge evaluation results"
    )

    metadata: EvaluationMetadata = Field(
        ...,
        description="Evaluation metadata"
    )

    job_id: str = Field(
        ...,
        description="Associated job ID"
    )

    stage: str = Field(
        default="evaluation",
        description="Pipeline stage"
    )
