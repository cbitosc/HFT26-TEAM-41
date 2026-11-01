"use client";

import Editor, { loader } from "@monaco-editor/react";
import { useEffect, useState } from "react";

// Same bundled Monaco as the session IDE (lib/monaco.ts, no CDN), with a night theme:
// lapis background, moonlight text, gilded strings.
let ready: Promise<void> | null = null;
function loadMonaco(): Promise<void> {
  ready ??= import("@/lib/monaco").then(({ monaco }) => {
    monaco.editor.defineTheme("olympus-night", {
      base: "vs-dark",
      inherit: true,
      rules: [
        { token: "", foreground: "e9e4d4" },
        { token: "comment", foreground: "6f76a3", fontStyle: "italic" },
        { token: "keyword", foreground: "8fa2ff" },
        { token: "string", foreground: "e2c286" },
        { token: "number", foreground: "f2a990" },
        { token: "type", foreground: "9fd8ff" },
        { token: "delimiter", foreground: "a9add0" },
        { token: "identifier", foreground: "e9e4d4" },
      ],
      colors: {
        "editor.background": "#0c1238",
        "editor.foreground": "#e9e4d4",
        "editorLineNumber.foreground": "#3c4478",
        "editorLineNumber.activeForeground": "#e2c286",
        "editor.lineHighlightBackground": "#151d4e",
        "editor.selectionBackground": "#2a3a9a",
        "editorCursor.foreground": "#e2c286",
        "editorIndentGuide.background1": "#1c2558",
        "editorWidget.background": "#101744",
        "scrollbarSlider.background": "#2a336a80",
      },
    });
    loader.config({ monaco });
  });
  return ready;
}

const LANG: Record<string, string> = { py: "python", js: "javascript", ts: "typescript", md: "markdown", json: "json", yml: "yaml", yaml: "yaml" };

export default function CodePane({
  path,
  value,
  readOnly = false,
  onChange,
}: {
  path: string;
  value: string;
  readOnly?: boolean;
  onChange?: (v: string) => void;
}) {
  const [ok, setOk] = useState(false);
  useEffect(() => {
    let live = true;
    loadMonaco().then(() => live && setOk(true));
    return () => {
      live = false;
    };
  }, []);
  if (!ok) return <p className="shimmer mono p-6 text-[13px]">Unrolling the scroll…</p>;
  return (
    <Editor
      path={path}
      defaultValue={value}
      language={LANG[path.split(".").pop() ?? ""] ?? "plaintext"}
      theme="olympus-night"
      onChange={(v) => onChange?.(v ?? "")}
      options={{
        readOnly,
        readOnlyMessage: { value: "Read-only in this trial." },
        minimap: { enabled: false },
        fontSize: 13.5,
        fontFamily: "'JetBrains Mono Variable', ui-monospace, monospace",
        fontLigatures: true,
        lineHeight: 22,
        padding: { top: 16 },
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 4,
        renderLineHighlight: "all",
        smoothScrolling: true,
        cursorBlinking: "smooth",
        cursorSmoothCaretAnimation: "on",
      }}
    />
  );
}
