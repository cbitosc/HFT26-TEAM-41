"use client";

import Editor from "@monaco-editor/react";

const LANGUAGES: Record<string, string> = {
  py: "python",
  js: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  ts: "typescript",
  tsx: "typescript",
  jsx: "javascript",
  go: "go",
  rb: "ruby",
  java: "java",
  rs: "rust",
  c: "c",
  h: "c",
  cpp: "cpp",
  cc: "cpp",
  cs: "csharp",
  php: "php",
  kt: "kotlin",
  swift: "swift",
  md: "markdown",
  json: "json",
  yml: "yaml",
  yaml: "yaml",
  toml: "ini",
  sh: "shell",
};

function languageFor(path: string): string {
  const extension = path.split(".").pop()?.toLowerCase() ?? "";
  return LANGUAGES[extension] ?? "plaintext";
}

export function CodeEditor({
  path,
  value,
  readOnly,
  onChange,
}: {
  path: string;
  value: string;
  readOnly: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <Editor
      height="100%"
      path={path}
      language={languageFor(path)}
      theme="vs"
      value={value}
      onChange={(next) => onChange(next ?? "")}
      options={{
        readOnly,
        fontSize: 13,
        fontFamily: "IBM Plex Mono, ui-monospace, monospace",
        minimap: { enabled: false },
        wordWrap: "on",
        scrollBeyondLastLine: false,
        padding: { top: 12 },
      }}
    />
  );
}
