from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

from src.utils.env_cache import cached_getenv, get_static_config

load_dotenv()


class Settings:
    """Settings class with environment variable caching for Lambda optimization."""

    @property
    def ENV(self) -> str:
        """Environment: local, dev, or prod"""
        return cached_getenv("ENV", "local")

    @property
    def STORAGE_MODE(self) -> str:
        return cached_getenv("STORAGE_MODE", "local")

    @property
    def LOCAL_OUTPUT_DIR(self) -> str:
        return cached_getenv("LOCAL_OUTPUT_DIR", "./local_output")

    # AWS settings with caching and environment-based defaults
    @property
    def S3_BUCKET(self) -> str:
        # Check for explicit override first
        explicit_bucket = cached_getenv("S3_BUCKET")
        if explicit_bucket:
            return explicit_bucket

        # Otherwise, use environment-based defaults
        env = self.ENV
        if env == "dev":
            return "security-assistant-dev-445567098699"
        elif env == "prod":
            return "security-assistant-files"
        else:
            # Local environment doesn't need a bucket
            return "local-bucket-not-used"

    @property
    def DYNAMODB_TABLE(self) -> str:
        # Check for explicit override first
        explicit_table = cached_getenv("DYNAMODB_TABLE")
        if explicit_table:
            return explicit_table

        # Otherwise, use environment-based defaults
        env = self.ENV
        if env == "dev":
            return "security-assistant-dev-jobs"
        elif env == "prod":
            return "security-assistant-jobs"
        else:
            # Local environment doesn't need a table
            return "local-table-not-used"

    @property
    def SQS_QUEUE_URL(self) -> Optional[str]:
        return cached_getenv("SQS_QUEUE_URL")

    # Google GenAI settings with caching
    @property
    def GEMINI_API_KEY(self) -> Optional[str]:
        return cached_getenv("GEMINI_API_KEY")

    # Static configuration (no caching needed as these don't change)
    GEMINI_MODEL: str = "models/gemini-2.5-pro"
    GEMINI_FLASH_MODEL: str = "models/gemini-2.5-flash"
    GEMINI_TOKEN_LIMIT: int = 32000  # 32K token limit for Gemini 2.5 Pro
    GEMINI_TOKEN_THRESHOLD: float = 0.5  # Process pages individually at 50% of limit

    # AWS Lambda static configuration
    @property
    def AWS_REGION(self) -> str:
        return get_static_config('aws_region') or 'us-east-1'

    @property
    def FUNCTION_NAME(self) -> Optional[str]:
        return get_static_config('function_name')

    @property
    def MEMORY_SIZE(self) -> Optional[str]:
        return get_static_config('memory_size')

    @property
    def ARCHITECTURE(self) -> str:
        return get_static_config('architecture') or 'arm64'

    @property
    def local_output_path(self) -> Path:
        return Path(self.LOCAL_OUTPUT_DIR).absolute()


settings = Settings()
