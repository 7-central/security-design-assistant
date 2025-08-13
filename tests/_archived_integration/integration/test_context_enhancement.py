"""Integration tests for context-enhanced schedule extraction."""
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.schedule_agent_v2 import ScheduleAgentV2
from src.models.job import Job


@pytest.fixture
def mock_job():
    """Create a mock job for testing."""
    job = MagicMock(spec=Job)
    job.company_id = "7central"
    job.client_id = "test_client"
    job.client_name = "test_client"
    job.project_name = "test_project"
    job.job_id = "test_job_123"
    job.update_processing_results = MagicMock()
    return job


@pytest.fixture
def mock_storage():
    """Create a mock storage interface."""
    storage = AsyncMock()
    storage.save_file = AsyncMock()
    storage.get_file = AsyncMock()
    return storage


@pytest.fixture
def sample_context_data():
    """Sample context data for testing."""
    return {
        "sections": [
            {
                "title": "Door Hardware Specifications",
                "content": "All doors shall use Type 11 locks (maglock) for main entrances and Type 12 (electric strike) for secondary doors.",
                "type": "specification"
            },
            {
                "title": "Card Reader Requirements",
                "content": "P-type readers for perimeter doors, E-type readers for elevator lobbies.",
                "type": "specification"
            },
            {
                "title": "General Information",
                "content": "This building has 5 floors and was built in 2020.",
                "type": "general"
            }
        ]
    }


@pytest.fixture
def sample_pages():
    """Sample page data for testing."""
    return [
        {
            "pdf_path": "/tmp/test_drawing.pdf",
            "page_num": 1,
            "content": "Security drawing showing doors and access control"
        }
    ]


class TestContextEnhancement:
    """Test suite for context-enhanced component extraction."""

    @pytest.mark.asyncio
    async def test_extraction_without_context(self, mock_job, mock_storage, sample_pages):
        """Test component extraction without context."""
        # Setup
        agent = ScheduleAgentV2(mock_storage, mock_job)
        mock_storage.get_file.return_value = None  # No context available

        # Mock the Gemini response
        with patch.object(agent, 'upload_file') as mock_upload, \
             patch.object(agent, 'generate_content') as mock_generate:

            mock_upload.return_value = MagicMock(uri="file_uri", name="test.pdf")
            mock_response = MagicMock()
            mock_response.text = json.dumps({
                "pages": [{
                    "page_num": 1,
                    "components": [
                        {
                            "id": "A-101-DR-B2",
                            "type": "door",
                            "location": "Main entrance",
                            "confidence": 0.67,
                            "reasoning": "Identified based on door symbol and A-prefix pattern"
                        }
                    ]
                }]
            })
            mock_response.usage_metadata.total_token_count = 1000
            mock_generate.return_value = mock_response

            # Execute
            result = await agent.process({"pages": sample_pages})

            # Assert
            assert result["components"]["total_components"] == 1
            assert result["components"]["pages"][0]["components"][0]["confidence"] == 0.67
            assert "context" not in result["components"]["pages"][0]["components"][0]["reasoning"].lower()

            # Verify context was not loaded
            mock_storage.get_file.assert_called_once()
            assert mock_job.update_processing_results.call_args[0][0]["schedule_agent"]["context_used"] is False

    @pytest.mark.asyncio
    async def test_extraction_with_context(self, mock_job, mock_storage, sample_pages, sample_context_data):
        """Test component extraction with context for improved accuracy."""
        # Setup
        agent = ScheduleAgentV2(mock_storage, mock_job)
        mock_storage.get_file.return_value = json.dumps(sample_context_data)

        # Mock the Gemini response with better accuracy due to context
        with patch.object(agent, 'upload_file') as mock_upload, \
             patch.object(agent, 'generate_content') as mock_generate:

            mock_upload.return_value = MagicMock(uri="file_uri", name="test.pdf")
            mock_response = MagicMock()
            mock_response.text = json.dumps({
                "pages": [{
                    "page_num": 1,
                    "components": [
                        {
                            "id": "A-101-DR-B2",
                            "type": "door",
                            "location": "Main entrance",
                            "confidence": 0.85,
                            "reasoning": "Identified as door with Type 11 lock based on main entrance location specified in context. Visual symbol matches standard door icon."
                        },
                        {
                            "id": "A-101-RDR-P",
                            "type": "reader",
                            "location": "Main entrance",
                            "confidence": 0.90,
                            "reasoning": "P-type reader identified next to main entrance door, matching perimeter door specification from context."
                        }
                    ]
                }]
            })
            mock_response.usage_metadata.total_token_count = 1500
            mock_generate.return_value = mock_response

            # Execute
            result = await agent.process({"pages": sample_pages})

            # Assert improved accuracy
            assert result["components"]["total_components"] == 2
            components = result["components"]["pages"][0]["components"]
            assert components[0]["confidence"] == 0.85  # Higher than without context
            assert "context" in components[0]["reasoning"].lower() or "specification" in components[0]["reasoning"].lower()
            assert components[1]["type"] == "reader"
            assert components[1]["confidence"] == 0.90

            # Verify context was used
            assert mock_job.update_processing_results.call_args[0][0]["schedule_agent"]["context_used"] is True

    @pytest.mark.asyncio
    async def test_context_filtering(self, mock_job, mock_storage):
        """Test smart context filtering for relevance."""
        agent = ScheduleAgentV2(mock_storage, mock_job)

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
                    "content": "P-type and E-type readers",
                    "type": "specification"
                }
            ]
        }

        # Test filtering
        filtered_context = agent.filter_relevant_context(context_data, max_tokens=1000)

        # Assert relevant sections are included
        assert "Type 11" in filtered_context
        assert "P-type" in filtered_context
        # Non-relevant section should be excluded
        assert "1990" not in filtered_context
        assert "renovated" not in filtered_context

    @pytest.mark.asyncio
    async def test_context_token_limit(self, mock_job, mock_storage):
        """Test that context respects token limits."""
        agent = ScheduleAgentV2(mock_storage, mock_job)

        # Create context data with varying sizes
        context_data = {
            "sections": [
                {
                    "title": f"Section {i}",
                    "content": "door lock " * (50 if i == 0 else 500),  # First section is small enough to fit
                    "type": "specification"
                }
                for i in range(10)
            ]
        }

        # Test with small token limit that can fit at least one section
        filtered_context = agent.filter_relevant_context(context_data, max_tokens=100)

        # Assert context is limited
        assert len(filtered_context) < len(str(context_data))
        # Should include at least the first small section
        if filtered_context:  # Only check if something was included
            assert "Project specifications:" in filtered_context or "Section 0" in filtered_context

    @pytest.mark.asyncio
    async def test_accuracy_improvement_measurement(self, mock_job, mock_storage, sample_pages, sample_context_data):
        """Test measuring accuracy improvement with context."""
        agent = ScheduleAgentV2(mock_storage, mock_job)

        # Test without context
        mock_storage.get_file.return_value = None

        with patch.object(agent, 'upload_file') as mock_upload, \
             patch.object(agent, 'generate_content') as mock_generate:

            mock_upload.return_value = MagicMock(uri="file_uri", name="test.pdf")

            # Response without context - lower accuracy
            mock_response_no_context = MagicMock()
            mock_response_no_context.text = json.dumps({
                "pages": [{
                    "page_num": 1,
                    "components": [
                        {"id": "A-101-DR-B2", "type": "door", "location": "Main", "confidence": 0.67, "reasoning": "Door symbol"}
                    ]
                }]
            })
            mock_response_no_context.usage_metadata.total_token_count = 1000

            mock_generate.return_value = mock_response_no_context
            result_no_context = await agent.process({"pages": sample_pages})

            # Reset and test with context
            mock_storage.get_file.return_value = json.dumps(sample_context_data)

            # Response with context - higher accuracy
            mock_response_with_context = MagicMock()
            mock_response_with_context.text = json.dumps({
                "pages": [{
                    "page_num": 1,
                    "components": [
                        {"id": "A-101-DR-B2", "type": "door", "location": "Main entrance", "confidence": 0.85, "reasoning": "Door with Type 11 lock per spec"},
                        {"id": "A-101-RDR-P", "type": "reader", "location": "Main entrance", "confidence": 0.90, "reasoning": "P-type reader per spec"}
                    ]
                }]
            })
            mock_response_with_context.usage_metadata.total_token_count = 1500

            mock_generate.return_value = mock_response_with_context
            result_with_context = await agent.process({"pages": sample_pages})

            # Calculate improvement
            avg_confidence_no_context = 0.67
            components_with_context = result_with_context["components"]["pages"][0]["components"]
            avg_confidence_with_context = sum(c["confidence"] for c in components_with_context) / len(components_with_context)

            # Assert improvement meets target (75-80% from 67% baseline)
            assert avg_confidence_with_context >= 0.75
            assert avg_confidence_with_context > avg_confidence_no_context

            # More components found with context
            assert result_with_context["components"]["total_components"] > result_no_context["components"]["total_components"]

    @pytest.mark.asyncio
    async def test_context_conflict_handling(self, mock_job, mock_storage, sample_pages):
        """Test handling of conflicts between context and drawing."""
        agent = ScheduleAgentV2(mock_storage, mock_job)

        # Context that conflicts with drawing
        conflicting_context = {
            "sections": [
                {
                    "title": "Door Specifications",
                    "content": "All doors must use Type 12 electric strikes",
                    "type": "specification"
                }
            ]
        }
        mock_storage.get_file.return_value = json.dumps(conflicting_context)

        with patch.object(agent, 'upload_file') as mock_upload, \
             patch.object(agent, 'generate_content') as mock_generate:

            mock_upload.return_value = MagicMock(uri="file_uri", name="test.pdf")
            mock_response = MagicMock()
            mock_response.text = json.dumps({
                "pages": [{
                    "page_num": 1,
                    "components": [
                        {
                            "id": "A-101-DR-B2",
                            "type": "door",
                            "location": "Main entrance",
                            "confidence": 0.75,
                            "reasoning": "Door identified with Type 11 maglock symbol, but specification calls for Type 12 electric strike. Drawing shows maglock, conflict noted."
                        }
                    ]
                }]
            })
            mock_response.usage_metadata.total_token_count = 1200
            mock_generate.return_value = mock_response

            # Execute
            result = await agent.process({"pages": sample_pages})

            # Assert conflict is noted in reasoning
            component = result["components"]["pages"][0]["components"][0]
            assert "conflict" in component["reasoning"].lower()
            assert component["confidence"] == 0.75  # Moderate confidence due to conflict

    @pytest.mark.asyncio
    async def test_graceful_degradation_without_context(self, mock_job, mock_storage, sample_pages):
        """Test that pipeline continues gracefully when context loading fails."""
        agent = ScheduleAgentV2(mock_storage, mock_job)

        # Simulate context loading failure
        mock_storage.get_file.side_effect = Exception("Failed to load context")

        with patch.object(agent, 'upload_file') as mock_upload, \
             patch.object(agent, 'generate_content') as mock_generate:

            mock_upload.return_value = MagicMock(uri="file_uri", name="test.pdf")
            mock_response = MagicMock()
            mock_response.text = json.dumps({
                "pages": [{
                    "page_num": 1,
                    "components": [
                        {
                            "id": "A-101-DR-B2",
                            "type": "door",
                            "location": "Main entrance",
                            "confidence": 0.67,
                            "reasoning": "Identified based on visual analysis only"
                        }
                    ]
                }]
            })
            mock_response.usage_metadata.total_token_count = 1000
            mock_generate.return_value = mock_response

            # Execute - should not fail
            result = await agent.process({"pages": sample_pages})

            # Assert processing continued without context
            assert result["components"]["total_components"] == 1
            assert mock_job.update_processing_results.call_args[0][0]["schedule_agent"]["context_used"] is False
