import type { Metadata, Viewport } from "next";
import "@fontsource-variable/cormorant/wght.css";
import "@fontsource-variable/cormorant/wght-italic.css";
import "@fontsource-variable/cinzel/wght.css";
import "@fontsource-variable/eb-garamond/wght.css";
import "@fontsource-variable/archivo/wdth.css";
import "@fontsource-variable/jetbrains-mono/index.css";
import "./globals.css";
import "./sections.css";
import { NAME } from "@/lib/site";
import SmoothScroll from "@/components/SmoothScroll";

export const metadata: Metadata = {
  title: `${NAME}: coding assessments built from the candidate's own work`,
  description:
    "Turns a candidate's portfolio into a validated 60-minute coding assessment in their own stack, runs it in sandboxes and grades it with tests only.",
};

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f3eee3" },
    { media: "(prefers-color-scheme: dark)", color: "#0b1131" },
  ],
};

// Runs before first paint so the saved (or system) theme never flashes the other one.
const THEME = `try{var t=localStorage.getItem("theme");if(t!=="light"&&t!=="dark")t=matchMedia("(prefers-color-scheme: dark)").matches?"dark":"light";document.documentElement.dataset.theme=t}catch(e){}`;

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" suppressHydrationWarning>
      <head>
        <script dangerouslySetInnerHTML={{ __html: THEME }} />
      </head>
      <body>
        <SmoothScroll>{children}</SmoothScroll>
      </body>
    </html>
  );
}
