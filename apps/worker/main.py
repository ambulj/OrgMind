from typing import Any, cast
from urllib.parse import urlparse

from arq import run_worker
from arq.connections import RedisSettings
from orgmind.config import settings
from orgmind.ingest.worker import WorkerSettings, execute_ingestion_job_task


def get_redis_settings() -> RedisSettings:
    """Parses RedisSettings from configured settings.REDIS_JOBS_URL."""
    parsed = urlparse(settings.REDIS_JOBS_URL)
    return RedisSettings(
        host=parsed.hostname or "localhost",
        port=parsed.port or 6380,
        password=parsed.password,
    )


class ArqWorkerConfig(WorkerSettings):
    """Runtime arq configuration."""

    redis_settings: Any = get_redis_settings()
    functions = [execute_ingestion_job_task]


def main() -> None:
    """Starts the arq worker process."""
    print("=" * 60)
    print(" [OrgMind Ingestion Worker] Starting background worker...")
    print(f" Redis Queue URL: {settings.REDIS_JOBS_URL}")
    print(" Registered Tasks: ['execute_ingestion_job_task']")
    print("=" * 60)
    run_worker(cast(Any, ArqWorkerConfig))


if __name__ == "__main__":
    main()
