from fastapi import APIRouter, HTTPException, status

from app.jobs import JobView, get_job

router = APIRouter(prefix="/jobs", tags=["jobs"])


@router.get("/{job_id}", response_model=JobView)
def job_status(job_id: str) -> JobView:
    """Status of a run or submit job. A run job's result holds visible tests only."""
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return job
