"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

export function StartRound({ taskId }: { taskId: string }) {
  const router = useRouter();
  const [pending, setPending] = useState(false);
  const [error, setError] = useState("");

  async function start() {
    setPending(true);
    setError("");
    const response = await fetch("/api/sessions", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ taskId }),
    });
    const data = (await response.json()) as { id?: string; error?: string };
    if (!response.ok || !data.id) {
      setError(data.error || "Could not start the round");
      setPending(false);
      return;
    }
    router.push(`/session/${data.id}`);
  }

  return (
    <div className="flex flex-col items-end gap-2">
      <button
        type="button"
        onClick={start}
        disabled={pending}
        className="bg-accent text-paper rounded-full px-4 py-2 text-sm disabled:opacity-60"
      >
        {pending ? "Preparing snapshot…" : "Start round"}
      </button>
      {error ? <p className="text-sm text-red-800">{error}</p> : null}
    </div>
  );
}
