import type { SnapshotFile } from "./types";

export function llmConfig(): { key: string; base: string; model: string } | null {
  const key = process.env.LLM_API_KEY?.trim();
  if (!key) return null;
  return {
    key,
    base: (process.env.LLM_BASE_URL || "https://api.openai.com/v1").replace(/\/$/, ""),
    model: process.env.LLM_MODEL || "gpt-4o-mini",
  };
}

export function systemPrompt(input: {
  title: string;
  body: string;
  repo: string;
  files: SnapshotFile[];
}): string {
  const files = input.files
    .map((file) => {
      const body = file.content.length > 4000 ? `${file.content.slice(0, 4000)}\n…` : file.content;
      return `FILE ${file.path}\n${body}`;
    })
    .join("\n\n")
    .slice(0, 14000);

  return [
    "You are the assistant beside the editor in a 60-minute code comprehension round.",
    "The candidate must read this unfamiliar code, fix the reported bug, and then describe one efficiency improvement.",
    "Help them reason. When you suggest a change, say how they can check it. Do not claim you edited the files.",
    "If you are unsure, say so. A vague answer is worse than a short one.",
    `Repository: ${input.repo}`,
    `Issue: ${input.title}`,
    input.body.slice(0, 2500),
    files,
  ].join("\n\n");
}
