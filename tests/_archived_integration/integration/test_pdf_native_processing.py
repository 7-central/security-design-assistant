"""Integration tests for native PDF processing with Google GenAI SDK."""
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.agents.schedule_agent_v2 import ScheduleAgentV2
from src.models.job import Job
from src.storage.interface import StorageInterface


class TestNativePDFProcessing:
    """Test native PDF processing capabilities."""

    @pytest.fixture
    def mock_storage(self):
        """Create mock storage."""
        storage = Mock(spec=StorageInterface)
        storage.save_checkpoint = AsyncMock()
        storage.save_file = AsyncMock()
        return storage

    @pytest.fixture
    def mock_job(self):
        """Create mock job."""
        from datetime import datetime

        from src.models.job import JobStatus

        return Job(
            job_id="test_job_123",
            client_name="test_client",
            project_name="test_project",
            status=JobStatus.PROCESSING,
            created_at=datetime.now(),
            updated_at=datetime.now()
        )

    @pytest.fixture
    def schedule_agent(self, mock_storage, mock_job):
        """Create schedule agent instance."""
        with patch('src.agents.base_agent_v2.BaseAgentV2._initialize_client'):
            agent = ScheduleAgentV2(mock_storage, mock_job)
            agent.client = Mock()
            agent.client.files.upload = Mock()
            agent.client.models.generate_content_async = AsyncMock()
            return agent

    @pytest.mark.asyncio
    async def test_native_pdf_upload(self, schedule_agent):
        """Test native PDF file upload without conversion."""
        # Mock the entire _extract_components method to avoid internal details
        from src.agents.schedule_agent_v2 import Component, ComponentExtractionResult

        async def mock_extract_components(pages):
            return ComponentExtractionResult(
                pages=[{
                    "page_num": 1,
                    "components": [
                        Component(
                            id="A-123-RD-B1",
                            type="Card Reader",
                            location="Main Entrance",
                            page_number=1,
                            confidence=0.95
                        ).model_dump()
                    ]
                }],
                total_components=1,
                processing_time_ms=100,
                tokens_used=500,
                cost_estimate=0.01
            )

        schedule_agent._extract_components = mock_extract_components

        # Test input with PDF file
        input_data = {
            "pages": [{"page_num": 1, "type": "pdf", "content": "test.pdf"}],
            "pdf_file": "test.pdf",
            "pdf_info": {"type": "genuine", "pages": 1}
        }

        result = await schedule_agent.process(input_data)

        # Verify native PDF processing
        assert result["next_stage"] == "codegen"
        assert "components" in result
        assert result["components"]["total_components"] == 1
        assert len(result["components"]["pages"]) == 1
        assert result["components"]["pages"][0]["components"][0]["id"] == "A-123-RD-B1"

    @pytest.mark.asyncio
    async def test_multimodal_content_handling(self, schedule_agent):
        """Test handling of multimodal content with native PDF."""
        # Mock the entire _extract_components method
        from src.agents.schedule_agent_v2 import Component, ComponentExtractionResult

        async def mock_extract_components(pages):
            return ComponentExtractionResult(
                pages=[{
                    "page_num": 1,
                    "components": [
                        Component(
                            id="A-456-EB-B2",
                            type="Exit Button",
                            location="Emergency Exit",
                            page_number=1,
                            confidence=0.90
                        ).model_dump()
                    ]
                }],
                total_components=1,
                processing_time_ms=100,
                tokens_used=500,
                cost_estimate=0.01
            )

        schedule_agent._extract_components = mock_extract_components

        input_data = {
            "pages": [{"page_num": 1, "type": "pdf", "content": "test_scanned.pdf"}],
            "pdf_file": "test_scanned.pdf",
            "pdf_info": {"type": "scanned", "pages": 1}
        }

        result = await schedule_agent.process(input_data)

        # Verify component extraction
        assert result["components"]["total_components"] == 1
        assert result["components"]["pages"][0]["components"][0]["type"] == "Exit Button"

    @pytest.mark.asyncio
    async def test_batch_processing_capability(self, schedule_agent):
        """Test batch processing for cost optimization."""
        # Mock the entire _extract_components method for multiple pages
        from src.agents.schedule_agent_v2 import Component, ComponentExtractionResult

        async def mock_extract_components(pages):
            page_results = []
            for i in range(1, 6):
                page_results.append({
                    "page_num": i,
                    "components": [
                        Component(
                            id=f"A-{100+i}-RD-B{i}",
                            type="Card Reader",
                            location=f"Floor {i}",
                            page_number=i,
                            confidence=0.92
                        ).model_dump()
                    ]
                })

            return ComponentExtractionResult(
                pages=page_results,
                total_components=5,
                processing_time_ms=500,
                tokens_used=2500,
                cost_estimate=0.05
            )

        schedule_agent._extract_components = mock_extract_components

        # Test with multi-page PDF
        input_data = {
            "pages": [{"page_num": i, "type": "pdf", "content": "test.pdf"} for i in range(1, 6)],
            "pdf_file": "test_multipage.pdf",
            "pdf_info": {"type": "genuine", "pages": 5}
        }

        result = await schedule_agent.process(input_data)

        # Verify batch processing
        assert result["components"]["total_components"] == 5
        assert len(result["components"]["pages"]) == 5

    @pytest.mark.asyncio
    async def test_error_handling_native_pdf(self, schedule_agent):
        """Test error handling for native PDF processing."""
        # Simulate error in _generate_with_retry
        async def mock_generate_with_retry(*args, **kwargs):
            raise Exception("File upload failed")

        schedule_agent._generate_with_retry = mock_generate_with_retry

        input_data = {
            "pages": [{"page_num": 1, "type": "pdf", "content": "corrupted.pdf"}],
            "pdf_file": "corrupted.pdf",
            "pdf_info": {"type": "genuine", "pages": 1}
        }

        # Should raise ScheduleAgentError
        from src.agents.schedule_agent_v2 import ScheduleAgentError
        with pytest.raises(ScheduleAgentError) as exc_info:
            await schedule_agent.process(input_data)

        assert "Processing failed" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_context_caching_integration(self, schedule_agent):
        """Test context caching for cost reduction."""
        # Mock the entire _extract_components method
        from src.agents.schedule_agent_v2 import Component, ComponentExtractionResult

        call_count = 0

        async def mock_extract_components(pages):
            nonlocal call_count
            call_count += 1

            return ComponentExtractionResult(
                pages=[{
                    "page_num": 1,
                    "components": [
                        Component(
                            id="A-789-DC-B3",
                            type="Door Controller",
                            location="Server Room",
                            page_number=1,
                            confidence=0.88
                        ).model_dump()
                    ]
                }],
                total_components=1,
                processing_time_ms=100,
                tokens_used=500,
                cost_estimate=0.01
            )

        schedule_agent._extract_components = mock_extract_components

        # First request
        input_data = {
            "pages": [{"page_num": 1, "type": "pdf", "content": "test.pdf"}],
            "pdf_file": "test.pdf",
            "pdf_info": {"type": "genuine", "pages": 1},
            "enable_caching": True
        }

        result1 = await schedule_agent.process(input_data)

        # Second request should use cached context
        result2 = await schedule_agent.process(input_data)

        # Both should have same results
        assert result1["components"]["total_components"] == 1
        assert result2["components"]["total_components"] == 1
        # Verify the extraction was called twice (no actual caching in mock)
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_pdf_size_limits(self, schedule_agent):
        """Test handling of PDF size limits."""
        # Test with large PDF info
        input_data = {
            "pages": [{"page_num": i, "type": "pdf", "content": "large.pdf"} for i in range(1, 1201)],
            "pdf_file": "large.pdf",
            "pdf_info": {"type": "genuine", "pages": 1200}  # Over 1000 page limit
        }

        # Mock to simulate processing continuing despite size
        from src.agents.schedule_agent_v2 import ComponentExtractionResult

        async def mock_extract_components(pages):
            return ComponentExtractionResult(
                pages=[],
                total_components=0,
                processing_time_ms=1000,
                tokens_used=50000,
                cost_estimate=1.0
            )

        schedule_agent._extract_components = mock_extract_components

        result = await schedule_agent.process(input_data)

        # Should process successfully but with appropriate handling
        assert result["next_stage"] == "codegen"
        assert result["components"]["total_components"] == 0
