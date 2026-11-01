"""Application factory. `app` is the instance a server would run."""

from fastapi import FastAPI

from app.repo import create_db
from app.routes import router
from app.services import ReportCache


def create_app() -> FastAPI:
    """A new app with its own in-memory database and report cache."""
    app = FastAPI(title="Expenses API")
    app.state.session_factory = create_db()
    app.state.report_cache = ReportCache()
    app.include_router(router)
    return app


app = create_app()
