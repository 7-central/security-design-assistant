"""Unit tests for Context Agent."""
import json
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.agents.context_agent import ContextAgent
from src.models.job import JobStatus


@pytest.fixture
def mock_storage():
    """Create mock storage interface."""
    storage = AsyncMock()
    storage.save_file = AsyncMock(return_value="saved_path")
    storage.get_file = AsyncMock(return_value=b"file_content")
    storage.file_exists = AsyncMock(return_value=True)
    storage.save_job_status = AsyncMock()
    return storage


@pytest.fixture
def mock_job():
    """Create mock job instance."""
    job = MagicMock()
    job.job_id = "test_job_123"
    job.client_name = "test_client"
    job.project_name = "test_project"
    job.status = JobStatus.PROCESSING
    job.update_metadata = MagicMock()
    job.update_processing_results = MagicMock()
    return job


@pytest.fixture
def context_agent(mock_storage, mock_job):
    """Create Context Agent instance."""
    with patch('src.agents.base_agent_v2.settings') as mock_settings:
        mock_settings.GEMINI_API_KEY = "test_api_key"
        agent = ContextAgent(mock_storage, mock_job)
        # Mock the _client attribute directly instead of the property
        agent._client = MagicMock()
        return agent


@pytest.mark.unit
class TestContextAgent:
    """Test cases for Context Agent."""

    @pytest.mark.asyncio
    async def test_process_no_context(self, context_agent):
        """Test processing when no context is provided."""
        input_data = {}

        result = await context_agent.process(input_data)

        assert result["sections"] == []
        assert result["metadata"]["source_type"] == "none"
        assert result["metadata"]["sections_count"] == 0
        assert result["metadata"]["tokens_used"] == 0

    @pytest.mark.asyncio
    async def test_process_text_context(self, context_agent):
        """Test processing text context."""
        input_data = {
            "context_text": "Lock Type 11: Electromagnetic lock with 1200lb holding force",
            "context_type": {"type": "text", "format": "string"}
        }

        # Mock the AI response
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "sections": [
                {
                    "title": "Lock Specifications",
                    "content": "Lock Type 11: Electromagnetic lock with 1200lb holding force",
                    "type": "specification"
                }
            ]
        })

        with patch.object(context_agent, '_generate_with_retry',
                         return_value=mock_response) as mock_generate:
            result = await context_agent.process(input_data)

        assert len(result["sections"]) == 1
        assert result["sections"][0]["title"] == "Lock Specifications"
        assert result["metadata"]["source_type"] == "text"
        assert result["metadata"]["sections_count"] == 1
        mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_docx_file(self, context_agent):
        """Test processing DOCX file."""
        # Create a temporary DOCX file for testing
        with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as tmp:
            tmp_path = tmp.name

        input_data = {
            "context_file_path": tmp_path,
            "context_type": {"type": "docx", "format": "file"}
        }

        # Mock docx library import
        import sys
        mock_docx = MagicMock()
        sys.modules['docx'] = mock_docx

        mock_doc = MagicMock()
        mock_para1 = MagicMock()
        mock_para1.text = "Lock Type 11"
        mock_para1.style.name = "Heading 1"

        mock_para2 = MagicMock()
        mock_para2.text = "Electromagnetic lock with 1200lb holding force"
        mock_para2.style.name = "Normal"

        mock_doc.paragraphs = [mock_para1, mock_para2]
        mock_doc.tables = []
        mock_docx.Document.return_value = mock_doc

        # Mock AI response
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "sections": [
                {
                    "title": "Lock Type 11",
                    "content": "Electromagnetic lock with 1200lb holding force",
                    "type": "specification"
                }
            ]
        })

        with patch.object(context_agent, '_generate_with_retry',
                        return_value=mock_response):
            result = await context_agent.process(input_data)

        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)

        # Clean up mock
        if 'docx' in sys.modules:
            del sys.modules['docx']

        assert len(result["sections"]) == 1
        assert result["metadata"]["source_type"] == "docx"
        assert result["metadata"]["sections_count"] == 1

    @pytest.mark.asyncio
    async def test_process_pdf_file(self, context_agent):
        """Test processing PDF file using Gemini multimodal."""
        # Create a temporary PDF file for testing
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
            tmp_path = tmp.name
            # Write minimal PDF header
            tmp.write(b"%PDF-1.4")

        input_data = {
            "context_file_path": tmp_path,
            "context_type": {"type": "pdf", "format": "file"}
        }

        # Mock file upload
        mock_uploaded_file = MagicMock()
        mock_uploaded_file.name = "uploaded_file_123"

        # Mock AI response
        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "sections": [
                {
                    "title": "Lock Specifications",
                    "content": "Various lock types defined",
                    "type": "specification"
                }
            ]
        })

        with patch.object(context_agent, 'upload_file',
                         return_value=mock_uploaded_file) as mock_upload:
            with patch.object(context_agent, 'generate_content',
                            return_value=mock_response) as mock_generate:
                result = await context_agent.process(input_data)

        # Clean up temp file
        Path(tmp_path).unlink(missing_ok=True)

        assert len(result["sections"]) == 1
        assert result["metadata"]["source_type"] == "pdf"
        mock_upload.assert_called_once_with(tmp_path)
        mock_generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_error_handling_continues_pipeline(self, context_agent):
        """Test that errors in context processing don't stop the pipeline."""
        input_data = {
            "context_text": "Some context",
            "context_type": {"type": "text", "format": "string"}
        }

        # Mock an error in AI generation
        with patch.object(context_agent, '_generate_with_retry',
                         side_effect=Exception("API Error")):
            result = await context_agent.process(input_data)

        # Should return empty sections but not raise
        assert result["sections"] == []
        assert result["metadata"]["sections_count"] == 0
        # Error is logged but not included in metadata for graceful degradation

    @pytest.mark.asyncio
    async def test_summarize_specifications(self, context_agent):
        """Test the summarize_specifications method."""
        raw_text = "Lock Type 11: Electromagnetic\nLock Type 12: Magnetic"

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "sections": [
                {
                    "title": "Lock Types",
                    "content": "Type 11 and 12 specifications",
                    "type": "specification"
                }
            ]
        })

        with patch.object(context_agent, '_generate_with_retry',
                         return_value=mock_response):
            result = await context_agent.summarize_specifications(raw_text)

        assert "sections" in result
        assert len(result["sections"]) == 1

    @pytest.mark.asyncio
    async def test_extract_context_unsupported_file(self, context_agent):
        """Test that unsupported file types raise an error."""
        with pytest.raises(ValueError, match="Unsupported file type"):
            await context_agent.extract_context("test.xyz")

    def test_parse_json_response_with_markdown(self, context_agent):
        """Test parsing JSON from markdown-formatted response."""
        response = """Here's the extracted data:

```json
{
    "sections": [
        {"title": "Test", "content": "Content", "type": "general"}
    ]
}
```"""

        result = context_agent._parse_json_response(response)
        assert "sections" in result
        assert len(result["sections"]) == 1

    def test_parse_json_response_malformed(self, context_agent):
        """Test parsing malformed JSON returns raw content."""
        response = "This is not JSON at all"

        result = context_agent._parse_json_response(response)
        assert "sections" in result
        assert result["sections"][0]["title"] == "Raw Content"
        assert response in result["sections"][0]["content"]

    @pytest.mark.asyncio
    async def test_checkpoint_saving(self, context_agent, mock_storage):
        """Test that checkpoints are saved correctly."""
        input_data = {
            "context_text": "Test content",
            "context_type": {"type": "text", "format": "string"}
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps({"sections": []})

        with patch.object(context_agent, '_generate_with_retry',
                         return_value=mock_response):
            await context_agent.process(input_data)

        # Verify save_checkpoint was called
        mock_storage.save_file.assert_called()
        call_args = mock_storage.save_file.call_args
        assert "checkpoint_context_v1.json" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_metadata_tracking(self, context_agent, mock_job):
        """Test that job metadata is updated with context processing info."""
        input_data = {
            "context_text": "Test content",
            "context_type": {"type": "text", "format": "string"}
        }

        mock_response = MagicMock()
        mock_response.text = json.dumps({
            "sections": [{"title": "Test", "content": "Content", "type": "general"}]
        })

        with patch.object(context_agent, '_generate_with_retry',
                         return_value=mock_response):
            result = await context_agent.process(input_data)

        # Verify job metadata was updated
        mock_job.update_metadata.assert_called_once()
        metadata_call = mock_job.update_metadata.call_args[0][0]
        assert "context_processing" in metadata_call
        assert metadata_call["context_processing"]["type"] == "text"
        assert metadata_call["context_processing"]["sections_found"] == 1
