import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft, ArrowRight } from "lucide-react";

import { getLegalDocument, LEGAL_DOCUMENT_SLUGS, listLegalDocuments } from "@/lib/legal-documents";
import { extractHeadings, LegalMarkdown, type HeadingLink } from "@/lib/legal-markdown";

import { DraftNotice, StatusBadge } from "../legal-ui";

type LegalDocumentPageProps = { params: Promise<{ slug: string }> };

// Only the documents in content/legal exist; any other slug is a 404.
export const dynamicParams = false;

export function generateStaticParams() {
  return LEGAL_DOCUMENT_SLUGS.map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: LegalDocumentPageProps): Promise<Metadata> {
  const { slug } = await params;
  const legalDocument = await getLegalDocument(slug);
  if (!legalDocument) return { title: "Legal document not found" };
  return {
    title: legalDocument.meta.title,
    description: legalDocument.meta.summary ?? undefined,
    // Unreviewed templates should not be indexed as if they were published terms.
    robots: legalDocument.meta.status === "draft" ? { index: false, follow: false } : undefined,
  };
}

function ContentsList({ headings }: { headings: HeadingLink[] }) {
  return (
    <ol className="space-y-1.5 text-[0.84rem] leading-5">
      {headings.map((heading) => (
        <li key={heading.id}>
          <a href={`#${heading.id}`} className="block rounded text-muted transition-colors hover:text-ink">
            {heading.text}
          </a>
        </li>
      ))}
    </ol>
  );
}

export default async function LegalDocumentPage({ params }: LegalDocumentPageProps) {
  const { slug } = await params;
  const legalDocument = await getLegalDocument(slug);
  if (!legalDocument) notFound();

  const { meta, blocks } = legalDocument;
  const headings = extractHeadings(blocks);
  const related = (await listLegalDocuments()).filter((entry) => entry.slug !== legalDocument.slug);

  return (
    <div className="mx-auto w-full max-w-6xl px-4 py-6 sm:px-6 sm:py-10">
      <Link
        href="/legal"
        className="inline-flex items-center gap-1.5 rounded text-[0.86rem] font-medium text-muted transition-colors hover:text-ink"
      >
        <ArrowLeft aria-hidden="true" className="h-4 w-4" />
        All legal documents
      </Link>

      <header className="mt-5 max-w-3xl">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
          <StatusBadge status={meta.status} />
          {meta.audience ? <span className="text-[0.8rem] leading-5 text-muted">{meta.audience}</span> : null}
        </div>
        <h1 className="display-font mt-3 text-[2rem] font-semibold leading-tight sm:text-[2.5rem]">{meta.title}</h1>
        {meta.summary ? <p className="mt-3 text-[0.95rem] leading-7 text-muted">{meta.summary}</p> : null}
        <p className="mt-3 text-[0.82rem] text-muted">
          Last reviewed: <span className="text-ink">{meta.lastReviewed ?? "Not yet reviewed"}</span>
        </p>
      </header>

      {meta.status === "draft" ? <DraftNotice className="mt-6 max-w-3xl" /> : null}

      <div className="mt-8 grid gap-6 lg:grid-cols-[minmax(0,1fr)_15rem] lg:gap-10">
        {headings.length ? (
          <aside className="min-w-0 lg:sticky lg:top-24 lg:col-start-2 lg:row-start-1 lg:self-start">
            <details className="card-muted px-4 py-3 lg:hidden">
              <summary className="cursor-pointer text-[0.86rem] font-semibold text-ink">Contents</summary>
              <nav aria-label="Contents" className="mt-3">
                <ContentsList headings={headings} />
              </nav>
            </details>
            <nav aria-label="Contents" className="hidden lg:block">
              <p className="section-title">On this page</p>
              <div className="mt-3">
                <ContentsList headings={headings} />
              </div>
            </nav>
          </aside>
        ) : null}

        <article className="enterprise-card min-w-0 break-words px-5 py-6 text-[0.95rem] leading-7 text-ink sm:px-8 sm:py-8 lg:col-start-1 lg:row-start-1 [&>*:first-child]:mt-0">
          <LegalMarkdown blocks={blocks} />
        </article>
      </div>

      {related.length ? (
        <section aria-labelledby="related-documents" className="mt-12">
          <h2 id="related-documents" className="section-title">
            Other legal documents
          </h2>
          <ul className="mt-4 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {related.map((entry) => (
              <li key={entry.slug} className="min-w-0">
                <Link
                  href={`/legal/${entry.slug}`}
                  className="card card-interactive flex h-full items-center justify-between gap-3 px-4 py-3.5"
                >
                  <span className="min-w-0 text-[0.9rem] font-semibold text-ink">{entry.meta.title}</span>
                  <ArrowRight aria-hidden="true" className="h-4 w-4 shrink-0 text-muted" />
                </Link>
              </li>
            ))}
          </ul>
        </section>
      ) : null}
    </div>
  );
}
