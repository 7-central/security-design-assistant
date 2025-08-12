"""Base Agent V2 with Google GenAI SDK and lazy loading optimization."""
import json
import logging
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, Optional

# Lazy loading imports - only import when needed
from src.config.settings import settings
from src.storage.interface import StorageInterface

logger = logging.getLogger(__name__)


class BaseAgentV2(ABC):
    """Base class for all AI agents using Google GenAI SDK."""

    def __init__(self, storage: StorageInterface, job: Any):
        """Initialize the base agent with storage interface and job.

        Args:
            storage: Storage interface for file operations
            job: Job instance being processed
        """
        self.storage = storage
        self.job = job
        self.agent_name = self.__class__.__name__
        self._client = None  # Lazy load client only when needed

    @property
    def client(self):
        """Lazy-loaded GenAI client."""
        if self._client is None:
            self._client = self._initialize_client()
        return self._client

    def _initialize_client(self):
        """Initialize the Google GenAI client with lazy loading.

        Returns:
            Configured GenAI client

        Raises:
            ValueError: If GEMINI_API_KEY is not set
        """
        # Import only when needed to reduce cold start time
        from google import genai
        from google.genai import types

        if not settings.GEMINI_API_KEY:
            raise ValueError(
                "GEMINI_API_KEY environment variable is required. "
                "Get your API key from https://aistudio.google.com/app/apikey"
            )

        return genai.Client(api_key=settings.GEMINI_API_KEY)

    @abstractmethod
    async def process(self, input_data: dict[str, Any]) -> dict[str, Any]:
        """Process the job with the given input data.

        Args:
            input_data: Input data for processing

        Returns:
            Processing results
        """
        pass

    async def save_checkpoint(
        self,
        stage: str,
        data: dict[str, Any]
    ) -> str:
        """Save a checkpoint for the current processing stage.

        Args:
            stage: Processing stage name
            data: Data to checkpoint

        Returns:
            Checkpoint file key
        """
        checkpoint_key = f"{self.job.client_name}/{self.job.project_name}/job_{self.job.job_id}/checkpoint_{stage}_v1.json"

        checkpoint_data = {
            "job_id": self.job.job_id,
            "stage": stage,
            "agent": self.agent_name,
            "timestamp": datetime.utcnow().isoformat(),
            "data": data
        }

        content = json.dumps(checkpoint_data, indent=2).encode('utf-8')
        await self.storage.save_file(checkpoint_key, content)
        logger.info(f"Saved checkpoint for job {self.job.job_id} at stage {stage}")
        return checkpoint_key

    async def load_checkpoint(
        self,
        stage: str
    ) -> Optional[dict[str, Any]]:
        """Load a checkpoint for a specific stage.

        Args:
            stage: Processing stage name

        Returns:
            Checkpoint data if exists, None otherwise
        """
        checkpoint_key = f"{self.job.client_name}/{self.job.project_name}/job_{self.job.job_id}/checkpoint_{stage}_v1.json"

        try:
            if await self.storage.file_exists(checkpoint_key):
                content = await self.storage.get_file(checkpoint_key)
                checkpoint_data = json.loads(content.decode('utf-8'))
                logger.info(f"Loaded checkpoint for job {self.job.job_id} at stage {stage}")
                return checkpoint_data.get("data")
        except Exception as e:
            logger.error(f"Failed to load checkpoint for job {self.job.job_id}: {e}")

        return None

    def upload_file(self, file_path: str):
        """Upload a file to Google GenAI for processing.

        Args:
            file_path: Path to the file to upload

        Returns:
            Uploaded file object
        """
        logger.info(f"Uploading file: {file_path}")
        # Use pathlib.Path for better compatibility
        uploaded_file = self.client.files.upload(path=str(file_path))
        logger.info(f"File uploaded successfully: {uploaded_file.name}")
        return uploaded_file

    def generate_content(
        self,
        model_name: str,
        contents: list[Any],
        generation_config: Optional[dict[str, Any]] = None
    ):
        """Generate content using the specified model.

        Args:
            model_name: Name of the model to use
            contents: Content to process (text, files, etc.)
            generation_config: Optional generation configuration

        Returns:
            Generated content response
        """
        config = generation_config or {
            "temperature": 0.1,
            "top_p": 0.95,
            "max_output_tokens": 8192,
        }

        response = self.client.models.generate_content(
            model=model_name,
            contents=contents,
            config=types.GenerateContentConfig(**config)
        )

        return response

    async def _generate_with_retry(
        self,
        prompt: str | list[Any],
        model_name: Optional[str] = None
    ):
        """Generate content with retry logic (compatibility method).

        Args:
            prompt: Text prompt or list of content parts
            model_name: Optional model name override

        Returns:
            Generated content response
        """
        # Use default model if not specified
        if model_name is None:
            model_name = settings.GEMINI_MODEL

        # If prompt is a string, wrap it in proper format
        if isinstance(prompt, str):
            contents = [prompt]
        else:
            contents = prompt

        # The GenAI SDK has built-in retry logic
        return self.generate_content(
            model_name=model_name,
            contents=contents
        )

    def handle_error(self, error: Exception) -> dict[str, Any]:
        """Handle common errors with appropriate responses.

        Args:
            error: The exception that occurred

        Returns:
            Error information dict
        """
        error_info = {
            "error": str(error),
            "type": type(error).__name__
        }

        # Map common errors to user-friendly messages
        if "API_KEY_INVALID" in str(error):
            error_info["message"] = "Invalid API key. Please check your GEMINI_API_KEY."
            error_info["status_code"] = 401
        elif "RATE_LIMIT_EXCEEDED" in str(error):
            error_info["message"] = "Rate limit exceeded. Please try again later."
            error_info["status_code"] = 429
        elif "RESOURCE_EXHAUSTED" in str(error):
            error_info["message"] = "Token limit exceeded. Please reduce input size."
            error_info["status_code"] = 413
        else:
            error_info["message"] = "An unexpected error occurred during processing."
            error_info["status_code"] = 500

        logger.error(f"Error in agent processing: {error_info}")
        return error_info

    def estimate_tokens(self, text: str) -> int:
        """Estimate token count for text.

        Args:
            text: Text to estimate tokens for

        Returns:
            Estimated token count
        """
        # Rough estimation: ~4 characters per token
        return len(text) // 4

    def estimate_pdf_tokens(self, num_pages: int) -> int:
        """Estimate token count for PDF pages.

        Args:
            num_pages: Number of PDF pages

        Returns:
            Estimated token count
        """
        # Each PDF page is approximately 258 tokens
        return num_pages * 258

    def log_structured(self, level: str, message: str, **kwargs: Any) -> None:
        """Log structured data with agent context.

        Args:
            level: Log level (info, warning, error)
            message: Log message
            **kwargs: Additional structured data
        """
        extra_data = {
            "job_id": self.job.job_id,
            "agent": self.agent_name,
            "client": self.job.client_name,
            "project": self.job.project_name,
            **kwargs
        }

        getattr(logger, level)(message, extra=extra_data)
