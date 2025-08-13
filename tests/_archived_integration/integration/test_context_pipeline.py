"""Integration tests for context processing pipeline."""
import asyncio
import tempfile
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


@pytest.fixture
def test_client():
    """Create test client for FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_storage():
    """Create mock storage for integration tests."""
    storage = AsyncMock()
    storage.save_file = AsyncMock(return_value="saved_path")
    storage.get_file = AsyncMock(return_value=b"file_content")
    storage.file_exists = AsyncMock(return_value=True)
    storage.save_job_status = AsyncMock()
    storage.get_job_status = AsyncMock()
    return storage


@pytest.fixture
def sample_pdf_content():
    """Create minimal PDF content for testing."""
    return b"%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R/Resources<</Font<</F1 4 0 R>>>>/Contents 5 0 R>>\nendobj\n4 0 obj\n<</Type/Font/Subtype/Type1/BaseFont/Helvetica>>\nendobj\n5 0 obj\n<</Length 44>>\nstream\nBT /F1 12 Tf 100 700 Td (Test PDF) Tj ET\nendstream\nendobj\nxref\n0 6\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\n0000000229 00000 n\n0000000306 00000 n\ntrailer\n<</Size 6/Root 1 0 R>>\nstartxref\n394\n%%EOF"


@pytest.fixture
def sample_docx_content():
    """Create minimal DOCX (ZIP) content for testing."""
    # This is a minimal ZIP file structure
    return b"PK\x03\x04\x14\x00\x00\x00\x08\x00"


class TestContextPipelineIntegration:
    """Integration tests for context processing in the pipeline."""

    @pytest.mark.asyncio
    async def test_full_pipeline_with_text_context(self, test_client, mock_storage):
        """Test full pipeline with text context provided."""
        with patch('src.api.routes.storage', mock_storage):
            with patch('src.api.routes.ScheduleAgentV2') as MockScheduleAgent:
                with patch('src.api.routes.ContextAgent') as MockContextAgent:
                    with patch('src.api.routes.ExcelGenerationAgent') as MockExcelAgent:
                        # Setup mocks
                        mock_schedule = MockScheduleAgent.return_value
                        mock_schedule.process = AsyncMock(return_value={
                            "components": {"pages": [{"components": []}]}
                        })

                        mock_context = MockContextAgent.return_value
                        mock_context.process = AsyncMock(return_value={
                            "sections": [
                                {
                                    "title": "Lock Types",
                                    "content": "Type 11: Electromagnetic",
                                    "type": "specification"
                                }
                            ],
                            "metadata": {
                                "source_type": "text",
                                "sections_count": 1,
                                "tokens_used": 100,
                                "processing_time_ms": 500
                            }
                        })

                        mock_excel = MockExcelAgent.return_value
                        mock_excel.process = AsyncMock(return_value={
                            "status": "completed",
                            "file_path": "path/to/excel.xlsx"
                        })

                        # Make request with context_text
                        # Create a more valid PDF structure
                        pdf_content = b"%PDF-1.4\n1 0 obj\n<</Type/Catalog/Pages 2 0 R>>\nendobj\n2 0 obj\n<</Type/Pages/Kids[3 0 R]/Count 1>>\nendobj\n3 0 obj\n<</Type/Page/MediaBox[0 0 612 792]/Parent 2 0 R>>\nendobj\nxref\n0 4\n0000000000 65535 f\n0000000009 00000 n\n0000000058 00000 n\n0000000115 00000 n\ntrailer\n<</Size 4/Root 1 0 R>>\nstartxref\n208\n%%EOF"
                        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_pdf:
                            tmp_pdf.write(pdf_content)
                            tmp_pdf.seek(0)

                            response = test_client.post(
                                "/process-drawing",
                                files={"drawing_file": ("test.pdf", tmp_pdf, "application/pdf")},
                                data={
                                    "client_name": "test_client",
                                    "project_name": "test_project",
                                    "context_text": "Lock Type 11: Electromagnetic lock"
                                }
                            )

                        assert response.status_code == 202
                        data = response.json()
                        assert "job_id" in data

                        # Verify context agent was called
                        mock_context.process.assert_called_once()
                        context_call_args = mock_context.process.call_args[0][0]
                        assert "context_text" in context_call_args
                        assert context_call_args["context_text"] == "Lock Type 11: Electromagnetic lock"

    @pytest.mark.asyncio
    async def test_full_pipeline_with_pdf_context_file(self, test_client, mock_storage, sample_pdf_content):
        """Test full pipeline with PDF context file."""
        with patch('src.api.routes.storage', mock_storage):
            with patch('src.api.routes.ScheduleAgentV2') as MockScheduleAgent:
                with patch('src.api.routes.ContextAgent') as MockContextAgent:
                    with patch('src.api.routes.ExcelGenerationAgent') as MockExcelAgent:
                        # Setup mocks
                        mock_schedule = MockScheduleAgent.return_value
                        mock_schedule.process = AsyncMock(return_value={
                            "components": {"pages": [{"components": []}]}
                        })

                        mock_context = MockContextAgent.return_value
                        mock_context.process = AsyncMock(return_value={
                            "sections": [],
                            "metadata": {
                                "source_type": "pdf",
                                "sections_count": 0,
                                "tokens_used": 200,
                                "processing_time_ms": 1000
                            }
                        })

                        mock_excel = MockExcelAgent.return_value
                        mock_excel.process = AsyncMock(return_value={
                            "status": "completed",
                            "file_path": "path/to/excel.xlsx"
                        })

                        # Make request with context file
                        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_pdf:
                            tmp_pdf.write(sample_pdf_content)
                            tmp_pdf.seek(0)

                            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_context:
                                tmp_context.write(b"%PDF-1.4 context content")
                                tmp_context.seek(0)

                                response = test_client.post(
                                    "/process-drawing",
                                    files={
                                        "drawing_file": ("drawing.pdf", tmp_pdf, "application/pdf"),
                                        "context_file": ("context.pdf", tmp_context, "application/pdf")
                                    },
                                    data={
                                        "client_name": "test_client",
                                        "project_name": "test_project"
                                    }
                                )

                        assert response.status_code == 202

                        # Verify context was processed
                        mock_context.process.assert_called_once()
                        context_call_args = mock_context.process.call_args[0][0]
                        assert "context_file_path" in context_call_args
                        assert context_call_args["context_type"]["type"] == "pdf"

    @pytest.mark.asyncio
    async def test_pipeline_continues_when_context_fails(self, test_client, mock_storage, sample_pdf_content):
        """Test that pipeline continues even when context processing fails."""
        with patch('src.api.routes.storage', mock_storage):
            with patch('src.api.routes.ScheduleAgentV2') as MockScheduleAgent:
                with patch('src.api.routes.ContextAgent') as MockContextAgent:
                    with patch('src.api.routes.ExcelGenerationAgent') as MockExcelAgent:
                        # Setup context to fail
                        mock_context = MockContextAgent.return_value
                        mock_context.process = AsyncMock(
                            side_effect=Exception("Context processing failed")
                        )

                        # Schedule agent should still be called
                        mock_schedule = MockScheduleAgent.return_value
                        mock_schedule.process = AsyncMock(return_value={
                            "components": {"pages": [{"components": []}]}
                        })

                        mock_excel = MockExcelAgent.return_value
                        mock_excel.process = AsyncMock(return_value={
                            "status": "completed",
                            "file_path": "path/to/excel.xlsx"
                        })

                        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_pdf:
                            tmp_pdf.write(sample_pdf_content)
                            tmp_pdf.seek(0)

                            response = test_client.post(
                                "/process-drawing",
                                files={"drawing_file": ("test.pdf", tmp_pdf, "application/pdf")},
                                data={
                                    "client_name": "test_client",
                                    "project_name": "test_project",
                                    "context_text": "This will fail"
                                }
                            )

                        # Pipeline should complete successfully
                        assert response.status_code == 202

                        # Schedule agent should still be called
                        mock_schedule.process.assert_called_once()
                        # Context should NOT be in the schedule input
                        schedule_call_args = mock_schedule.process.call_args[0][0]
                        assert "context" not in schedule_call_args

    @pytest.mark.asyncio
    async def test_context_timeout_handling(self, test_client, mock_storage, sample_pdf_content):
        """Test that context processing times out after 30 seconds."""
        with patch('src.api.routes.storage', mock_storage):
            with patch('src.api.routes.ScheduleAgentV2') as MockScheduleAgent:
                with patch('src.api.routes.ContextAgent') as MockContextAgent:
                    with patch('src.api.routes.ExcelGenerationAgent') as MockExcelAgent:
                        # Setup context to take too long
                        async def slow_process(*args, **kwargs):
                            await asyncio.sleep(35)  # Longer than 30s timeout
                            return {"sections": []}

                        mock_context = MockContextAgent.return_value
                        mock_context.process = slow_process

                        mock_schedule = MockScheduleAgent.return_value
                        mock_schedule.process = AsyncMock(return_value={
                            "components": {"pages": [{"components": []}]}
                        })

                        mock_excel = MockExcelAgent.return_value
                        mock_excel.process = AsyncMock(return_value={
                            "status": "completed",
                            "file_path": "path/to/excel.xlsx"
                        })

                        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_pdf:
                            tmp_pdf.write(sample_pdf_content)
                            tmp_pdf.seek(0)

                            # Use asyncio.wait_for to simulate timeout
                            with patch('asyncio.wait_for',
                                      side_effect=asyncio.TimeoutError()):
                                response = test_client.post(
                                    "/process-drawing",
                                    files={"drawing_file": ("test.pdf", tmp_pdf, "application/pdf")},
                                    data={
                                        "client_name": "test_client",
                                        "project_name": "test_project",
                                        "context_text": "Some context"
                                    }
                                )

                        # Pipeline should still complete
                        assert response.status_code == 202

                        # Schedule agent should be called without context
                        mock_schedule.process.assert_called_once()

    @pytest.mark.asyncio
    async def test_multiple_context_formats(self, test_client, mock_storage, sample_pdf_content):
        """Test processing different context file formats."""
        test_cases = [
            ("context.docx", b"PK\x03\x04", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "docx"),
            ("context.pdf", b"%PDF-1.4", "application/pdf", "pdf"),
            ("context.txt", b"Plain text content", "text/plain", "text")
        ]

        for filename, content, mime_type, expected_type in test_cases:
            with patch('src.api.routes.storage', mock_storage):
                with patch('src.api.routes.ScheduleAgentV2') as MockScheduleAgent:
                    with patch('src.api.routes.ContextAgent') as MockContextAgent:
                        with patch('src.api.routes.ExcelGenerationAgent') as MockExcelAgent:
                            # Setup mocks
                            mock_context = MockContextAgent.return_value
                            mock_context.process = AsyncMock(return_value={
                                "sections": [],
                                "metadata": {
                                    "source_type": expected_type,
                                    "sections_count": 0,
                                    "tokens_used": 100,
                                    "processing_time_ms": 500
                                }
                            })

                            mock_schedule = MockScheduleAgent.return_value
                            mock_schedule.process = AsyncMock(return_value={
                                "components": {"pages": [{"components": []}]}
                            })

                            mock_excel = MockExcelAgent.return_value
                            mock_excel.process = AsyncMock(return_value={
                                "status": "completed",
                                "file_path": "path/to/excel.xlsx"
                            })

                            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_pdf:
                                tmp_pdf.write(sample_pdf_content)
                                tmp_pdf.seek(0)

                                with tempfile.NamedTemporaryFile() as tmp_context:
                                    tmp_context.write(content)
                                    tmp_context.seek(0)

                                    response = test_client.post(
                                        "/process-drawing",
                                        files={
                                            "drawing_file": ("drawing.pdf", tmp_pdf, "application/pdf"),
                                            "context_file": (filename, tmp_context, mime_type)
                                        },
                                        data={
                                            "client_name": "test_client",
                                            "project_name": "test_project"
                                        }
                                    )

                            assert response.status_code == 202

                            # Verify correct type was detected
                            context_call_args = mock_context.process.call_args[0][0]
                            assert context_call_args["context_type"]["type"] == expected_type

    @pytest.mark.asyncio
    async def test_context_passed_to_schedule_agent(self, test_client, mock_storage, sample_pdf_content):
        """Test that context is properly passed to Schedule Agent."""
        with patch('src.api.routes.storage', mock_storage):
            with patch('src.api.routes.ScheduleAgentV2') as MockScheduleAgent:
                with patch('src.api.routes.ContextAgent') as MockContextAgent:
                    with patch('src.api.routes.ExcelGenerationAgent') as MockExcelAgent:
                        # Setup context agent to return data
                        context_data = {
                            "sections": [
                                {
                                    "title": "Lock Specifications",
                                    "content": "Type 11: Electromagnetic",
                                    "type": "specification"
                                }
                            ],
                            "metadata": {
                                "source_type": "text",
                                "sections_count": 1,
                                "tokens_used": 100,
                                "processing_time_ms": 500
                            }
                        }

                        mock_context = MockContextAgent.return_value
                        mock_context.process = AsyncMock(return_value=context_data)

                        mock_schedule = MockScheduleAgent.return_value
                        mock_schedule.process = AsyncMock(return_value={
                            "components": {"pages": [{"components": []}]}
                        })

                        mock_excel = MockExcelAgent.return_value
                        mock_excel.process = AsyncMock(return_value={
                            "status": "completed",
                            "file_path": "path/to/excel.xlsx"
                        })

                        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_pdf:
                            tmp_pdf.write(b"%PDF-1.4 test")
                            tmp_pdf.seek(0)

                            response = test_client.post(
                                "/process-drawing",
                                files={"drawing_file": ("test.pdf", tmp_pdf, "application/pdf")},
                                data={
                                    "client_name": "test_client",
                                    "project_name": "test_project",
                                    "context_text": "Lock specifications"
                                }
                            )

                        assert response.status_code == 202

                        # Verify context was passed to schedule agent
                        schedule_call_args = mock_schedule.process.call_args[0][0]
                        assert "context" in schedule_call_args
                        assert schedule_call_args["context"] == context_data

    @pytest.mark.asyncio
    async def test_context_storage_and_logging(self, test_client, mock_storage, sample_pdf_content):
        """Test that context files are saved to storage and logged properly."""
        with patch('src.api.routes.storage', mock_storage):
            with patch('src.api.routes.ScheduleAgentV2') as MockScheduleAgent:
                with patch('src.api.routes.ContextAgent') as MockContextAgent:
                    with patch('src.api.routes.ExcelGenerationAgent') as MockExcelAgent:
                        # Setup mocks
                        mock_context = MockContextAgent.return_value
                        mock_context.process = AsyncMock(return_value={
                            "sections": [],
                            "metadata": {
                                "source_type": "pdf",
                                "sections_count": 0,
                                "tokens_used": 100,
                                "processing_time_ms": 500
                            }
                        })

                        mock_schedule = MockScheduleAgent.return_value
                        mock_schedule.process = AsyncMock(return_value={
                            "components": {"pages": [{"components": []}]}
                        })

                        mock_excel = MockExcelAgent.return_value
                        mock_excel.process = AsyncMock(return_value={
                            "status": "completed",
                            "file_path": "path/to/excel.xlsx"
                        })

                        with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_pdf:
                            tmp_pdf.write(b"%PDF-1.4 test")
                            tmp_pdf.seek(0)

                            with tempfile.NamedTemporaryFile(suffix=".pdf") as tmp_context:
                                tmp_context.write(b"%PDF-1.4 context")
                                tmp_context.seek(0)

                                response = test_client.post(
                                    "/process-drawing",
                                    files={
                                        "drawing_file": ("drawing.pdf", tmp_pdf, "application/pdf"),
                                        "context_file": ("context.pdf", tmp_context, "application/pdf")
                                    },
                                    data={
                                        "client_name": "test_client",
                                        "project_name": "test_project"
                                    }
                                )

                        assert response.status_code == 202

                        # Verify context file was saved to storage
                        save_calls = mock_storage.save_file.call_args_list
                        context_saved = any(
                            "context.pdf" in str(call[0][0])
                            for call in save_calls
                        )
                        assert context_saved
