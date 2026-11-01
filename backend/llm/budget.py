"""Per-slot token and spend tracking in Redis, and the hard budget guard."""

from dataclasses import dataclass

from redis import Redis

from llm.config import SLOTS, SlotConfig

KEY_PREFIX = "llm:usage:"


class BudgetExceededError(RuntimeError):
    """Estimated spend has reached LLM_BUDGET_USD. Only cache hits are served."""


@dataclass(frozen=True)
class SlotUsage:
    slot: str
    calls: int
    cache_hits: int
    input_tokens: int
    output_tokens: int
    cost_usd: float


def estimate_cost(config: SlotConfig, input_tokens: int, output_tokens: int) -> float:
    return (input_tokens * config.price_in + output_tokens * config.price_out) / 1_000_000


class UsageTracker:
    def __init__(self, redis: Redis, budget_usd: float) -> None:
        self._redis = redis
        self._budget_usd = budget_usd

    def record_call(
        self, slot: str, input_tokens: int, output_tokens: int, cost_usd: float
    ) -> None:
        # Cost is stored at the prices in force when the call was made, so changing a
        # slot's model or prices later doesn't rewrite past spend.
        key = KEY_PREFIX + slot
        pipe = self._redis.pipeline()
        pipe.hincrby(key, "calls", 1)
        pipe.hincrby(key, "input_tokens", input_tokens)
        pipe.hincrby(key, "output_tokens", output_tokens)
        pipe.hincrbyfloat(key, "cost_usd", cost_usd)
        pipe.execute()

    def record_cache_hit(self, slot: str) -> None:
        self._redis.hincrby(KEY_PREFIX + slot, "cache_hits", 1)

    def usage(self, slot: str) -> SlotUsage:
        data = self._redis.hgetall(KEY_PREFIX + slot)
        return SlotUsage(
            slot=slot,
            calls=int(data.get("calls", 0)),
            cache_hits=int(data.get("cache_hits", 0)),
            input_tokens=int(data.get("input_tokens", 0)),
            output_tokens=int(data.get("output_tokens", 0)),
            cost_usd=float(data.get("cost_usd", 0.0)),
        )

    def total_spend(self) -> float:
        return sum(self.usage(slot).cost_usd for slot in SLOTS)

    def check_budget(self) -> None:
        spend = self.total_spend()
        if spend >= self._budget_usd:
            raise BudgetExceededError(
                f"Estimated LLM spend ${spend:.4f} has reached LLM_BUDGET_USD "
                f"${self._budget_usd:.2f}; only cached responses are available."
            )
