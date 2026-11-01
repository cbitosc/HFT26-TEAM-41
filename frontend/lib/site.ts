// Where the other parts of the platform run (see README "Local Setup"). NEXT_PUBLIC_*
// values are read when `next dev` / `next build` starts.
export const SHOWCASE_URL = process.env.NEXT_PUBLIC_SHOWCASE_URL ?? "http://localhost:3001";
/** The code-reading app, code-compr/. */
export const CODE_READING_URL = process.env.NEXT_PUBLIC_CODE_READING_URL ?? "http://localhost:3002";
/** The browser AI interview page of the showcase site. */
export const INTERVIEW_URL = `${SHOWCASE_URL}/interview`;
