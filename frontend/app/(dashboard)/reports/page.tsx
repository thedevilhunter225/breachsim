import Link from "next/link";
import { Panel } from "@/components/panel";

export default function ReportsPage() {
  return (
    <>
      <Panel>
        <div className="section-title">Reports and Exports</div>
        <h2 className="mt-4 text-3xl font-semibold">CSV and PDF-friendly HTML exports for evaluators and auditors</h2>
      </Panel>

      <div className="grid gap-4 md:grid-cols-2">
        <Panel>
          <div className="section-title">Audit Export</div>
          <h3 className="mt-3 text-2xl font-semibold text-ink">Evidence pack for reviewers</h3>
          <p className="mt-4 text-sm leading-7 text-slate">
            Export approval history, scenario versions, delivery attempts, tracked events, and audit actions for compliance review.
          </p>
        </Panel>
        <Panel>
          <div className="section-title">Campaign Report</div>
          <h3 className="mt-3 text-2xl font-semibold text-ink">Board-ready campaign summary</h3>
          <p className="mt-4 text-sm leading-7 text-slate">
            Summarize delivery rate, click rate, report rate, QR scans, training assignments, and department risk movement.
          </p>
          <Link href="/risk-intelligence" className="mt-5 inline-flex rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white">
            Open Risk Intelligence
          </Link>
        </Panel>
      </div>
    </>
  );
}
