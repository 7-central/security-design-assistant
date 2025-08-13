"""Unit tests for Excel Generation Agent."""
import base64
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.excel_generation_agent import ExcelGenerationAgent
from src.models.job import Job, JobStatus


@pytest.fixture
def mock_storage():
    """Create mock storage interface."""
    storage = AsyncMock()
    storage.save_file = AsyncMock(return_value="test_client/test_project/job_123/schedule_20250207_120000.xlsx")
    storage.file_exists = AsyncMock(return_value=True)
    storage.get_file = AsyncMock(return_value=b"test_file_content")
    storage.save_job_status = AsyncMock()
    return storage


@pytest.fixture
def mock_job():
    """Create mock job instance."""
    from datetime import datetime
    job = Job(
        job_id="test_job_123",
        client_name="test_client",
        project_name="test_project",
        status=JobStatus.PROCESSING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    return job


@pytest.fixture
def sample_components():
    """Create sample component data."""
    return [
        {
            "id": "A-101-DR-B2",
            "type": "door",
            "location": "Main Entrance",
            "page_number": 1,
            "confidence": 0.95,
            "attributes": {
                "lock_type": "11",
                "card_reader": "A-101-RDR-P"
            }
        },
        {
            "id": "A-101-RDR-P",
            "type": "reader",
            "location": "Main Entrance",
            "page_number": 1,
            "confidence": 0.92,
            "attributes": {}
        },
        {
            "id": "A-102-DR-B2",
            "type": "door",
            "location": "Conference Room",
            "page_number": 2,
            "confidence": 0.88,
            "attributes": {
                "lock_type": "12"
            }
        },
        {
            "id": "A-102-EBG",
            "type": "exit_button",
            "location": "Conference Room",
            "page_number": 2,
            "confidence": 0.90,
            "attributes": {}
        }
    ]


@pytest.fixture
def mock_excel_base64():
    """Create mock base64 Excel data."""
    return base64.b64encode(b"mock_excel_file_content").decode('utf-8')


class TestExcelGenerationAgent:
    """Test suite for Excel Generation Agent."""

    @pytest.mark.asyncio
    async def test_agent_initialization(self, mock_storage, mock_job):
        """Test agent initializes correctly."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            agent = ExcelGenerationAgent(mock_storage, mock_job)

            assert agent.storage == mock_storage
            assert agent.job == mock_job
            assert agent.model_name == "gemini-2.5-flash"
            assert agent.cost_per_million_input == 0.075
            assert agent.cost_per_million_output == 0.30

    @pytest.mark.asyncio
    async def test_process_with_valid_components(self, mock_storage, mock_job, sample_components, mock_excel_base64):
        """Test successful Excel generation with valid components."""
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            # Mock Gemini response with code execution result
            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = f"EXCEL_BASE64:{mock_excel_base64}"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            mock_client.return_value.models.generate_content.return_value = mock_response

            agent = ExcelGenerationAgent(mock_storage, mock_job)

            result = await agent.process({"components": sample_components})

            assert result["status"] == "completed"
            assert "file_path" in result
            assert "test_client/test_project/job_test_job_123/schedule_" in result["file_path"]
            assert result["file_path"].endswith(".xlsx")
            assert "summary" in result
            assert result["summary"]["doors_found"] == 2
            assert result["summary"]["readers_found"] == 1
            assert result["summary"]["exit_buttons_found"] == 1

            # Two calls expected: Excel file and checkpoint
            assert mock_storage.save_file.call_count == 2

    @pytest.mark.asyncio
    async def test_process_with_empty_components(self, mock_storage, mock_job):
        """Test handling of empty component list."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            agent = ExcelGenerationAgent(mock_storage, mock_job)

            result = await agent.process({"components": []})

            assert result["status"] == "error"
            assert "No components provided" in result["message"]

    @pytest.mark.asyncio
    async def test_generate_excel_with_gemini_failure(self, mock_storage, mock_job, sample_components):
        """Test fallback to partial schedule when Gemini fails."""
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            # First call fails, second call (partial) succeeds
            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = "EXCEL_BASE64:partial_data"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            mock_client.return_value.models.generate_content.side_effect = [
                Exception("Gemini API error"),
                mock_response
            ]

            agent = ExcelGenerationAgent(mock_storage, mock_job)

            excel_base64 = await agent.generate_excel(sample_components)

            assert excel_base64 == "partial_data"
            assert mock_client.return_value.models.generate_content.call_count == 2

    def test_build_excel_prompt(self, mock_storage, mock_job, sample_components):
        """Test Excel prompt generation."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            agent = ExcelGenerationAgent(mock_storage, mock_job)

            prompt = agent._build_excel_prompt(sample_components)

            assert "Generate an Excel file" in prompt
            assert "Door ID" in prompt
            assert "Location" in prompt
            assert "Reader E/KP" in prompt
            assert json.dumps(sample_components, indent=2) in prompt

    def test_extract_excel_from_response(self, mock_storage, mock_job, mock_excel_base64):
        """Test extraction of base64 data from Gemini response."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            agent = ExcelGenerationAgent(mock_storage, mock_job)

            # Create mock response with Excel base64
            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = f"Some logs\nEXCEL_BASE64:{mock_excel_base64}"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            result = agent._extract_excel_from_response(mock_response)

            assert result == mock_excel_base64.strip()

    def test_extract_excel_no_base64_found(self, mock_storage, mock_job):
        """Test handling when no base64 data found in response."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            agent = ExcelGenerationAgent(mock_storage, mock_job)

            # Create mock response without Excel base64
            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = "Just some logs without base64"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            result = agent._extract_excel_from_response(mock_response)

            assert result is None

    def test_calculate_summary(self, mock_storage, mock_job, sample_components):
        """Test summary calculation from components."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            agent = ExcelGenerationAgent(mock_storage, mock_job)

            summary = agent._calculate_summary(sample_components)

            assert summary["doors_found"] == 2
            assert summary["readers_found"] == 1
            assert summary["exit_buttons_found"] == 1
            assert summary["total_components"] == 4

    def test_generate_partial_schedule(self, mock_storage, mock_job):
        """Test partial schedule generation for unmappable components."""
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = "EXCEL_BASE64:partial_excel"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            mock_client.return_value.models.generate_content.return_value = mock_response

            agent = ExcelGenerationAgent(mock_storage, mock_job)

            # Include some invalid components
            mixed_components = [
                {"id": "A-101", "type": "door", "location": "Valid"},
                {"type": "door"},  # Missing ID
                {"id": "A-102"},  # Missing type
            ]

            result = agent._generate_partial_schedule(mixed_components)

            assert result == "partial_excel"

    def test_track_cost(self, mock_storage, mock_job):
        """Test API cost tracking."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            agent = ExcelGenerationAgent(mock_storage, mock_job)

            # Mock response with text
            mock_response = MagicMock()
            mock_response.text = "Sample response text"

            prompt = "Test prompt" * 100  # ~400 chars = ~100 tokens

            with patch.object(agent, 'log_structured') as mock_log:
                agent._track_cost(prompt, mock_response)

                mock_log.assert_called_once()
                call_args = mock_log.call_args
                assert call_args[0][0] == "info"
                assert "Excel generation cost tracked" in call_args[0][1]
                assert "input_tokens" in call_args[1]
                assert "output_tokens" in call_args[1]
                assert "total_cost_usd" in call_args[1]

    @pytest.mark.asyncio
    async def test_save_excel(self, mock_storage, mock_job, mock_excel_base64):
        """Test saving Excel file from base64 data."""
        with patch('src.agents.base_agent_v2.genai.Client'):
            agent = ExcelGenerationAgent(mock_storage, mock_job)

            file_path = await agent._save_excel(mock_excel_base64)

            assert "test_client/test_project/job_test_job_123/schedule_" in file_path
            assert file_path.endswith(".xlsx")

            # Verify the file was saved with decoded content
            mock_storage.save_file.assert_called_once()
            saved_content = mock_storage.save_file.call_args[0][1]
            assert saved_content == base64.b64decode(mock_excel_base64)

    @pytest.mark.asyncio
    async def test_checkpoint_saving(self, mock_storage, mock_job, sample_components, mock_excel_base64):
        """Test that checkpoints are saved after successful generation."""
        with patch('src.agents.base_agent_v2.genai.Client') as mock_client:
            mock_response = MagicMock()
            mock_part = MagicMock()
            mock_part.code_execution_result.output = f"EXCEL_BASE64:{mock_excel_base64}"
            mock_response.candidates = [MagicMock(content=MagicMock(parts=[mock_part]))]

            mock_client.return_value.models.generate_content.return_value = mock_response

            agent = ExcelGenerationAgent(mock_storage, mock_job)

            await agent.process({"components": sample_components})

            # Verify checkpoint was saved
            checkpoint_calls = [call for call in mock_storage.save_file.call_args_list
                              if "checkpoint" in str(call)]
            assert len(checkpoint_calls) > 0
