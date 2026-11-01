"use client";

import { EVENT, NAME, REPO_URL, TEAM, TEAM_LINE } from "@/lib/site";
import { Engraving, Label, Magnetic, Parallax } from "./fx";
import { Reveal, Item } from "./Reveal";

export default function Team() {
  return (
    <footer className="section dark team" id="team">
      <div className="wrap team-in">
        <Label n={9}>The makers</Label>
        <Reveal as="ul" className="team-list">
          {TEAM.map((m) => (
            <Item as="li" key={m.name}>
              <span className="display team-name">{m.name}</span>
              {m.role && <span className="inscr team-role">{m.role}</span>}
            </Item>
          ))}
        </Reveal>
        <div className="team-foot">
          <div className="team-motto">
            <Engraving name="wreath-bow" ink className="team-wreath" />
            <p>
              <span className="team-greek">ΓΝΩΘΙ ΣΕΑΥΤΟΝ</span>
              <span className="small">Know thyself. Cut above Apollo&apos;s temple at Delphi; we ask candidates to show it.</span>
            </p>
          </div>
          <div className="team-links">
            <p>
              {TEAM_LINE}, {EVENT}.
            </p>
            <Magnetic>
              <a href={REPO_URL} className="btn">
                Source on GitHub
              </a>
            </Magnetic>
          </div>
        </div>
      </div>
      <Parallax speed={6} className="team-coast">
        <Engraving name="coast" ink />
      </Parallax>
      <p className="display team-mark" aria-hidden>
        {NAME}
      </p>
    </footer>
  );
}
