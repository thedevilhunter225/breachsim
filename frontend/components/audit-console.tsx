"use client";

import { useEffect, useState } from "react";

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
      <Panel>
        <div className="section-title">Audit and Compliance</div>
        <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="display-font text-4xl font-semibold tracking-[-0.04em]">Append-only timeline of launches, approvals, edits, and configuration changes</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate">
              This page exists for accountability. Every critical action in BreachSim is written to the audit trail so an admin, reviewer, or evaluator can see what happened and who did it.
            </p>
          </div>
          <div className="rounded-[1.4rem] bg-sand px-4 py-3 text-sm text-slate">
            Total entries: <span className="font-semibold text-ink">{logs.length}</span>
          </div>
        </div>
      </Panel>

      <Panel className="overflow-hidden p-0">
        {logs.length ? (
          <div className="overflow-x-auto">
            <table className="min-w-full text-left text-sm">
              <thead className="bg-white/85">
                <tr className="text-slate">
                  <th className="px-5 py-4">Action</th>
                  <th className="px-5 py-4">Resource</th>
                  <th className="px-5 py-4">Details</th>
                  <th className="px-5 py-4">Timestamp</th>
                </tr>
              </thead>
              <tbody>
                {logs.map((log) => (
                  <tr key={log.id} className="border-t border-ink/10 bg-white/60">
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
