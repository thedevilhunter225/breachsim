import Link from "next/link";
import { Panel } from "@/components/panel";

export default function EmployeePortalPage() {
  return (
    <main className="page-shell min-h-screen px-4 py-6 md:px-6">
      <div className="mx-auto max-w-5xl space-y-4">
        <Panel>
          <div className="section-title">Employee Transparency Portal</div>
          <h1 className="mt-4 text-4xl font-semibold">Your awareness history and data usage</h1>
          <p className="mt-4 max-w-3xl text-sm leading-7 text-slate">
            This portal explains what approved data is used for simulation context, shows your training history and personal risk trend, and provides privacy controls.
          </p>
        </Panel>

        <div className="grid gap-4 md:grid-cols-2">
          <Panel>
            <div className="section-title">What data is used</div>
            <ul className="mt-4 space-y-3 text-sm leading-7 text-slate">
              <li>Role, department, approved notes, and organization-provided public profile summary.</li>
              <li>Consent state and training preferences.</li>
              <li>Behavior during BreachSim-owned training interactions only.</li>
            </ul>
          </Panel>
          <Panel>
            <div className="section-title">Your options</div>
            <div className="mt-4 space-y-3 text-sm text-slate">
              <div>Consent status: <span className="font-semibold text-ink">Consented</span></div>
              <div>Training completions: <span className="font-semibold text-ink">4</span></div>
              <div>Current risk trend: <span className="font-semibold text-moss">Improving</span></div>
            </div>
          </Panel>
        </div>

        <Link href="/login" className="inline-flex rounded-2xl bg-ink px-4 py-3 text-sm font-semibold text-white">
          Return to BreachSim
        </Link>
      </div>
    </main>
  );
}
