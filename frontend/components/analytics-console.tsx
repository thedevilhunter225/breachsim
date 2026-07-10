"use client";

import { useEffect, useState } from "react";

import { RiskBandChart, TrendChart } from "@/components/charts";
import { MetricCard } from "@/components/metric-card";
import { Panel } from "@/components/panel";
import { useSession } from "@/components/session-provider";
import { DashboardData, getDashboard } from "@/lib/client-api";

export function AnalyticsConsole() {
  const { session } = useSession();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);

  useEffect(() => {
    if (!session) return;
    void getDashboard(session.access_token).then(setDashboard);
  }, [session]);

  if (!dashboard) {
    return <Panel>Loading analytics...</Panel>;
  }

  return (
    <>
      <Panel>
        <div className="section-title">Analytics</div>
        <div className="mt-4 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <h2 className="display-font text-4xl font-semibold tracking-[-0.04em]">Organization-wide campaign outcomes and engagement trends</h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-slate">
              Use analytics for the broad picture: what happened across campaigns, which channels performed, and how employee engagement and reporting rates are moving at the organization level.
            </p>
          </div>
          <div className="rounded-[1.4rem] bg-sand px-4 py-3 text-sm text-slate">
            Most exposed department: <span className="font-semibold text-ink">{dashboard.vulnerable_departments[0]?.department ?? "None yet"}</span>
          </div>
        </div>
      </Panel>

      <div className="grid gap-4 md:grid-cols-3">
        <MetricCard label="Top Vulnerable Department" value={dashboard.vulnerable_departments[0]?.department ?? "-"} tone="ember" />
        <MetricCard label="Best Report Rate" value={`${dashboard.kpis[3]?.value}%`} tone="tide" />
        <MetricCard label="Training Posture" value="Active" tone="moss" />
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Panel>
          <div className="section-title">Event Trend</div>
          <h3 className="display-font mt-3 text-2xl font-semibold tracking-[-0.03em]">Weekly interaction volume</h3>
          <div className="mt-4">
            <TrendChart data={dashboard.trend.map((point) => ({ date: point.date, value: point.value }))} />
          </div>
        </Panel>
        <Panel>
          <div className="section-title">Risk Banding</div>
          <h3 className="display-font mt-3 text-2xl font-semibold tracking-[-0.03em]">Employee risk distribution</h3>
          <div className="mt-4">
            <RiskBandChart data={dashboard.risk_distribution} />
          </div>
        </Panel>
      </div>

      <Panel>
        <div className="section-title">Channel Breakdown</div>
        <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          {dashboard.channel_performance.map((channel) => (
            <div key={channel.channel} className="rounded-[1.45rem] border border-ink/10 bg-white/82 p-5">
              <div className="text-xs uppercase tracking-[0.18em] text-slate">{channel.channel}</div>
              <div className="mt-3 display-font text-3xl font-semibold uppercase tracking-[-0.03em] text-ink">{channel.delivered}</div>
              <div className="text-sm text-slate">Delivered</div>
              <div className="mt-5 grid grid-cols-2 gap-2 text-sm">
                <MiniMetric label="Clicks" value={channel.clicks} tone="ember" />
                <MiniMetric label="Reports" value={channel.reports} tone="tide" />
              </div>
            </div>
          ))}
        </div>
      </Panel>
    </>
  );
}

function MiniMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "ember" | "tide" | "moss";
}) {
  const toneMap = {
    ember: "text-ember bg-ember/8",
    tide: "text-tide bg-tide/8",
    moss: "text-moss bg-moss/12",
  };

  return (
    <div className={`rounded-[1rem] px-3 py-3 ${toneMap[tone]}`}>
      <div className="text-[0.62rem] uppercase tracking-[0.18em]">{label}</div>
      <div className="mt-2 text-lg font-semibold">{value}</div>
    </div>
  );
}
