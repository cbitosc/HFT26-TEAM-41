from fastapi import FastAPI

from app.cache import check_redis
from app.db import check_db
from app.routes import hints, interviews, jobs, practice, profiles, report, scores, sessions, trail

app = FastAPI(title="HFT26 Team 41 API")
app.include_router(sessions.router)
app.include_router(jobs.router)
app.include_router(scores.router)
app.include_router(profiles.router)
app.include_router(practice.router)
app.include_router(hints.router)
app.include_router(trail.router)
app.include_router(report.router)
app.include_router(interviews.router)


@app.get("/health")
def health() -> dict:
    # "status" reports that the API process is up; dependency state is in the booleans.
    return {"status": "ok", "db": check_db(), "redis": check_redis()}
