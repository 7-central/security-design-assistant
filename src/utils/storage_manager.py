"""Storage manager implementation."""
import logging

from src.config.settings import settings
from src.storage.aws_storage import AWSStorage
from src.storage.interface import StorageInterface
from src.storage.local_storage import LocalStorage

logger = logging.getLogger(__name__)


class StorageManager:
    """Factory for creating storage instances based on configuration."""

    @staticmethod
    def get_storage() -> StorageInterface:
        """Get appropriate storage implementation based on settings.

        Returns:
            StorageInterface implementation (LocalStorage or AWSStorage)
        """
        storage_mode = settings.storage_mode

        if storage_mode == "local":
            logger.info("Using local file system storage")
            return LocalStorage()
        elif storage_mode == "aws":
            logger.info("Using AWS S3/DynamoDB storage")
            return AWSStorage()
        else:
            raise ValueError(f"Unknown storage mode: {storage_mode}")


async def save_file(path: str, content: bytes) -> str:
    """Convenience function to save a file using configured storage.

    Args:
        path: File path/key
        content: File content as bytes

    Returns:
        Storage path or URL
    """
    storage = StorageManager.get_storage()
    return await storage.save_file(path, content)


async def get_file(path: str) -> bytes:
    """Convenience function to get a file using configured storage.

    Args:
        path: File path/key

    Returns:
        File content as bytes
    """
    storage = StorageManager.get_storage()
    return await storage.get_file(path)


async def generate_download_url(path: str) -> str:
    """Generate a download URL for the file.

    Args:
        path: File path/key

    Returns:
        Download URL (presigned for S3, local path for filesystem)
    """
    storage = StorageManager.get_storage()

    if hasattr(storage, 'generate_presigned_url'):
        return await storage.generate_presigned_url(path)
    else:
        return f"/download/{path}"
