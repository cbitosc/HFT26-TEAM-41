"use client";

import { Reveal, Item } from "./Reveal";
import Chip from "./Chip";
import { Engraving, Label, Tilt, Words } from "./fx";
import type { Status } from "@/lib/site";
import type { GreekName } from "@/lib/greek";

// Three tiers as three orders of column: plainer to more ornate as the problem grows.
type Tier = {
  name: string;
  order: string;
  art: GreekName;
  task: string;
  builder: string;
  builderStatus: Status;
  dsa: string;
  assistant: string;
  score: string;
};

const TIERS: Tier[] = [
  {
    name: "Novice",
    order: "The plain column",
    art: "column",
    task: "Find and fix one bug in one file.",
    builder: "Mutation engine: six LibCST operators, kept only if the sandbox shows the bug breaks a concept test.",
    builderStatus: "built",
    dsa: "Easy, from claimed topics",
    assistant: "None",
    score: "Mean correctness",
  },
  {
    name: "Adept",
    order: "The Ionic order",
    art: "ionic",
    task: "Build back a feature that was stubbed out across 2–3 files.",
    builder: "Feature removal: signatures and docstrings stay, bodies become NotImplementedError.",
    builderStatus: "built",
    dsa: "Medium, from claimed topics",
    assistant: "Guarded hints",
    score: "0.8 × correctness + 20 × AI efficiency",
  },
  {
    name: "Master",
    order: "The Corinthian order",
    art: "corinthian",
    task: "Debug across files and meet a performance budget.",
    builder: "Bug plus a performance regression from four LibCST operators, such as a set lookup turned into a list scan.",
    builderStatus: "built",
    dsa: "Medium or hard",
    assistant: "Guarded hints",
    score: "Same, with perf_factor: 1.0 in budget, down to 0.5 at 3×",
  },
];

const ROWS: [keyof Tier, string][] = [
  ["task", "Domain task"],
  ["dsa", "DSA task"],
  ["assistant", "AI assistant"],
  ["score", "Final score"],
];

export default function Tiers() {
  return (
    <section className="section tiers-sec" id="tiers">
      <div className="wrap">
        <div className="grid">
          <div className="tiers-intro">
            <Label n={3}>Three orders</Label>
            <Words className="h2" text="Same sixty minutes. What changes is the *size* of the problem." />
            <p className="muted">
              One domain task (about 35 minutes) and one DSA task (about 25), always in the candidate&apos;s stack.
              The recruiter picks the tier; the profiler suggests one from projects and solved counts.
            </p>
          </div>
        </div>

        <Reveal className="tiers" amount={0.12}>
          {TIERS.map((t, i) => (
            <Item key={t.name} className="tier">
              <Tilt className="tier-art" max={6}>
                <Engraving name={t.art} alt={`${t.order} capital`} />
              </Tilt>
              <p className="inscr tier-order">
                {["I", "II", "III"][i]} · {t.order}
              </p>
              <h3 className="tier-name">{t.name}</h3>
              <dl className="tier-rows">
                {ROWS.map(([key, label]) => (
                  <div key={key}>
                    <dt>{label}</dt>
                    <dd>{t[key]}</dd>
                  </div>
                ))}
                <div>
                  <dt>Task builder</dt>
                  <dd>
                    {t.builder}
                    <span className="tier-chip">
                      <Chip s={t.builderStatus} />
                    </span>
                  </dd>
                </div>
              </dl>
            </Item>
          ))}
        </Reveal>
      </div>
    </section>
  );
}
