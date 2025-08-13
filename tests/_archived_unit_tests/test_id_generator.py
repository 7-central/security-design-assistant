import re
import time

from src.utils.id_generator import generate_job_id


class TestGenerateJobId:
    def test_job_id_format(self) -> None:
        job_id = generate_job_id()

        # Check format: job_YYYYMMDDHHMMSSMMM
        pattern = r"^job_\d{17}$"
        assert re.match(pattern, job_id) is not None
        assert job_id.startswith("job_")
        assert len(job_id) == 21  # "job_" (4) + 17 digits

    def test_job_id_uniqueness(self) -> None:
        job_ids = []

        # Generate multiple IDs quickly
        for _ in range(10):
            job_id = generate_job_id()
            job_ids.append(job_id)
            time.sleep(0.001)  # Small delay to ensure different timestamps

        # Check all IDs are unique
        assert len(job_ids) == len(set(job_ids))

    def test_job_id_timestamp_ordering(self) -> None:
        job_id1 = generate_job_id()
        time.sleep(0.01)  # Ensure different timestamps
        job_id2 = generate_job_id()

        # Later job ID should have a higher timestamp value
        timestamp1 = job_id1.replace("job_", "")
        timestamp2 = job_id2.replace("job_", "")
        assert timestamp2 > timestamp1
