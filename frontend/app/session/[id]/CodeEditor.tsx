"use client";

import Editor, { loader, type OnMount } from "@monaco-editor/react";
import { useEffect, useRef, useState } from "react";
import type { Telemetry } from "@/lib/telemetry";

const LANGUAGES: Record<string, string> = {
  py: "python",
  js: "javascript",
  jsx: "javascript",
  mjs: "javascript",
  cjs: "javascript",
  ts: "typescript",
  tsx: "typescript",
  json: "json",
  md: "markdown",
  yaml: "yaml",
  yml: "yaml",
  html: "html",
  css: "css",
  ini: "ini",
};

// Point @monaco-editor/react at the bundled Monaco (lib/monaco.ts) instead of its CDN
// default. Loaded once, in the browser only.
let monacoReady: Promise<void> | null = null;
function loadMonaco(): Promise<void> {
  monacoReady ??= import("@/lib/monaco").then(({ monaco }) => {
    loader.config({ monaco });
  });
  return monacoReady;
}

function languageOf(path: string): string {
  return LANGUAGES[path.split(".").pop() ?? ""] ?? "plaintext";
}

type Props = {
  taskId: string;
  path: string;
  initialValue: string;
  readOnly: boolean;
  telemetry: Telemetry;
  onChange: (value: string) => void;
};

/** One Monaco instance; each task file keeps its own model (and undo history) by path. */
export default function CodeEditor({ taskId, path, initialValue, readOnly, telemetry, onChange }: Props) {
  // Editor event handlers are registered once, so they read the current file from here.
  const current = useRef({ taskId, path, telemetry });
  const editorRef = useRef<Parameters<OnMount>[0] | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    loadMonaco().then(() => active && setReady(true));
    return () => {
      active = false;
    };
  }, []);

  useEffect(() => {
    current.current = { taskId, path, telemetry };
    const line = editorRef.current?.getPosition()?.lineNumber ?? 1;
    telemetry.setPosition(taskId, path, line);
  }, [taskId, path, telemetry]);

  const onMount: OnMount = (editor) => {
    editorRef.current = editor;
    editor.onDidChangeModelContent((e) => {
      if (e.isFlush) return; // model replaced programmatically, not typed
      let added = 0;
      let removed = 0;
      for (const change of e.changes) {
        added += change.text.length;
        removed += change.rangeLength;
      }
      const { taskId, path, telemetry } = current.current;
      telemetry.recordEdit(taskId, path, added, removed);
    });
    editor.onDidPaste((e) => {
      const chars = editor.getModel()?.getValueInRange(e.range).length ?? 0;
      current.current.telemetry.recordPaste(current.current.taskId, chars);
    });
    editor.onDidChangeCursorPosition((e) => {
      const { taskId, path, telemetry } = current.current;
      telemetry.setPosition(taskId, path, e.position.lineNumber);
    });
    editor.onDidFocusEditorText(() => current.current.telemetry.setEditorFocused(true));
    editor.onDidBlurEditorText(() => current.current.telemetry.setEditorFocused(false));
  };

  if (!ready) return <p className="p-4 text-sm text-gray-500">Loading editor…</p>;

  return (
    <Editor
      path={`${taskId}/${path}`}
      defaultValue={initialValue}
      language={languageOf(path)}
      onMount={onMount}
      onChange={(value) => onChange(value ?? "")}
      options={{
        readOnly,
        readOnlyMessage: { value: "This file is read-only." },
        minimap: { enabled: false },
        fontSize: 13,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 4,
      }}
    />
  );
}
