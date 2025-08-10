"""Component models for security schedule extraction."""
from typing import Any

from pydantic import BaseModel, Field


class ComponentAttributes(BaseModel):
    """Flexible attributes for project-specific component properties."""
    model_config = {"extra": "allow"}


class Component(BaseModel):
    """Component model for extracted security components with enhanced reasoning."""
    id: str = Field(..., description="Component ID e.g. A-101-DR-B2")
    type: str = Field(..., description="Component type: door, reader, exit_button, lock")
    location: str = Field(..., description="Descriptive location")
    page_number: int = Field(..., description="Source page in PDF")
    confidence: float = Field(default=0.95, ge=0.0, le=1.0, description="Confidence score 0.0-1.0")
    reasoning: str = Field(default="", description="Explanation of why component was identified, including context used")
    attributes: dict[str, Any] = Field(default_factory=dict, description="Flexible project-specific properties")


class PageComponents(BaseModel):
    """Components found on a single page."""
    page_num: int
    components: list[Component]


class ComponentExtractionResult(BaseModel):
    """Result of component extraction from drawing."""
    pages: list[PageComponents]
    total_components: int = 0
    processing_metadata: dict[str, Any] = Field(default_factory=dict)

    def model_post_init(self, __context: Any) -> None:
        """Calculate total components after initialization."""
        self.total_components = sum(len(page.components) for page in self.pages)
