# Showcase design brief

A one-page site for the live presentation (2026-10-31, 8:30). Audience: hackathon
judges and engineers. Its job: in five minutes of scrolling, show that this is a
real, working verification system, and be honest about what isn't built yet.

## Research notes

**Awwwards.** A jury-judged showcase of web design. Each site is scored on design,
usability, creativity and content (content counts, it is not decoration). The
Site-of-the-Day winners we looked at share a few habits: one strong idea carried
through the whole page instead of many small effects; type used as image (very
large, set tightly, often wide or condensed); restrained palettes with one accent;
motion tied to scroll position so the reader controls the pace; real product
material instead of illustration; and generous, uneven whitespace on a visible grid.

**supermemory.ai** (full-page capture, 1440 px, 6390 px tall).
- Layout: a fixed left rail (logo, page nav, an "on this page" index) and one
  narrow reading column (~640 px) on the right. Reads like documentation, not a
  marketing page. Hairline borders, square corners.
- Type: one family, Geist (17 px body, 40 px H1 at weight 400, nothing bold),
  Geist Mono at 11–12 px for buttons and small labels. A quiet, flat scale; the
  headline is set light rather than heavy.
- Colour: white, near-black text, one saturated blue for actions, links and the
  one highlighted bar in each chart. Imagery is blue/orange halftone photography.
- Motion: very little. Hover states and a sticky index. Confidence comes from
  content, not animation.
- Rhythm: short sections separated by hairlines; a "proof" block of real numbers
  (latency table, token chart, benchmark bars) with sources linked.
- Product: shown as numbers and charts with citations, not screenshots.
- Take-away for us: real numbers, cited; one accent; quiet type; let proof carry it.

**hermes-agent.nousresearch.com** (Nous Research, raw HTML and CSS read 2026-10-31).
- A classical engraving (a many-armed Hermes in a sunburst of ray-lines) fused with
  technical marks: halftone, UI windows, a cobalt accent (#0847c4) on black and white.
- Type: EB Garamond for display, condensed gothics for labels, a mono for UI.
- Structure is a plain product page (hero, downloads, six numbered features, FAQ,
  pricing); the myth lives in the imagery and the name, not in the story.
- Take-away for us: the engraving-meets-machine look works. We go further by letting
  each myth carry a section's meaning, not just decorate it.

**hackerrank.com.** A capture wasn't possible: the site's Akamai bot wall returns
"Access Denied" to headless Chromium, and we didn't get around it. Notes below come
from our own familiarity with the public site, not from a fresh capture.
- Layout: a centered marketing hero with product UI mockups, logo walls, then
  alternating text/image rows; a dark navy and bright green palette; bold
  geometric sans; customer logos and big numbers as social proof.
- Take-away for us, mostly by contrast: this is the category's default look
  (centered, logo-wall proof, alternating rows). We have no customers and won't
  pretend to, so our proof is test counts, timings and the code itself.

## Name

**Apollo**, god of truth; his oracle at Delphi bore "Know thyself" and never handed
anyone an answer, which is the assistant's rule. The voice interviewer is **Athena**,
who founded the first court in the Eumenides. Both live in `lib/site.ts` (`NAME`,
`AGENT`).

## Direction: "engraved porcelain"

Greek myth, chosen because its best-known stories are about fair judgement and
finding the truth, which is what the product does. Every section is one plate, named
with a Greek numeral, and the myth is the argument, not decoration:

| Section | Myth | Why it fits |
| --- | --- | --- |
| Hero | Athena, with an astrolabe as her halo | She founds the first court in the Eumenides: evidence heard, votes counted |
| Α΄ The riddle | Hermes | Patron of tricksters: who really wrote the take-home? |
| Β΄ The voyage | A ship sailing seven ports; Pegasus crosses | The pipeline as a route; each port has an emblem (scroll, compass, amphora, arch, torch, helmet, laurel) |
| Γ΄ Ariadne's thread | The labyrinth and the Minotaur | The Trail Map is the thread through the code; the bug node is the bull |
| Δ΄ Three orders | Plain, Ionic, Corinthian columns | Novice to Master: plainer to more ornate as the problem grows |
| Ε΄ The aegis | Athena's shield, the night sky | The threat model; fixed laws like the stars, so the score is reproducible |
| Ϛ΄ It runs today | none | Real screenshots of the running app, no myth needed |
| Ζ΄ The oracle | Delphi | Answers in hints, never solutions; then the oracle speaks (voice interview) |
| Η΄ The ascent | Steps | Phases drawn as rising stairs |
| Θ΄ The temple | A temple | Columns that don't touch (strict boundaries) on the database base |
| Ι΄ The makers | ΓΝΩΘΙ ΣΕΑΥΤΟΝ, Delphi's motto | Know thyself: what we ask candidates to show |

Two surfaces: **parchment** with cobalt engraving ink (what people read) and **lapis
night** with laurel gold (where code runs and is judged: aegis, oracle, footer, and
the interview page).

**Dark theme.** A sun/moon toggle in the header switches the whole page to night:
lapis paper, moonlit-cream headings, engravings printed as pale porcelain-blue
negatives, gold accents. The choice is saved per browser (`localStorage`, wrapped in
try/catch); without one the page follows the system setting. An inline script in
`<head>` sets `data-theme` before first paint, and a `prefers-color-scheme` block
covers visitors without JavaScript. The validation certificate stays parchment in
both themes.

## Imagery

Single engravings cut from the team's asset sheets by `scripts/cut-greek.mjs` into
`public/greek/`, at 4x the sheet resolution. The sheets are first upscaled 4x with
Real-ESRGAN (`scripts/upscale-sheets.py`); each crop blends 35% of that (crisp
outlines) with 65% sharpened Lanczos (keeps the stipple and hatching, which ESRGAN
alone smooths into flat cartoon shading). Then: ink density to alpha, flood-fill
from a seed to drop neighbouring drawings, holes filled for an opaque silhouette.
Each asset is two alpha masks, `-ink` (line work) and `-sil` (silhouette), coloured
by CSS tokens (`--engr-ink`, `--engr-paper`) so both themes share one set of files;
`<Engraving ink>` prints the line work alone in `currentColor`. Masks load when an
engraving comes within 1200 px of the viewport. Scenes (ship, arch, coast, amphora)
are kept whole with feathered edges.
Vector ornaments (astrolabe, meander, stars, temple) are drawn in SVG/CSS so they
stay crisp at any size.

## Type

- Display: **Cormorant** (variable, with italic), light and large; italics mark the
  one accented word in a heading.
- Inscriptions: **Cinzel**, small, tracked capitals for labels and captions.
- Greek letters: **EB Garamond**, a per-glyph fallback (Cormorant has no Greek).
- Text: **Archivo** at normal width, 18 px / 1.62; code: **JetBrains Mono**.
- All self-hosted via Fontsource.

## Palette

| Token | Hex | Role |
| --- | --- | --- |
| paper | #F3EEE3 | parchment background |
| ink | #1B2D8F | engraving ink: headings, art, rules |
| text-ink | #232853 | body text on paper |
| sandbox (night) | #0A1034 | lapis night sections |
| gold-hi / gold | #E2C27A / #A9822F | accents on night, seals, the progress bar |
| accent | #2442C9 | links and pass marks on paper |
| thread / fail | #B4432F | Ariadne's thread, failing tests |

Token names are shared with the interview and code-reading pages, so those pages
follow the theme without their own changes.

## Motion and interaction

- Opening plate: a laurel and a count to 100, then the curtain lifts (once per tab).
- Hero: four depth layers (astrolabe, Athena, stars, the name) shift with the
  pointer; on scroll Athena rises out of the letters and the astrolabe turns.
- Headings rise word by word out of a mask; an inscription marquee follows scroll
  velocity; Pegasus crosses the screen on the way into the voyage.
- The voyage is sticky and scroll-scrubbed: emblem, numeral and panel change per
  port while the ship sails the route.
- Hover: magnetic buttons, 3D tilt with a sheen on engravings, rolling nav labels,
  lifting tier cards. The system cursor is kept.
- The oracle orb (components/OracleOrb.tsx): one WebGL shader, a marbled porcelain
  sphere with engraving hatch lines inside a corona of hair-thin rays that follow the
  audio level; an orbit with three dots while thinking, ripples on spoken words. Used
  on the home page and as Athena, the interviewer, on /interview.
- Only transform, opacity and clip-path animate. `prefers-reduced-motion` removes
  the intro, Lenis, parallax and the loops; final states show at once.

## What we're avoiding

Glass cards, icon-in-circle feature grids, three identical feature cards, logo walls,
invented numbers, stock art, and myth for its own sake: if a section's myth doesn't
explain the section, it goes. Copy speaks like the engineers who built it: what it
does, how, and what's not done yet.
