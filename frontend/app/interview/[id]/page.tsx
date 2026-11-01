import { Suspense } from "react";
import Interview from "./Interview";
import "./interview.css";

async function InterviewLoader({ params }: { params: PageProps<"/interview/[id]">["params"] }) {
  const { id } = await params;
  return <Interview sessionId={id} />;
}

export default function InterviewPage({ params }: PageProps<"/interview/[id]">) {
  return (
    <Suspense fallback={<p className="p-8 text-gray-500">Loading interview…</p>}>
      <InterviewLoader params={params} />
    </Suspense>
  );
}
