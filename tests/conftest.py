import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import boto3
import pytest
from fastapi.testclient import TestClient
from moto import mock_dynamodb, mock_s3, mock_sqs

from src.api.main import app


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def temp_output_dir() -> Generator[Path, None, None]:
    """Create a temporary output directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir, patch.dict(os.environ, {"LOCAL_OUTPUT_DIR": temp_dir}):
        yield Path(temp_dir)


@pytest.fixture
def sample_pdf_content() -> bytes:
    """Create sample PDF content for testing."""
    # Minimal valid PDF structure
    pdf_content = b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] >>
endobj
xref
0 4
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
trailer
<< /Size 4 /Root 1 0 R >>
startxref
190
%%EOF"""
    return pdf_content


@pytest.fixture
def invalid_pdf_content() -> bytes:
    """Create invalid PDF content for testing."""
    return b"This is not a valid PDF file"


@pytest.fixture
def large_pdf_content() -> bytes:
    """Create PDF content that exceeds size limit."""
    # Start with valid PDF header
    content = b"%PDF-1.4\n"
    # Add padding to exceed 100MB
    padding_size = 101 * 1024 * 1024  # 101MB
    content += b"0" * padding_size
    return content


@pytest.fixture
def mock_aws_credentials():
    """Mock AWS credentials for testing."""
    with patch.dict(
        os.environ,
        {
            "AWS_ACCESS_KEY_ID": "testing",
            "AWS_SECRET_ACCESS_KEY": "testing",
            "AWS_SECURITY_TOKEN": "testing",
            "AWS_SESSION_TOKEN": "testing",
            "AWS_DEFAULT_REGION": "us-east-1",
        },
    ):
        yield


@pytest.fixture
def mock_dynamodb_table(mock_aws_credentials):
    """Create a mocked DynamoDB table for testing."""
    with mock_dynamodb():
        dynamodb = boto3.resource("dynamodb", region_name="us-east-1")
        table = dynamodb.create_table(
            TableName="test-jobs-table",
            KeySchema=[{"AttributeName": "company#client#job", "KeyType": "HASH"}],
            AttributeDefinitions=[
                {"AttributeName": "company#client#job", "AttributeType": "S"},
                {"AttributeName": "status", "AttributeType": "S"},
                {"AttributeName": "created_at", "AttributeType": "S"},
                {"AttributeName": "client_name", "AttributeType": "S"},
                {"AttributeName": "date_bucket", "AttributeType": "S"},
            ],
            GlobalSecondaryIndexes=[
                {
                    "IndexName": "StatusDateIndex",
                    "KeySchema": [
                        {"AttributeName": "status", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
                {
                    "IndexName": "ClientProjectIndex",
                    "KeySchema": [
                        {"AttributeName": "client_name", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
                {
                    "IndexName": "DateRangeIndex",
                    "KeySchema": [
                        {"AttributeName": "date_bucket", "KeyType": "HASH"},
                        {"AttributeName": "created_at", "KeyType": "RANGE"},
                    ],
                    "Projection": {"ProjectionType": "ALL"},
                    "ProvisionedThroughput": {"ReadCapacityUnits": 5, "WriteCapacityUnits": 5},
                },
            ],
            BillingMode="PROVISIONED",
            ProvisionedThroughput={"ReadCapacityUnits": 10, "WriteCapacityUnits": 10},
        )
        yield table


@pytest.fixture
def mock_s3_bucket(mock_aws_credentials):
    """Create a mocked S3 bucket for testing."""
    with mock_s3():
        s3_client = boto3.client("s3", region_name="us-east-1")
        s3_client.create_bucket(Bucket="test-bucket")
        yield s3_client


@pytest.fixture
def mock_sqs_queue(mock_aws_credentials):
    """Create a mocked SQS queue for testing."""
    with mock_sqs():
        sqs_client = boto3.client("sqs", region_name="us-east-1")
        queue_url = sqs_client.create_queue(QueueName="test-queue")["QueueUrl"]
        yield {"client": sqs_client, "queue_url": queue_url}
