import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()


class Settings:
    STORAGE_MODE: str = os.getenv("STORAGE_MODE", "local")
    LOCAL_OUTPUT_DIR: str = os.getenv("LOCAL_OUTPUT_DIR", "./local_output")
    
    # AWS settings
    S3_BUCKET: str = os.getenv("S3_BUCKET", "security-assistant-files")
    DYNAMODB_TABLE: str = os.getenv("DYNAMODB_TABLE", "security-assistant-jobs")
    SQS_QUEUE_URL: str | None = os.getenv("SQS_QUEUE_URL")
    
    # Google GenAI settings
    GEMINI_API_KEY: str | None = os.getenv("GEMINI_API_KEY")
    
    # Gemini model settings
    GEMINI_MODEL: str = "models/gemini-2.5-pro"
    GEMINI_FLASH_MODEL: str = "models/gemini-2.5-flash"
    GEMINI_TOKEN_LIMIT: int = 32000  # 32K token limit for Gemini 2.5 Pro
    GEMINI_TOKEN_THRESHOLD: float = 0.5  # Process pages individually at 50% of limit

    @property
    def local_output_path(self) -> Path:
        return Path(self.LOCAL_OUTPUT_DIR).absolute()


settings = Settings()
