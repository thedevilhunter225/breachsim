"use client";

import { Activity, ArrowRight, ArrowUpRight, BarChart3, CalendarDays, Mail, MessageSquare, QrCode, RefreshCw, ShieldAlert, UsersRound, PhoneCall, Video, type LucideIcon } from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { TrendChart } from "@/components/charts";
import { PageHeading } from "@/components/page-heading";
import { StatusBadge } from "@/components/status-badge";
import { useSession } from "@/components/session-provider";
import { useTheme } from "@/components/theme-provider";
import { type DashboardData, getDashboard, getRiskIntelligence, type RiskIntelligenceData } from "@/lib/client-api";

const channelIcons: Record<string, LucideIcon> = { email: Mail, qr: QrCode, sms: MessageSquare, vishing: PhoneCall, deepfake: Video };
const bandLabels: Record<string, string> = { "0-25": "Low", "26-50": "Moderate", "51-75": "High", "76-100": "Critical" };
const bandColors: Record<string, string> = { "0-25": "#408f81", "26-50": "#6994d1", "51-75": "#d4a85a", "76-100": "#cf6e73" };
const count = (value: number) => value.toLocaleString();

export function DashboardConsole() {
  const { session } = useSession();
  const { theme } = useTheme();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [risk, setRisk] = useState<RiskIntelligenceData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);
  const [updatedAt, setUpdatedAt] = useState<Date | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    setRefreshing(true);
    setError(null);
    try {
      const [summary, insights] = await Promise.all([getDashboard(session.access_token), getRiskIntelligence(session.access_token)]);
      setDashboard(summary);
      setRisk(insights);
      setUpdatedAt(new Date());
    } catch (err) {
      setError(err instanceof TypeError ? "We couldn't connect to the workspace API. Please try again." : err instanceof Error ? err.message : "We couldn't load the overview. Please try again.");
    } finally {
      setRefreshing(false);
    }
  }, [session]);
  useEffect(() => { void load(); }, [load]);

  const header = <PageHeading title="Workspace overview" eyebrow="Human risk management"
    description="Understand your exposure. See where your team needs support."
    actions={<><button type="button" className="app-secondary-button" onClick={() => void load()} disabled={refreshing}><RefreshCw size={14} className={refreshing ? "animate-spin" : ""} />{refreshing ? "Refreshing" : "Refresh"}</button><Link href="/reports" className="app-primary-button"><ArrowUpRight size={15} />View reports</Link></>} />;

  if (!dashboard || !risk) {
    return <div>{header}{error ? <div className="workspace-error" role="alert"><span>{error}</span><button className="app-secondary-button" onClick={() => void load()}>Try again</button></div> :
      <div role="status" aria-label="Loading overview"><div className="overview-metrics">{[0, 1, 2, 3].map((i) => <div key={i} className="skeleton h-36" />)}</div><div className="overview-grid mt-5"><div className="skeleton h-80" /><div className="skeleton h-80" /></div></div>}</div>;
  }

  const totalCampaigns = dashboard.kpis.find((kpi) => kpi.label === "Total Campaigns")?.value ?? 0;
  const reportRate = dashboard.kpis.find((kpi) => kpi.label === "Report Rate")?.value ?? 0;
  const clickRate = dashboard.kpis.find((kpi) => kpi.label === "Click Rate")?.value ?? 0;
  const deliveryRate = dashboard.kpis.find((kpi) => kpi.label === "Delivery Success")?.value;
  const deliveries = dashboard.channel_performance.reduce((sum, item) => sum + item.delivered, 0);
  const periodEvents = dashboard.trend.reduce((sum, item) => sum + item.value, 0);
  const bandTotal = dashboard.risk_distribution.reduce((sum, band) => sum + band.count, 0);
  const departments = [...risk.department_reports].sort((a, b) => b.avg_risk_score - a.avg_risk_score);
  const mostExposed = departments.find((department) => department.employee_count > 0);
  const metrics = [
    { label: "People monitored", value: count(risk.overview.monitored_employees), note: "Employees in your workspace", icon: UsersRound },
    { label: "Total campaigns", value: count(totalCampaigns), note: "Across all recorded campaigns", icon: BarChart3 },
    { label: "Average risk score", value: risk.overview.average_risk_score.toFixed(1), note: "Out of 100 · Lower is better", icon: ShieldAlert },
    { label: "Report rate", value: reportRate + "%", note: "Reported suspicious activity", icon: Activity },
  ];

  return (
    <div className="space-y-5">
      {header}
      {error ? <div className="workspace-error" role="alert">Refresh failed: {error}. Showing the last loaded data.</div> : null}
      <section className="overview-metrics" aria-label="Workspace metrics">
        {metrics.map(({ label, value, note, icon: Icon }) => <div key={label} className="overview-metric"><div className="overview-metric-label"><span>{label}</span><Icon size={17} strokeWidth={1.6} /></div><div className="overview-metric-value">{value}</div><p className="overview-metric-note">{note}</p></div>)}
      </section>

      <div className="overview-grid">
        <section className="overview-card" aria-labelledby="activity-heading">
          <div className="overview-card-header"><div><h2 id="activity-heading">Activity over time</h2><p>Recorded events across your workspace</p></div><span className="overview-period flex items-center gap-1.5"><CalendarDays size={12} />{dashboard.trend.length || 7} days</span></div>
          <div className="overview-chart"><TrendChart data={dashboard.trend} theme={theme} compact /></div>
          {periodEvents === 0 ? <p className="overview-chart-empty">No events recorded during this period.</p> : null}
          <div className="overview-chart-footer"><span><strong>{count(periodEvents)}</strong>events in period</span><span><strong>{count(deliveries)}</strong>historical deliveries</span><span><strong>{clickRate}%</strong>overall click rate</span></div>
        </section>

        <section className="overview-card" aria-labelledby="risk-heading">
          <div className="overview-card-header"><div><h2 id="risk-heading">Risk distribution</h2><p>Current scores for monitored employees</p></div><ShieldAlert size={17} className="text-muted" /></div>
          <div className="overview-risk-score"><strong>{risk.overview.average_risk_score.toFixed(1)}</strong><span>/ 100 average</span></div>
          <div className="overview-risk-bar" role="img" aria-label={dashboard.risk_distribution.map((band) => (bandLabels[band.band] ?? band.band) + ": " + band.count).join(", ")}>
            {dashboard.risk_distribution.map((band) => <div key={band.band} style={{ width: (bandTotal ? band.count / bandTotal * 100 : 0) + "%", background: bandColors[band.band] ?? "#6994d1" }} />)}
          </div>
          <div className="overview-risk-legend">{dashboard.risk_distribution.map((band) => <div key={band.band}><span className="overview-dot" style={{ background: bandColors[band.band] ?? "#6994d1" }} /><span>{bandLabels[band.band] ?? band.band}</span><strong>{band.count}</strong></div>)}</div>
          <div className="overview-risk-note"><span className="font-medium text-ink">{risk.overview.high_risk_employees} {risk.overview.high_risk_employees === 1 ? "person requires" : "people require"} attention.</span> Review the underlying behavior before choosing follow-up training.<Link href="/risk-intelligence" className="workspace-text-link mt-3">Explore risk insights <ArrowRight size={13} /></Link></div>
        </section>
      </div>

      <div className="overview-grid">
        <section className="overview-card" aria-labelledby="department-heading">
          <div className="overview-card-header pb-5"><div><h2 id="department-heading">Department overview</h2><p>Prioritized by average risk score</p></div><Link href="/employees" className="workspace-text-link">View people <ArrowUpRight size={13} /></Link></div>
          {departments.length ? <div className="overflow-x-auto"><table className="data-table"><caption className="sr-only">Department risk, employee count and reporting rate</caption><thead><tr><th>Department</th><th>People</th><th>Report rate</th><th>Risk score</th></tr></thead><tbody>
            {departments.slice(0, 5).map((department) => <tr key={department.department_id}><td><span className="font-medium">{department.department}</span></td><td className="text-muted">{department.employee_count}</td><td className="text-muted">{department.report_rate}%</td><td><div className="flex items-center justify-end gap-3"><span className="hidden h-1.5 w-14 overflow-hidden rounded-full bg-surface-sunken sm:block"><span className="block h-full rounded-full" style={{ width: Math.min(100, Math.max(0, department.avg_risk_score)) + "%", background: department.avg_risk_score > 75 ? "#cf6e73" : department.avg_risk_score > 50 ? "#d4a85a" : "#6994d1" }} /></span><span className="w-8 text-right tabular-nums">{department.avg_risk_score.toFixed(1)}</span></div></td></tr>)}
          </tbody></table></div> : <p className="p-6 text-sm text-muted">Department insights will appear as activity is recorded.</p>}
          <div className="overview-chart-footer"><span>{departments.length} departments in this workspace</span><Link href="/risk-intelligence" className="workspace-text-link ml-auto">Full breakdown <ArrowRight size={12} /></Link></div>
        </section>

        <section className="overview-card" aria-labelledby="attention-heading">
          <div className="overview-card-header"><div><h2 id="attention-heading">Where to focus</h2><p>Follow-up informed by recorded behavior</p></div><span className="grid h-7 w-7 place-items-center rounded-md bg-caution/10 text-caution"><ShieldAlert size={15} /></span></div>
          <div className="overview-insight">
            {mostExposed ? <><div className="overview-insight-title"><span>{mostExposed.department}</span><StatusBadge value={mostExposed.avg_risk_score > 75 ? "critical" : mostExposed.avg_risk_score > 50 ? "high" : mostExposed.avg_risk_score > 25 ? "medium" : "low"} /></div><p>This department has the highest average score. Review its activity and training history to understand the areas needing support.</p></> : <p>As your team completes exercises, this view highlights departments that could benefit from additional support.</p>}
            <dl><div><dt>Departments flagged</dt><dd>{risk.overview.departments_flagged}</dd></div><div><dt>People improving</dt><dd className="text-signal">{risk.overview.improving_employees}</dd></div></dl>
            <Link href="/risk-intelligence" className="workspace-text-link">Review department insights <ArrowRight size={13} /></Link>
          </div>
        </section>
      </div>

      <section className="overview-card" aria-labelledby="channels-heading">
        <div className="overview-card-header"><div><h2 id="channels-heading">Recorded channel activity</h2><p>Historical records, including sandbox exercises</p></div><Link href="/analytics" className="workspace-text-link">Analytics <ArrowUpRight size={13} /></Link></div>
        <div className="overview-channel-grid">
          {dashboard.channel_performance.map((channel) => {
            const Icon = channelIcons[channel.channel] ?? Activity;
            return <div key={channel.channel} className="overview-channel"><div className="overview-channel-name"><Icon size={15} /><span>{formatChannel(channel.channel)}</span></div><div className="overview-channel-count">{count(channel.delivered)}</div><small>{channel.channel === "email" || channel.channel === "qr" ? "Recorded deliveries" : "Sandbox activity"}</small><div className="overview-channel-outcomes"><span><b>{channel.risky_actions ?? channel.clicks}</b> risky</span><span><b>{channel.protective_actions ?? channel.reports}</b> protective</span></div></div>;
          })}
        </div>
        {deliveryRate !== undefined ? <div className="overview-chart-footer"><span><strong>{deliveryRate}%</strong>historical delivery success · Provider acceptance does not confirm inbox placement.</span></div> : null}
      </section>
      <footer className="flex flex-wrap items-center justify-between gap-2 text-[11px] text-muted"><span>Data follows your workspace reporting permissions.</span><span>{updatedAt ? "Last refreshed " + updatedAt.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}</span></footer>
    </div>
  );
}

function formatChannel(value: string) {
  return ({ email: "Email", qr: "QR code", sms: "SMS", vishing: "Voice", deepfake: "Video" } as Record<string, string>)[value] ?? value;
}
