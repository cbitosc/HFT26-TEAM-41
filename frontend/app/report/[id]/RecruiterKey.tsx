"use client";

// The recruiter key (X-Recruiter-Key) for the report's recruiter tabs, kept in sessionStorage
// for this browser tab only.
import { useState } from "react";

const KEY_STORAGE = "recruiter-key";

export function readKey(): string {
  try {
    return sessionStorage.getItem(KEY_STORAGE) ?? "";
  } catch {
    return "";
  }
}

export function saveKey(key: string): void {
  try {
    if (key) sessionStorage.setItem(KEY_STORAGE, key);
    else sessionStorage.removeItem(KEY_STORAGE);
  } catch {
    // Private mode: the key is asked for again next time.
  }
}

export function KeyForm({ error, onKey }: { error: string | null; onKey: (key: string) => void }) {
  const [draft, setDraft] = useState("");
  return (
    <form
      className="flex max-w-md flex-col gap-2"
      onSubmit={(e) => {
        e.preventDefault();
        saveKey(draft);
        onKey(draft);
      }}
    >
      <label className="text-sm text-gray-700" htmlFor="recruiter-key">
        Recruiter key
      </label>
      <div className="flex gap-2">
        <input
          id="recruiter-key"
          type="password"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          className="flex-1 rounded border border-gray-300 px-2 py-1.5 text-sm"
          data-testid="recruiter-key"
        />
        <button className="rounded bg-blue-600 px-4 py-1.5 text-sm font-medium text-white">Show</button>
      </div>
      {error && <p className="text-sm text-red-700">{error}</p>}
    </form>
  );
}
