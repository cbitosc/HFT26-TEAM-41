"""Practice mode API: browse the DSA bank, Run and Submit without an assessment session."""

from typing import Annotated, Any, Literal

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, Field

from app import dsa, practice, practice_jobs
from app.celery_app import celery_app
from app.practice import Language

router = APIRouter(prefix="/practice", tags=["practice"])

ClientId = Annotated[str, Header(alias="X-Client-Id")]


class ProblemSummary(BaseModel):
    id: str
    title: str
    difficulty: Literal["easy", "medium", "hard"]
    tags: list[str]


class Example(BaseModel):
    id: str
    input: dict[str, Any]
    expected: Any


class LanguageView(BaseModel):
    statement_md: str
    starter: str
    file: str
    examples: list[Example]
    parameters: list[str]


class ProblemOut(ProblemSummary):
    languages: dict[str, LanguageView]


class RunIn(BaseModel):
    language: Language
    code: str = Field(max_length=practice.MAX_CODE_CHARS)
    custom_input: str | None = None
    """A JSON object keyed by the parameter names. Null runs the visible examples."""


class SubmitIn(BaseModel):
    language: Language
    code: str = Field(max_length=practice.MAX_CODE_CHARS)


class JobOut(BaseModel):
    job_id: str


class PracticeJobView(BaseModel):
    job_id: str
    status: Literal["queued", "running", "done", "failed"]
    result: dict[str, Any] | None
    error: str | None


def _summary(problem) -> ProblemSummary:
    return ProblemSummary(
        id=problem.id,
        title=practice.title(problem),
        difficulty=problem.difficulty,
        tags=list(problem.tags),
    )


def _problem_or_404(problem_id: str):
    problem = practice.get_problem(problem_id)
    if problem is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "problem not found")
    return problem


def _check_client(client_id: str) -> None:
    if not practice_jobs.valid_client_id(client_id):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "invalid X-Client-Id")


@router.get("/problems", response_model=list[ProblemSummary])
def list_problems() -> list[ProblemSummary]:
    order = {"easy": 0, "medium": 1, "hard": 2}
    problems = sorted(practice.load_problems(), key=lambda p: (order[p.difficulty], p.id))
    return [_summary(p) for p in problems]


@router.get("/problems/{problem_id}", response_model=ProblemOut)
def get_problem(problem_id: str) -> ProblemOut:
    """Statement, starter code and the visible examples per language. No hidden cases."""
    problem = _problem_or_404(problem_id)
    languages = {}
    for language in practice.LANGUAGES:
        spec = practice.spec_for(problem.id, language)
        file, _ = dsa.entry_point(spec)
        languages[language] = LanguageView(
            statement_md=spec.statement_md,
            starter=spec.starter_files[file],
            file=file,
            examples=[
                Example(id=c.id, input=c.input, expected=c.expected) for c in spec.dsa_cases.visible
            ],
            parameters=practice.parameter_names(spec),
        )
    return ProblemOut(**_summary(problem).model_dump(), languages=languages)


def _enqueue(client_id: str, args: list[Any]) -> JobOut:
    try:
        job_id = practice_jobs.create(client_id)
    except practice_jobs.RateLimited:
        raise HTTPException(
            status.HTTP_429_TOO_MANY_REQUESTS, "too many runs, wait a minute"
        ) from None
    except practice_jobs.Busy:
        raise HTTPException(status.HTTP_409_CONFLICT, "a run is already in progress") from None
    try:
        celery_app.send_task("practice_job", args=[job_id, client_id, *args], task_id=job_id)
    except Exception:
        practice_jobs.release(client_id, job_id)
        raise
    return JobOut(job_id=job_id)


@router.post("/problems/{problem_id}/run", response_model=JobOut)
def run(problem_id: str, body: RunIn, client_id: ClientId) -> JobOut:
    problem = _problem_or_404(problem_id)
    _check_client(client_id)
    custom = None
    if body.custom_input is not None:
        spec = practice.spec_for(problem.id, body.language)
        try:
            custom = practice.parse_custom_input(spec, body.custom_input)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from None
    return _enqueue(client_id, ["run", problem.id, body.language, body.code, custom])


@router.post("/problems/{problem_id}/submit", response_model=JobOut)
def submit(problem_id: str, body: SubmitIn, client_id: ClientId) -> JobOut:
    problem = _problem_or_404(problem_id)
    _check_client(client_id)
    return _enqueue(client_id, ["submit", problem.id, body.language, body.code, None])


@router.get("/jobs/{job_id}", response_model=PracticeJobView)
def job(job_id: str) -> PracticeJobView:
    record = practice_jobs.read(job_id)
    if record is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "job not found")
    return PracticeJobView(job_id=job_id, **record)
