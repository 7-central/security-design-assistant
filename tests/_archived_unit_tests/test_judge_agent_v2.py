"""Unit tests for Judge Agent V2."""
import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest

from src.agents.judge_agent_v2 import JudgeAgentV2
from src.models.job import Job, JobStatus


@pytest.fixture
def mock_storage():
    """Create a mock storage instance."""
    storage = AsyncMock()
    storage.save_checkpoint = AsyncMock()
    storage.load_checkpoint = AsyncMock(return_value=None)
    storage.file_exists = AsyncMock(return_value=True)
    storage.get_file = AsyncMock()
    storage.save_file = AsyncMock()
    return storage


@pytest.fixture
def mock_job():
    """Create a mock job instance."""
    job = Mock(spec=Job)
    job.job_id = "test-job-123"
    job.client_name = "TestClient"
    job.project_name = "TestProject"
    job.status = JobStatus.PROCESSING
    job.metadata = {}
    job.processing_results = {}
    job.update_metadata = Mock()
    job.update_processing_results = Mock()
    return job


@pytest.fixture
def sample_components():
    """Create sample components for testing."""
    return [
        {
            "id": "A-101-DR-B2",
            "type": "door",
            "location": "Main entrance",
            "page_number": 1,
            "confidence": 0.95,
            "reasoning": "Identified as door based on symbol and label",
            "attributes": {
                "door_type": "Single",
                "hardware": "Card reader + Exit button"
            }
        },
        {
            "id": "A-101-RDR-01",
            "type": "reader",
            "location": "Main entrance - exterior",
            "page_number": 1,
            "confidence": 0.90,
            "reasoning": "Standard card reader symbol near door",
            "attributes": {
                "reader_type": "Proximity",
                "model": "P-Series"
            }
        },
        {
            "id": "A-101-EX-01",
            "type": "exit_button",
            "location": "Main entrance - interior",
            "page_number": 1,
            "confidence": 0.88,
            "reasoning": "Exit button symbol on interior side",
            "attributes": {
                "button_type": "Push to exit"
            }
        }
    ]


@pytest.fixture
def good_evaluation_response():
    """Create a good evaluation response."""
    return json.dumps({
        "overall_assessment": "Good performance - extracted 95% of visible components with high accuracy",
        "completeness": "Found all main doors, readers, and exit buttons. Only missed 1 emergency exit sensor in the stairwell",
        "correctness": "Component IDs follow expected pattern (A-XXX-BB-B2), types correctly identified, no confusion between readers and exit buttons",
        "context_usage": "Successfully applied lock type specifications from context, used vendor model information appropriately",
        "spatial_understanding": "Excellent door-reader associations, components properly grouped by door, floor assignments accurate",
        "false_positives": "None detected",
        "improvement_suggestions": [
            "Focus on identifying emergency exit sensors in stairwells",
            "Consider extracting power supply components visible on drawing"
        ]
    })


@pytest.fixture
def fair_evaluation_response():
    """Create a fair evaluation response."""
    return json.dumps({
        "overall_assessment": "Fair performance - extracted 70% of components with some classification errors",
        "completeness": "Found most doors in main areas but missed several emergency exits and secondary entrances",
        "correctness": "Some confusion between proximity readers and biometric readers, door IDs mostly correct",
        "context_usage": "Partially applied context information, ignored some lock type specifications",
        "spatial_understanding": "Generally correct associations but some readers linked to wrong doors",
        "false_positives": "2 text labels incorrectly identified as components",
        "improvement_suggestions": [
            "Improve distinction between reader types",
            "Focus on emergency exit door patterns",
            "Better handle overlapping annotations"
        ]
    })


@pytest.fixture
def poor_evaluation_response():
    """Create a poor evaluation response."""
    return json.dumps({
        "overall_assessment": "Poor performance - extracted less than 50% of components with significant errors",
        "completeness": "Missed majority of doors, only found components in first floor area",
        "correctness": "Many misclassifications, door IDs don't follow expected patterns",
        "context_usage": "Context information was largely ignored or misapplied",
        "spatial_understanding": "Confused spatial relationships, components not properly associated",
        "false_positives": "Multiple false positives including title blocks and legends",
        "improvement_suggestions": [
            "Need better understanding of security drawing symbols",
            "Implement multi-page processing",
            "Improve component type classification logic"
        ]
    })


class TestJudgeAgentV2:
    """Test suite for Judge Agent V2."""

    @pytest.mark.asyncio
    async def test_initialization(self, mock_storage, mock_job):
        """Test agent initialization."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        assert agent.storage == mock_storage
        assert agent.job == mock_job
        assert agent.model_name == "models/gemini-2.0-flash-exp"
        assert agent.prompt_file == Path("src/config/prompts/judge_prompt.txt")

    @pytest.mark.asyncio
    async def test_evaluate_good_extraction(self, mock_storage, mock_job, sample_components, good_evaluation_response):
        """Test evaluation of a good extraction."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        with patch.object(agent, '_generate_with_retry', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = good_evaluation_response

            # Mock file upload
            with patch.object(agent.client.files, 'upload') as mock_upload:
                mock_upload.return_value = MagicMock()

                result = await agent.evaluate_extraction(
                    drawing_path=Path("/tmp/test_drawing.pdf"),
                    context={"lock_types": "Magnetic locks on all doors"},
                    components=sample_components,
                    excel_path=Path("/tmp/test_excel.xlsx")
                )

        assert result["overall_assessment"] == "Good performance - extracted 95% of visible components with high accuracy"
        assert "None detected" in result["false_positives"]
        assert len(result["improvement_suggestions"]) == 2

    @pytest.mark.asyncio
    async def test_evaluate_fair_extraction(self, mock_storage, mock_job, sample_components, fair_evaluation_response):
        """Test evaluation of a fair extraction."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        with patch.object(agent, '_generate_with_retry', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = fair_evaluation_response

            result = await agent.evaluate_extraction(
                drawing_path=None,  # No drawing provided
                context={"lock_types": "Magnetic locks"},
                components=sample_components,
                excel_path=Path("/tmp/test_excel.xlsx")
            )

        assert "Fair performance" in result["overall_assessment"]
        assert "2 text labels" in result["false_positives"]
        assert len(result["improvement_suggestions"]) == 3

    @pytest.mark.asyncio
    async def test_evaluate_poor_extraction(self, mock_storage, mock_job, poor_evaluation_response):
        """Test evaluation of a poor extraction."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        with patch.object(agent, '_generate_with_retry', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = poor_evaluation_response

            # Test with empty components
            result = await agent.evaluate_extraction(
                drawing_path=None,
                context=None,
                components=[],
                excel_path=None
            )

        assert "Poor performance" in result["overall_assessment"]
        assert "Multiple false positives" in result["false_positives"]
        assert len(result["improvement_suggestions"]) == 3

    @pytest.mark.asyncio
    async def test_missing_inputs_handling(self, mock_storage, mock_job):
        """Test handling of missing inputs."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        with patch.object(agent, '_generate_with_retry', new_callable=AsyncMock) as mock_generate:
            # Return evaluation with missing fields
            mock_generate.return_value = json.dumps({
                "overall_assessment": "Fair performance",
                "completeness": "Partial coverage"
                # Missing other required fields
            })

            result = await agent.evaluate_extraction(
                drawing_path=None,
                context=None,
                components=[],
                excel_path=None
            )

        # Check that missing fields are filled with defaults
        assert "overall_assessment" in result
        assert "completeness" in result
        assert result["correctness"] == "Not evaluated"  # Default value
        assert result["context_usage"] == "Not evaluated"
        assert result["spatial_understanding"] == "Not evaluated"
        assert result["false_positives"] == "Not evaluated"
        assert result["improvement_suggestions"] == ["Unable to generate specific suggestions"]

    @pytest.mark.asyncio
    async def test_json_parsing_error(self, mock_storage, mock_job):
        """Test handling of JSON parsing errors."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        with patch.object(agent, '_generate_with_retry', new_callable=AsyncMock) as mock_generate:
            # Return invalid JSON
            mock_generate.return_value = "This is not valid JSON {incomplete:"

            result = await agent.evaluate_extraction(
                drawing_path=None,
                context=None,
                components=[],
                excel_path=None
            )

        assert "Poor performance - evaluation failed" in result["overall_assessment"]
        assert "error" in result
        assert result["improvement_suggestions"] == ["Fix evaluation errors and retry"]

    @pytest.mark.asyncio
    async def test_process_method(self, mock_storage, mock_job, sample_components, good_evaluation_response):
        """Test the main process method."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        with patch.object(agent, '_generate_with_retry', new_callable=AsyncMock) as mock_generate:
            mock_generate.return_value = good_evaluation_response

            # Mock save_checkpoint to actually be called
            with patch.object(agent, 'save_checkpoint', new_callable=AsyncMock) as mock_save_checkpoint:
                mock_save_checkpoint.return_value = None

                input_data = {
                    "drawing_file": "/tmp/test_drawing.pdf",
                    "context": {"lock_types": "Magnetic locks"},
                    "components": sample_components,
                    "excel_file": "/tmp/test_excel.xlsx"
                }

                result = await agent.process(input_data)

                assert "evaluation" in result
                assert result["next_stage"] == "complete"
                assert "metadata" in result
                assert result["metadata"]["overall_assessment"] == "Good performance - extracted 95% of visible components with high accuracy"
                assert result["metadata"]["suggestions_count"] == 2

                # Verify checkpoint was saved
                mock_save_checkpoint.assert_called_once()
                checkpoint_data = mock_save_checkpoint.call_args[0][1]
                assert "evaluation" in checkpoint_data
                assert "timestamp" in checkpoint_data

    @pytest.mark.asyncio
    async def test_process_with_exception(self, mock_storage, mock_job):
        """Test process method with exception handling."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        with patch.object(agent, 'evaluate_extraction', new_callable=AsyncMock) as mock_evaluate:
            mock_evaluate.side_effect = Exception("Test error")

            input_data = {"components": []}
            result = await agent.process(input_data)

        assert "evaluation" in result
        assert "Poor performance - process error" in result["evaluation"]["overall_assessment"]
        assert result["next_stage"] == "complete"

    @pytest.mark.asyncio
    async def test_extract_components_various_formats(self, mock_storage, mock_job):
        """Test _extract_components with various input formats."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        # Test direct components
        input_data = {"components": [{"id": "1"}]}
        components = agent._extract_components(input_data)
        assert components == [{"id": "1"}]

        # Test components in schedule_data
        input_data = {"schedule_data": {"components": [{"id": "2"}]}}
        components = agent._extract_components(input_data)
        assert components == [{"id": "2"}]

        # Test components in pages
        input_data = {"pages": [
            {"components": [{"id": "3"}]},
            {"components": [{"id": "4"}]}
        ]}
        components = agent._extract_components(input_data)
        assert len(components) == 2
        assert components[0]["id"] == "3"
        assert components[1]["id"] == "4"

        # Test empty/missing components
        input_data = {}
        components = agent._extract_components(input_data)
        assert components == []

    @pytest.mark.asyncio
    async def test_validate_evaluation(self, mock_storage, mock_job):
        """Test _validate_evaluation method."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        # Test with complete evaluation
        evaluation = {
            "overall_assessment": "Good",
            "completeness": "Complete",
            "correctness": "Correct",
            "context_usage": "Used well",
            "spatial_understanding": "Excellent",
            "false_positives": "None",
            "improvement_suggestions": ["Suggestion 1"]
        }

        validated = agent._validate_evaluation(evaluation)
        assert validated == evaluation

        # Test with missing fields
        evaluation = {"overall_assessment": "Good"}
        validated = agent._validate_evaluation(evaluation)

        assert validated["overall_assessment"] == "Good"
        assert validated["completeness"] == "Not evaluated"
        assert validated["correctness"] == "Not evaluated"
        assert validated["context_usage"] == "Not evaluated"
        assert validated["spatial_understanding"] == "Not evaluated"
        assert validated["false_positives"] == "Not evaluated"
        assert validated["improvement_suggestions"] == ["Unable to generate specific suggestions"]

        # Test with non-list improvement_suggestions
        evaluation = {
            "overall_assessment": "Good",
            "improvement_suggestions": "Single suggestion as string"
        }
        validated = agent._validate_evaluation(evaluation)
        assert validated["improvement_suggestions"] == ["Single suggestion as string"]

    @pytest.mark.asyncio
    async def test_prompt_template_loading(self, mock_storage, mock_job):
        """Test loading of prompt template."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        # Test with existing file
        with patch.object(Path, 'exists', return_value=True):
            with patch.object(Path, 'read_text', return_value="Test prompt {drawing_info}"):
                prompt = agent._load_prompt_template()
                assert "Test prompt" in prompt

        # Test with missing file (fallback)
        with patch.object(Path, 'exists', return_value=False):
            prompt = agent._load_prompt_template()
            assert "security drawing processing pipeline" in prompt
            assert "{drawing_info}" in prompt

    @pytest.mark.asyncio
    async def test_generate_with_files(self, mock_storage, mock_job):
        """Test _generate_with_files method."""
        agent = JudgeAgentV2(storage=mock_storage, job=mock_job)

        mock_file = MagicMock()
        files = [mock_file]

        with patch.object(agent.client.models, 'generate_content', new_callable=AsyncMock) as mock_generate:
            mock_response = MagicMock()
            mock_response.text = "Test response"
            mock_generate.return_value = mock_response

            result = await agent._generate_with_files("Test prompt", files)

            assert result == "Test response"
            mock_generate.assert_called_once()

            # Check that files were included in the call
            call_args = mock_generate.call_args
            assert call_args[1]["contents"][0] == mock_file
            assert call_args[1]["contents"][1] == "Test prompt"
