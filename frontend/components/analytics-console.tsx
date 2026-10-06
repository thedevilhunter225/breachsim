"use client";

import { useEffect, useState } from "react";

import { RiskBandChart, TrendChart } from "@/components/charts";
import { MetricCard } from "@/components/metric-card";
import { DataState } from "@/components/data-state";
import { Panel } from "@/components/panel";
import { useSession } from "@/components/session-provider";
import { useTheme } from "@/components/theme-provider";
import { DashboardData, getDashboard } from "@/lib/client-api";

export function AnalyticsConsole() {
  const { session } = useSession();
  const { theme } = useTheme();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [reload, setReload] = useState(0);

  useEffect(() => {
    if (!session) return;
    setError(null);
    void getDashboard(session.access_token).then(setDashboard).catch(() => setError("We couldn't retrieve analytics. Check your connection and try again."));
  }, [session, reload]);

  if (!dashboard) {
    return <DataState label="Analytics" error={error} onRetry={() => setReload((value) => value + 1)} />;
  }

  return (
    <>
      <section className="workspace-page-header">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <div className="section-title">Performance analytics</div>
            <h1 className="display-font mt-2 text-2xl font-semibold tracking-[-0.035em] text-ink">Campaign outcomes</h1>
            <p className="mt-1.5 text-sm text-slate">Compare delivery, engagement, reporting and channel performance.</p>
          </div>
          <div className="rounded-xl border border-ink/[0.08] bg-sand/55 px-4 py-3 text-sm text-slate">
            Most exposed: <span className="font-semibold text-ink">{dashboard.vulnerable_departments[0]?.department ?? "No data"}</span>
          </div>
        </div>
      </section>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Top Vulnerable Department" value={dashboard.vulnerable_departments[0]?.department ?? "-"} tone="ember" />
        <MetricCard label="Overall report rate" value={`${dashboard.kpis.find((kpi) => kpi.label === "Report Rate")?.value ?? 0}%`} tone="tide" />
        <MetricCard label="Recorded events in period" value={dashboard.trend.reduce((total, point) => total + point.value, 0)} tone="moss" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel>
          <div className="section-title">Event Trend</div>
          <h3 className="display-font mt-3 text-2xl font-semibold tracking-[-0.03em]">Weekly interaction volume</h3>
          <div className="mt-4">
            <TrendChart data={dashboard.trend.map((point) => ({ date: point.date, value: point.value }))} theme={theme} compact />
          </div>
        </Panel>
        <Panel>
          <div className="section-title">Risk Banding</div>
          <h3 className="display-font mt-3 text-2xl font-semibold tracking-[-0.03em]">Employee risk distribution</h3>
          <div className="mt-4">
            <RiskBandChart data={dashboard.risk_distribution} theme={theme} compact />
          </div>
        </Panel>
      </div>

      <Panel>
        <div className="section-title">Channel Breakdown</div>
        <p className="mt-1.5 text-[0.82rem] leading-relaxed text-muted">
          Each channel fails in its own vocabulary — a click on email, a scan on QR, a disclosure on a
          call, trusting a fake on deepfake. Rates are share of people reached, not share of events.
        </p>
        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {dashboard.channel_performance.map((channel) => {
            const risky = channel.risky_actions ?? channel.clicks;
            const protective = channel.protective_actions ?? channel.reports;
            const untested = channel.delivered === 0;

            return (
              <div
                key={channel.channel}
                className={`card-muted p-4 ${untested ? "opacity-60" : ""}`}
              >
                <div className="text-[0.62rem] font-bold uppercase tracking-[0.16em] text-subtle">
                  {formatChannel(channel.channel)}
                </div>
                <div className="numeric display-font mt-2 text-2xl font-bold text-ink">{channel.delivered}</div>
                <div className="text-[0.78rem] text-muted">Delivered</div>

                {untested ? (
                  <div className="mt-4 text-[0.74rem] leading-relaxed text-subtle">Not yet exercised</div>
                ) : (
                  <div className="mt-4 grid grid-cols-2 gap-2">
                    <MiniMetric label="Risky" value={risky} rate={channel.failure_rate} tone="breach" />
                    <MiniMetric label="Safe" value={protective} rate={channel.resilience_rate} tone="signal" />
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </Panel>
    </>
  );
}

function formatChannel(channel: string) {
  if (channel === "sms") return "SMS";
  if (channel === "qr") return "QR";
  if (channel === "vishing") return "Voice";
  if (channel === "deepfake") return "Deepfake";
  return channel.charAt(0).toUpperCase() + channel.slice(1);
}

function MiniMetric({
  label,
  value,
  rate,
  tone,
}: {
  label: string;
  value: number;
  rate?: number;
  tone: "breach" | "signal";
}) {
  const toneMap = {
    breach: "text-breach bg-breach/8",
    signal: "text-signal bg-signal/10",
  };

  return (
    <div className={`rounded-lg px-2.5 py-2 ${toneMap[tone]}`}>
      <div className="text-[0.6rem] font-bold uppercase tracking-[0.12em]">{label}</div>
      <div className="numeric mt-1 text-base font-bold">{value}</div>
      {typeof rate === "number" ? (
        <div className="numeric text-[0.65rem] opacity-75">{rate}% of people</div>
      ) : null}
    </div>
  );
}
