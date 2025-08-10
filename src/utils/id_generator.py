from datetime import datetime


def generate_job_id() -> str:
    """
    Generate a unique job ID based on timestamp.

    Returns:
        Job ID in format: job_YYYYMMDDHHMMSSMMM
    """
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S%f")[:-3]
    return f"job_{timestamp}"
