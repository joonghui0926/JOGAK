from __future__ import annotations

from sqlalchemy.orm import Session

from jogak_api.core.config import get_settings
from jogak_api.db.models import GenerationJob


def create_generation_job(db: Session, *, job_type: str, payload: dict) -> GenerationJob:
    job = GenerationJob(type=job_type, payload_json=payload, progress=0, current_state="queued")
    db.add(job)
    db.commit()
    db.refresh(job)
    enqueue_generation_job(job.id)
    return job


def enqueue_generation_job(job_id: str) -> None:
    settings = get_settings()
    if settings.jogak_sync_jobs:
        from worker.tasks import run_generation_job

        run_generation_job(job_id)
        return

    try:
        from redis import Redis
        from rq import Queue

        queue = Queue("jogak-gpu", connection=Redis.from_url(settings.redis_url))
        queue.enqueue("worker.tasks.run_generation_job", job_id, job_timeout=60 * 60)
    except Exception:
        # Redis can be offline in local UI work. The job remains queued and can be run by worker later.
        return


def update_job(db: Session, job_id: str, *, state: str, progress: int, status: str = "running", result: dict | None = None, error: str | None = None) -> GenerationJob:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise ValueError(f"Job not found: {job_id}")
    job.current_state = state
    job.progress = progress
    job.status = status
    if result is not None:
        job.result_json = result
    if error is not None:
        job.error = error
    db.add(job)
    db.commit()
    db.refresh(job)
    return job
