import type { Metadata } from "next";
import type { ReactNode } from "react";
import "@fontsource-variable/cormorant-garamond/wght.css";
import "@fontsource-variable/cormorant-garamond/wght-italic.css";
import "@fontsource-variable/inter-tight/wght.css";
import "@fontsource-variable/jetbrains-mono/wght.css";
import "lenis/dist/lenis.css";
import "./olympus.css";
import Shell from "@/components/olympus/Shell";

export const metadata: Metadata = {
  title: "Areté — prove your excellence",
  description:
    "A technical assessment forged from your own record: résumé, GitHub, LeetCode and Codeforces become a personalised trial, a code-comprehension labyrinth and a voice interview.",
};

export default function OlympusLayout({ children }: { children: ReactNode }) {
  return <Shell>{children}</Shell>;
}
