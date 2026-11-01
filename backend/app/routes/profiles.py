"""Profile a portfolio: the first step of building an assessment (BLUEPRINT flow A)."""

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Assessment
from contracts_gen.portfolio import Portfolio
from contracts_gen.profile import Profile
from profiler.profile import build_profile

router = APIRouter(prefix="/profiles", tags=["profiles"])

DbSession = Annotated[Session, Depends(get_db)]


class ProfileIn(BaseModel):
    portfolio: dict[str, Any]
    """A Portfolio (contracts/portfolio.schema.json), stored exactly as sent."""


class ProfileOut(BaseModel):
    assessment_id: uuid.UUID
    profile: Profile


@router.post("", response_model=ProfileOut, status_code=status.HTTP_201_CREATED)
def create_profile(body: ProfileIn, db: DbSession) -> ProfileOut:
    """Profile the portfolio and store it on a new assessment (status "profiled", tier =
    the suggested tier until the recruiter picks one). May make one cached LLM call."""
    try:
        portfolio = Portfolio.model_validate(body.portfolio)
    except ValidationError as exc:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, exc.errors(include_url=False)
        ) from None
    profile = build_profile(body.portfolio)
    assessment = Assessment(
        candidate_name=portfolio.basics.name,
        portfolio=body.portfolio,
        tier=profile.suggested_tier,
        status="profiled",
        profile=profile.model_dump(mode="json"),
    )
    db.add(assessment)
    db.commit()
    return ProfileOut(assessment_id=assessment.id, profile=profile)
