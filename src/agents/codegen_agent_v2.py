"""Code Generation Agent V2 for creating Excel schedules using Google GenAI SDK."""
import json
import os
from datetime import datetime
from typing import Any

from src.agents.base_agent_v2 import BaseAgentV2


class CodeGenAgentV2(BaseAgentV2):
    """Agent for generating Excel schedules from extracted components."""

    def __init__(self, storage, job):
        """Initialize Code Generation Agent."""
        super().__init__(storage, job)
        self.model_name = "models/gemini-2.5-pro"  # Model with code execution
        self.enable_code_execution = True

    def _build_excel_generation_prompt(self, components: list[dict], context: dict) -> str:
        """Build prompt for Excel generation with code execution."""
        # Extract unique component types for dynamic columns
        component_types = list({comp.get("type", "Unknown") for comp in components})

        return f"""Generate an Excel file for the security access control schedule using openpyxl.

Components data:
{json.dumps(components, indent=2)}

Requirements:
1. Create headers: Location, Door ID, {', '.join(component_types)}
2. Group components by location/door
3. Format: Bold headers, borders, auto-width columns
4. Add project info header if available from context
5. Color code by component type if helpful
6. Save as 'schedule.xlsx'

Write Python code using openpyxl to create this Excel file. The code should:
- Import openpyxl
- Create workbook and worksheet
- Add all components organized by location
- Apply professional formatting
- Save the file
- Print "Excel file generated successfully" when done

Execute the code to create the actual file."""

    def _prepare_components_data(self, input_data: dict[str, Any]) -> list[dict]:
        """Extract and prepare components data from input."""
        components = []

        # Handle different input formats
        if "components" in input_data:
            components = input_data["components"]
        elif "schedule_data" in input_data and "components" in input_data["schedule_data"]:
            components = input_data["schedule_data"]["components"]
        elif "pages" in input_data:
            # Extract from pages structure
            for page in input_data["pages"]:
                if "components" in page:
                    components.extend(page["components"])

        return components

    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Generate Excel schedule from components.

        Args:
            input_data: Dictionary with extracted components

        Returns:
            Dictionary with generated Excel file information
        """
        self.log_structured("info", "Starting Excel schedule generation")

        try:
            # Extract components
            components = self._prepare_components_data(input_data)

            if not components:
                self.log_structured("warning", "No components found to generate schedule")
                return {"excel_file": None, "error": "No components found", "next_stage": "judge"}

            # Get context if available
            context = input_data.get("context", {})

            # Build prompt
            prompt = self._build_excel_generation_prompt(components, context)

            # Generate and execute code
            self.log_structured("info", f"Generating Excel with {len(components)} components")
            response = await self._generate_with_retry(prompt)

            # Check if file was created
            output_file = "schedule.xlsx"
            if os.path.exists(output_file):
                # Move to output directory
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                final_path = f"output/{self.job.job_id}_schedule_{timestamp}.xlsx"

                os.makedirs("output", exist_ok=True)
                os.rename(output_file, final_path)

                # Save to storage
                await self.storage.save_file(final_path, f"{self.job.job_id}/schedule.xlsx")

                self.log_structured("info", f"Excel schedule generated: {final_path}")

                # Save checkpoint
                await self.save_checkpoint("codegen", {"excel_file": final_path, "components_count": len(components)})

                return {"excel_file": final_path, "components_count": len(components), "next_stage": "judge"}
            else:
                # Try to extract code from response and save for debugging
                self.log_structured("error", "Excel file not generated from code execution")
                return {
                    "excel_file": None,
                    "error": "Code execution did not produce Excel file",
                    "response": response[:500],  # First 500 chars for debugging
                    "next_stage": "judge",
                }

        except Exception as e:
            self.log_structured("error", f"Excel generation failed: {e!s}")
            return {"excel_file": None, "error": str(e), "next_stage": "judge"}
