"use client";

import clsx from "clsx";
import {
  ArrowRight,
  Download,
  FileChartColumn,
  FileSpreadsheet,
  FileText,
  Loader2,
  Mail,
  MessageSquare,
  PhoneCall,
  QrCode,
  ShieldCheck,
  Video,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useSession } from "@/components/session-provider";
import { StatusBadge } from "@/components/status-badge";
import {
  API_BASE,
  downloadReport,
  getReportableCampaigns,
  type ReportableCampaign,
} from "@/lib/client-api";

const CHANNEL_ICONS: Record<string, LucideIcon> = {
  email: Mail,
  sms: MessageSquare,
  qr: QrCode,
  vishing: PhoneCall,
  deepfake: Video,
};

export function ReportsConsole() {
  const { session } = useSession();
  const [campaigns, setCampaigns] = useState<ReportableCampaign[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    try {
      setCampaigns(await getReportableCampaigns(session.access_token));
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void load();
  }, [load]);

  async function run(key: string, path: string, filename: string, success: string) {
    if (!session) return;
    setBusy(key);
    setNotice(null);
    try {
      await downloadReport(session.access_token, path, filename);
      setNotice({ tone: "ok", text: success });
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <section className="workspace-page-header">
        <div className="section-title">Evidence center</div>
        <h1 className="display-font mt-1.5 text-2xl font-bold text-ink">Reports and exports</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
          Every export is scoped to this workspace and recorded in the report log. The campaign pack
          follows the full chain: authorization, delivery, interaction, remediation and risk movement.
        </p>
      </section>

      {notice ? (
        <div
          className={clsx(
            "rounded-xl border px-4 py-3 text-[0.85rem]",
            notice.tone === "ok"
              ? "border-signal/25 bg-signal/8 text-signal"
              : "border-breach/25 bg-breach/8 text-breach",
          )}
        >
          {notice.text}
        </div>
      ) : null}

      {/* Workspace-wide exports */}
      <section className="grid gap-4 lg:grid-cols-3">
        <article className="card flex flex-col p-5">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
            <ShieldCheck size={20} />
          </div>
          <div className="section-title mt-4">Compliance</div>
          <h2 className="display-font mt-1.5 text-lg font-bold text-ink">Audit evidence pack</h2>
          <p className="mt-2 flex-1 text-[0.84rem] leading-relaxed text-muted">
            Approvals, scenario versions, persona consent decisions, launches and workspace
            administration as an append-only record.
          </p>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              className="btn-primary btn-sm"
              disabled={busy === "audit"}
              onClick={() =>
                void run(
                  "audit",
                  "/reports/audit/download",
                  "breachsim-audit-log.csv",
                  "Audit log exported as CSV.",
                )
              }
            >
              {busy === "audit" ? <Loader2 size={13} className="animate-spin" /> : <FileSpreadsheet size={13} />}
              Download CSV
            </button>
            <Link href="/audit" className="btn-secondary btn-sm">
              Review in app
              <ArrowRight size={13} />
            </Link>
          </div>
        </article>

        <article className="card flex flex-col p-5">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
            <FileChartColumn size={20} />
          </div>
          <div className="section-title mt-4">Performance</div>
          <h2 className="display-font mt-1.5 text-lg font-bold text-ink">Channel analytics</h2>
          <p className="mt-2 flex-1 text-[0.84rem] leading-relaxed text-muted">
            Delivery, failure and resilience rates compared across email, SMS, QR, voice and
            synthetic media.
          </p>
          <Link href="/analytics" className="btn-secondary btn-sm mt-4 self-start">
            Open analytics
            <ArrowRight size={13} />
          </Link>
        </article>

        <article className="card flex flex-col p-5">
          <div className="grid h-11 w-11 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
            <FileText size={20} />
          </div>
          <div className="section-title mt-4">Human risk</div>
          <h2 className="display-font mt-1.5 text-lg font-bold text-ink">Risk intelligence brief</h2>
          <p className="mt-2 flex-1 text-[0.84rem] leading-relaxed text-muted">
            Department exposure, score drivers and the adaptive retest each employee should receive
            next.
          </p>
          <Link href="/risk-intelligence" className="btn-secondary btn-sm mt-4 self-start">
            Open risk intelligence
            <ArrowRight size={13} />
          </Link>
        </article>
      </section>

      {/* Per-campaign packs */}
      <section className="card overflow-hidden">
        <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
          <div>
            <div className="section-title">Campaign evidence packs</div>
            <h2 className="display-font mt-0.5 text-lg font-bold text-ink">Per-campaign reports</h2>
          </div>
          <span className="badge badge-neutral">{campaigns.length} campaigns</span>
        </div>

        {loading ? (
          <div className="space-y-3 p-5">
            {[0, 1, 2].map((index) => (
              <div key={index} className="skeleton h-16 w-full" />
            ))}
          </div>
        ) : campaigns.length === 0 ? (
          <div className="px-5 py-14 text-center">
            <FileChartColumn className="mx-auto text-subtle" size={30} />
            <p className="mt-3 text-[0.9rem] font-semibold text-ink">No campaigns to report on yet</p>
            <p className="mx-auto mt-1.5 max-w-md text-[0.83rem] leading-relaxed text-muted">
              Run a campaign and its evidence pack will appear here.
            </p>
          </div>
        ) : (
          <div className="table-scroll">
            <table className="data-table">
              <thead>
                <tr>
                  <th>Campaign</th>
                  <th>Channel</th>
                  <th>Status</th>
                  <th className="text-right">Targets</th>
                  <th className="text-right">Evidence pack</th>
                </tr>
              </thead>
              <tbody>
                {campaigns.map((campaign) => {
                  const Icon = CHANNEL_ICONS[campaign.channel] ?? Mail;
                  const htmlKey = `${campaign.id}-html`;
                  const csvKey = `${campaign.id}-csv`;
                  return (
                    <tr key={campaign.id}>
                      <td>
                        <div className="font-semibold text-ink">{campaign.name}</div>
                        <div className="mt-0.5 text-[0.74rem] text-subtle">
                          {new Date(campaign.created_at).toLocaleDateString()}
                        </div>
                      </td>
                      <td>
                        <span className="badge badge-brand">
                          <Icon size={11} />
                          {formatChannel(campaign.channel)}
                        </span>
                      </td>
                      <td>
                        <StatusBadge value={campaign.status} />
                      </td>
                      <td className="numeric text-right font-semibold text-ink">{campaign.target_count}</td>
                      <td>
                        <div className="flex flex-wrap justify-end gap-1.5">
                          <button
                            type="button"
                            className="btn-secondary btn-sm"
                            disabled={busy === htmlKey}
                            onClick={() =>
                              void run(
                                htmlKey,
                                `/reports/campaign/${campaign.id}/download?format=html`,
                                `breachsim-${slug(campaign.name)}.html`,
                                `Evidence pack exported for "${campaign.name}".`,
                              )
                            }
                          >
                            {busy === htmlKey ? (
                              <Loader2 size={12} className="animate-spin" />
                            ) : (
                              <Download size={12} />
                            )}
                            Report
                          </button>
                          <button
                            type="button"
                            className="btn-ghost btn-sm"
                            disabled={busy === csvKey}
                            onClick={() =>
                              void run(
                                csvKey,
                                `/reports/campaign/${campaign.id}/download?format=csv`,
                                `breachsim-${slug(campaign.name)}.csv`,
                                `Outcome table exported for "${campaign.name}".`,
                              )
                            }
                          >
                            <FileSpreadsheet size={12} />
                            CSV
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}
      </section>

      <p className="px-1 text-[0.78rem] leading-relaxed text-subtle">
        The HTML pack is styled for printing — open it and use your browser&apos;s
        &ldquo;Save as PDF&rdquo; to attach it to a report. API base: <code className="font-mono">{API_BASE}</code>
      </p>
    </div>
  );
}

function formatChannel(channel: string) {
  if (channel === "sms") return "SMS";
  if (channel === "qr") return "QR";
  if (channel === "vishing") return "Voice";
  if (channel === "deepfake") return "Deepfake";
  return channel.charAt(0).toUpperCase() + channel.slice(1);
}

function slug(value: string) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "")
    .slice(0, 60);
}

function readError(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    return String((error as Error).message);
  }
  return "Export failed.";
}
