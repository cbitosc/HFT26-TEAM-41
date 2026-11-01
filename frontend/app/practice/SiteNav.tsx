import Link from "next/link";
import { CODE_READING_URL, INTERVIEW_URL, SHOWCASE_URL } from "@/lib/site";

const LINK = "text-blue-700 underline";

/** Links between the platform's parts: practice problems, code reading, AI interview. */
export default function SiteNav() {
  return (
    <nav aria-label="Platform" className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
      <a href={SHOWCASE_URL} className={LINK}>
        Home
      </a>
      <Link href="/practice" className="font-medium text-gray-900 no-underline" aria-current="page">
        Practice
      </Link>
      <a href={CODE_READING_URL} className={LINK}>
        Code reading
      </a>
      <a href={INTERVIEW_URL} className={LINK}>
        AI interview
      </a>
    </nav>
  );
}
