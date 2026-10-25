import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { ArrowRight, FileSignature, Handshake, Megaphone, Scale, Server, ShieldCheck } from "lucide-react";

import { listLegalDocuments, type LegalSlug } from "@/lib/legal-documents";

import { DraftNotice, StatusBadge } from "./legal-ui";

const ICON_CLASS = "h-5 w-5";

const DOCUMENT_ICONS: Record<LegalSlug, ReactNode> = {
  privacy: <ShieldCheck aria-hidden="true" className={ICON_CLASS} />,
  terms: <Scale aria-hidden="true" className={ICON_CLASS} />,
  dpa: <Handshake aria-hidden="true" className={ICON_CLASS} />,
  subprocessors: <Server aria-hidden="true" className={ICON_CLASS} />,
  "simulation-authorization": <FileSignature aria-hidden="true" className={ICON_CLASS} />,
  "employee-notice": <Megaphone aria-hidden="true" className={ICON_CLASS} />,
};

export async function generateMetadata(): Promise<Metadata> {
  const entries = await listLegalDocuments();
  const hasDraft = entries.some((entry) => entry.meta.status === "draft");
  return {
    title: "Legal documents",
    description: "Privacy, terms, data processing and simulation authorization documents for BreachSim.",
    // Unreviewed templates should not be indexed as if they were published terms.
    robots: hasDraft ? { index: false, follow: false } : undefined,
  };
}

export default async function LegalIndexPage() {
  const entries = await listLegalDocuments();
  const hasDraft = entries.some((entry) => entry.meta.status === "draft");

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6 sm:py-12">
      <div className="max-w-3xl">
        <p className="section-title">Legal</p>
        <h1 className="display-font mt-3 text-[2rem] font-semibold leading-tight sm:text-[2.5rem]">Legal documents</h1>
        <p className="mt-3 text-[0.95rem] leading-7 text-muted">
          How BreachSim handles the personal data of the organisations that use it and of the people taking part in
          their awareness programmes, and the documents that govern an authorized simulation programme.
        </p>
      </div>

      {hasDraft ? <DraftNotice className="mt-6 max-w-3xl" /> : null}

      <ul className="mt-8 grid gap-4 md:grid-cols-2">
        {entries.map((entry) => (
          <li key={entry.slug} className="min-w-0">
            <Link href={`/legal/${entry.slug}`} className="card card-interactive flex h-full flex-col p-5 sm:p-6">
              <div className="flex items-start justify-between gap-3">
                <span className="grid h-10 w-10 shrink-0 place-items-center rounded-lg border border-line bg-surface-muted text-muted">
                  {DOCUMENT_ICONS[entry.slug]}
                </span>
                <StatusBadge status={entry.meta.status} />
              </div>
              <h2 className="mt-4 text-[1.08rem] font-semibold leading-snug text-ink">{entry.meta.title}</h2>
              {entry.meta.audience ? (
                <p className="mt-1 text-[0.78rem] font-medium leading-5 text-muted">{entry.meta.audience}</p>
              ) : null}
              {entry.meta.summary ? (
                <p className="mt-3 text-[0.88rem] leading-6 text-muted">{entry.meta.summary}</p>
              ) : null}
              <span className="mt-auto inline-flex items-center gap-1.5 pt-5 text-[0.86rem] font-semibold text-ink">
                Read document
                <ArrowRight aria-hidden="true" className="h-4 w-4" />
              </span>
            </Link>
          </li>
        ))}
      </ul>
    </div>
  );
}
