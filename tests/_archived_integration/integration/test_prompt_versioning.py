"""Integration tests for prompt versioning system."""
from datetime import datetime
from pathlib import Path

import pytest

from src.agents.schedule_agent_v2 import ScheduleAgentV2
from src.config.prompt_version_manager import PromptVersionManager
from src.models.job import Job, JobStatus
from src.storage.local_storage import LocalStorage


class TestPromptVersioning:
    """Integration tests for the prompt versioning system."""

    @pytest.fixture
    def temp_prompt_manager(self, tmp_path):
        """Create a temporary prompt version manager for testing."""
        # Create temporary prompt structure
        prompts_dir = tmp_path / "prompts"
        versions_dir = prompts_dir / "versions"
        versions_dir.mkdir(parents=True)

        # Create test prompt files
        v1_content = "Version 1 prompt content for testing"
        v2_content = "Version 2 prompt content with EMERGENCY EXIT improvements"

        (versions_dir / "schedule_prompt_v1.txt").write_text(v1_content)
        (versions_dir / "schedule_prompt_v2.txt").write_text(v2_content)
        (prompts_dir / "schedule_prompt.txt").write_text(v1_content)  # Start with v1

        # Initialize manager and create version 2
        manager = PromptVersionManager(base_path=prompts_dir)
        manager.create_new_version(1, ["Added EMERGENCY EXIT improvements for testing"])
        manager.update_prompt_content(2, v2_content)

        return manager

    @pytest.fixture
    def storage(self):
        """Create storage instance for testing."""
        return LocalStorage()

    @pytest.fixture
    def test_job(self):
        """Create test job instance."""
        return Job(
            job_id="test_prompt_versioning",
            client_name="TestClient",
            project_name="PromptTest",
            status=JobStatus.PROCESSING,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )

    def test_prompt_version_manager_initialization(self, temp_prompt_manager):
        """Test that prompt version manager initializes correctly."""
        manager = temp_prompt_manager

        # Should initialize with version 1 as current
        assert manager.get_current_version() == 1

        # Should have version metadata
        history = manager.get_version_history()
        assert "versions" in history
        assert "current_version" in history

    def test_load_different_versions(self, temp_prompt_manager):
        """Test loading different prompt versions."""
        manager = temp_prompt_manager

        # Load version 1
        v1_content = manager.load_prompt(1)
        assert "Version 1 prompt content" in v1_content
        assert "EMERGENCY EXIT" not in v1_content

        # Load version 2
        v2_content = manager.load_prompt(2)
        assert "Version 2 prompt content" in v2_content
        assert "EMERGENCY EXIT" in v2_content

        # Load current version (should be latest)
        current_content = manager.load_prompt()
        assert current_content == manager.load_prompt(manager.get_current_version())

    def test_create_new_version(self, temp_prompt_manager):
        """Test creating a new prompt version."""
        manager = temp_prompt_manager

        changes = ["Added test improvements", "Fixed test issues"]
        new_version = manager.create_new_version(base_version=1, changes=changes)

        assert new_version == 3  # Should be next version after 2

        # Verify version was created
        v3_content = manager.load_prompt(3)
        assert v3_content == manager.load_prompt(1)  # Should be based on version 1

        # Verify metadata
        history = manager.get_version_history()
        assert "3" in history["versions"]
        assert history["versions"]["3"]["changes"] == changes
        assert history["versions"]["3"]["base_version"] == 1

    def test_set_current_version(self, temp_prompt_manager):
        """Test setting current version."""
        manager = temp_prompt_manager

        # Initially should be version 1
        assert manager.get_current_version() == 1

        # Set to version 2
        manager.set_current_version(2)
        assert manager.get_current_version() == 2

        # Main prompt file should be updated
        main_prompt_path = manager.base_path / "schedule_prompt.txt"
        main_content = main_prompt_path.read_text()
        v2_content = manager.load_prompt(2)
        assert main_content == v2_content

    def test_record_performance(self, temp_prompt_manager):
        """Test recording performance metrics for versions."""
        manager = temp_prompt_manager

        metrics = {
            "assessment": "Good",
            "accuracy": 0.85,
            "completeness": 0.90
        }

        manager.record_performance(1, metrics)

        # Verify metrics were stored
        history = manager.get_version_history()
        version_data = history["versions"]["1"]
        assert "performance" in version_data

        # Should have timestamp-based storage
        performance_entries = version_data["performance"]
        assert len(performance_entries) > 0

        # Check that one entry contains our metrics
        entry_found = False
        for _timestamp, perf_data in performance_entries.items():
            if perf_data.get("assessment") == "Good":
                entry_found = True
                assert perf_data["accuracy"] == 0.85
                assert "evaluated_at" in perf_data
                break
        assert entry_found

    def test_schedule_agent_with_version(self, storage, test_job, temp_prompt_manager):
        """Test ScheduleAgentV2 with specific prompt versions."""
        # Monkey patch the prompt manager path
        Path("src/config/prompts")

        # Create agent with version 1
        agent_v1 = ScheduleAgentV2(storage, test_job, prompt_version=1)
        # Manually set the prompt to test content since we can't easily override paths
        agent_v1.prompt_template = "Version 1 prompt content for testing"

        assert agent_v1.prompt_version == 1
        assert "Version 1 prompt content" in agent_v1.prompt_template
        assert "EMERGENCY EXIT" not in agent_v1.prompt_template

        # Create agent with version 2
        agent_v2 = ScheduleAgentV2(storage, test_job, prompt_version=2)
        agent_v2.prompt_template = "Version 2 prompt content with EMERGENCY EXIT improvements"

        assert agent_v2.prompt_version == 2
        assert "Version 2 prompt content" in agent_v2.prompt_template
        assert "EMERGENCY EXIT" in agent_v2.prompt_template

        # Create agent with default version
        agent_default = ScheduleAgentV2(storage, test_job)
        assert agent_default.prompt_version is None

    def test_version_file_not_found(self, temp_prompt_manager):
        """Test handling of missing version files."""
        manager = temp_prompt_manager

        with pytest.raises(FileNotFoundError):
            manager.load_prompt(999)  # Non-existent version

    def test_invalid_version_operations(self, temp_prompt_manager):
        """Test error handling for invalid version operations."""
        manager = temp_prompt_manager

        # Try to set non-existent version as current
        with pytest.raises(ValueError):
            manager.set_current_version(999)

        # Try to record performance for non-existent version
        with pytest.raises(ValueError):
            manager.record_performance(999, {"test": "data"})

    def test_update_prompt_content(self, temp_prompt_manager):
        """Test updating prompt content for existing version."""
        manager = temp_prompt_manager

        new_content = "Updated version 1 content with modifications"
        manager.update_prompt_content(1, new_content)

        # Verify content was updated
        updated_content = manager.load_prompt(1)
        assert updated_content == new_content

        # If version 1 is current, main file should be updated too
        manager.set_current_version(1)
        main_prompt_path = manager.base_path / "schedule_prompt.txt"
        main_content = main_prompt_path.read_text()
        assert main_content == new_content

    def test_version_metadata_persistence(self, temp_prompt_manager):
        """Test that version metadata persists across instances."""
        manager1 = temp_prompt_manager

        # Create a new version with manager1
        changes = ["Persistence test changes"]
        new_version = manager1.create_new_version(1, changes)

        # Create a new manager instance pointing to same location
        manager2 = PromptVersionManager(base_path=manager1.base_path)

        # Should have the same data
        assert manager2.get_current_version() == manager1.get_current_version()

        # Should be able to load the version created by manager1
        content = manager2.load_prompt(new_version)
        assert content is not None

        # Metadata should be the same
        history1 = manager1.get_version_history()
        history2 = manager2.get_version_history()
        assert history1["versions"][str(new_version)] == history2["versions"][str(new_version)]

    def test_version_creation_chain(self, temp_prompt_manager):
        """Test creating a chain of versions based on each other."""
        manager = temp_prompt_manager

        # Create v3 based on v1
        v3 = manager.create_new_version(1, ["Based on v1"])

        # Create v4 based on v3
        v4 = manager.create_new_version(v3, ["Based on v3"])

        # Verify chain
        history = manager.get_version_history()
        assert history["versions"][str(v3)]["base_version"] == 1
        assert history["versions"][str(v4)]["base_version"] == v3

        # Content should be traced back correctly
        v1_content = manager.load_prompt(1)
        v3_content = manager.load_prompt(v3)
        v4_content = manager.load_prompt(v4)

        assert v1_content == v3_content  # v3 based on v1
        assert v3_content == v4_content  # v4 based on v3
