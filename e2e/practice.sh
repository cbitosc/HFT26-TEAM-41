#!/bin/sh
# `make e2e-practice`: the practice-mode browser flow in e2e/practice.mjs. Needs the stack
# running (`make up`). Restarts worker first: Celery doesn't reload code.
set -eu
cd "$(dirname "$0")/.."

running=$(docker compose ps --status running --services)
for service in api worker frontend; do
    if ! printf '%s\n' "$running" | grep -qx "$service"; then
        echo "e2e-practice: $service is not running; start the stack with 'make up'" >&2
        exit 1
    fi
done

docker compose restart worker
mkdir -p e2e/artifacts
docker compose --profile e2e build --quiet e2e
docker compose --profile e2e run --rm --no-deps --user "$(id -u):$(id -g)" -e HOME=/tmp \
    e2e node practice.mjs
