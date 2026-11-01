import { Suspense } from "react";
import SessionIDE from "./SessionIDE";

async function Session({ params }: { params: PageProps<"/session/[id]">["params"] }) {
  const { id } = await params;
  return <SessionIDE sessionId={id} />;
}

export default function SessionPage({ params }: PageProps<"/session/[id]">) {
  return (
    <Suspense fallback={<p className="p-8 text-gray-500">Loading session…</p>}>
      <Session params={params} />
    </Suspense>
  );
}
