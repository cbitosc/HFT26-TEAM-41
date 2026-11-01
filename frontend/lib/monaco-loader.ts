// Points @monaco-editor/react at the bundled Monaco (lib/monaco.ts) instead of its CDN
// default. Loaded once, in the browser only.
import { loader } from "@monaco-editor/react";

let monacoReady: Promise<void> | null = null;

export function loadMonaco(): Promise<void> {
  monacoReady ??= import("@/lib/monaco").then(({ monaco }) => {
    loader.config({ monaco });
  });
  return monacoReady;
}
