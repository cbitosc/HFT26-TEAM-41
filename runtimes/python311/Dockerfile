# Python test runner image. Build: make runtimes (tag: assess-python311).
# backend/runner starts one locked-down container per run: no network, read-only root,
# writable /workspace only, uid 10001.
FROM python:3.11.18-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

COPY requirements.txt constraints.txt /tmp/deps/
RUN pip install --root-user-action=ignore -r /tmp/deps/requirements.txt -c /tmp/deps/constraints.txt \
    && rm -rf /tmp/deps

RUN useradd --uid 10001 --user-group --no-create-home --shell /usr/sbin/nologin runner \
    && mkdir /workspace \
    && chown runner:runner /workspace

USER 10001
WORKDIR /workspace
