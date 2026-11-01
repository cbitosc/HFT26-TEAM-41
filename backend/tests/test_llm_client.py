"""LLM client tests. Featherless is replaced by an in-process mock transport, Redis by
fakeredis: no network, no API key, and the real spend counters are never touched.

The OpenAI SDK, Instructor and Pydantic run for real, so retries and parsing are exercised.
"""

import json
import logging
from collections.abc import Callable

import fakeredis
import httpx2
import pytest
from instructor.v2.core.errors import InstructorRetryException
from pydantic import BaseModel

from llm import BudgetExceededError
from llm.client import LLMClient
from llm.config import LLMSettings

API_KEY = "test-key-must-never-be-logged"


class StackInfo(BaseModel):
    language: str
    framework: str


MESSAGES = [{"role": "user", "content": 'Extract language and framework: "a REST API in FastAPI"'}]
VALID = '{"language": "Python", "framework": "FastAPI"}'


def completion(content: str, prompt_tokens: int = 50, completion_tokens: int = 10) -> dict:
    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "created": 0,
        "model": "mock",
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": content},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }


Reply = httpx2.Response | Callable[[httpx2.Request], httpx2.Response]


class FakeFeatherless:
    """Serves queued replies in order and records every request body."""

    def __init__(self) -> None:
        self.replies: list[Reply] = []
        self.requests: list[dict] = []

    def queue(self, *replies: Reply) -> None:
        self.replies.extend(replies)

    def handler(self, request: httpx2.Request) -> httpx2.Response:
        self.requests.append(json.loads(request.content))
        reply = self.replies.pop(0)
        return reply(request) if callable(reply) else reply


def ok(content: str = VALID, **usage: int) -> httpx2.Response:
    return httpx2.Response(200, json=completion(content, **usage))


def make_settings(**overrides) -> LLMSettings:
    # Every field is set explicitly so FEATHERLESS_*/LLM_* variables in the
    # container environment can't leak into the tests.
    values = {
        "redis_url": "redis://unused",
        "featherless_api_key": API_KEY,
        "featherless_model_generator": "mock/generator-model",
        "featherless_model_assistant": "mock/assistant-model",
        "featherless_model_probe": "mock/probe-model",
        "featherless_model_interviewer": "mock/interviewer-model",
        "featherless_price_in_generator": 0.14,
        "featherless_price_out_generator": 0.28,
        "featherless_price_in_assistant": 0.14,
        "featherless_price_out_assistant": 0.28,
        "featherless_price_in_probe": 0.125,
        "featherless_price_out_probe": 0.45,
        "featherless_price_in_interviewer": 0.05,
        "featherless_price_out_interviewer": 0.08,
        "featherless_chat_template_kwargs_generator": {"thinking": False},
        "featherless_chat_template_kwargs_assistant": {"thinking": False},
        "featherless_chat_template_kwargs_probe": {},
        "featherless_chat_template_kwargs_interviewer": {},
        "llm_timeout_s": 5.0,
        "llm_max_retries": 2,
        "llm_cache_enabled": True,
        "llm_cache_ttl_s": 60,
        "llm_budget_usd": 20.0,
    }
    values.update(overrides)
    return LLMSettings(_env_file=None, **values)


@pytest.fixture
def api() -> FakeFeatherless:
    return FakeFeatherless()


@pytest.fixture
def make_client(api: FakeFeatherless) -> Callable[..., LLMClient]:
    redis = fakeredis.FakeRedis(decode_responses=True)

    def build(**overrides) -> LLMClient:
        http = httpx2.Client(transport=httpx2.MockTransport(api.handler))
        return LLMClient(make_settings(**overrides), redis, http_client=http)

    return build


def test_structured_call_parses_and_records_usage(api, make_client) -> None:
    api.queue(ok(prompt_tokens=1000, completion_tokens=200))
    client = make_client()

    result, info = client.structured("generator", MESSAGES, StackInfo)

    assert result == StackInfo(language="Python", framework="FastAPI")
    assert (info.cache_hit, info.prompt_tokens, info.completion_tokens) == (False, 1000, 200)
    assert info.cost_usd == pytest.approx((1000 * 0.14 + 200 * 0.28) / 1_000_000)

    body = api.requests[0]
    assert body["model"] == "mock/generator-model"  # slot resolved from settings
    assert body["chat_template_kwargs"] == {"thinking": False}
    assert body["response_format"] == {"type": "json_object"}  # JSON mode
    assert "tools" not in body  # no native tool calling
    assert body["max_tokens"] == 800  # token policy: every call sets max_tokens

    usage = client._usage.usage("generator")
    assert (usage.calls, usage.input_tokens, usage.output_tokens) == (1, 1000, 200)


def test_slot_without_template_kwargs_sends_none(api, make_client) -> None:
    api.queue(ok())

    make_client().structured("probe", MESSAGES, StackInfo)

    assert api.requests[0]["model"] == "mock/probe-model"
    assert "chat_template_kwargs" not in api.requests[0]


def test_interviewer_slot_uses_its_own_model_and_prices(api, make_client) -> None:
    api.queue(ok(prompt_tokens=1000, completion_tokens=200))
    client = make_client()

    _, info = client.structured("interviewer", MESSAGES, StackInfo)

    assert api.requests[0]["model"] == "mock/interviewer-model"
    assert info.cost_usd == pytest.approx((1000 * 0.05 + 200 * 0.08) / 1_000_000)
    assert client._usage.usage("interviewer").calls == 1


def _connect_error(request: httpx2.Request) -> httpx2.Response:
    raise httpx2.ConnectError("connection refused", request=request)


@pytest.mark.parametrize(
    "failure",
    [
        # retry-after-ms keeps the SDK's backoff short in tests.
        httpx2.Response(429, headers={"retry-after-ms": "1"}, json={"error": "rate limited"}),
        httpx2.Response(503, headers={"retry-after-ms": "1"}, json={"error": "unavailable"}),
        _connect_error,
    ],
    ids=["http_429", "http_503", "network_error"],
)
def test_transient_failure_is_retried(api, make_client, failure) -> None:
    api.queue(failure, ok())

    result, _ = make_client().structured("generator", MESSAGES, StackInfo)

    assert result.framework == "FastAPI"
    assert len(api.requests) == 2


def test_validation_failure_triggers_instructor_retry(api, make_client) -> None:
    api.queue(
        ok('{"language": "Python"}', prompt_tokens=100, completion_tokens=5),  # no framework
        ok(prompt_tokens=150, completion_tokens=10),
    )
    client = make_client()

    result, info = client.structured("generator", MESSAGES, StackInfo, max_retries=3)

    assert result.framework == "FastAPI"
    assert len(api.requests) == 2
    # The retry tells the model what was wrong with its first answer.
    assert "framework" in json.dumps(api.requests[1]["messages"][len(MESSAGES) :])
    # Tokens from the failed attempt are paid for too.
    assert (info.prompt_tokens, info.completion_tokens) == (250, 15)


def test_exhausted_validation_retries_still_charge_tokens(api, make_client, caplog) -> None:
    # A reply that never parses, e.g. a server dropping the opening brace.
    broken = 'language": "Python", "framework": "FastAPI"}'
    api.queue(*[ok(broken, prompt_tokens=100, completion_tokens=10) for _ in range(3)])
    client = make_client()

    with caplog.at_level(logging.INFO), pytest.raises(InstructorRetryException):
        client.structured("generator", MESSAGES, StackInfo, max_retries=2)

    assert len(api.requests) == 3  # first attempt + 2 retries
    usage = client._usage.usage("generator")
    assert (usage.input_tokens, usage.output_tokens) == (300, 30)
    error_log = json.loads(next(r.getMessage() for r in caplog.records if r.name == "llm"))
    assert error_log["error"].startswith("ValidationError after 3 attempts")
    assert broken not in error_log["error"]  # raw model output stays out of the log


def test_second_identical_call_is_served_from_cache(api, make_client) -> None:
    api.queue(ok())
    client = make_client()

    first, first_info = client.structured("generator", MESSAGES, StackInfo)
    second, second_info = client.structured("generator", MESSAGES, StackInfo)

    assert second == first
    assert (first_info.cache_hit, second_info.cache_hit) == (False, True)
    assert second_info.cost_usd == 0
    assert len(api.requests) == 1
    assert client._usage.usage("generator").cache_hits == 1


def test_cache_can_be_disabled(api, make_client) -> None:
    api.queue(ok(), ok())
    client = make_client(llm_cache_enabled=False)

    client.structured("generator", MESSAGES, StackInfo)
    client.structured("generator", MESSAGES, StackInfo)

    assert len(api.requests) == 2


def test_budget_exceeded_blocks_new_calls_but_serves_cache(api, make_client) -> None:
    # One call costs (1000 * 1.0 + 1000 * 1.0) / 1M = $0.002, which uses up the budget.
    api.queue(ok(prompt_tokens=1000, completion_tokens=1000))
    client = make_client(
        llm_budget_usd=0.002,
        featherless_price_in_generator=1.0,
        featherless_price_out_generator=1.0,
    )
    first, _ = client.structured("generator", MESSAGES, StackInfo)

    other_messages = [{"role": "user", "content": "A different question"}]
    with pytest.raises(BudgetExceededError):
        client.structured("generator", other_messages, StackInfo)
    with pytest.raises(BudgetExceededError):
        client.text("assistant", other_messages)
    assert len(api.requests) == 1  # nothing was sent after the budget was reached

    cached, info = client.structured("generator", MESSAGES, StackInfo)
    assert cached == first
    assert info.cache_hit


def test_text_completion(api, make_client) -> None:
    api.queue(ok("Use a dict to count characters."))
    client = make_client()

    text, info = client.text("assistant", MESSAGES)

    assert text == "Use a dict to count characters."
    assert not info.cache_hit
    body = api.requests[0]
    assert (body["model"], body["temperature"], body["max_tokens"]) == (
        "mock/assistant-model",
        0.3,
        800,
    )
    assert body["chat_template_kwargs"] == {"thinking": False}


def test_calls_are_logged_as_json_without_the_api_key(api, make_client, caplog) -> None:
    api.queue(ok())
    client = make_client()

    with caplog.at_level(logging.DEBUG):
        client.structured("generator", MESSAGES, StackInfo)
        client.structured("generator", MESSAGES, StackInfo)

    call_logs = [json.loads(r.getMessage()) for r in caplog.records if r.name == "llm"]
    assert [entry["cache_hit"] for entry in call_logs] == [False, True]
    assert {"slot", "model", "latency_ms", "prompt_tokens", "completion_tokens"} <= set(
        call_logs[0]
    )
    assert API_KEY not in caplog.text


def test_speech_posts_model_voice_and_text_and_caches_the_audio(api, make_client) -> None:
    api.queue(httpx2.Response(200, content=b"ID3-fake-mp3", headers={"content-type": "audio/mpeg"}))
    client = make_client(featherless_tts_model="mock/tts", featherless_tts_voice="af_bella")

    first, hit = client.speech("Hello there.")
    again, hit_again = client.speech("Hello there.")

    assert (first, hit) == (b"ID3-fake-mp3", False)
    assert (again, hit_again) == (b"ID3-fake-mp3", True)
    assert len(api.requests) == 1  # the second one came from the cache
    body = api.requests[0]
    assert (body["model"], body["voice"], body["input"]) == ("mock/tts", "af_bella", "Hello there.")


def test_speech_without_a_model_fails_closed(api, make_client) -> None:
    with pytest.raises(ValueError, match="FEATHERLESS_TTS_MODEL"):
        make_client(featherless_tts_model="").speech("Hi")
    assert api.requests == []
