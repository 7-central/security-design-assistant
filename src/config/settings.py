from pathlib import Path

from dotenv import load_dotenv

from src.utils.env_cache import cached_getenv, get_static_config

load_dotenv()


class Settings:
    """Settings class with environment variable caching for Lambda optimization."""

    @property
    def env(self) -> str:
        """Environment: local, dev, or prod"""
        return str(cached_getenv("ENV", "local"))

    @property
    def storage_mode(self) -> str:
        return str(cached_getenv("STORAGE_MODE", "local"))

    @property
    def local_output_dir(self) -> str:
        return str(cached_getenv("LOCAL_OUTPUT_DIR", "./local_output"))

    # AWS settings with caching and environment-based defaults
    @property
    def s3_bucket(self) -> str:
        # Check for explicit override first
        explicit_bucket = cached_getenv("S3_BUCKET")
        if explicit_bucket:
            return str(explicit_bucket)

        # Otherwise, use environment-based defaults
        env = self.env
        if env == "dev":
            return "security-assistant-dev-445567098699"
        elif env == "prod":
            return "security-assistant-files"
        else:
            # Local environment doesn't need a bucket
            return "local-bucket-not-used"

    @property
    def dynamodb_table(self) -> str:
        # Check for explicit override first
        explicit_table = cached_getenv("DYNAMODB_TABLE")
        if explicit_table:
            return str(explicit_table)

        # Otherwise, use environment-based defaults
        env = self.env
        if env == "dev":
            return "security-assistant-dev-jobs"
        elif env == "prod":
            return "security-assistant-jobs"
        else:
            # Local environment doesn't need a table
            return "local-table-not-used"

    @property
    def sqs_queue_url(self) -> str | None:
        result = cached_getenv("SQS_QUEUE_URL")
        return str(result) if result is not None else None

    # Google GenAI settings with caching
    @property
    def gemini_api_key(self) -> str | None:
        result = cached_getenv("GEMINI_API_KEY")
        return str(result) if result is not None else None

    # Static configuration (no caching needed as these don't change)
    gemini_model: str = "models/gemini-2.5-pro"
    gemini_flash_model: str = "models/gemini-2.5-flash"
    gemini_token_limit: int = 32000  # 32K token limit for Gemini 2.5 Pro
    gemini_token_threshold: float = 0.5  # Process pages individually at 50% of limit

    # AWS Lambda static configuration
    @property
    def aws_region(self) -> str:
        return get_static_config("aws_region") or "us-east-1"

    @property
    def function_name(self) -> str | None:
        return get_static_config("function_name")

    @property
    def memory_size(self) -> str | None:
        return get_static_config("memory_size")

    @property
    def architecture(self) -> str:
        return get_static_config("architecture") or "arm64"

    @property
    def local_output_path(self) -> Path:
        return Path(self.local_output_dir).absolute()


settings = Settings()
