import { readFile } from "node:fs/promises";
import path from "node:path";

import { parseLegalDocument, type BlockNode, type LegalMeta } from "./legal-markdown";

/**
 * Published legal templates, in display order. Each slug is also the Markdown file name in
 * `content/legal`, which is the single source of truth for the /legal pages. The directory
 * lives inside frontend/ so the frontend Docker build context includes it.
 */
export const LEGAL_DOCUMENT_SLUGS = [
  "privacy",
  "terms",
  "dpa",
  "subprocessors",
  "simulation-authorization",
  "employee-notice",
] as const;

export type LegalSlug = (typeof LEGAL_DOCUMENT_SLUGS)[number];

export type LegalDocument = { slug: LegalSlug; meta: LegalMeta; blocks: BlockNode[] };

export function legalContentDirectory(): string {
  return path.join(process.cwd(), "content", "legal");
}

export function isLegalSlug(value: string): value is LegalSlug {
  return (LEGAL_DOCUMENT_SLUGS as readonly string[]).includes(value);
}

async function loadLegalDocument(slug: LegalSlug): Promise<LegalDocument> {
  const source = await readFile(path.join(legalContentDirectory(), `${slug}.md`), "utf8");
  return { slug, ...parseLegalDocument(source, slug) };
}

/** Only allow-listed slugs ever reach the filesystem, so a crafted URL cannot name another file. */
export async function getLegalDocument(slug: string): Promise<LegalDocument | null> {
  return isLegalSlug(slug) ? loadLegalDocument(slug) : null;
}

export async function listLegalDocuments(): Promise<LegalDocument[]> {
  return Promise.all(LEGAL_DOCUMENT_SLUGS.map(loadLegalDocument));
}
