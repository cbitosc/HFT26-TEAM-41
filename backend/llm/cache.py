"""Redis response cache. Replaying identical calls from the cache keeps the demo reliable."""

import hashlib
import json
from typing import Any

from redis import Redis

KEY_PREFIX = "llm:cache:"


def cache_key(
    slot: str,
    model: str,
    messages: list[dict[str, Any]],
    response_model: str,
    temperature: float,
    **extra: Any,
) -> str:
    payload = {
        "slot": slot,
        "model": model,
        "messages": messages,
        "response_model": response_model,
        "temperature": temperature,
        **extra,
    }
    blob = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return KEY_PREFIX + hashlib.sha256(blob.encode()).hexdigest()


class ResponseCache:
    def __init__(self, redis: Redis, ttl_s: int, enabled: bool) -> None:
        self._redis = redis
        self._ttl_s = ttl_s
        self._enabled = enabled

    def get(self, key: str) -> str | None:
        if not self._enabled:
            return None
        return self._redis.get(key)

    def set(self, key: str, value: str) -> None:
        if self._enabled:
            self._redis.set(key, value, ex=self._ttl_s)
