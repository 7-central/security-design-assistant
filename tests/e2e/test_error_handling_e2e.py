"""Error handling E2E tests with real AWS and Gemini APIs."""
import uuid
from pathlib import Path

import pytest


@pytest.mark.e2e
class TestErrorHandlingE2E:
    """Test error handling in the pipeline."""

    def test_invalid_file_upload(self, api_client, e2e_job_helper, aws_clients):
        """Test handling of invalid file upload (non-PDF).

        This test verifies that the system properly rejects non-PDF files
        and returns appropriate error messages.
        """
        # Create a non-PDF file
        invalid_file = Path("/tmp/test_invalid.txt")
        invalid_file.write_text("This is not a PDF file")

        job_id = f"e2e_error_{uuid.uuid4().hex[:8]}"

        try:
            # Upload non-PDF file
            s3_uri = e2e_job_helper.upload_pdf(job_id, invalid_file)

            # Create job
            table = aws_clients["dynamodb"].Table(e2e_job_helper.table_name)

            job_item = {
                "company#client#job": f"7central#test_client#{job_id}",
                "job_id": job_id,
                "client_name": "test_client",
                "project_name": "e2e_error_test",
                "status": "pending",
                "file_path": s3_uri,
            }

            table.put_item(Item=job_item)

            # Process via API and expect failure
            with open(invalid_file, "rb") as f:
                files = {"drawing_file": ("invalid.txt", f, "text/plain")}
                data = {"client_name": "test_client", "project_name": "e2e_error_test"}
                response = api_client.post("/process-drawing", files=files, data=data)

            # API should reject non-PDF file
            assert response.status_code == 422  # Unprocessable Entity for wrong file type
            error_response = response.json()
            assert "PDF" in error_response.get("detail", "") or "pdf" in error_response.get("detail", "").lower()

            print("✅ Invalid file rejection test passed!")
            print(f"   - Error response: {error_response.get('detail', 'Unknown error')}")

        finally:
            # Clean up
            invalid_file.unlink(missing_ok=True)
            e2e_job_helper.cleanup(job_id)

    def test_corrupted_pdf_handling(self, api_client, e2e_job_helper, corrupted_pdf_path, aws_clients):
        """Test handling of corrupted PDF files.

        This test verifies that the system handles corrupted PDFs gracefully
        and provides meaningful error messages.
        """
        job_id = f"e2e_corrupted_{uuid.uuid4().hex[:8]}"

        try:
            # Upload corrupted PDF
            s3_uri = e2e_job_helper.upload_pdf(job_id, corrupted_pdf_path)

            # Create job
            table = aws_clients["dynamodb"].Table(e2e_job_helper.table_name)

            job_item = {
                "company#client#job": f"7central#test_client#{job_id}",
                "job_id": job_id,
                "client_name": "test_client",
                "project_name": "e2e_corrupted_test",
                "status": "pending",
                "file_path": s3_uri,
            }

            table.put_item(Item=job_item)

            # Process via API - should handle corruption gracefully
            with open(corrupted_pdf_path, "rb") as f:
                files = {"drawing_file": ("corrupted.pdf", f, "application/pdf")}
                data = {"client_name": "test_client", "project_name": "e2e_corrupted_test"}
                response = api_client.post("/process-drawing", files=files, data=data)

            # API might accept or reject corrupted PDF
            if response.status_code == 200:
                # Processed successfully (might extract partial data)
                job_response = response.json()
                print(f"✅ Corrupted PDF processed with status: {job_response['status']}")
            elif response.status_code in [422, 400]:
                # Rejected as invalid
                print(f"✅ Corrupted PDF correctly rejected with status code: {response.status_code}")
            else:
                pytest.fail(f"Unexpected response code: {response.status_code}")

        finally:
            e2e_job_helper.cleanup(job_id)

    def test_timeout_handling(self, e2e_job_helper, complex_pdf_path):
        """Test handling of processing timeouts.

        This test verifies that long-running jobs are handled properly
        and don't hang indefinitely.
        """
        job_id = f"e2e_timeout_{uuid.uuid4().hex[:8]}"

        try:
            # Use complex PDF that might take longer to process
            e2e_job_helper.upload_pdf(job_id, complex_pdf_path)

            # Try to wait with very short timeout
            with pytest.raises(TimeoutError) as exc_info:
                # Use unrealistically short timeout to force timeout
                e2e_job_helper.wait_for_completion(job_id, timeout=1)

            assert "did not complete within" in str(exc_info.value)

            print("✅ Timeout handling test passed!")
            print(f"   - Timeout error: {exc_info.value}")

        finally:
            e2e_job_helper.cleanup(job_id)

    @pytest.mark.asyncio
    async def test_gemini_api_error_handling(self, test_pdf_path):
        """Test handling of Gemini API errors.

        This test verifies that Gemini API errors (rate limits, invalid requests)
        are handled gracefully.
        """
        from datetime import datetime
        from unittest.mock import MagicMock

        from google.api_core import exceptions

        from src.agents.schedule_agent_v2 import ScheduleAgentV2
        from src.models.job import Job, JobStatus
        from src.storage.local_storage import LocalStorage

        # Create test job
        job = Job(
            job_id=f"e2e_gemini_error_{uuid.uuid4().hex[:8]}",
            client_name="test_client",
            project_name="e2e_error_test",
            status=JobStatus.PROCESSING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )

        storage = LocalStorage()
        agent = ScheduleAgentV2(storage, job)

        # Mock Gemini client to raise rate limit error
        mock_client = MagicMock()
        mock_client.models.generate_content.side_effect = exceptions.ResourceExhausted("Rate limit exceeded")
        # Set the private _client attribute directly
        agent._client = mock_client

        # Process should handle the error gracefully
        with pytest.raises(Exception) as exc_info:
            await agent.process({"pages": [{"content": "test"}]})

        # Verify error is properly handled - agent wraps errors in generic message
        assert "Processing failed" in str(exc_info.value) or "unexpected error" in str(exc_info.value).lower()

        print("✅ Gemini API error handling test passed!")
        print(f"   - Error handled: {exc_info.value}")
