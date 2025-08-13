"""Schedule Agent V2 for analyzing security drawings using Google GenAI SDK."""
import io
import json
import time
from pathlib import Path
from typing import Any

from google.genai import types
from PIL import Image

from src.agents.base_agent_v2 import BaseAgentV2
from src.config.settings import settings
from src.models.component import Component, ComponentExtractionResult, PageComponents
from src.models.job import Job
from src.storage.interface import StorageInterface


class ScheduleAgentError(Exception):
    """Base exception for Schedule Agent."""
    pass


class ScheduleAgentV2(BaseAgentV2):
    """Agent for analyzing security drawings using Google GenAI SDK."""

    def __init__(self, storage: StorageInterface, job: Job, prompt_version: int | None = None):
        """Initialize Schedule Agent V2.

        Args:
            storage: Storage interface for checkpoints
            job: Current job being processed
            prompt_version: Optional specific prompt version to use
        """
        super().__init__(storage, job)
        self.prompt_version = prompt_version
        self.prompt_template = self._load_prompt_template()

    def _load_prompt_template(self) -> str:
        """Load the schedule prompt template."""
        # If a specific version is requested, use the version manager
        if self.prompt_version is not None:
            from src.config.prompt_version_manager import PromptVersionManager
            manager = PromptVersionManager()
            return manager.load_prompt(self.prompt_version)

        # Otherwise load the current/default prompt
        prompt_path = Path(__file__).parent.parent / "config" / "prompts" / "schedule_prompt.txt"
        try:
            with open(prompt_path) as f:
                return f.read()
        except FileNotFoundError:
            self.log_structured(
                "error",
                "Prompt template not found",
                path=str(prompt_path)
            )
            raise

    def filter_relevant_context(self, context_data: dict[str, Any], max_tokens: int = 4000) -> str:
        """Filter context sections for relevance to access control components.

        Args:
            context_data: Context checkpoint data with sections
            max_tokens: Maximum tokens to use for context (default 4000)

        Returns:
            Filtered context string for prompt injection
        """
        if not context_data or "sections" not in context_data:
            return ""

        # Keywords for relevance filtering
        keywords = ["door", "lock", "reader", "exit", "hardware", "type", "access", "control",
                   "type 11", "type 12", "maglock", "electric strike", "rex", "button"]

        relevant_sections = []
        current_tokens = 0

        # Prioritize specification sections over general sections
        sections = sorted(context_data["sections"],
                         key=lambda x: 0 if x.get("type") == "specification" else 1)

        for section in sections:
            content = section.get("content", "").lower()
            title = section.get("title", "").lower()

            # Check if section is relevant
            is_relevant = any(keyword in content or keyword in title for keyword in keywords)

            if is_relevant:
                # Estimate tokens (rough approximation: 1 token ≈ 4 characters)
                section_text = f"{section.get('title', '')}: {section.get('content', '')}"
                estimated_tokens = len(section_text) // 4

                if current_tokens + estimated_tokens <= max_tokens:
                    relevant_sections.append(section)
                    current_tokens += estimated_tokens

                    self.log_structured(
                        "info",
                        "Context section included",
                        title=section.get("title"),
                        estimated_tokens=estimated_tokens,
                        total_tokens=current_tokens
                    )
                else:
                    self.log_structured(
                        "info",
                        "Context section skipped - token limit",
                        title=section.get("title"),
                        estimated_tokens=estimated_tokens
                    )
                    break

        # Build context string
        if not relevant_sections:
            return ""

        context_parts = ["Project specifications:"]
        for section in relevant_sections:
            context_parts.append(f"\n{section.get('title', 'Section')}:")
            context_parts.append(section.get('content', ''))

        context_string = "\n".join(context_parts)

        self.log_structured(
            "info",
            "Context filtering complete",
            sections_included=len(relevant_sections),
            total_sections=len(context_data.get("sections", [])),
            estimated_tokens_used=current_tokens
        )

        return context_string

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Process PDF data and extract security components.

        Args:
            input_data: Dictionary with 'pages' key containing PDF data

        Returns:
            Dictionary with extracted components
        """
        start_time = time.time()

        self.log_structured("info", "Starting schedule agent V2 processing")

        # Validate input
        if "pages" not in input_data:
            raise ValueError("Input data must contain 'pages' key")

        pages = input_data["pages"]
        if not pages:
            raise ValueError("No pages to process")

        # Load context checkpoint if available
        context_data = None
        try:
            context_checkpoint = await self.storage.get_file(
                f"7central/{self.job.client_name}/{self.job.job_id}/checkpoint_context_v1.json"
            )
            if context_checkpoint:
                import json
                context_data = json.loads(context_checkpoint)
                self.log_structured("info", "Context checkpoint loaded successfully")
        except Exception as e:
            self.log_structured("info", f"No context checkpoint available: {e}")

        try:
            # Process pages and extract components with context
            extraction_result = await self._extract_components(pages, context_data)

            # Calculate processing time and log metrics
            processing_time_ms = int((time.time() - start_time) * 1000)

            # Log token usage and cost
            self.log_structured(
                "info",
                "Schedule agent V2 processing complete",
                tokens_used=extraction_result.processing_metadata.get("tokens_used", 0),
                estimated_cost=extraction_result.processing_metadata.get("estimated_cost", 0.0),
                processing_time_ms=processing_time_ms,
                total_components=extraction_result.total_components
            )

            # Save checkpoint
            checkpoint_data = {
                "components": extraction_result.model_dump(),
                "processing_time_ms": processing_time_ms
            }
            await self.save_checkpoint("components_extracted", checkpoint_data)

            # Update job processing results
            self.job.update_processing_results({
                "schedule_agent": {
                    "total_components": extraction_result.total_components,
                    "processing_time_ms": processing_time_ms,
                    "tokens_used": extraction_result.processing_metadata.get("tokens_used", 0),
                    "estimated_cost": extraction_result.processing_metadata.get("estimated_cost", 0.0),
                    "context_used": context_data is not None
                }
            })

            return {
                "components": extraction_result.model_dump(),
                "next_stage": "codegen"
            }

        except Exception as e:
            error_info = self.handle_error(e)
            self.log_structured("error", f"Schedule agent processing failed: {error_info.get('message', str(e))}")
            raise ScheduleAgentError(f"Processing failed: {error_info['message']}") from e

    async def _extract_components(self, pages: list[dict[str, Any]], context_data: dict[str, Any] | None = None) -> ComponentExtractionResult:
        """Extract components from PDF pages using native PDF support.

        Args:
            pages: List of page data dictionaries
            context_data: Optional context checkpoint data

        Returns:
            ComponentExtractionResult with extracted components
        """
        self.log_structured("info", "Starting component extraction", total_pages=len(pages), has_context=context_data is not None)

        # Check if we have a PDF file path
        pdf_path = pages[0].get("pdf_path") if pages else None

        if pdf_path and Path(pdf_path).exists():
            # Use native PDF upload for better performance
            return await self._extract_components_native_pdf(pdf_path, context_data)
        else:
            # Fall back to page-by-page processing
            return await self._extract_components_by_pages(pages, context_data)

    async def _extract_components_native_pdf(self, pdf_path: str, context_data: dict[str, Any] | None = None) -> ComponentExtractionResult:
        """Extract components using the working method - FileData with file_uri.

        Args:
            pdf_path: Path to the PDF file
            context_data: Optional context checkpoint data

        Returns:
            ComponentExtractionResult with extracted components
        """
        self.log_structured("info", "Using working method: FileData with file_uri", pdf_path=pdf_path)

        # Upload PDF file
        uploaded_file = self.upload_file(pdf_path)
        self.log_structured("info", f"File uploaded: {uploaded_file.name}, URI: {uploaded_file.uri}")

        # Filter and prepare context
        context_section = ""
        if context_data:
            context_section = self.filter_relevant_context(context_data)

        # Build prompt with context injection
        prompt = self.prompt_template.format(
            context_section=context_section if context_section else "",
            page_number="all",
            total_pages="entire document"
        )

        # Generate content using the WORKING method
        from google.genai import types
        file_part = types.Part(
            file_data=types.FileData(
                file_uri=uploaded_file.uri,  # Use file_uri not fileUri!
                mime_type="application/pdf"
            )
        )

        # Use gemini-2.5-pro model for extraction
        response = self.generate_content(
            model_name="models/gemini-2.5-pro",
            contents=[prompt, file_part]
        )

        # Parse response
        return self._parse_extraction_response(response)

    async def _extract_components_by_pages(self, pages: list[dict[str, Any]], context_data: dict[str, Any] | None = None) -> ComponentExtractionResult:
        """Extract components page by page (fallback method).

        Args:
            pages: List of page data dictionaries
            context_data: Optional context checkpoint data

        Returns:
            ComponentExtractionResult with extracted components
        """
        all_results = []
        total_tokens = 0

        # Filter context once for all pages
        context_section = ""
        if context_data:
            context_section = self.filter_relevant_context(context_data)

        for i, page_data in enumerate(pages):
            page_num = i + 1
            self.log_structured("info", f"Processing page {page_num}/{len(pages)}")

            # Build content for this page with context
            contents = self._build_page_content(page_data, page_num, len(pages), context_section)

            # Generate content
            response = self.generate_content(
                model_name=settings.gemini_model,
                contents=contents
            )

            # Track token usage
            if hasattr(response, 'usage_metadata'):
                total_tokens += response.usage_metadata.total_token_count

            # Parse components from response
            page_result = self._parse_page_response(response, page_num)
            if page_result.components:
                all_results.append(page_result)

        # Calculate cost (Gemini 2.5 Pro pricing)
        estimated_cost = (total_tokens / 1_000_000) * 2.50

        return ComponentExtractionResult(
            pages=all_results,
            processing_metadata={
                "tokens_used": total_tokens,
                "estimated_cost": estimated_cost,
                "processing_method": "page_by_page"
            }
        )

    def _build_page_content(self, page_data: dict[str, Any], page_num: int, total_pages: int, context_section: str = "") -> list[Any]:
        """Build content for Gemini from page data.

        Args:
            page_data: Page data with either 'content' (text) or 'image' (PIL Image)
            page_num: Current page number
            total_pages: Total number of pages
            context_section: Optional context string to inject

        Returns:
            List of content items for Gemini
        """
        contents = []

        # Add prompt with context
        prompt = self.prompt_template.format(
            context_section=context_section,
            page_number=page_num,
            total_pages=total_pages
        )
        contents.append(prompt)

        # Add image if this is a scanned page
        if "image" in page_data and isinstance(page_data["image"], Image.Image):
            # For GenAI SDK, we need to save image temporarily
            img_buffer = io.BytesIO()
            page_data["image"].save(img_buffer, format='PNG')
            img_buffer.seek(0)

            # Create a temporary file
            import tempfile
            with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                tmp_file.write(img_buffer.getvalue())
                tmp_path = tmp_file.name

            # Upload the image
            uploaded_image = self.upload_file(tmp_path)
            contents.append(uploaded_image)

            # Clean up temp file
            Path(tmp_path).unlink()

        # Add text content if available
        elif "content" in page_data and page_data["content"]:
            contents.append(f"Page {page_num} text content:\n{page_data['content']}")

        return contents

    def _parse_extraction_response(self, response: types.GenerateContentResponse) -> ComponentExtractionResult:
        """Parse the extraction response from Gemini.

        Args:
            response: Response from Gemini

        Returns:
            ComponentExtractionResult
        """
        try:
            # Extract JSON from response
            response_text = response.text

            # Find JSON content
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result_data = json.loads(json_str)

                # Convert to our model
                pages = []
                for page_data in result_data.get("pages", []):
                    components = []
                    page_num = page_data.get("page_num", 1)
                    for comp_data in page_data.get("components", []):
                        # Ensure page_number is set
                        if "page_number" not in comp_data:
                            comp_data["page_number"] = page_num
                        component = Component(**comp_data)
                        components.append(component)

                    if components:
                        pages.append(PageComponents(
                            page_num=page_data["page_num"],
                            components=components
                        ))

                # Track token usage
                tokens_used = 0
                if hasattr(response, 'usage_metadata'):
                    tokens_used = response.usage_metadata.total_token_count

                return ComponentExtractionResult(
                    pages=pages,
                    processing_metadata={
                        "tokens_used": tokens_used,
                        "estimated_cost": (tokens_used / 1_000_000) * 2.50,
                        "processing_method": "native_pdf"
                    }
                )
            else:
                raise ValueError("No valid JSON found in response")

        except Exception as e:
            self.log_structured("error", f"Failed to parse extraction response: {e}")
            return ComponentExtractionResult(pages=[], processing_metadata={"error": str(e)})

    def _parse_page_response(self, response: types.GenerateContentResponse, page_num: int) -> PageComponents:
        """Parse response for a single page.

        Args:
            response: Response from Gemini
            page_num: Page number

        Returns:
            PageComponents for this page
        """
        try:
            # Similar parsing logic but for single page
            response_text = response.text
            json_start = response_text.find('{')
            json_end = response_text.rfind('}') + 1

            if json_start >= 0 and json_end > json_start:
                json_str = response_text[json_start:json_end]
                result_data = json.loads(json_str)

                components = []
                # Handle both single page and multi-page response formats
                if "components" in result_data:
                    comp_list = result_data["components"]
                elif "pages" in result_data and result_data["pages"]:
                    comp_list = result_data["pages"][0].get("components", [])
                else:
                    comp_list = []

                for comp_data in comp_list:
                    # Ensure page_number is set
                    if "page_number" not in comp_data:
                        comp_data["page_number"] = page_num
                    component = Component(**comp_data)
                    components.append(component)

                return PageComponents(page_num=page_num, components=components)

        except Exception as e:
            self.log_structured("error", f"Failed to parse page {page_num} response: {e}")

        return PageComponents(page_num=page_num, components=[])
