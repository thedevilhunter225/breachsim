"use client";

import clsx from "clsx";
import {
  ArrowRight,
  BarChart3,
  Building2,
  CheckCircle2,
  Mail,
  MailCheck,
  MessageSquare,
  MousePointerClick,
  PhoneCall,
  QrCode,
  Send,
  ShieldAlert,
  Sparkles,
  UsersRound,
  Video,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { RiskBandChart, TrendChart } from "@/components/charts";
import { StatusBadge } from "@/components/status-badge";
import { useSession } from "@/components/session-provider";
import { useTheme } from "@/components/theme-provider";
import { DashboardData, getDashboard, getRiskIntelligence, RiskIntelligenceData } from "@/lib/client-api";

const metricIcons: LucideIcon[] = [BarChart3, MailCheck, MousePointerClick, CheckCircle2];

const CHANNEL_ICONS: Record<string, LucideIcon> = {
  email: Mail,
  sms: MessageSquare,
  qr: QrCode,
  vishing: PhoneCall,
  deepfake: Video,
};

export function DashboardConsole() {
  const { session } = useSession();
  const { theme } = useTheme();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [risk, setRisk] = useState<RiskIntelligenceData | null>(null);

  useEffect(() => {
    if (!session) return;
    void Promise.all([getDashboard(session.access_token), getRiskIntelligence(session.access_token)]).then(([dashboardResponse, riskResponse]) => {
      setDashboard(dashboardResponse);
      setRisk(riskResponse);
    });
  }, [session]);

  const insights = useMemo(() => {
    if (!dashboard || !risk) return null;
    const recommendation = risk.adaptive_recommendations[0] ?? null;
    const department = [...risk.department_reports].sort((a, b) => b.avg_risk_score - a.avg_risk_score)[0] ?? null;
    const channel = [...dashboard.channel_performance].sort((a, b) => b.delivered - a.delivered)[0] ?? null;
    return {
      recommendation,
      department,
      channel,
      deliveries: dashboard.channel_performance.reduce((sum, item) => sum + item.delivered, 0),
    };
  }, [dashboard, risk]);

  if (!dashboard || !risk || !insights) {
    return <DashboardLoadingState />;
  }

  return (
    <div className="stagger space-y-4">
      <section className="app-surface overflow-hidden rounded-xl">
        <div className="grid lg:grid-cols-[1fr_auto] lg:items-center">
          <div className="p-5 md:p-6">
            <div className="flex flex-wrap items-center gap-3">
              <div className="section-title">Security posture</div>
              <StatusBadge value="operator ready" />
            </div>
            <h1 className="display-font mt-2 text-2xl font-semibold tracking-[-0.035em] text-ink md:text-3xl">
              Command Center
            </h1>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-slate">
              Live simulation performance and human-risk movement across your organization.
            </p>
          </div>

          <div className="grid grid-cols-3 border-t border-ink/[0.08] lg:border-l lg:border-t-0">
            <HeaderStat icon={UsersRound} label="Employees" value={risk.overview.monitored_employees} />
            <HeaderStat icon={Send} label="Deliveries" value={insights.deliveries} />
            <HeaderStat icon={ShieldAlert} label="Average risk" value={risk.overview.average_risk_score.toFixed(1)} suffix="/100" />
          </div>
        </div>
      </section>

      <section className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {dashboard.kpis.map((kpi, index) => {
          const Icon = metricIcons[index] ?? BarChart3;
          return (
            <div key={kpi.label} className="app-surface group rounded-xl p-4 transition-shadow hover:shadow-sm">
              <div className="flex items-start justify-between gap-3">
                <div className="grid h-9 w-9 place-items-center rounded-lg bg-tide/[0.08] text-tide">
                  <Icon size={17} />
                </div>
                <span className="rounded-full bg-sand px-2.5 py-1 text-[0.62rem] font-semibold uppercase tracking-[0.11em] text-slate">
                  Live
                </span>
              </div>
              <div className="mt-4 display-font text-[1.9rem] font-semibold tracking-[-0.04em] text-ink">
                {formatKpi(kpi.label, kpi.value)}
              </div>
              <div className="mt-1 text-xs font-semibold text-slate">{kpi.label}</div>
            </div>
          );
        })}
      </section>

      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(320px,0.65fr)]">
        <div className="app-surface rounded-xl p-5 md:p-6">
          <SectionHeading eyebrow="Telemetry" title="Weekly event volume" meta="Last 7 days" />
          <div className="mt-4 rounded-lg border border-ink/[0.08] bg-sand/45 p-2">
            <TrendChart data={dashboard.trend.map((point) => ({ date: point.date, value: point.value }))} theme={theme} compact />
          </div>
        </div>

        <div className="app-surface flex flex-col rounded-xl p-5 md:p-6">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="section-title">Adaptive action</div>
              <h2 className="display-font mt-2 text-xl font-semibold tracking-[-0.03em] text-ink">Recommended next test</h2>
            </div>
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-tide/[0.1] text-tide">
              <Sparkles size={19} />
            </div>
          </div>

          {insights.recommendation ? (
            <div className="mt-5 flex flex-1 flex-col">
              <div className="rounded-xl border border-ink/[0.08] bg-sand/55 p-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <div className="text-sm font-semibold text-ink">{insights.recommendation.employee_name}</div>
                    <div className="mt-1 text-xs text-slate">{insights.recommendation.department ?? "General"}</div>
                  </div>
                  <StatusBadge value={insights.recommendation.risk_band} />
                </div>
                <div className="mt-4 border-t border-ink/[0.08] pt-4">
                  <div className="text-[0.65rem] font-semibold uppercase tracking-[0.13em] text-slate">Next simulation</div>
                  <div className="mt-2 text-sm font-semibold text-ink">
                    {formatChannel(insights.recommendation.recommended_channel)} · {humanize(insights.recommendation.recommended_theme)}
                  </div>
                </div>
                <div className="mt-4 grid grid-cols-2 gap-2">
                  <MiniStat label="Priority" value={`${insights.recommendation.priority_score}%`} />
                  <MiniStat label="Confidence" value={`${insights.recommendation.confidence}%`} />
                </div>
              </div>
              <Link href="/risk-intelligence" className="app-primary-button mt-4 w-full">
                Open risk intelligence
                <ArrowRight size={15} />
              </Link>
            </div>
          ) : (
            <div className="mt-5 flex flex-1 items-center rounded-xl border border-dashed border-ink/15 bg-sand/45 p-5 text-sm leading-6 text-slate">
              Run a campaign to generate enough behavior signals for an adaptive recommendation.
            </div>
          )}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-[0.78fr_1.22fr]">
        <div className="app-surface rounded-xl p-5 md:p-6">
          <SectionHeading eyebrow="Risk composition" title="Employee distribution" meta={`${risk.overview.high_risk_employees} high risk`} />
          <div className="mt-4">
            <RiskBandChart data={dashboard.risk_distribution} theme={theme} compact />
          </div>
          <div className="mt-3 grid grid-cols-4 gap-2">
            {dashboard.risk_distribution.map((band) => (
              <div key={band.band} className="rounded-lg bg-sand/70 px-3 py-2.5 text-center">
                <div className="text-[0.6rem] font-semibold uppercase tracking-[0.1em] text-slate">{band.band}</div>
                <div className="mt-1 text-sm font-bold text-ink">{band.count}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="app-surface overflow-hidden rounded-xl">
          <div className="flex items-center justify-between gap-4 border-b border-ink/[0.08] px-5 py-4 md:px-6">
            <div>
              <div className="section-title">Department exposure</div>
              <h2 className="display-font mt-1.5 text-xl font-semibold tracking-[-0.03em] text-ink">Teams requiring attention</h2>
            </div>
            <Link href="/risk-intelligence" className="app-secondary-button">
              View all
              <ArrowRight size={14} />
            </Link>
          </div>

          {risk.department_reports.length ? (
            <div className="overflow-x-auto">
              <table className="data-table min-w-full text-left text-sm">
                <thead>
                  <tr>
                    <th className="px-5 py-3 md:px-6">Department</th>
                    <th className="px-4 py-3">Employees</th>
                    <th className="px-4 py-3">Click rate</th>
                    <th className="px-4 py-3">Report rate</th>
                    <th className="px-5 py-3 text-right md:px-6">Risk</th>
                  </tr>
                </thead>
                <tbody>
                  {risk.department_reports.slice(0, 5).map((department) => (
                    <tr key={department.department_id}>
                      <td className="px-5 py-3.5 md:px-6">
                        <div className="flex items-center gap-3">
                          <div className="grid h-8 w-8 place-items-center rounded-lg bg-tide/[0.08] text-tide"><Building2 size={15} /></div>
                          <span className="font-semibold text-ink">{department.department}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3.5 text-slate">{department.employee_count}</td>
                      <td className="px-4 py-3.5 text-slate">{department.click_rate}%</td>
                      <td className="px-4 py-3.5 text-slate">{department.report_rate}%</td>
                      <td className="px-5 py-3.5 text-right md:px-6">
                        <span className="font-semibold text-ink">{department.avg_risk_score.toFixed(1)}</span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="grid min-h-48 place-items-center px-6 text-center text-sm text-slate">
              Department exposure appears after the first tracked campaign.
            </div>
          )}
        </div>
      </section>

      <section className="card p-5 md:p-6">
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div>
            <div className="section-title">Channel health</div>
            <h2 className="display-font mt-1.5 text-xl font-bold text-ink">Multi-channel coverage</h2>
          </div>
          <span className="text-xs font-semibold text-muted">
            {formatChannel(insights.channel?.channel ?? "email")} leads volume
          </span>
        </div>

        <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
          {dashboard.channel_performance.map((channel) => {
            const Icon = CHANNEL_ICONS[channel.channel] ?? Send;
            const failureRate = channel.failure_rate ?? 0;
            const resilienceRate = channel.resilience_rate ?? 0;
            const untested = channel.delivered === 0;

            return (
              <div
                key={channel.channel}
                className={clsx("card-muted p-4", untested && "opacity-60")}
              >
                <div className="flex items-center justify-between gap-2">
                  <div className="flex items-center gap-2">
                    <Icon size={15} className="text-brand-500" />
                    <span className="text-[0.85rem] font-bold text-ink">{formatChannel(channel.channel)}</span>
                  </div>
                  <span className="numeric text-[0.7rem] font-bold text-subtle">{channel.delivered}</span>
                </div>

                {untested ? (
                  <p className="mt-3.5 text-[0.72rem] leading-relaxed text-subtle">Not yet exercised</p>
                ) : (
                  <>
                    <div className="mt-3.5 space-y-2">
                      <MeterRow label="Failed" value={failureRate} tone="bg-breach" />
                      <MeterRow label="Resisted" value={resilienceRate} tone="bg-signal" />
                    </div>
                    <div className="mt-3 flex items-center gap-3 border-t border-line pt-2.5 text-[0.68rem] text-muted">
                      <span>
                        <strong className="numeric text-breach">{channel.risky_actions ?? channel.clicks}</strong> risky
                      </span>
                      <span>
                        <strong className="numeric text-signal">{channel.protective_actions ?? channel.reports}</strong> safe
                      </span>
                    </div>
                  </>
                )}
              </div>
            );
          })}
        </div>
      </section>
    </div>
  );
}

function HeaderStat({ icon: Icon, label, value, suffix }: { icon: LucideIcon; label: string; value: string | number; suffix?: string }) {
  return (
    <div className="flex flex-col items-start justify-center gap-2 border-r border-ink/[0.08] px-3 py-4 last:border-r-0 lg:min-h-[116px] lg:min-w-[150px] lg:px-6">
      <Icon size={16} className="text-tide" />
      <div>
        <div className="display-font text-xl font-semibold tracking-[-0.03em] text-ink">{value}<span className="text-xs text-slate">{suffix}</span></div>
        <div className="mt-0.5 text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-slate">{label}</div>
      </div>
    </div>
  );
}

function SectionHeading({ eyebrow, title, meta }: { eyebrow: string; title: string; meta: string }) {
  return (
    <div className="flex items-end justify-between gap-4">
      <div>
        <div className="section-title">{eyebrow}</div>
        <h2 className="display-font mt-1.5 text-xl font-semibold tracking-[-0.03em] text-ink">{title}</h2>
      </div>
      <div className="text-[0.65rem] font-semibold uppercase tracking-[0.12em] text-slate">{meta}</div>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-ink/[0.08] bg-white/70 px-3 py-2.5">
      <div className="text-[0.58rem] font-semibold uppercase tracking-[0.12em] text-slate">{label}</div>
      <div className="mt-1 text-sm font-bold text-ink">{value}</div>
    </div>
  );
}

function MeterRow({ label, value, tone }: { label: string; value: number; tone: string }) {
  return (
    <div>
      <div className="flex items-center justify-between text-[0.65rem] font-semibold text-muted">
        <span>{label}</span>
        <span className="numeric">{value}%</span>
      </div>
      <div className="meter mt-1">
        <div className={clsx("meter-fill", tone)} style={{ width: `${Math.min(100, Math.max(0, value))}%` }} />
      </div>
    </div>
  );
}

function DashboardLoadingState() {
  return (
    <div className="space-y-4">
      <div className="skeleton h-32 rounded-xl" />
      <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="skeleton h-32 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-[1.35fr_0.65fr]">
        <div className="skeleton h-80 rounded-xl" />
        <div className="skeleton h-80 rounded-xl" />
      </div>
    </div>
  );
}

function formatKpi(label: string, value: number) {
  return label === "Total Campaigns" ? String(value) : `${value}%`;
}

function formatChannel(channel: string) {
  const lower = channel.toLowerCase();
  if (lower === "sms") return "SMS";
  if (lower === "qr") return "QR";
  if (lower === "vishing") return "Voice";
  if (lower === "deepfake") return "Deepfake";
  return channel.charAt(0).toUpperCase() + channel.slice(1);
}

function humanize(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
}
