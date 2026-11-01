import { Suspense } from "react";
import Report from "./Report";

async function ReportLoader({ params }: { params: PageProps<"/report/[id]">["params"] }) {
  const { id } = await params;
  return <Report sessionId={id} />;
}

export default function ReportPage({ params }: PageProps<"/report/[id]">) {
  return (
    <Suspense fallback={<p className="p-8 text-gray-500">Loading report…</p>}>
      <ReportLoader params={params} />
    </Suspense>
  );
}
