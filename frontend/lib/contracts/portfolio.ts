// Generated from contracts/portfolio.schema.json by `make contracts`. Do not edit.

/**
 * A date where each section after the year is optional, e.g. 2014-06-29 or 2023-04 (JSON Resume convention).
 */
export type Iso8601 = string;

/**
 * A candidate portfolio. Compatible with the JSON Resume schema (https://jsonresume.org/schema): every valid portfolio is also a valid JSON Resume document. Adds the required `assessment` extension.
 */
export interface Portfolio {
  /**
   * Link to the schema version the document follows.
   */
  $schema?: string;
  basics: Basics;
  skills?: Skill[];
  projects?: Project[];
  meta?: Meta;
  assessment: Assessment;
  [k: string]: unknown;
}
export interface Basics {
  name: string;
  label?: string;
  image?: string;
  email?: string;
  phone?: string;
  url?: string;
  summary?: string;
  location?: Location;
  profiles?: Profile[];
  [k: string]: unknown;
}
export interface Location {
  address?: string;
  postalCode?: string;
  city?: string;
  /**
   * ISO-3166-1 ALPHA-2 code, e.g. IN, US.
   */
  countryCode?: string;
  region?: string;
  [k: string]: unknown;
}
export interface Profile {
  network?: string;
  username?: string;
  url?: string;
  [k: string]: unknown;
}
export interface Skill {
  name?: string;
  level?: string;
  keywords?: string[];
  [k: string]: unknown;
}
export interface Project {
  name?: string;
  description?: string;
  highlights?: string[];
  /**
   * The project's tech stack (languages, frameworks, datastores, tools). Used to choose the domain task's runtime and seed.
   */
  keywords?: string[];
  startDate?: Iso8601;
  endDate?: Iso8601;
  url?: string;
  roles?: string[];
  entity?: string;
  type?: string;
  [k: string]: unknown;
}
export interface Meta {
  canonical?: string;
  version?: string;
  lastModified?: string;
  [k: string]: unknown;
}
/**
 * Extension to JSON Resume: what the candidate claims, used to build the assessment.
 */
export interface Assessment {
  /**
   * DSA topic name (snake_case, e.g. two_pointers) -> number of problems solved.
   */
  dsaTopicsSolved: {
    [k: string]: number;
  };
  githubUrls?: string[];
}
