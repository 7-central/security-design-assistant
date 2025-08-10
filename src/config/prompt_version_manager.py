"""Prompt version management for iterative prompt optimization."""
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


class PromptVersionManager:
    """Manages prompt versions for schedule extraction optimization."""

    def __init__(self, base_path: Path | None = None):
        """Initialize prompt version manager.

        Args:
            base_path: Base path for prompts directory. Defaults to src/config/prompts
        """
        if base_path is None:
            base_path = Path(__file__).parent / "prompts"

        self.base_path = base_path
        self.versions_dir = base_path / "versions"
        self.versions_dir.mkdir(parents=True, exist_ok=True)
        self.version_metadata_file = self.versions_dir / "version_metadata.json"
        self._ensure_metadata_file()

    def _ensure_metadata_file(self) -> None:
        """Ensure version metadata file exists."""
        if not self.version_metadata_file.exists():
            initial_metadata = {
                "current_version": 1,
                "versions": {
                    "1": {
                        "created_at": datetime.utcnow().isoformat(),
                        "description": "Baseline prompt",
                        "changes": [],
                        "performance": {}
                    }
                }
            }
            self.version_metadata_file.write_text(json.dumps(initial_metadata, indent=2))

    def get_current_version(self) -> int:
        """Get the current active prompt version number.

        Returns:
            Current version number
        """
        metadata = self._load_metadata()
        return metadata.get("current_version", 1)

    def load_prompt(self, version: int | None = None) -> str:
        """Load a specific prompt version or the latest.

        Args:
            version: Version number to load. If None, loads current version.

        Returns:
            Prompt content

        Raises:
            FileNotFoundError: If requested version doesn't exist
        """
        if version is None:
            version = self.get_current_version()

        prompt_file = self.versions_dir / f"schedule_prompt_v{version}.txt"

        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt version {version} not found at {prompt_file}")

        logger.info(f"Loading prompt version {version}")
        return prompt_file.read_text()

    def create_new_version(self, base_version: int | None, changes: list[str]) -> int:
        """Create a new prompt version with documented changes.

        Args:
            base_version: Version to base new version on. If None, uses current.
            changes: List of changes made in this version

        Returns:
            New version number
        """
        if base_version is None:
            base_version = self.get_current_version()

        # Load base prompt
        base_prompt = self.load_prompt(base_version)

        # Get next version number
        metadata = self._load_metadata()
        existing_versions = [int(v) for v in metadata["versions"]]
        new_version = max(existing_versions) + 1

        # Save new version
        new_prompt_file = self.versions_dir / f"schedule_prompt_v{new_version}.txt"
        new_prompt_file.write_text(base_prompt)

        # Update metadata
        metadata["versions"][str(new_version)] = {
            "created_at": datetime.utcnow().isoformat(),
            "base_version": base_version,
            "changes": changes,
            "performance": {}
        }
        self._save_metadata(metadata)

        logger.info(f"Created new prompt version {new_version} based on version {base_version}")
        logger.info(f"Changes: {', '.join(changes)}")

        return new_version

    def set_current_version(self, version: int) -> None:
        """Set the current active prompt version.

        Args:
            version: Version number to set as current

        Raises:
            ValueError: If version doesn't exist
        """
        metadata = self._load_metadata()

        if str(version) not in metadata["versions"]:
            raise ValueError(f"Version {version} doesn't exist")

        metadata["current_version"] = version
        self._save_metadata(metadata)

        # Also update the main schedule_prompt.txt to match current version
        current_prompt = self.load_prompt(version)
        main_prompt_file = self.base_path / "schedule_prompt.txt"
        main_prompt_file.write_text(current_prompt)

        logger.info(f"Set current prompt version to {version}")

    def record_performance(self, version: int, metrics: dict[str, Any]) -> None:
        """Record performance metrics for a specific version.

        Args:
            version: Version number
            metrics: Performance metrics (e.g., judge scores, accuracy)
        """
        metadata = self._load_metadata()

        if str(version) not in metadata["versions"]:
            raise ValueError(f"Version {version} doesn't exist")

        # Add timestamp to metrics
        metrics["evaluated_at"] = datetime.utcnow().isoformat()

        # Append to performance history
        if "performance" not in metadata["versions"][str(version)]:
            metadata["versions"][str(version)]["performance"] = {}

        # Store by timestamp to track multiple evaluations
        timestamp_key = datetime.utcnow().isoformat()
        metadata["versions"][str(version)]["performance"][timestamp_key] = metrics

        self._save_metadata(metadata)
        logger.info(f"Recorded performance metrics for version {version}")

    def get_version_history(self) -> dict[str, Any]:
        """Get complete version history with metadata.

        Returns:
            Dictionary with all version metadata
        """
        return self._load_metadata()

    def _load_metadata(self) -> dict[str, Any]:
        """Load version metadata from file."""
        if not self.version_metadata_file.exists():
            self._ensure_metadata_file()

        return json.loads(self.version_metadata_file.read_text())

    def _save_metadata(self, metadata: dict[str, Any]) -> None:
        """Save version metadata to file."""
        self.version_metadata_file.write_text(json.dumps(metadata, indent=2))

    def update_prompt_content(self, version: int, new_content: str) -> None:
        """Update the content of a specific prompt version.

        Args:
            version: Version number to update
            new_content: New prompt content
        """
        prompt_file = self.versions_dir / f"schedule_prompt_v{version}.txt"

        if not prompt_file.exists():
            raise FileNotFoundError(f"Prompt version {version} not found")

        prompt_file.write_text(new_content)

        # Update metadata with modification timestamp
        metadata = self._load_metadata()
        if str(version) in metadata["versions"]:
            metadata["versions"][str(version)]["modified_at"] = datetime.utcnow().isoformat()
            self._save_metadata(metadata)

        # If this is the current version, also update main prompt file
        if version == self.get_current_version():
            main_prompt_file = self.base_path / "schedule_prompt.txt"
            main_prompt_file.write_text(new_content)

        logger.info(f"Updated content for prompt version {version}")
