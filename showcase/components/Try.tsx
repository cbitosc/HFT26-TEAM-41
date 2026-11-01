import Link from "next/link";
import { Reveal, Item } from "./Reveal";
import { PRACTICE_URL } from "@/lib/site";

// The three things a visitor can do on the platform. Practice is the FastAPI-backed app
// (frontend/ in this repo); the other two run entirely in the browser on this site.
const TOOLS: { id: string; title: string; body: string; cta: string; href: string; external?: boolean }[] = [
  {
    id: "practice",
    title: "Practice problems",
    body: "A problem list and an in-browser editor (Monaco). Write Python or JavaScript, run it on the examples or your own input, then submit against hidden cases. Code runs in a locked-down sandbox on the server.",
    cta: "Open the problems",
    href: PRACTICE_URL,
    external: true,
  },
  {
    id: "reading",
    title: "Code reading",
    body: "Read an unfamiliar repository, ask the assistant questions, and propose a fix. The review scores how you investigated and how you used the AI, not only the patch.",
    cta: "Start the exercise",
    href: "/comprehension",
  },
  {
    id: "interview",
    title: "AI mock interview",
    body: "A ten-minute spoken interview about your own project. It adapts its follow-ups to how much you say, and runs entirely in your browser.",
    cta: "Start the interview",
    href: "/interview",
  },
];

export default function Try() {
  return (
    <section className="section" id="try">
      <div className="wrap">
        <p className="label">Try it</p>
        <h2 className="h2">Practise the three things we assess.</h2>
        <Reveal as="ul" className="try-list" amount={0.15}>
          {TOOLS.map((t) => (
            <Item as="li" key={t.id} className="try-card">
              <h3 className="h3">{t.title}</h3>
              <p className="small">{t.body}</p>
              {t.external ? (
                <a href={t.href} className="try-cta">
                  {t.cta} →
                </a>
              ) : (
                <Link href={t.href} className="try-cta">
                  {t.cta} →
                </Link>
              )}
            </Item>
          ))}
        </Reveal>
      </div>
    </section>
  );
}
