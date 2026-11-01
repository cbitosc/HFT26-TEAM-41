"""Practice job records and per-client limits, in Redis.

Practice has no sessions, so the browser sends a random X-Client-Id. A client has at most
one job in flight and a capped number of jobs per minute; both stop one visitor from
filling the sandbox workers. Job records are separate from assessment jobs (app.jobs).
"""

import json
import re
import time
import uuid
from typing import Any

from app.cache import redis_client

RECORD_TTL_S = 3600
# Longer than a submit can take (two sandbox runs); a crashed worker frees it this way.
LOCK_TTL_S = 180
MAX_JOBS_PER_MINUTE = 20

_CLIENT_ID = re.compile(r"[A-Za-z0-9-]{8,64}")


class Busy(Exception):
    """The client already has a job queued or running."""


class RateLimited(Exception):
    pass


def valid_client_id(client_id: str) -> bool:
    return bool(_CLIENT_ID.fullmatch(client_id))


def _record_key(job_id: str) -> str:
    return f"practice:job:{job_id}"


def _lock_key(client_id: str) -> str:
    return f"practice:lock:{client_id}"


def create(client_id: str) -> str:
    """Take the client's job slot and write a queued record; returns the job id."""
    minute = int(time.time() // 60)
    rate_key = f"practice:rate:{client_id}:{minute}"
    if redis_client.incr(rate_key) == 1:
        redis_client.expire(rate_key, 120)
    if int(redis_client.get(rate_key) or 0) > MAX_JOBS_PER_MINUTE:
        raise RateLimited
    job_id = str(uuid.uuid4())
    if not redis_client.set(_lock_key(client_id), job_id, nx=True, ex=LOCK_TTL_S):
        raise Busy
    write(job_id, {"status": "queued", "result": None, "error": None})
    return job_id


def release(client_id: str, job_id: str) -> None:
    if redis_client.get(_lock_key(client_id)) == job_id.encode():
        redis_client.delete(_lock_key(client_id))


def write(job_id: str, record: dict[str, Any]) -> None:
    redis_client.set(_record_key(job_id), json.dumps(record), ex=RECORD_TTL_S)


def read(job_id: str) -> dict[str, Any] | None:
    raw = redis_client.get(_record_key(job_id))
    return None if raw is None else json.loads(raw)
