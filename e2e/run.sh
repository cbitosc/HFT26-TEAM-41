#!/bin/sh
# `make e2e`: a fresh seed-demo session, then the headless browser flow in e2e/demo.mjs.
# Needs the stack running (`make up`). Restarts worker and beat first: Celery doesn't
# reload code, and a stale worker would grade with old code and fail for no real reason.
set -eu
cd "$(dirname "$0")/.."

running=$(docker compose ps --status running --services)
for service in api worker beat frontend; do
    if ! printf '%s\n' "$running" | grep -qx "$service"; then
        echo "e2e: $service is not running; start the stack with 'make up'" >&2
        exit 1
    fi
done

docker compose restart worker beat

mkdir -p e2e/artifacts
out=$(make -s seed-demo)
printf '%s\n' "$out"
session=$(printf '%s\n' "$out" | sed -n 's|^session URL: .*/session/\([0-9a-f-]*\).*|\1|p')
if [ -z "$session" ]; then
    echo "e2e: no session URL in the seed-demo output" >&2
    exit 1
fi

docker compose --profile e2e build --quiet e2e
# As the host user, so failure screenshots in e2e/artifacts aren't root-owned.
docker compose --profile e2e run --rm --no-deps --user "$(id -u):$(id -g)" -e HOME=/tmp \
    e2e node demo.mjs "$session"
