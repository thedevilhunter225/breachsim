import clsx from "clsx";
import { TriangleAlert } from "lucide-react";

import type { LegalStatus } from "@/lib/legal-markdown";

export function StatusBadge({ status }: { status: LegalStatus }) {
  return status === "draft" ? (
    <span className="inline-flex shrink-0 items-center rounded-full border border-caution/50 bg-caution/10 px-2.5 py-0.5 text-[0.7rem] font-semibold text-ink">
      Draft
    </span>
  ) : (
    <span className="inline-flex shrink-0 items-center rounded-full border border-signal/40 bg-signal/10 px-2.5 py-0.5 text-[0.7rem] font-semibold text-ink">
      Approved
    </span>
  );
}

/** Page-level status banner shown whenever a document's frontmatter status is "draft". */
export function DraftNotice({ className }: { className?: string }) {
  return (
    <div
      role="note"
      className={clsx("flex gap-3 rounded-xl border border-caution/50 bg-caution/10 px-4 py-3.5 sm:px-5", className)}
    >
      <TriangleAlert aria-hidden="true" className="mt-0.5 h-5 w-5 shrink-0 text-caution" />
      <div className="min-w-0 text-[0.86rem] leading-6 text-ink">
        <p className="font-semibold">Draft — pending legal review</p>
        <p className="mt-0.5 text-ink/80">
          A template prepared from BreachSim’s documented product behaviour. It is not legal advice and must be
          reviewed and adapted by qualified counsel for each jurisdiction before use.
        </p>
      </div>
    </div>
  );
}
