"""Featherless client. Every Featherless call in the project goes through this module.

Order of operations for each call: response cache (free, allowed even over budget)
-> budget guard -> API call -> usage tracking, structured log line, cache write.
"""

import base64
import copy
import json
import logging
import time
from dataclasses import asdict, dataclass
from functools import lru_cache
from typing import Any, TypeVar

import httpx2
import instructor
from instructor.v2.core.errors import InstructorRetryException
from openai import OpenAI
from pydantic import BaseModel, ValidationError
from redis import Redis

from llm.budget import UsageTracker, estimate_cost
from llm.cache import ResponseCache, cache_key
from llm.config import FEATHERLESS_BASE_URL, LLMSettings, Slot, SlotConfig, get_llm_settings

logger = logging.getLogger("llm")

T = TypeVar("T", bound=BaseModel)
Messages = list[dict[str, Any]]


@dataclass(frozen=True)
class CallInfo:
    slot: Slot
    model: str
    latency_ms: int
    cache_hit: bool
    prompt_tokens: int
    completion_tokens: int
    cost_usd: float


class LLMClient:
    def __init__(
        self,
        settings: LLMSettings,
        redis: Redis,
        http_client: httpx2.Client | None = None,
    ) -> None:
        self._settings = settings
        self._openai = OpenAI(
            base_url=FEATHERLESS_BASE_URL,
            api_key=settings.featherless_api_key.get_secret_value(),
            timeout=settings.llm_timeout_s,
            max_retries=settings.llm_max_retries,
            http_client=http_client,
        )
        # JSON mode: the schema goes in the prompt and the reply is parsed as JSON;
        # no native tool calling.
        self._instructor = instructor.from_openai(self._openai, mode=instructor.Mode.JSON)
        self._cache = ResponseCache(redis, settings.llm_cache_ttl_s, settings.llm_cache_enabled)
        self._usage = UsageTracker(redis, settings.llm_budget_usd)

    def structured(
        self,
        slot: Slot,
        messages: Messages,
        response_model: type[T],
        temperature: float = 0.2,
        max_retries: int = 3,
        max_tokens: int = 800,
    ) -> tuple[T, CallInfo]:
        config = self._settings.slot(slot)
        key = cache_key(
            slot,
            config.model,
            messages,
            response_model.__name__,
            temperature,
            max_tokens=max_tokens,
        )
        start = time.perf_counter()

        cached = self._cache.get(key)
        if cached is not None:
            try:
                result = response_model.model_validate_json(cached)
            except ValidationError:
                # The model changed shape since this entry was cached; call the API instead.
                logger.warning(json.dumps({"event": "llm_cache_stale", "slot": slot}))
            else:
                return result, self._log_cache_hit(slot, config, start)

        self._usage.check_budget()
        try:
            result, completion = self._instructor.chat.completions.create_with_completion(
                model=config.model,
                # Instructor adds its own instructions to the messages; keep the caller's intact.
                messages=copy.deepcopy(messages),
                response_model=response_model,
                temperature=temperature,
                max_retries=max_retries,
                max_tokens=max_tokens,
                **self._extra_body(config),
            )
        except InstructorRetryException as exc:
            # Failed attempts still cost tokens.
            self._record_call(slot, config, start, exc.total_usage, error=summarize_error(exc))
            raise

        # Instructor sums usage over its validation retries; fall back to the last reply.
        usage = getattr(result, "_total_usage", None) or completion.usage
        info = self._record_call(slot, config, start, usage)
        payload = result.model_dump_json()
        self._cache.set(key, payload)
        # Instructor attaches its raw response to the result; return a clean instance so
        # a fresh result and a cache hit are indistinguishable.
        return response_model.model_validate_json(payload), info

    def text(
        self,
        slot: Slot,
        messages: Messages,
        temperature: float = 0.3,
        max_tokens: int = 800,
    ) -> tuple[str, CallInfo]:
        config = self._settings.slot(slot)
        # max_tokens is part of the key so a short reply isn't served for a longer request.
        key = cache_key(slot, config.model, messages, "text", temperature, max_tokens=max_tokens)
        start = time.perf_counter()

        cached = self._cache.get(key)
        if cached is not None:
            return cached, self._log_cache_hit(slot, config, start)

        self._usage.check_budget()
        try:
            completion = self._openai.chat.completions.create(
                model=config.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **self._extra_body(config),
            )
        except Exception as exc:
            self._record_call(slot, config, start, None, error=summarize_error(exc))
            raise

        content = completion.choices[0].message.content or ""
        info = self._record_call(slot, config, start, completion.usage)
        self._cache.set(key, content)
        return content, info

    def speech(self, text: str) -> tuple[bytes, bool]:
        """MP3 of `text` from Featherless /v1/audio/speech (FEATHERLESS_TTS_MODEL/_VOICE).

        Cached by (model, voice, text) like the text calls; returns (audio, cache_hit).
        """
        model = self._settings.featherless_tts_model
        voice = self._settings.featherless_tts_voice
        if not model:
            raise ValueError("FEATHERLESS_TTS_MODEL is not set")
        key = cache_key("tts", model, [{"voice": voice, "input": text}], "mp3", 0.0)
        start = time.perf_counter()
        cached = self._cache.get(key)
        if cached is not None:
            self._usage.record_cache_hit("tts")
            logger.info(json.dumps({"event": "tts_call", "cache_hit": True, "chars": len(text)}))
            return base64.b64decode(cached), True

        self._usage.check_budget()
        response = self._openai.audio.speech.create(
            model=model, voice=voice, input=text, response_format="mp3"
        )
        audio = response.read()
        # Priced per character, not per token: counted for the log, not for the budget.
        self._usage.record_call("tts", len(text), 0, 0.0)
        logger.info(
            json.dumps(
                {
                    "event": "tts_call",
                    "cache_hit": False,
                    "chars": len(text),
                    "bytes": len(audio),
                    "latency_ms": _elapsed_ms(start),
                }
            )
        )
        self._cache.set(key, base64.b64encode(audio).decode())
        return audio, False

    @staticmethod
    def _extra_body(config: SlotConfig) -> dict[str, Any]:
        if not config.chat_template_kwargs:
            return {}
        return {"extra_body": {"chat_template_kwargs": config.chat_template_kwargs}}

    def _record_call(
        self,
        slot: Slot,
        config: SlotConfig,
        start: float,
        usage: Any,
        error: str | None = None,
    ) -> CallInfo:
        prompt_tokens = getattr(usage, "prompt_tokens", 0) or 0
        completion_tokens = getattr(usage, "completion_tokens", 0) or 0
        cost = estimate_cost(config, prompt_tokens, completion_tokens)
        self._usage.record_call(slot, prompt_tokens, completion_tokens, cost)

        info = CallInfo(
            slot=slot,
            model=config.model,
            latency_ms=_elapsed_ms(start),
            cache_hit=False,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            cost_usd=cost,
        )
        fields: dict[str, Any] = {"event": "llm_call", **asdict(info)}
        if usage is None and error is None:
            fields["warning"] = "response had no token usage; spend not tracked"
        if error is not None:
            fields["error"] = error
            logger.error(json.dumps(fields))
        else:
            logger.info(json.dumps(fields))
        return info

    def _log_cache_hit(self, slot: Slot, config: SlotConfig, start: float) -> CallInfo:
        self._usage.record_cache_hit(slot)
        info = CallInfo(
            slot=slot,
            model=config.model,
            latency_ms=_elapsed_ms(start),
            cache_hit=True,
            prompt_tokens=0,
            completion_tokens=0,
            cost_usd=0.0,
        )
        logger.info(json.dumps({"event": "llm_call", **asdict(info)}))
        return info


def _elapsed_ms(start: float) -> int:
    return round((time.perf_counter() - start) * 1000)


def summarize_error(exc: Exception, limit: int = 200) -> str:
    """Short error for the log. Instructor's own message embeds every raw model reply."""
    if isinstance(exc, InstructorRetryException):
        cause = exc.__cause__ or exc
        first_line = str(cause).splitlines()[0] if str(cause) else ""
        return f"{type(cause).__name__} after {exc.n_attempts} attempts: {first_line}"[:limit]
    return f"{type(exc).__name__}: {exc}".splitlines()[0][:limit]


@lru_cache
def default_client() -> LLMClient:
    settings = get_llm_settings()
    return LLMClient(settings, Redis.from_url(settings.redis_url, decode_responses=True))


def complete_structured(
    slot: Slot,
    messages: Messages,
    response_model: type[T],
    temperature: float = 0.2,
    max_retries: int = 3,
    max_tokens: int = 800,
) -> T:
    result, _ = default_client().structured(
        slot,
        messages,
        response_model,
        temperature=temperature,
        max_retries=max_retries,
        max_tokens=max_tokens,
    )
    return result


def complete_text(
    slot: Slot,
    messages: Messages,
    temperature: float = 0.3,
    max_tokens: int = 800,
) -> str:
    result, _ = default_client().text(
        slot, messages, temperature=temperature, max_tokens=max_tokens
    )
    return result


def synthesize_speech(text: str) -> bytes:
    audio, _ = default_client().speech(text)
    return audio
