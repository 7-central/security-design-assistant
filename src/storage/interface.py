from abc import ABC, abstractmethod
from typing import Any


class StorageInterface(ABC):
    """Abstract interface for storage operations."""

    @abstractmethod
    async def save_file(self, key: str, content: bytes, metadata: dict[str, Any] | None = None) -> str:
        """
        Save a file to storage.

        Args:
            key: Unique identifier for the file
            content: File content as bytes
            metadata: Optional metadata to store with the file

        Returns:
            Storage path or URL
        """
        pass

    @abstractmethod
    async def get_file(self, key: str) -> bytes:
        """
        Retrieve a file from storage.

        Args:
            key: Unique identifier for the file

        Returns:
            File content as bytes
        """
        pass

    @abstractmethod
    async def file_exists(self, key: str) -> bool:
        """
        Check if a file exists in storage.

        Args:
            key: Unique identifier for the file

        Returns:
            True if file exists, False otherwise
        """
        pass

    @abstractmethod
    async def delete_file(self, key: str) -> bool:
        """
        Delete a file from storage.

        Args:
            key: Unique identifier for the file

        Returns:
            True if file was deleted, False otherwise
        """
        pass

    @abstractmethod
    async def save_job_status(self, job_id: str, status_data: dict[str, Any]) -> None:
        """
        Save job status information.

        Args:
            job_id: Unique job identifier
            status_data: Job status data to store
        """
        pass

    @abstractmethod
    async def get_job_status(self, job_id: str) -> dict[str, Any] | None:
        """
        Retrieve job status information.

        Args:
            job_id: Unique job identifier

        Returns:
            Job status data if found, None otherwise
        """
        pass

    async def generate_presigned_url(self, key: str, expiration: int = 3600) -> str:
        """
        Generate a presigned URL for file access (optional implementation).

        Args:
            key: File key/path
            expiration: URL expiration time in seconds (default: 1 hour)

        Returns:
            Presigned URL for file access
        """
        # Default implementation returns the key as-is for local storage
        return key
