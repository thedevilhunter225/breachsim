import Link from "next/link";
import type { ReactNode } from "react";

import { BrandShield } from "@/components/brand-logo";
import { listLegalDocuments } from "@/lib/legal-documents";

export default async function LegalLayout({ children }: { children: ReactNode }) {
  const entries = await listLegalDocuments();
  const hasDraft = entries.some((entry) => entry.meta.status === "draft");

  return (
    <div className="page-shell flex min-h-screen flex-col text-ink">
      <header className="app-topbar sticky top-0 z-20">
        <div className="mx-auto flex w-full max-w-6xl items-center justify-between gap-3 px-4 py-3 sm:px-6">
          <Link href="/legal" className="flex min-w-0 items-center gap-2.5 rounded-md">
            <BrandShield className="h-7 w-7 shrink-0" />
            <span className="display-font text-[1.02rem] font-bold tracking-[-0.025em]">BreachSim</span>
            <span aria-hidden="true" className="text-subtle">
              /
            </span>
            <span className="truncate text-sm font-medium text-muted">Legal</span>
          </Link>
          <Link href="/login" className="btn-secondary btn-sm shrink-0">
            Sign in
          </Link>
        </div>
      </header>

      <main id="content" className="flex-1">
        {children}
      </main>

      <footer className="border-t border-line">
        <div className="mx-auto w-full max-w-6xl px-4 py-8 sm:px-6">
          <nav aria-label="Legal documents">
            <ul className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
              {entries.map((entry) => (
                <li key={entry.slug}>
                  <Link
                    href={`/legal/${entry.slug}`}
                    className="text-muted underline-offset-4 transition-colors hover:text-ink hover:underline"
                  >
                    {entry.meta.title}
                  </Link>
                </li>
              ))}
            </ul>
          </nav>
          {hasDraft ? (
            <p className="mt-4 max-w-3xl text-xs leading-5 text-muted">
              Documents marked as drafts are templates prepared from BreachSim’s documented product behaviour. They are
              not legal advice and must be reviewed by qualified counsel before they are relied on.
            </p>
          ) : null}
        </div>
      </footer>
    </div>
  );
}
