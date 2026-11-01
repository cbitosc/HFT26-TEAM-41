import type { Metadata } from "next";
import Comprehension from "@/components/comprehension/Comprehension";
import { NAME } from "@/lib/site";
import "./comprehension.css";

export const metadata: Metadata = {
  title: `Code comprehension: ${NAME}`,
  description:
    "A practice round on an unfamiliar codebase: read the issue, fix the bug, name one efficiency gain. Runs entirely in the browser.",
};

export default function ComprehensionPage() {
  return <Comprehension />;
}
