import Header from "@/components/Header";
import Intro from "@/components/Intro";
import Hero from "@/components/Hero";
import Marquee from "@/components/Marquee";
import Try from "@/components/Try";
import Problem from "@/components/Problem";
import Pipeline from "@/components/Pipeline";
import TrailMap from "@/components/TrailMap";
import Tiers from "@/components/Tiers";
import Trust from "@/components/Trust";
import Assistant from "@/components/Assistant";
import Product from "@/components/Product";
import Progress from "@/components/Progress";
import Stack from "@/components/Stack";
import Team from "@/components/Team";

const BAND = [
  "Your own stack",
  "Your own domain",
  "Sixty minutes",
  "Validated before it ships",
  "Sandboxed, network off",
  "Graded by tests alone",
  "Re-graded to the byte",
];

export default function Page() {
  return (
    <>
      <Intro />
      <Header />
      <main>
        <Hero />
        <Marquee items={BAND} />
        <Try />
        <Problem />
        <Pipeline />
        <TrailMap />
        <Tiers />
        <Trust />
        <Product />
        <Assistant />
        <Progress />
        <Stack />
      </main>
      <Team />
    </>
  );
}
