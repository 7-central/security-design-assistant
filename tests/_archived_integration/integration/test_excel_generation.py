"""Integration tests for Excel Generation pipeline."""
import base64
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import pytest_asyncio

from src.agents.excel_generation_agent import ExcelGenerationAgent
from src.models.job import Job, JobStatus
from src.storage.local_storage import LocalStorage


@pytest_asyncio.fixture
async def local_storage():
    """Create local storage instance with temp directory."""
    storage = LocalStorage()
    # Use temp directory for testing
    with tempfile.TemporaryDirectory() as temp_dir:
        storage.base_path = Path(temp_dir)
        yield storage


@pytest.fixture
def sample_job():
    """Create sample job for testing."""
    return Job(
        job_id="test_job_integration",
        client_name="test_client",
        project_name="test_project",
        status=JobStatus.PROCESSING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )


@pytest.fixture
def mock_schedule_agent_output():
    """Mock output from Schedule Agent."""
    return {
        "components": [
            {
                "id": "A-101-DR-B2",
                "type": "door",
                "location": "Main Entrance",
                "page_number": 1,
                "confidence": 0.95,
                "attributes": {
                    "lock_type": "11",
                    "card_reader": "A-101-RDR-P",
                    "intercom": True
                }
            },
            {
                "id": "A-101-RDR-P",
                "type": "reader",
                "location": "Main Entrance Reader",
                "page_number": 1,
                "confidence": 0.92,
                "attributes": {
                    "reader_type": "proximity"
                }
            },
            {
                "id": "A-102-DR-B2",
                "type": "door",
                "location": "Conference Room",
                "page_number": 2,
                "confidence": 0.88,
                "attributes": {
                    "lock_type": "12",
                    "exit_button": "A-102-EBG"
                }
            },
            {
                "id": "A-102-EBG",
                "type": "exit_button",
                "location": "Conference Room Exit",
                "page_number": 2,
                "confidence": 0.90,
                "attributes": {}
            },
            {
                "id": "A-103-DR-B2",
                "type": "door",
                "location": "Storage Room",
                "page_number": 3,
                "confidence": 0.85,
                "attributes": {
                    "lock_type": "11"
                }
            }
        ],
        "status": "completed"
    }


class TestExcelGenerationIntegration:
    """Integration tests for Excel generation workflow."""

    @pytest.mark.asyncio
    async def test_complete_pipeline_with_excel_generation(
        self,
        local_storage,
        sample_job,
        mock_schedule_agent_output
    ):
        """Test complete pipeline including Excel generation."""
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            # Mock Gemini response with Excel base64
            mock_excel_content = b"mock_excel_file_content"
            mock_excel_base64 = base64.b64encode(mock_excel_content).decode('utf-8')

            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = f"EXCEL_BASE64:{mock_excel_base64}"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            mock_client.return_value.models.generate_content.return_value = mock_response

            # Initialize Excel Generation Agent
            excel_agent = ExcelGenerationAgent(storage=local_storage, job=sample_job)

            # Process components from Schedule Agent
            result = await excel_agent.process(mock_schedule_agent_output)

            # Verify successful completion
            assert result["status"] == "completed"
            assert "file_path" in result
            assert result["file_path"].endswith(".xlsx")

            # Verify summary statistics
            assert result["summary"]["doors_found"] == 3
            assert result["summary"]["readers_found"] == 1
            assert result["summary"]["exit_buttons_found"] == 1
            assert result["summary"]["total_components"] == 5

            # Verify file was saved to storage
            file_path = result["file_path"]
            assert await local_storage.file_exists(file_path)

            # Verify checkpoint was created
            checkpoint_key = f"{sample_job.client_name}/{sample_job.project_name}/job_{sample_job.job_id}/checkpoint_excel_generation_v1.json"
            assert await local_storage.file_exists(checkpoint_key)

    @pytest.mark.asyncio
    async def test_pipeline_with_partial_schedule(
        self,
        local_storage,
        sample_job
    ):
        """Test pipeline handles partial schedule generation."""
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            # First call fails, second call succeeds with partial data
            partial_excel_base64 = base64.b64encode(b"partial_excel").decode('utf-8')

            mock_partial_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = f"EXCEL_BASE64:{partial_excel_base64}"
            mock_partial_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            mock_client.return_value.models.generate_content.side_effect = [
                Exception("Gemini API error"),
                mock_partial_response
            ]

            excel_agent = ExcelGenerationAgent(storage=local_storage, job=sample_job)

            # Process with some invalid components
            mixed_components = {
                "components": [
                    {"id": "A-101", "type": "door", "location": "Valid Door"},
                    {"type": "door", "location": "Missing ID"},  # Invalid
                    {"id": "A-102", "location": "Missing Type"},  # Invalid
                ]
            }

            result = await excel_agent.process(mixed_components)

            # Should still complete with partial data
            assert result["status"] == "completed"
            assert "file_path" in result

            # Verify Gemini was called twice (main + partial)
            assert mock_client.return_value.models.generate_content.call_count == 2

    @pytest.mark.asyncio
    async def test_download_endpoint_integration(
        self,
        local_storage,
        sample_job,
        mock_schedule_agent_output
    ):
        """Test download endpoint retrieves generated Excel file."""
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            mock_excel_content = b"test_excel_content"
            mock_excel_base64 = base64.b64encode(mock_excel_content).decode('utf-8')

            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = f"EXCEL_BASE64:{mock_excel_base64}"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            mock_client.return_value.models.generate_content.return_value = mock_response

            # Generate Excel
            excel_agent = ExcelGenerationAgent(storage=local_storage, job=sample_job)
            result = await excel_agent.process(mock_schedule_agent_output)

            # Save job status with Excel path
            job_data = sample_job.to_dict()
            job_data["metadata"]["excel_file_path"] = result["file_path"]
            job_data["processing_results"] = {
                "excel_generation": {
                    "completed": True,
                    "file_path": result["file_path"],
                    "summary": result["summary"]
                }
            }
            await local_storage.save_job_status(sample_job.job_id, job_data)

            # Verify we can retrieve the Excel file
            retrieved_job = await local_storage.get_job_status(sample_job.job_id)
            excel_path = retrieved_job["metadata"]["excel_file_path"]

            assert excel_path == result["file_path"]
            assert await local_storage.file_exists(excel_path)

            # Verify file content
            file_content = await local_storage.get_file(excel_path)
            assert file_content == mock_excel_content

    @pytest.mark.asyncio
    async def test_excel_generation_with_empty_components(
        self,
        local_storage,
        sample_job
    ):
        """Test Excel generation handles empty component list gracefully."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            excel_agent = ExcelGenerationAgent(storage=local_storage, job=sample_job)

            result = await excel_agent.process({"components": []})

            assert result["status"] == "error"
            assert "No components provided" in result["message"]

    @pytest.mark.asyncio
    async def test_excel_structure_validation(
        self,
        local_storage,
        sample_job,
        mock_schedule_agent_output
    ):
        """Test that generated Excel has correct structure."""
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            # Mock a more detailed Excel generation
            mock_excel_base64 = base64.b64encode(b"excel_with_structure").decode('utf-8')

            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = f"EXCEL_BASE64:{mock_excel_base64}"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            mock_client.return_value.models.generate_content.return_value = mock_response

            excel_agent = ExcelGenerationAgent(storage=local_storage, job=sample_job)

            # Verify the prompt includes correct column structure
            prompt = excel_agent._build_excel_prompt(mock_schedule_agent_output["components"])

            assert "Door ID" in prompt
            assert "Location" in prompt
            assert "Reader E/KP" in prompt
            assert "EBG" in prompt
            assert "Outputs" in prompt
            assert "Lock Type" in prompt
            assert "Total Doors" in prompt
            assert "Total Readers" in prompt
            assert "Total Exit Buttons" in prompt

    @pytest.mark.asyncio
    async def test_checkpoint_recovery(
        self,
        local_storage,
        sample_job
    ):
        """Test recovery from checkpoint if Excel generation is interrupted."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            excel_agent = ExcelGenerationAgent(storage=local_storage, job=sample_job)

            # Save a checkpoint manually
            checkpoint_data = {
                "file_path": "test_client/test_project/job_test/schedule.xlsx",
                "summary": {
                    "doors_found": 5,
                    "readers_found": 3,
                    "exit_buttons_found": 2
                },
                "component_count": 10
            }

            await excel_agent.save_checkpoint("excel_generation", checkpoint_data)

            # Load checkpoint
            loaded_data = await excel_agent.load_checkpoint("excel_generation")

            assert loaded_data == checkpoint_data
            assert loaded_data["file_path"] == checkpoint_data["file_path"]
            assert loaded_data["summary"]["doors_found"] == 5

    @pytest.mark.asyncio
    async def test_cost_tracking_integration(
        self,
        local_storage,
        sample_job,
        mock_schedule_agent_output
    ):
        """Test that API costs are tracked correctly."""
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            mock_excel_base64 = base64.b64encode(b"test").decode('utf-8')

            mock_response = MagicMock()
            mock_response.text = "Generated Excel code here"
            mock_part = MagicMock()
            mock_part.code_execution_result.output = f"EXCEL_BASE64:{mock_excel_base64}"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            mock_client.return_value.models.generate_content.return_value = mock_response

            excel_agent = ExcelGenerationAgent(storage=local_storage, job=sample_job)

            with patch.object(excel_agent, 'log_structured') as mock_log:
                await excel_agent.process(mock_schedule_agent_output)

                # Verify cost tracking was called
                cost_logs = [call for call in mock_log.call_args_list
                           if "cost tracked" in str(call)]
                assert len(cost_logs) > 0

                # Verify cost calculation details
                cost_log = cost_logs[0]
                assert cost_log[1]["input_tokens"] > 0
                assert cost_log[1]["output_tokens"] > 0
                assert "total_cost_usd" in cost_log[1]
