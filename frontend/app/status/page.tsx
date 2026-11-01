import Link from "next/link";
import { connection } from "next/server";
import { Suspense } from "react";

type Health = { status: string; db: boolean; redis: boolean };

const API_URL = process.env.API_URL ?? "http://localhost:8000";

async function fetchHealth(): Promise<Health> {
  const res = await fetch(`${API_URL}/health`, { cache: "no-store" });
  if (!res.ok) {
    throw new Error(`GET /health returned ${res.status}`);
  }
  return res.json();
}

function Indicator({ label, ok }: { label: string; ok: boolean }) {
  return (
    <li className="flex items-center justify-between gap-8 py-2">
      <span className="font-medium">{label}</span>
      <span className={ok ? "text-green-600" : "text-red-600"}>{ok ? "up" : "down"}</span>
    </li>
  );
}

async function HealthStatus() {
  // Render per request; otherwise the build prerenders this and logs an aborted fetch.
  await connection();
  let health: Health;
  try {
    health = await fetchHealth();
    console.log(`[health] ${API_URL}/health ->`, JSON.stringify(health));
  } catch (err) {
    console.error(`[health] ${API_URL}/health failed:`, err);
    return <p className="text-red-600">API unreachable at {API_URL}</p>;
  }

  return (
    <ul className="divide-y divide-gray-200">
      <Indicator label="API" ok={health.status === "ok"} />
      <Indicator label="Postgres" ok={health.db} />
      <Indicator label="Redis" ok={health.redis} />
    </ul>
  );
}

export default function Status() {
  return (
    <main className="mx-auto max-w-md p-8">
      <h1 className="mb-4 text-2xl font-semibold">System health</h1>
      <Suspense fallback={<p className="text-gray-500">Checking…</p>}>
        <HealthStatus />
      </Suspense>
      <Link href="/practice" className="mt-6 inline-block text-blue-700 underline">
        Practice problems
      </Link>
    </main>
  );
}
