"""Context Agent V2 for processing context documents using Google GenAI SDK."""
import json
from pathlib import Path
from typing import Any

from src.agents.base_agent_v2 import BaseAgentV2
from src.utils.pdf_processor import PDFProcessor


class ContextAgentV2(BaseAgentV2):
    """Agent for processing context documents (specifications, requirements, etc.)."""

    def __init__(self, storage, job):
        """Initialize Context Agent."""
        super().__init__(storage, job)
        self.pdf_processor = PDFProcessor()
        self.model_name = "models/gemini-2.5-pro"  # Using consistent model across agents

    def _build_context_prompt(self, content_type: str, content: str) -> str:
        """Build prompt for context extraction."""
        return f"""You are analyzing a context document for a security drawing processing system.
Your task is to extract structured information that will help understand access control components.

Document Type: {content_type}

Extract the following information in a structured format:
1. Specifications - Technical requirements, component standards, naming conventions
2. General Information - Project details, site information, revision notes
3. Component Patterns - Any patterns for identifying access control devices
4. Special Instructions - Any specific requirements or exceptions

Document Content:
{content}

Return a JSON object with this structure:
{{
    "sections": [
        {{
            "title": "Section Title",
            "content": "Extracted content",
            "type": "specification" or "general"
        }}
    ],
    "component_patterns": ["list of patterns found"],
    "key_requirements": ["important requirements"]
}}"""

    async def _process_pdf_context(self, file_path: str) -> dict[str, Any]:
        """Process PDF context document."""
        try:
            # Check if PDF is genuine or scanned
            pdf_info = self.pdf_processor.get_pdf_info(file_path)

            if pdf_info["type"] == "genuine":
                # Extract text from genuine PDF
                pages = self.pdf_processor.extract_text_from_pdf(file_path)
                full_text = "\n\n".join([f"Page {p['page']}: {p['text']}" for p in pages])

                # Use Gemini to structure the text
                prompt = self._build_context_prompt("PDF Document", full_text)
                response = await self._generate_with_retry(prompt)

            else:
                # For scanned PDFs, convert to images and use multimodal
                images = self.pdf_processor.convert_pdf_to_images(file_path)

                # Build multimodal content
                contents = ["Analyze this scanned context document and extract structured information:"]
                for img_path in images:
                    contents.append({"path": img_path, "mime_type": "image/png"})

                # Generate with multimodal content
                response = await self._generate_with_retry(contents)

            # Parse response
            return self._parse_json_response(response)

        except Exception as e:
            self.log_structured("error", f"Error processing PDF context: {e!s}")
            return {"sections": [], "error": str(e)}

    async def _process_text_context(self, content: str) -> dict[str, Any]:
        """Process text-based context."""
        try:
            prompt = self._build_context_prompt("Text Document", content)
            response = await self._generate_with_retry(prompt)
            return self._parse_json_response(response)
        except Exception as e:
            self.log_structured("error", f"Error processing text context: {e!s}")
            return {"sections": [], "error": str(e)}

    def _parse_json_response(self, response: str) -> dict[str, Any]:
        """Parse JSON response with error handling."""
        try:
            # Extract JSON from response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0].strip()
            elif "{" in response and "}" in response:
                start = response.find("{")
                end = response.rfind("}") + 1
                json_str = response[start:end]
            else:
                json_str = response

            return json.loads(json_str)
        except json.JSONDecodeError as e:
            self.log_structured("warning", f"Failed to parse JSON response: {e}")
            # Return a basic structure
            return {"sections": [{"title": "Raw Content", "content": response, "type": "general"}]}

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Process context document and extract relevant information.

        Args:
            input_data: Dictionary with context document data

        Returns:
            Dictionary with extracted context information
        """
        self.log_structured("info", "Starting context document processing")

        try:
            # Check if context is provided
            if "context_file" not in input_data and "context_text" not in input_data:
                self.log_structured("info", "No context provided, skipping context processing")
                return {"context": {"sections": []}, "next_stage": "schedule"}

            # Process based on input type
            if "context_file" in input_data:
                file_path = input_data["context_file"]
                if Path(file_path).suffix.lower() == ".pdf":
                    context_data = await self._process_pdf_context(file_path)
                else:
                    # Read text file
                    with open(file_path) as f:
                        content = f.read()
                    context_data = await self._process_text_context(content)
            else:
                # Process direct text input
                context_data = await self._process_text_context(input_data["context_text"])

            # Log processing metrics
            sections_count = len(context_data.get("sections", []))
            self.log_structured("info", f"Context processing complete - extracted {sections_count} sections")

            # Save checkpoint
            await self.save_checkpoint("context", {"context_data": context_data})

            return {"context": context_data, "next_stage": "schedule"}

        except Exception as e:
            self.log_structured("error", f"Context processing failed: {e!s}")
            # Continue without context on failure
            return {"context": {"sections": [], "error": str(e)}, "next_stage": "schedule"}
