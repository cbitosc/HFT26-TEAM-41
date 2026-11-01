"""Settings for the Featherless client, read from the environment (.env)."""

from functools import lru_cache
from typing import Any, Literal, get_args

from pydantic import BaseModel, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

Slot = Literal["generator", "assistant", "probe", "interviewer"]
SLOTS: tuple[Slot, ...] = get_args(Slot)

FEATHERLESS_BASE_URL = "https://api.featherless.ai/v1"


class SlotConfig(BaseModel):
    model: str
    price_in: float
    """USD per 1M input tokens."""
    price_out: float
    """USD per 1M output tokens."""
    chat_template_kwargs: dict[str, Any]
    """Reasoning controls etc. for this model, sent as Featherless `chat_template_kwargs`."""


class LLMSettings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    redis_url: str
    featherless_api_key: SecretStr = SecretStr("")

    # Per slot. Code refers to slots only; model IDs and prices live in the environment.
    featherless_model_generator: str = ""
    featherless_model_assistant: str = ""
    featherless_model_probe: str = ""
    featherless_model_interviewer: str = ""
    featherless_price_in_generator: float | None = None
    featherless_price_out_generator: float | None = None
    featherless_price_in_assistant: float | None = None
    featherless_price_out_assistant: float | None = None
    featherless_price_in_probe: float | None = None
    featherless_price_out_probe: float | None = None
    featherless_price_in_interviewer: float | None = None
    featherless_price_out_interviewer: float | None = None
    featherless_chat_template_kwargs_generator: dict[str, Any] = {}
    featherless_chat_template_kwargs_assistant: dict[str, Any] = {}
    featherless_chat_template_kwargs_probe: dict[str, Any] = {}
    featherless_chat_template_kwargs_interviewer: dict[str, Any] = {}
    featherless_tts_model: str = ""
    featherless_tts_voice: str = "af_bella"

    llm_timeout_s: float = 60.0
    llm_max_retries: int = 3
    """Retries on network errors, 429 and 5xx (exponential backoff, done by the OpenAI SDK)."""
    llm_cache_enabled: bool = True
    llm_cache_ttl_s: int = 7 * 24 * 3600
    llm_budget_usd: float = 20.0

    def slot(self, slot: Slot) -> SlotConfig:
        model = getattr(self, f"featherless_model_{slot}")
        price_in = getattr(self, f"featherless_price_in_{slot}")
        price_out = getattr(self, f"featherless_price_out_{slot}")
        # Fail closed: without a model or prices the budget guard can't work.
        if not model:
            raise ValueError(f"FEATHERLESS_MODEL_{slot.upper()} is not set")
        if price_in is None or price_out is None:
            raise ValueError(
                f"FEATHERLESS_PRICE_IN_{slot.upper()} and FEATHERLESS_PRICE_OUT_{slot.upper()} "
                "must be set"
            )
        return SlotConfig(
            model=model,
            price_in=price_in,
            price_out=price_out,
            chat_template_kwargs=getattr(self, f"featherless_chat_template_kwargs_{slot}"),
        )


@lru_cache
def get_llm_settings() -> LLMSettings:
    return LLMSettings()
