import tempfile
from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from src.api.main import app
from src.config.settings import settings


@pytest.fixture
def test_client() -> TestClient:
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def temp_output_dir() -> Generator[Path, None, None]:
    """Create a temporary output directory for testing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        original_dir = settings.LOCAL_OUTPUT_DIR
        settings.LOCAL_OUTPUT_DIR = temp_dir
        yield Path(temp_dir)
        settings.LOCAL_OUTPUT_DIR = original_dir


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
