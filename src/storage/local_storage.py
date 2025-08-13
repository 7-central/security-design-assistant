import json
from typing import Any

from src.config.settings import settings
from src.storage.interface import StorageInterface


class LocalStorage(StorageInterface):
    """Local file system implementation of storage interface."""

    def __init__(self) -> None:
        self.base_path = settings.local_output_path
        self.jobs_file = self.base_path / "jobs.json"
        self._ensure_directories()

    def _ensure_directories(self) -> None:
        """Ensure required directories exist with proper permissions."""
        self.base_path.mkdir(parents=True, exist_ok=True)

        # Verify write permissions
        test_file = self.base_path / ".write_test"
        try:
            test_file.touch()
            test_file.unlink()
        except Exception as e:
            raise PermissionError(f"Cannot write to output directory {self.base_path}: {e}") from e

        # Ensure jobs file exists
        if not self.jobs_file.exists():
            self.jobs_file.write_text("{}")

    async def save_file(self, key: str, content: bytes, metadata: dict[str, Any] | None = None) -> str:
        """Save a file to local storage."""
        file_path = self.base_path / key
        file_path.parent.mkdir(parents=True, exist_ok=True)

        file_path.write_bytes(content)

        if metadata:
            metadata_path = file_path.with_suffix(file_path.suffix + ".metadata.json")
            metadata_path.write_text(json.dumps(metadata, indent=2))

        return str(file_path)

    async def get_file(self, key: str) -> bytes:
        """Retrieve a file from local storage."""
        file_path = self.base_path / key

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {key}")

        return file_path.read_bytes()

    async def file_exists(self, key: str) -> bool:
        """Check if a file exists in local storage."""
        file_path = self.base_path / key
        return file_path.exists()

    async def delete_file(self, key: str) -> bool:
        """Delete a file from local storage."""
        file_path = self.base_path / key

        if file_path.exists():
            file_path.unlink()

            # Also delete metadata if exists
            metadata_path = file_path.with_suffix(file_path.suffix + ".metadata.json")
            if metadata_path.exists():
                metadata_path.unlink()

            return True

        return False

    async def save_job_status(self, job_id: str, status_data: dict[str, Any]) -> None:
        """Save job status to local JSON file."""
        jobs_data = {}

        if self.jobs_file.exists():
            try:
                jobs_data = json.loads(self.jobs_file.read_text())
            except json.JSONDecodeError:
                jobs_data = {}

        jobs_data[job_id] = status_data

        self.jobs_file.write_text(json.dumps(jobs_data, indent=2))

    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """Retrieve job status from local JSON file."""
        if not self.jobs_file.exists():
            return None

        try:
            jobs_data = json.loads(self.jobs_file.read_text())
            result = jobs_data.get(job_id)
            return result if result is not None else None
        except json.JSONDecodeError:
            return None

    async def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """Return local file path for local storage."""
        return str(self.base_path / key)
