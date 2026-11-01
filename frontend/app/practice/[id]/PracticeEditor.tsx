"use client";

import Editor from "@monaco-editor/react";
import { useEffect, useState } from "react";
import { loadMonaco } from "@/lib/monaco-loader";

type Props = {
  /** Unique per problem and language: each keeps its own Monaco model and undo history. */
  modelPath: string;
  language: string;
  value: string;
  onChange: (value: string) => void;
};

export default function PracticeEditor({ modelPath, language, value, onChange }: Props) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    let active = true;
    loadMonaco().then(() => active && setReady(true));
    return () => {
      active = false;
    };
  }, []);

  if (!ready) return <p className="p-4 text-sm text-gray-500">Loading editor…</p>;

  return (
    <Editor
      path={modelPath}
      language={language}
      value={value}
      onChange={(v) => onChange(v ?? "")}
      options={{
        minimap: { enabled: false },
        fontSize: 14,
        scrollBeyondLastLine: false,
        automaticLayout: true,
        tabSize: 4,
        padding: { top: 8 },
      }}
    />
  );
}
