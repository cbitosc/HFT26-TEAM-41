import type { Metadata } from "next";
import Interview from "@/components/interview/Interview";
import { NAME } from "@/lib/site";
import "./interview.css";

export const metadata: Metadata = {
  title: `AI interview: ${NAME}`,
  description: "A ten-minute practice voice interview about your own project, running entirely in the browser.",
};

export default function InterviewPage() {
  return <Interview />;
}
