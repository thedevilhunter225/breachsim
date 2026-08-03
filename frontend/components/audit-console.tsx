"use client";

import { useEffect, useState } from "react";
import { FileDown, History } from "lucide-react";
import Link from "next/link";

import { Panel } from "@/components/panel";
import { useSession } from "@/components/session-provider";
import { AuditLog, getAuditLogs } from "@/lib/client-api";

export function AuditConsole() {
  const { session } = useSession();
  const [logs, setLogs] = useState<AuditLog[]>([]);

  useEffect(() => {
    if (!session) return;
    void getAuditLogs(session.access_token).then(setLogs);
  }, [session]);

  return (
    <>
      <section className="app-surface rounded-xl p-5 md:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="section-title">Governance evidence</div>
            <h1 className="display-font mt-2 text-2xl font-semibold tracking-[-0.035em] text-ink">Audit trail</h1>
            <p className="mt-1.5 text-sm text-slate">Approvals, content changes, launches and administrative activity.</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="app-secondary-button"><History size={15} /> {logs.length} entries</div>
            <Link href="/reports" className="app-primary-button"><FileDown size={15} /> Export</Link>
          </div>
        </div>
      </section>

      <Panel className="overflow-hidden p-0">
        {logs.length ? (
          <div className="overflow-x-auto">
            <table className="data-table min-w-full text-left text-sm">
              <thead>
                <tr>
                  <th className="px-5 py-3">Action</th>
                  <th className="px-5 py-3">Resource</th>
                  <th className="px-5 py-3">Details</th>
                  <th className="px-5 py-3">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id}>
                    <td className="px-5 py-4">
                      <div className="font-semibold text-ink">{log.action}</div>
                      <div className="mt-1 text-xs uppercase tracking-[0.18em] text-slate">{log.resource_type}</div>
                    </td>
                    <td className="px-5 py-4 text-slate">{log.resource_type}</td>
                    <td className="px-5 py-4 text-slate">
                      <pre className="max-w-[38rem] whitespace-pre-wrap break-words font-mono text-[0.72rem] leading-6 text-slate">
                        {JSON.stringify(log.details, null, 2)}
                      </pre>
                    </td>
                    <td className="px-5 py-4 text-slate">{new Date(log.occurred_at).toLocaleString()}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="grid min-h-[320px] place-items-center px-6 py-10 text-center">
            <div className="max-w-xl">
              <div className="text-xs uppercase tracking-[0.2em] text-slate">No Audit Data</div>
              <h3 className="mt-4 text-3xl font-semibold text-ink">The audit trail will populate as admins start working</h3>
              <p className="mt-3 text-sm leading-7 text-slate">
                Scenario generation, approval, launch actions, policy edits, and integration changes all appear here automatically.
              </p>
            </div>
          </div>
        )}
      </Panel>
    </>
  );
}
