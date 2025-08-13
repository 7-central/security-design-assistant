"""E2E test fixtures with real AWS and Gemini clients."""
import os
import threading
import time
from pathlib import Path
from typing import Any

import boto3
import httpx
import pytest
import uvicorn
from dotenv import load_dotenv
from google import genai

# Load environment variables from .env file
load_dotenv()


@pytest.fixture(scope="session")
def fastapi_server():
    """Start FastAPI server for E2E testing."""
    from src.api.main import app

    # Configure server
    config = uvicorn.Config(app=app, host="127.0.0.1", port=8000, log_level="warning")
    server = uvicorn.Server(config)

    # Start server in background thread
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()

    # Wait for server to start
    time.sleep(2)

    # Verify server is running
    max_retries = 10
    for _ in range(max_retries):
        try:
            response = httpx.get("http://127.0.0.1:8000/health")
            if response.status_code == 200:
                break
        except httpx.ConnectError:
            time.sleep(1)
    else:
        raise RuntimeError("FastAPI server failed to start")

    yield "http://127.0.0.1:8000"

    # Server will be terminated when process ends (daemon thread)


@pytest.fixture(scope="session")
def api_client(fastapi_server):
    """HTTP client for API testing."""
    # Increased timeout to 5 minutes to accommodate Judge Agent processing
    return httpx.Client(base_url=fastapi_server, timeout=300.0)


@pytest.fixture(scope="session")
def aws_clients():
    """Real AWS clients for E2E testing using design-lee profile."""
    # Use profile if available, otherwise use default credentials
    profile_name = os.environ.get("AWS_PROFILE", "design-lee")
    region_name = os.environ.get("AWS_DEFAULT_REGION", "eu-west-2")

    try:
        session = boto3.Session(profile_name=profile_name, region_name=region_name)
    except Exception:
        # Fall back to default credentials if profile doesn't exist
        session = boto3.Session(region_name=region_name)

    return {"s3": session.client("s3"), "dynamodb": session.resource("dynamodb"), "sqs": session.client("sqs")}


@pytest.fixture(scope="session")
def gemini_client():
    """Real Gemini client for E2E testing."""
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        pytest.skip("GEMINI_API_KEY not set in environment")

    return genai.Client(api_key=api_key)


@pytest.fixture(scope="session")
def test_bucket():
    """Get the test S3 bucket name based on environment."""
    env = os.environ.get("ENV", "dev")

    # Check for explicit override first
    explicit_bucket = os.environ.get("S3_BUCKET")
    if explicit_bucket:
        return explicit_bucket

    # Use environment-based defaults
    if env == "dev":
        return "security-assistant-dev-445567098699"
    elif env == "prod":
        return "security-assistant-files"
    else:
        return "security-assistant-files"


@pytest.fixture(scope="session")
def test_table():
    """Get the test DynamoDB table name based on environment."""
    env = os.environ.get("ENV", "dev")

    # Check for explicit override first
    explicit_table = os.environ.get("DYNAMODB_TABLE")
    if explicit_table:
        return explicit_table

    # Use environment-based defaults
    if env == "dev":
        return "security-assistant-dev-jobs"
    elif env == "prod":
        return "security-assistant-jobs"
    else:
        return "security-assistant-jobs"


@pytest.fixture(scope="session")
def test_queue_url():
    """Get the test SQS queue URL."""
    return os.environ.get("SQS_QUEUE_URL")


@pytest.fixture
def test_pdf_path():
    """Path to test PDF file."""
    return Path(__file__).parent.parent / "fixtures" / "pdfs" / "example_b2_drawing.pdf"


@pytest.fixture
def complex_pdf_path():
    """Path to complex multi-page test PDF file."""
    return Path(__file__).parent.parent / "fixtures" / "pdfs" / "103P3-E34-QCI-40098_Ver1.pdf"


@pytest.fixture
def corrupted_pdf_path():
    """Path to corrupted PDF file for error testing."""
    return Path(__file__).parent.parent / "fixtures" / "pdfs" / "corrupted.pdf"


def wait_for_job_completion(dynamodb_table, job_id: str, timeout: int = 120) -> dict[str, Any]:
    """Wait for a job to complete in DynamoDB.

    Args:
        dynamodb_table: DynamoDB table resource
        job_id: Job ID to monitor
        timeout: Maximum time to wait in seconds

    Returns:
        Final job status

    Raises:
        TimeoutError: If job doesn't complete within timeout
    """
    start_time = time.time()
    env = os.environ.get("ENV", "dev")
    table_name = os.environ.get("DYNAMODB_TABLE")
    if not table_name:
        table_name = "security-assistant-dev-jobs" if env == "dev" else "security-assistant-jobs"
    table = dynamodb_table.Table(table_name)

    while time.time() - start_time < timeout:
        try:
            response = table.get_item(Key={"company#client#job": f"7central#test_client#{job_id}"})

            if "Item" in response:
                job = response["Item"]
                status = job.get("status", "unknown")

                if status in ["completed", "failed", "error"]:
                    return job

            time.sleep(2)  # Poll every 2 seconds

        except Exception as e:
            print(f"Error checking job status: {e}")
            time.sleep(2)

    raise TimeoutError(f"Job {job_id} did not complete within {timeout} seconds")


def upload_test_file(s3_client, bucket: str, key: str, file_path: Path) -> str:
    """Upload a test file to S3.

    Args:
        s3_client: S3 client
        bucket: S3 bucket name
        key: S3 object key
        file_path: Local file path

    Returns:
        S3 URI of uploaded file
    """
    with open(file_path, "rb") as f:
        s3_client.put_object(Bucket=bucket, Key=key, Body=f.read(), ContentType="application/pdf")

    return f"s3://{bucket}/{key}"


def cleanup_s3_files(s3_client, bucket: str, prefix: str):
    """Clean up test files from S3.

    Args:
        s3_client: S3 client
        bucket: S3 bucket name
        prefix: S3 key prefix to delete
    """
    try:
        response = s3_client.list_objects_v2(Bucket=bucket, Prefix=prefix)

        if "Contents" in response:
            objects = [{"Key": obj["Key"]} for obj in response["Contents"]]
            s3_client.delete_objects(Bucket=bucket, Delete={"Objects": objects})
    except Exception as e:
        print(f"Error cleaning up S3 files: {e}")


@pytest.fixture
def e2e_job_helper(aws_clients):
    """Helper fixture for E2E job operations."""

    class JobHelper:
        def __init__(self):
            self.s3 = aws_clients["s3"]
            self.dynamodb = aws_clients["dynamodb"]
            env = os.environ.get("ENV", "dev")

            # S3 bucket with environment-based defaults
            self.bucket = os.environ.get("S3_BUCKET")
            if not self.bucket:
                self.bucket = "security-assistant-dev-445567098699" if env == "dev" else "security-assistant-files"

            # DynamoDB table with environment-based defaults
            self.table_name = os.environ.get("DYNAMODB_TABLE")
            if not self.table_name:
                self.table_name = "security-assistant-dev-jobs" if env == "dev" else "security-assistant-jobs"

        def upload_pdf(self, job_id: str, pdf_path: Path) -> str:
            """Upload PDF for testing."""
            key = f"7central/test_client/{job_id}/input.pdf"
            return upload_test_file(self.s3, self.bucket, key, pdf_path)

        def wait_for_completion(self, job_id: str, timeout: int = 120) -> dict:
            """Wait for job to complete."""
            return wait_for_job_completion(self.dynamodb, job_id, timeout)

        def cleanup(self, job_id: str):
            """Clean up job files."""
            prefix = f"7central/test_client/{job_id}/"
            cleanup_s3_files(self.s3, self.bucket, prefix)

    return JobHelper()
