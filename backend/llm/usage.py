"""Print tokens and estimated spend per slot. Run: python -m llm.usage (or `make llm-usage`)."""

from redis import Redis

from llm.budget import UsageTracker
from llm.config import SLOTS, get_llm_settings


def main() -> None:
    settings = get_llm_settings()
    redis = Redis.from_url(settings.redis_url, decode_responses=True)
    tracker = UsageTracker(redis, settings.llm_budget_usd)

    header = ("slot", "current model", "calls", "cache hits", "input tok", "output tok", "est. USD")
    rows = []
    for slot in SLOTS:
        usage = tracker.usage(slot)
        model = getattr(settings, f"featherless_model_{slot}") or "(not set)"
        rows.append(
            (
                slot,
                model,
                str(usage.calls),
                str(usage.cache_hits),
                str(usage.input_tokens),
                str(usage.output_tokens),
                f"{usage.cost_usd:.6f}",
            )
        )

    widths = [max(len(row[i]) for row in [header, *rows]) for i in range(len(header))]
    for row in [header, *rows]:
        print("  ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True)))

    spent = tracker.total_spend()
    budget = settings.llm_budget_usd
    print(f"\nTotal estimated spend: ${spent:.6f} of ${budget:.2f} budget")
    print(f"Remaining: ${budget - spent:.6f}")


if __name__ == "__main__":
    main()
