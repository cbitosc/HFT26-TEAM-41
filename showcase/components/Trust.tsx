"use client";

import { useRef } from "react";
import { motion, useInView } from "motion/react";
import { Reveal, Item } from "./Reveal";
import Counter from "./Counter";
import Chip from "./Chip";
import { FACTS } from "@/lib/site";
import { Engraving, Label, Parallax, Words } from "./fx";

const CERT: [string, string][] = [
  ["Reference solution", "passes 65 / 65, three times"],
  ["Starter", "fails 1 of 3 visible"],
  ["Split", "3 visible, 62 hidden"],
  ["Changed lines", "1"],
  ["Test ids", "pinned at build"],
  ["Scope", "app/utils.py"],
];

function Certificate() {
  const ref = useRef<HTMLDivElement>(null);
  const seen = useInView(ref, { once: true, amount: 0.5 });
  return (
    <div className="cert" ref={ref}>
      <div className="cert-top">
        <span>Validation certificate</span>
        <span>pagination, novice</span>
      </div>
      <ul>
        {CERT.map(([k, v], i) => (
          <motion.li
            key={k}
            initial={{ opacity: 0, x: -10 }}
            animate={seen ? { opacity: 1, x: 0 } : {}}
            transition={{ delay: 0.25 + i * 0.18, duration: 0.4 }}
          >
            <span>{k}</span>
            <span>{v}</span>
          </motion.li>
        ))}
      </ul>
      <motion.div
        className="cert-stamp"
        initial={{ opacity: 0, scale: 1.6, rotate: -18 }}
        animate={seen ? { opacity: 1, scale: 1, rotate: -8 } : {}}
        transition={{ delay: 0.25 + CERT.length * 0.18, type: "spring", stiffness: 380, damping: 18 }}
        aria-label="Passed"
      >
        <Engraving name="wreath" ink className="cert-wreath" />
        <span>passed</span>
        <small>sandbox</small>
      </motion.div>
      <p className="small cert-foot">
        From the P2.7 gate on the demo task (make seed-demo, 2026-10-31). The certificate view in the app is P4.1.
      </p>
    </div>
  );
}

const THREATS: [string, string][] = [
  [
    "Read the hidden tests",
    "They run in their own sandbox and are never in the visible run. Only counts are stored. DSA answers never enter a sandbox at all: the harness gets inputs, the backend compares outputs.",
  ],
  [
    "Edit tests, conftest.py, pytest.ini, package.json",
    "Editable allowlist: only starter files outside tests and config. Checked at save, at Run, and again when the workspace is built.",
  ],
  [
    "Delete or rename test files mid-run",
    "Test files are root-owned and read-only, and so is every directory above them.",
  ],
  [
    "Skip, add or rename tests to change the counts",
    "The collected test ids must equal the ids recorded at build time, or the run scores zero (test_set_mismatch).",
  ],
  [
    "Escape, use the network, exhaust resources",
    "Fresh container per run: network off, read-only root, non-root user, no capabilities, CPU, memory, PID and time limits.",
  ],
];

export default function Trust() {
  return (
    <section className="section dark trust" id="trust">
      <div className="wrap">
        <Parallax speed={18} className="trust-sky">
          <Engraving name="sky" ink />
        </Parallax>
        <Label n={4}>The aegis</Label>
        <div className="grid trust-top">
          <div className="trust-intro">
            <Words className="h2" text="Tests decide. Models *never* do." />
            <p>
              No LLM reads the candidate&apos;s code to judge it. The score is a pure function of stored test results
              and the event log, so the same records always give the same number.
            </p>
            <div className="regrade">
              <span className="regrade-n display">
                <Counter to={100} />
              </span>
              <span className="regrade-n display">
                <Counter to={100} />
              </span>
              <p className="small">
                Submit, then Re-grade from the stored runs: the breakdowns are byte-identical.{" "}
                <Chip s="built" />
              </p>
            </div>
          </div>
          <Certificate />
        </div>

        <div className="grid trust-code">
          <div className="trust-code-text">
            <h3 className="h3">The whole correctness rule</h3>
            <p className="muted">
              From <code>backend/scoring/correctness.py</code>. Rates count the tests that failed on the starter and now
              pass; hidden tests weigh 70%, and breaking a test that used to pass costs you.
            </p>
          </div>
          <pre className="code">
            <span className="k">def</span> <span className="n">correctness</span>
            {`(visible_rate, hidden_rate, factor, regression=1.0):
    `}<span className="s">{`"""100 × (0.3 × visible_rate + 0.7 × hidden_rate)
       × regression_factor × perf_factor."""`}</span>{`
    `}<span className="k">if</span>{` visible_rate `}<span className="k">is None and</span>{` hidden_rate `}<span className="k">is None</span>{`:
        `}<span className="k">return</span>{` 0.0
    ...
    combined = VISIBLE_WEIGHT * visible_rate + HIDDEN_WEIGHT * hidden_rate
    `}<span className="k">return</span>{` 100.0 * combined * regression * factor

BANDS = [(80.0, `}<span className="s">&quot;strong&quot;</span>{`), (60.0, `}<span className="s">&quot;pass&quot;</span>{`), (45.0, `}<span className="s">&quot;borderline&quot;</span>{`)]`}
          </pre>
        </div>

        <div className="threats">
          <div className="threats-head">
            <div className="threats-shield" aria-hidden>
              <Engraving name="aegis" ink />
            </div>
            <h3 className="h3">What a candidate might try, and what stops it</h3>
            <p className="small">
              Threat model, BLUEPRINT §11. Known limit, stated there too: code inside the pytest process could forge a
              report that keeps the exact test ids. That is flagged for the recruiter, not prevented.
            </p>
          </div>
          <Reveal as="ol" className="threat-list" amount={0.1}>
            {THREATS.map(([attack, defence]) => (
              <Item as="li" key={attack}>
                <span className="threat-a">{attack}</span>
                <span className="threat-d">{defence}</span>
              </Item>
            ))}
          </Reveal>
        </div>

        <div className="numbers">
          <div>
            <span className="display"><Counter to={FACTS.backendTests} /></span>
            <span className="small">backend tests passing (make test)</span>
          </div>
          <div>
            <span className="display"><Counter to={FACTS.dockerTests} /></span>
            <span className="small">tests that start real sandbox containers</span>
          </div>
          <div>
            <span className="display"><Counter to={FACTS.visibleResultS} decimals={2} suffix=" s" /></span>
            <span className="small">median Run to visible result, down from 4.69 s</span>
          </div>
          <div>
            <span className="display"><Counter to={FACTS.e2eBrowserS + FACTS.e2eSeedS} prefix="~" suffix=" s" /></span>
            <span className="small">make e2e: seed, solve in headless Chromium, submit, check the report</span>
          </div>
        </div>
      </div>
    </section>
  );
}
