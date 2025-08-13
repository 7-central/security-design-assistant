import json
import tempfile
from pathlib import Path

import pytest

from src.storage.local_storage import LocalStorage


@pytest.fixture
def local_storage(temp_output_dir: Path) -> LocalStorage:
    """Create LocalStorage instance with temporary directory."""
    from src.utils.env_cache import get_env_cache

    # Clear the environment cache to pick up the patched values
    get_env_cache().clear_cache()

    # Ensure clean state - delete jobs.json if it exists
    jobs_file = temp_output_dir / "jobs.json"
    if jobs_file.exists():
        jobs_file.unlink()

    storage = LocalStorage()

    # Verify we're using the temp directory
    assert str(storage.base_path) == str(temp_output_dir)

    return storage


@pytest.mark.unit
class TestLocalStorage:
    @pytest.mark.asyncio
    async def test_save_and_get_file(self, local_storage: LocalStorage) -> None:
        key = "test/file.pdf"
        content = b"test content"

        # Save file
        path = await local_storage.save_file(key, content)
        assert Path(path).exists()

        # Get file
        retrieved_content = await local_storage.get_file(key)
        assert retrieved_content == content

    @pytest.mark.asyncio
    async def test_save_file_with_metadata(self, local_storage: LocalStorage) -> None:
        key = "test/file.pdf"
        content = b"test content"
        metadata = {"client": "TestClient", "project": "TestProject"}

        # Save file with metadata
        path = await local_storage.save_file(key, content, metadata)

        # Check metadata file exists
        metadata_path = Path(path).with_suffix(".pdf.metadata.json")
        assert metadata_path.exists()

        # Verify metadata content
        saved_metadata = json.loads(metadata_path.read_text())
        assert saved_metadata == metadata

    @pytest.mark.asyncio
    async def test_file_exists(self, local_storage: LocalStorage) -> None:
        key = "nonexistent/file.pdf"

        # Check non-existent file
        exists = await local_storage.file_exists(key)
        assert exists is False

        # Save file
        key = "test/file.pdf"
        await local_storage.save_file(key, b"content")

        # Check existing file
        exists = await local_storage.file_exists(key)
        assert exists is True

        # Check non-existent file in same dir
        exists = await local_storage.file_exists("test/other.pdf")
        assert exists is False

    @pytest.mark.asyncio
    async def test_delete_file(self, local_storage: LocalStorage) -> None:
        key = "test/file.pdf"
        content = b"test content"
        metadata = {"test": "data"}

        # Save file with metadata
        await local_storage.save_file(key, content, metadata)

        # Delete file
        deleted = await local_storage.delete_file(key)
        assert deleted is True

        # Verify file and metadata are deleted
        exists = await local_storage.file_exists(key)
        assert exists is False

        # Try to delete non-existent file
        deleted = await local_storage.delete_file(key)
        assert deleted is False

    @pytest.mark.asyncio
    async def test_get_non_existent_file(self, local_storage: LocalStorage) -> None:
        with pytest.raises(FileNotFoundError, match="File not found"):
            await local_storage.get_file("non/existent/file.pdf")

    @pytest.mark.asyncio
    async def test_save_and_get_job_status(self, local_storage: LocalStorage) -> None:
        job_id = "job_123"
        status_data = {"status": "processing", "created_at": "2024-01-01T00:00:00", "client_name": "TestClient"}

        # Save job status
        await local_storage.save_job_status(job_id, status_data)

        # Get job status
        retrieved_status = await local_storage.get_job_status(job_id)
        assert retrieved_status == status_data

    @pytest.mark.asyncio
    async def test_get_non_existent_job_status(self, local_storage: LocalStorage) -> None:
        status = await local_storage.get_job_status("non_existent_job")
        assert status is None

    def test_ensure_directories_creates_structure(self, local_storage: LocalStorage) -> None:
        # Check base directory exists
        assert local_storage.base_path.exists()
        assert local_storage.base_path.is_dir()

        # Check jobs file exists and is empty
        assert local_storage.jobs_file.exists()
        assert local_storage.jobs_file.read_text() == "{}"

    def test_ensure_directories_permission_error(self) -> None:
        import os
        from unittest.mock import patch

        from src.utils.env_cache import get_env_cache

        # Create a read-only directory
        with tempfile.TemporaryDirectory() as temp_dir:
            test_dir = Path(temp_dir) / "readonly"
            test_dir.mkdir()
            test_dir.chmod(0o444)

            # Mock the environment variable for LOCAL_OUTPUT_DIR
            try:
                with patch.dict(os.environ, {"LOCAL_OUTPUT_DIR": str(test_dir / "output")}):
                    # Clear the environment cache to pick up the patched value
                    get_env_cache().clear_cache()
                    with pytest.raises(PermissionError):
                        LocalStorage()
            finally:
                test_dir.chmod(0o755)  # Restore permissions for cleanup
                # Clear cache again to reset for next tests
                get_env_cache().clear_cache()
