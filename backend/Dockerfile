FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install dependencies first so code edits don't bust the layer cache.
COPY pyproject.toml ./
RUN mkdir app assistant builder contracts_gen gate interviewer llm profiler report runner scoring trail \
    && touch app/__init__.py assistant/__init__.py builder/__init__.py contracts_gen/__init__.py llm/__init__.py \
       gate/__init__.py profiler/__init__.py report/__init__.py runner/__init__.py scoring/__init__.py \
       trail/__init__.py interviewer/__init__.py \
    && pip install -e ".[dev]"

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
