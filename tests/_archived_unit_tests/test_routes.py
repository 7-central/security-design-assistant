import io

from fastapi import status
from fastapi.testclient import TestClient


class TestHealthEndpoint:
    def test_health_check_returns_healthy(self, test_client: TestClient) -> None:
        response = test_client.get("/health")

        assert response.status_code == status.HTTP_200_OK
        assert response.json() == {
            "status": "healthy",
            "version": "1.0.0"
        }


class TestProcessDrawingEndpoint:
    def test_process_drawing_success(self, test_client: TestClient, sample_pdf_content: bytes) -> None:
        files = {
            "drawing_file": ("test_drawing.pdf", io.BytesIO(sample_pdf_content), "application/pdf")
        }
        data = {
            "client_name": "Test Client",
            "project_name": "Test Project"
        }

        response = test_client.post("/process-drawing", files=files, data=data)

        assert response.status_code == status.HTTP_202_ACCEPTED
        response_data = response.json()
        assert "job_id" in response_data
        assert response_data["job_id"].startswith("job_")
        assert response_data["status"] == "processing"
        assert response_data["estimated_time_seconds"] == 300

    def test_process_drawing_missing_file(self, test_client: TestClient) -> None:
        data = {
            "client_name": "Test Client",
            "project_name": "Test Project"
        }

        response = test_client.post("/process-drawing", data=data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY

    def test_process_drawing_non_pdf_file(self, test_client: TestClient) -> None:
        files = {
            "drawing_file": ("test.txt", io.BytesIO(b"Not a PDF"), "text/plain")
        }
        data = {
            "client_name": "Test Client",
            "project_name": "Test Project"
        }

        response = test_client.post("/process-drawing", files=files, data=data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "File must be a PDF" in response.json()["detail"]

    def test_process_drawing_invalid_pdf(self, test_client: TestClient, invalid_pdf_content: bytes) -> None:
        files = {
            "drawing_file": ("test.pdf", io.BytesIO(invalid_pdf_content), "application/pdf")
        }
        data = {
            "client_name": "Test Client",
            "project_name": "Test Project"
        }

        response = test_client.post("/process-drawing", files=files, data=data)

        assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
        assert "Invalid PDF file" in response.json()["detail"]

    def test_process_drawing_empty_file(self, test_client: TestClient) -> None:
        files = {
            "drawing_file": ("empty.pdf", io.BytesIO(b""), "application/pdf")
        }
        data = {
            "client_name": "Test Client",
            "project_name": "Test Project"
        }

        response = test_client.post("/process-drawing", files=files, data=data)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "File is empty" in response.json()["detail"]

    def test_process_drawing_file_too_large(self, test_client: TestClient) -> None:
        # Create a file larger than 100MB
        large_content = b"%PDF-1.4\n" + b"0" * (101 * 1024 * 1024)

        files = {
            "drawing_file": ("large.pdf", io.BytesIO(large_content), "application/pdf")
        }
        data = {
            "client_name": "Test Client",
            "project_name": "Test Project"
        }

        response = test_client.post("/process-drawing", files=files, data=data)

        assert response.status_code == status.HTTP_413_REQUEST_ENTITY_TOO_LARGE
        assert "File size exceeds 100MB limit" in response.json()["detail"]

    def test_process_drawing_unique_job_ids(self, test_client: TestClient, sample_pdf_content: bytes) -> None:
        job_ids = []

        for _ in range(3):
            files = {
                "drawing_file": ("test.pdf", io.BytesIO(sample_pdf_content), "application/pdf")
            }
            data = {
                "client_name": "Test Client",
                "project_name": "Test Project"
            }

            response = test_client.post("/process-drawing", files=files, data=data)
            assert response.status_code == status.HTTP_202_ACCEPTED
            job_ids.append(response.json()["job_id"])

        # Check all job IDs are unique
        assert len(job_ids) == len(set(job_ids))
