"use client";

import { Engraving, Label, Parallax, Tilt, Words } from "./fx";
import { Reveal, Item } from "./Reveal";

export default function Problem() {
  return (
    <section className="section problem" id="problem">
      <div className="wrap grid problem-grid">
        <div className="problem-text">
          <Label n={0}>The riddle</Label>
          <Words
            className="problem-claim"
            text="A LeetCode medium says nothing about whether someone can find a bug in a *FastAPI* service."
          />
          <Words
            className="problem-claim problem-claim-b"
            text="And a take-home in 2026 measures the candidate’s *AI* about as much as the candidate."
            delay={0.15}
          />
          <Reveal className="problem-body">
            <Item as="p">
              Generic tests ignore what the candidate says they&apos;ve built. Take-homes say more, but you can&apos;t
              tell who, or what, wrote the code.
            </Item>
            <Item as="p">
              We wanted a test about the candidate&apos;s own claimed work, in their own stack, that an AI can&apos;t
              finish on its own, and whose score depends on nobody&apos;s judgement. Not a reviewer&apos;s, and not a
              model&apos;s.
            </Item>
          </Reveal>
        </div>

        <figure className="problem-fig">
          <Parallax speed={10}>
            <Tilt className="problem-tilt">
              <Engraving name="hermes" alt="Bust of Hermes in a winged hat" />
            </Tilt>
          </Parallax>
          <figcaption>
            <span className="inscr">Plate II · Hermes</span>
            <span className="small">Messenger of the gods, and patron of tricksters. In 2026 he does take-homes.</span>
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
