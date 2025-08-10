"""Excel Generation Agent using Gemini code execution."""
import base64
import json
import logging
from typing import Any

from google.genai import types

from src.agents.base_agent_v2 import BaseAgentV2
from src.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


class ExcelGenerationAgent(BaseAgentV2):
    """Agent for generating Excel schedules from extracted components using Gemini code execution."""

    def __init__(self, storage: StorageInterface, job: Any):
        """Initialize Excel Generation Agent.

        Args:
            storage: Storage interface for file operations
            job: Job instance being processed
        """
        super().__init__(storage, job)
        self.model_name = "models/gemini-2.5-pro"
        self.cost_per_million_input = 0.075
        self.cost_per_million_output = 0.30

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Process components and generate Excel schedule.

        Args:
            input_data: Dictionary containing 'components' key with extracted component data

        Returns:
            Processing results including Excel file path and summary statistics
        """
        try:
            components = input_data.get("components", [])
            if not components:
                return {
                    "status": "error",
                    "message": "No components provided for Excel generation"
                }

            self.log_structured("info", "Starting Excel generation",
                               component_count=len(components))

            excel_base64 = await self.generate_excel(components)

            if not excel_base64:
                return {
                    "status": "error",
                    "message": "Failed to generate Excel file"
                }

            file_path = await self._save_excel(excel_base64)

            summary = self._calculate_summary(components)

            await self.save_checkpoint("excel_generation", {
                "file_path": file_path,
                "summary": summary,
                "component_count": len(components)
            })

            return {
                "status": "completed",
                "file_path": file_path,
                "summary": summary
            }

        except Exception as e:
            logger.error(f"Excel generation failed: {e}")
            return self.handle_error(e)

    async def generate_excel(self, components_json: list[dict[str, Any]]) -> str | None:
        """Generate Excel using Gemini code execution.

        Args:
            components_json: List of component dictionaries

        Returns:
            Base64 encoded Excel file data
        """
        prompt = self._build_excel_prompt(components_json)

        try:
            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=65536,
                    tools=[types.Tool(code_execution=types.ToolCodeExecution())]
                )
            )

            self._track_cost(prompt, response)

            excel_base64 = self._extract_excel_from_response(response)

            if not excel_base64:
                logger.warning("Attempting partial schedule generation")
                return self._generate_partial_schedule(components_json)

            return excel_base64

        except Exception as e:
            logger.error(f"Failed to generate Excel with Gemini: {type(e).__name__}: {str(e)[:200]}")
            return self._generate_partial_schedule(components_json)

    def _build_excel_prompt(self, components: list[dict[str, Any]]) -> str:
        """Build prompt for Gemini to generate Excel code.

        Args:
            components: List of component dictionaries

        Returns:
            Formatted prompt for Gemini
        """
        components_json = json.dumps(components, indent=2)

        return f"""Generate an Excel file for the security door schedule using the following component data.

Component data:
```json
{components_json}
```

Requirements:
1. Create an Excel file with these columns:
   - Door ID (primary key from component id)
   - Location (from component location field)
   - Reader E/KP (linked reader component if exists)
   - EBG (linked exit button if exists)
   - Outputs (any additional outputs or attributes)
   - Dynamic lock type columns (Lock Type 11, Lock Type 12, etc based on found types)

2. Data processing:
   - Group components by door ID (pattern A-XXX-BB-B2)
   - For each door, find associated reader and exit button components
   - Extract lock types from attributes and create dynamic columns
   - Handle missing components gracefully

3. Add summary row at the bottom with:
   - Total Doors count
   - Total Readers count
   - Total Exit Buttons count

4. Apply formatting:
   - Bold headers
   - Borders on all data cells
   - Autofit all columns
   - Light gray fill for header row

5. Use Python with openpyxl to generate the Excel file
6. Return the Excel file as base64 encoded string
7. Print the base64 string with prefix "EXCEL_BASE64:"

Write and execute the Python code to generate this Excel file."""

    def _extract_excel_from_response(self, response: types.GenerateContentResponse) -> str | None:
        """Extract base64 Excel data from Gemini response.

        Args:
            response: Gemini API response

        Returns:
            Base64 encoded Excel data or None if not found
        """
        try:
            for part in response.candidates[0].content.parts:
                if hasattr(part, 'code_execution_result') and part.code_execution_result:
                    output = part.code_execution_result.output

                    if "EXCEL_BASE64:" in output:
                        base64_data = output.split("EXCEL_BASE64:")[1].strip()
                        return base64_data

            logger.warning("No Excel base64 data found in Gemini response")
            return None

        except Exception as e:
            logger.error(f"Failed to extract Excel from response: {e}")
            return None

    async def _save_excel(self, base64_data: str) -> str:
        """Save Excel file from base64 data.

        Args:
            base64_data: Base64 encoded Excel file

        Returns:
            File path where Excel was saved
        """
        from datetime import datetime

        excel_bytes = base64.b64decode(base64_data)

        timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        file_key = f"{self.job.client_name}/{self.job.project_name}/job_{self.job.job_id}/schedule_{timestamp}.xlsx"

        await self.storage.save_file(file_key, excel_bytes)

        return file_key

    def _calculate_summary(self, components: list[dict[str, Any]]) -> dict[str, Any]:
        """Calculate summary statistics from components.

        Args:
            components: List of component dictionaries

        Returns:
            Summary statistics dictionary
        """
        door_count = sum(1 for c in components if c.get("type") == "door")
        reader_count = sum(1 for c in components if c.get("type") == "reader")
        exit_button_count = sum(1 for c in components if c.get("type") == "exit_button")

        return {
            "doors_found": door_count,
            "readers_found": reader_count,
            "exit_buttons_found": exit_button_count,
            "total_components": len(components)
        }

    def _track_cost(self, prompt: str, response: types.GenerateContentResponse) -> None:
        """Track API usage costs.

        Args:
            prompt: Input prompt sent to API
            response: API response
        """
        input_tokens = self.estimate_tokens(prompt)
        
        # Handle code execution responses differently
        output_text = ""
        try:
            # For code execution, estimate tokens from the executed code and output
            if response.candidates and response.candidates[0].content.parts:
                for part in response.candidates[0].content.parts:
                    if hasattr(part, 'executable_code') and part.executable_code:
                        output_text += str(part.executable_code.code)
                    elif hasattr(part, 'code_execution_result') and part.code_execution_result:
                        output_text += str(part.code_execution_result.output)
                    elif hasattr(part, 'text'):
                        output_text += str(part.text)
            
            # Only try to access response.text if there are no code execution parts
            if not output_text and hasattr(response, 'text'):
                try:
                    output_text = str(response.text)
                except Exception:
                    pass  # response.text not available for code execution responses
        except Exception as e:
            logger.debug(f"Could not extract text for cost tracking: {e}")
            output_text = ""
        
        output_tokens = self.estimate_tokens(output_text)

        input_cost = (input_tokens / 1_000_000) * self.cost_per_million_input
        output_cost = (output_tokens / 1_000_000) * self.cost_per_million_output
        total_cost = input_cost + output_cost

        self.log_structured("info", "Excel generation cost tracked",
                           input_tokens=input_tokens,
                           output_tokens=output_tokens,
                           total_cost_usd=round(total_cost, 4))

    def _generate_partial_schedule(self, components: list[dict[str, Any]]) -> str | None:
        """Generate a partial schedule when full generation fails.

        Args:
            components: List of component dictionaries

        Returns:
            Base64 encoded partial Excel file or None
        """
        try:
            # Ensure components is a list
            if not isinstance(components, list):
                logger.error(f"Expected list of components, got {type(components).__name__}")
                return None
                
            mappable_components = []
            unmappable_components = []

            for component in components:
                if component.get("id") and component.get("type"):
                    mappable_components.append(component)
                else:
                    unmappable_components.append(component)
                    logger.warning(f"Unmappable component: {component}")

            if not mappable_components:
                logger.error("No mappable components found for partial schedule")
                return None

            logger.info(f"Generating partial schedule with {len(mappable_components)} of {len(components)} components")

            simplified_prompt = self._build_simple_excel_prompt(mappable_components)

            response = self.client.models.generate_content(
                model=self.model_name,
                contents=[simplified_prompt],
                config=types.GenerateContentConfig(
                    temperature=0.1,
                    max_output_tokens=32768,
                    tools=[types.Tool(code_execution=types.ToolCodeExecution())]
                )
            )

            return self._extract_excel_from_response(response)

        except Exception as e:
            logger.error(f"Partial schedule generation failed: {e}")
            return None

    def _build_simple_excel_prompt(self, components: list[dict[str, Any]]) -> str:
        """Build simplified prompt for partial Excel generation.

        Args:
            components: List of mappable component dictionaries

        Returns:
            Simplified prompt for Gemini
        """
        components_json = json.dumps(components, indent=2)

        return f"""Generate a simplified Excel schedule with the following components.

Component data:
```json
{components_json}
```

Create a basic Excel file with columns: Door ID, Location, Type
Use Python with openpyxl. Return as base64 with prefix "EXCEL_BASE64:"
"""
