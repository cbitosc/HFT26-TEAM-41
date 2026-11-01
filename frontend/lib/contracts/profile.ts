// Generated from contracts/profile.schema.json by `make contracts`. Do not edit.

export type Domain = "backend" | "web" | "ml" | "security";
export type Runtime = "python311" | "node20";
export type TopicList = string[];
export type Source = "rules" | "llm" | "default";

/**
 * What backend/profiler reads from a portfolio: the stack and concepts the domain task is built from, and the DSA topics each tier may use. Computed by deterministic rules; an LLM fills a field only when the rules find nothing (see `sources`).
 */
export interface Profile {
  domain: Domain;
  runtime: Runtime;
  /**
   * Concepts from the seed concept vocabulary (union of seeds/* /concepts.yaml), strongest evidence first.
   */
  concepts: string[];
  /**
   * Problems solved per canonical DSA topic (dsa/taxonomy.yaml), after mapping the portfolio's topic names through their synonyms and summing.
   */
  topics_solved: {
    [k: string]: number;
  };
  /**
   * Canonical DSA topics allowed for each tier: listed for the tier in the taxonomy and solved at least the tier difficulty's threshold times.
   */
  allowed_topics: {
    novice: TopicList;
    adept: TopicList;
    master: TopicList;
  };
  suggested_tier: "novice" | "adept" | "master";
  /**
   * Why this tier, in one sentence with the numbers used.
   */
  tier_reason: string;
  /**
   * What the profiler could not use as claimed: unsupported stacks and the runtime used instead, unknown DSA topic names, failed fallbacks.
   */
  unsupported_notes: string[];
  /**
   * Where each inferred field came from. rules: keyword rules. llm: the generator fallback (rules found nothing). default: neither found anything.
   */
  sources: {
    domain: Source;
    runtime: Source;
    concepts: Source;
  };
}
