import { Suspense } from "react";
import PracticeIDE from "./PracticeIDE";

async function Problem({ params }: { params: PageProps<"/practice/[id]">["params"] }) {
  const { id } = await params;
  return <PracticeIDE problemId={id} />;
}

export default function PracticeProblemPage({ params }: PageProps<"/practice/[id]">) {
  return (
    <Suspense fallback={<p className="p-8 text-gray-500">Loading problem…</p>}>
      <Problem params={params} />
    </Suspense>
  );
}
