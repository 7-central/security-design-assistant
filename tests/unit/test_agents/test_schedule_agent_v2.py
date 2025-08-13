"""Unit tests for Schedule Agent V2."""
import json
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.agents.schedule_agent_v2 import ScheduleAgentV2
from src.models.component import Component, ComponentExtractionResult, PageComponents
from src.models.job import Job, JobStatus
from src.storage.local_storage import LocalStorage


@pytest.fixture
def mock_storage():
    """Create a mock storage interface."""
    storage = AsyncMock(spec=LocalStorage)
    storage.save_file = AsyncMock(return_value="path/to/file")
    storage.get_file = AsyncMock()
    storage.file_exists = AsyncMock(return_value=False)
    storage.save_job_status = AsyncMock()
    return storage


@pytest.fixture
def sample_job():
    """Create a sample job for testing."""
    return Job(
        job_id="test_job_123",
        client_name="test_client",
        project_name="test_project",
        status=JobStatus.PROCESSING,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        file_path="test_drawing.pdf"
    )


@pytest.fixture
def schedule_agent_v2(mock_storage, sample_job):
    """Create a Schedule Agent V2 instance."""
    with patch('src.agents.base_agent_v2.settings') as mock_base_settings:
        mock_base_settings.GEMINI_API_KEY = "test-api-key"
        with patch('src.agents.schedule_agent_v2.settings') as mock_settings:
            mock_settings.GEMINI_API_KEY = "test-api-key"
            mock_settings.GEMINI_MODEL = "gemini-2.5-pro"
            agent = ScheduleAgentV2(mock_storage, sample_job)
            # Mock the _client attribute directly instead of the property
            agent._client = Mock()
            return agent


@pytest.mark.unit
class TestScheduleAgentV2:
    """Test cases for Schedule Agent V2."""

    def test_initialization(self, mock_storage, sample_job):
        """Test agent initialization."""
        with patch('src.agents.base_agent_v2.settings') as mock_settings:
            mock_settings.GEMINI_API_KEY = "test-api-key"
            with patch('src.agents.schedule_agent_v2.settings') as mock_settings2:
                mock_settings2.GEMINI_API_KEY = "test-api-key"
                agent = ScheduleAgentV2(mock_storage, sample_job)
                assert agent.storage == mock_storage
                assert agent.job == sample_job
                assert agent.agent_name == "ScheduleAgentV2"

    def test_initialization_no_api_key(self, mock_storage, sample_job):
        """Test initialization fails without API key."""
        with patch('src.agents.base_agent_v2.settings') as mock_settings:
            mock_settings.GEMINI_API_KEY = None
            agent = ScheduleAgentV2(mock_storage, sample_job)
            # With lazy loading, the error occurs when accessing the client
            with pytest.raises(ValueError, match="GEMINI_API_KEY environment variable is required"):
                _ = agent.client

    @pytest.mark.asyncio
    async def test_process_no_pages(self, schedule_agent_v2):
        """Test process fails with no pages."""
        with pytest.raises(ValueError, match="Input data must contain 'pages' key"):
            await schedule_agent_v2.process({})

    @pytest.mark.asyncio
    async def test_process_empty_pages(self, schedule_agent_v2):
        """Test process fails with empty pages."""
        with pytest.raises(ValueError, match="No pages to process"):
            await schedule_agent_v2.process({"pages": []})

    def test_estimate_tokens(self, schedule_agent_v2):
        """Test token estimation."""
        assert schedule_agent_v2.estimate_tokens("Hello world") == 2  # 11 chars / 4
        assert schedule_agent_v2.estimate_tokens("A" * 100) == 25  # 100 / 4

    def test_estimate_pdf_tokens(self, schedule_agent_v2):
        """Test PDF token estimation."""
        assert schedule_agent_v2.estimate_pdf_tokens(1) == 258
        assert schedule_agent_v2.estimate_pdf_tokens(10) == 2580

    def test_component_model(self):
        """Test Component model."""
        component = Component(
            id="A-101-DR-B2",
            type="door",
            location="Main entrance",
            page_number=1,
            confidence=0.95,
            attributes={"lock_type": "11"}
        )
        assert component.id == "A-101-DR-B2"
        assert component.type == "door"
        assert component.confidence == 0.95
        assert component.attributes["lock_type"] == "11"

    def test_component_model_with_reasoning(self):
        """Test Component model with reasoning field."""
        component = Component(
            id="A-101-DR-B2",
            type="door",
            location="Main entrance",
            page_number=1,
            confidence=0.95,
            reasoning="Identified based on door symbol and Type 11 lock specification from context",
            attributes={"lock_type": "11"}
        )
        assert component.reasoning == "Identified based on door symbol and Type 11 lock specification from context"
        assert component.confidence == 0.95

    def test_component_extraction_result(self):
        """Test ComponentExtractionResult model."""

        pages = [
            PageComponents(
                page_num=1,
                components=[
                    Component(
                        id="A-101-DR-B2",
                        type="door",
                        location="Main entrance",
                        page_number=1,
                        confidence=0.95
                    )
                ]
            )
        ]

        result = ComponentExtractionResult(pages=pages)
        assert result.total_components == 1
        assert len(result.pages) == 1

    def test_filter_relevant_context(self, schedule_agent_v2):
        """Test context filtering for relevance."""
        context_data = {
            "sections": [
                {
                    "title": "Door Hardware",
                    "content": "Type 11 locks for main doors",
                    "type": "specification"
                },
                {
                    "title": "Building History",
                    "content": "Built in 1990, renovated in 2010",
                    "type": "general"
                },
                {
                    "title": "Card Readers",
                    "content": "P-type and E-type readers for access control",
                    "type": "specification"
                }
            ]
        }

        filtered = schedule_agent_v2.filter_relevant_context(context_data)

        # Relevant sections should be included
        assert "Type 11" in filtered
        assert "P-type" in filtered
        assert "Project specifications:" in filtered

        # Non-relevant section should be excluded
        assert "1990" not in filtered
        assert "renovated" not in filtered

    def test_filter_relevant_context_empty(self, schedule_agent_v2):
        """Test context filtering with empty input."""
        # Test with None
        assert schedule_agent_v2.filter_relevant_context(None) == ""

        # Test with empty dict
        assert schedule_agent_v2.filter_relevant_context({}) == ""

        # Test with missing sections
        assert schedule_agent_v2.filter_relevant_context({"other": "data"}) == ""

    def test_filter_relevant_context_token_limit(self, schedule_agent_v2):
        """Test context filtering respects token limits."""
        large_context = {
            "sections": [
                {
                    "title": f"Section {i}",
                    "content": "door lock hardware " * 200,  # Large content
                    "type": "specification"
                }
                for i in range(10)
            ]
        }

        # Filter with small limit
        filtered = schedule_agent_v2.filter_relevant_context(large_context, max_tokens=100)

        # Should be limited in size
        assert len(filtered) < 1000  # Much smaller than full content

    def test_filter_relevant_context_prioritization(self, schedule_agent_v2):
        """Test that specifications are prioritized over general sections."""
        context = {
            "sections": [
                {
                    "title": "General Info",
                    "content": "door information",
                    "type": "general"
                },
                {
                    "title": "Door Specs",
                    "content": "door lock type",
                    "type": "specification"
                }
            ]
        }

        filtered = schedule_agent_v2.filter_relevant_context(context, max_tokens=50)

        # Specification should be prioritized
        assert "Door Specs" in filtered or "lock type" in filtered

    def test_prompt_with_context(self, schedule_agent_v2):
        """Test prompt building with context."""
        context_section = "Project specifications:\nType 11 locks"
        page_data = {"content": "Page text"}

        contents = schedule_agent_v2._build_page_content(page_data, 1, 10, context_section)

        # First item should be the formatted prompt
        assert len(contents) > 0
        prompt = contents[0]
        assert "Project specifications" in prompt

    def test_prompt_without_context(self, schedule_agent_v2):
        """Test prompt building without context."""
        page_data = {"content": "Page text"}

        contents = schedule_agent_v2._build_page_content(page_data, 1, 10, "")

        # Should still build valid prompt
        assert len(contents) > 0
        # No context should be present
        assert "Project specifications" not in contents[0]

    @pytest.mark.asyncio
    async def test_process_with_context_loading(self, schedule_agent_v2, sample_job):
        """Test that process attempts to load context checkpoint."""
        # Mock context checkpoint
        sample_context = {
            "sections": [
                {"title": "Test", "content": "door lock", "type": "specification"}
            ]
        }
        # Use AsyncMock to return the value properly
        schedule_agent_v2.storage.get_file = AsyncMock(return_value=json.dumps(sample_context))

        # Mock extract_components to prevent full execution
        with patch.object(schedule_agent_v2, '_extract_components', new=AsyncMock()) as mock_extract:
            mock_extract.return_value = ComponentExtractionResult(pages=[])

            # Execute
            await schedule_agent_v2.process({"pages": [{"pdf_path": "/tmp/test.pdf"}]})

            # Verify context loading was attempted with the correct path
            expected_path = f"7central/{sample_job.client_name}/{sample_job.job_id}/checkpoint_context_v1.json"
            schedule_agent_v2.storage.get_file.assert_called_once_with(expected_path)

    @pytest.mark.asyncio
    async def test_process_without_context_continues(self, schedule_agent_v2):
        """Test that process continues when context is unavailable."""
        # Mock context loading failure
        schedule_agent_v2.storage.get_file.side_effect = Exception("Not found")

        # Mock extract_components
        with patch.object(schedule_agent_v2, '_extract_components') as mock_extract:
            mock_extract.return_value = ComponentExtractionResult(pages=[])

            # Should not fail
            result = await schedule_agent_v2.process({"pages": [{"pdf_path": "/tmp/test.pdf"}]})

            assert result is not None
            assert "components" in result
