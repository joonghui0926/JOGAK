from fastapi import APIRouter, HTTPException

from jogak_api.deps import DBSession
from jogak_api.db.models import GenerationJob
from jogak_api.schemas import JobRead

router = APIRouter(prefix="/api/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobRead)
def get_job(job_id: str, db: DBSession) -> JobRead:
    job = db.get(GenerationJob, job_id)
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobRead(
        id=job.id,
        type=job.type,
        status=job.status,
        current_state=job.current_state,
        progress=job.progress,
        error=job.error,
        result=job.result_json,
        created_at=job.created_at,
        updated_at=job.updated_at,
    )
