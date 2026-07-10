"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { RiskBandChart, TrendChart } from "@/components/charts";
import { StatusBadge } from "@/components/status-badge";
import { useSession } from "@/components/session-provider";
import { useTheme } from "@/components/theme-provider";
import { DashboardData, getDashboard, getRiskIntelligence, RiskIntelligenceData } from "@/lib/client-api";

const quickActions = [
  { title: "Directory", href: "/employees" },
  { title: "Scenario Lab", href: "/scenario-lab" },
  { title: "Campaigns", href: "/campaigns" },
];

const bandToneMap: Record<string, string> = {
  "0-25": "bg-emerald-400/14 text-emerald-200 border-emerald-300/12",
  "26-50": "bg-cyan-400/14 text-cyan-100 border-cyan-300/12",
  "51-75": "bg-amber-400/14 text-amber-100 border-amber-300/12",
  "76-100": "bg-rose-400/14 text-rose-100 border-rose-300/12",
};

export function DashboardConsole() {
  const { session } = useSession();
  const { theme } = useTheme();
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [risk, setRisk] = useState<RiskIntelligenceData | null>(null);
  const isDark = theme === "dark";

  useEffect(() => {
    if (!session) return;
    void Promise.all([getDashboard(session.access_token), getRiskIntelligence(session.access_token)]).then(([dashboardResponse, riskResponse]) => {
      setDashboard(dashboardResponse);
      setRisk(riskResponse);
    });
  }, [session]);

  const insights = useMemo(() => {
    if (!dashboard || !risk) return null;

    const topDepartment = risk.department_reports[0] ?? null;
    const activeChannel =
      [...dashboard.channel_performance].sort((left, right) => {
        const leftScore = left.delivered + left.clicks + left.reports;
        const rightScore = right.delivered + right.clicks + right.reports;
        return rightScore - leftScore;
      })[0] ?? null;

    return {
      topDepartment,
      topRecommendation: risk.adaptive_recommendations?.[0] ?? null,
      activeChannel,
      totalDeliveries: dashboard.channel_performance.reduce((sum, item) => sum + item.delivered, 0),
      totalEmployees: risk.overview.monitored_employees,
    };
  }, [dashboard, risk]);

  if (!dashboard || !risk || !insights) {
    return <DashboardLoadingState />;
  }

  return (
    <div className="space-y-4">
      <section
        className={
          isDark
            ? "rounded-[1.7rem] border border-white/8 bg-[linear-gradient(180deg,#0a1322_0%,#0c1729_100%)] px-5 py-5 text-white shadow-[0_20px_70px_rgba(4,10,24,0.22)]"
            : "rounded-[1.7rem] border border-white/70 bg-[linear-gradient(180deg,rgba(255,255,255,0.94),rgba(245,248,252,0.96))] px-5 py-5 text-ink shadow-[0_20px_70px_rgba(16,22,37,0.08)]"
        }
      >
        <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
          <div>
            <div className={isDark ? "section-title !text-cyan-100/52" : "section-title"}>Executive Dashboard</div>
            <div className="mt-3 flex flex-wrap items-center gap-3">
              <h1 className="display-font text-2xl font-semibold tracking-[-0.04em] sm:text-[2.1rem]">Command Center</h1>
              <StatusBadge value="operator ready" />
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <HeaderPill label={`${insights.totalEmployees} employees`} dark={isDark} />
              <HeaderPill label={`${dashboard.kpis[0]?.value ?? 0} campaigns`} dark={isDark} />
              <HeaderPill label={`${insights.totalDeliveries} deliveries`} dark={isDark} />
              <HeaderPill label={`${risk.overview.average_risk_score.toFixed(1)} avg risk`} dark={isDark} />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {quickActions.map((item, index) => (
              <Link
                key={item.href}
                href={item.href}
                className={index === 0 ? primaryActionClass : isDark ? secondaryActionDarkClass : secondaryActionLightClass}
              >
                {item.title}
              </Link>
            ))}
          </div>
        </div>
      </section>

      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {dashboard.kpis.map((kpi, index) => (
          <MetricTile
            key={kpi.label}
            label={kpi.label}
            value={formatKpi(kpi.label, kpi.value)}
            accent={index === 0 ? "cyan" : index === 1 ? "indigo" : index === 2 ? "amber" : "emerald"}
            dark={isDark}
          />
        ))}
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.18fr_0.82fr]">
        <section
          className={
            isDark
              ? "rounded-[1.7rem] border border-white/8 bg-[linear-gradient(180deg,#0b1524_0%,#0d1829_100%)] p-5 text-white shadow-[0_20px_70px_rgba(4,10,24,0.22)]"
              : "rounded-[1.7rem] border border-white/70 bg-white/88 p-5 text-ink shadow-card"
          }
        >
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className={isDark ? "section-title !text-cyan-100/52" : "section-title"}>Activity</div>
              <h2 className="display-font mt-2 text-2xl font-semibold tracking-[-0.04em]">Weekly event volume</h2>
            </div>
            <div
              className={
                isDark
                  ? "rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-white/66"
                  : "rounded-full bg-sand px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-slate"
              }
            >
              Last 7 days
            </div>
          </div>

          <div className={isDark ? "mt-5 rounded-[1.25rem] border border-white/8 bg-black/10 p-3" : "mt-5 rounded-[1.25rem] border border-ink/8 bg-sand/55 p-3"}>
            <TrendChart data={dashboard.trend.map((point) => ({ date: point.date, value: point.value }))} theme={isDark ? "dark" : "light"} />
          </div>
        </section>

        <section
          className={
            isDark
              ? "rounded-[1.7rem] border border-white/8 bg-[linear-gradient(180deg,#0a1322_0%,#102033_100%)] p-5 text-white shadow-[0_20px_70px_rgba(4,10,24,0.22)]"
              : "rounded-[1.7rem] border border-white/70 bg-white/88 p-5 text-ink shadow-card"
          }
        >
          <div className={isDark ? "section-title !text-cyan-100/52" : "section-title"}>Focus</div>
          <div className="mt-3 space-y-3">
            <FocusRow label="Top department" value={insights.topDepartment?.department ?? "None"} dark={isDark} />
            <FocusRow label="Priority target" value={insights.topRecommendation?.employee_name ?? "None"} dark={isDark} />
            <FocusRow label="Top vector" value={formatChannel(insights.activeChannel?.channel ?? "email")} dark={isDark} />
            <FocusRow label="High-risk employees" value={risk.overview.high_risk_employees} dark={isDark} />
            <FocusRow label="Improving employees" value={risk.overview.improving_employees} dark={isDark} />
          </div>

        </section>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <section className="rounded-[1.7rem] border border-white/65 bg-white/86 p-5 shadow-card">
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className="section-title">Risk Mix</div>
              <h2 className="display-font mt-2 text-2xl font-semibold tracking-[-0.04em] text-ink">Population distribution</h2>
            </div>
            <div className="rounded-full bg-sand px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-slate">Live</div>
          </div>

          <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_auto]">
            <RiskBandChart data={dashboard.risk_distribution} theme="light" />
            <div className="grid gap-2 self-start">
              {dashboard.risk_distribution.map((band) => (
                <div key={band.band} className={`rounded-[1.05rem] border px-4 py-3 ${bandToneMap[band.band] ?? "border-ink/10 bg-sand text-ink"}`}>
                  <div className="text-[0.64rem] uppercase tracking-[0.18em] opacity-75">{band.band}</div>
                  <div className="mt-1.5 text-lg font-semibold">{band.count}</div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section
          className={
            isDark
              ? "rounded-[1.7rem] border border-white/8 bg-[linear-gradient(180deg,#0b1627_0%,#101a2d_100%)] p-5 text-white shadow-[0_20px_70px_rgba(4,10,24,0.22)]"
              : "rounded-[1.7rem] border border-white/70 bg-white/88 p-5 text-ink shadow-card"
          }
        >
          <div className="flex items-center justify-between gap-4">
            <div>
              <div className={isDark ? "section-title !text-cyan-100/52" : "section-title"}>Channels</div>
              <h2 className="display-font mt-2 text-2xl font-semibold tracking-[-0.04em]">Delivery performance</h2>
            </div>
            <div
              className={
                isDark
                  ? "rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-white/66"
                  : "rounded-full bg-sand px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-slate"
              }
            >
              Live
            </div>
          </div>

          <div className="mt-5 grid gap-3 md:grid-cols-2">
            {dashboard.channel_performance.map((channel) => (
              <ChannelCard
                key={channel.channel}
                channel={channel.channel}
                delivered={channel.delivered}
                clicks={channel.clicks}
                reports={channel.reports}
                dark={isDark}
              />
            ))}
          </div>
        </section>
      </div>

      <section className="rounded-[1.7rem] border border-white/65 bg-white/86 p-5 shadow-card">
        <div className="flex items-center justify-between gap-4">
          <div>
            <div className="section-title">Departments</div>
            <h2 className="display-font mt-2 text-2xl font-semibold tracking-[-0.04em] text-ink">Exposure ranking</h2>
          </div>
          <Link href="/risk-intelligence" className="rounded-full bg-sand px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.18em] text-slate">
            Open Risk Intelligence
          </Link>
        </div>

        <div className="mt-5 grid gap-3">
          {risk.department_reports.length ? (
            risk.department_reports.slice(0, 4).map((department, index) => (
              <div key={department.department_id} className="grid gap-3 rounded-[1.2rem] border border-ink/8 bg-white px-4 py-4 md:grid-cols-[auto_1fr_auto_auto] md:items-center">
                <div className="text-sm font-semibold text-slate">#{index + 1}</div>
                <div>
                  <div className="text-base font-semibold text-ink">{department.department}</div>
                  <div className="mt-1 text-sm text-slate">
                    {department.employee_count} employees · {department.training_completion_count} completions
                  </div>
                </div>
                <div className="text-sm font-semibold text-ink">{department.avg_risk_score.toFixed(1)}</div>
                <StatusBadge value={department.avg_risk_score >= 60 ? "high" : department.avg_risk_score >= 35 ? "medium" : "low"} />
              </div>
            ))
          ) : (
            <div className="rounded-[1.2rem] border border-dashed border-ink/16 bg-sand/65 px-5 py-8 text-center text-sm text-slate">
              Department exposure will appear after campaigns generate telemetry.
            </div>
          )}
        </div>
      </section>
    </div>
  );
}

function DashboardLoadingState() {
  return (
    <div className="space-y-4 animate-pulse">
      <div className="h-24 rounded-[1.7rem] border border-white/10 bg-[#0b1627]" />
      <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((_, index) => (
          <div key={index} className="h-28 rounded-[1.35rem] border border-white/50 bg-white/75" />
        ))}
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        <div className="h-80 rounded-[1.7rem] border border-white/10 bg-[#0b1627]" />
        <div className="h-80 rounded-[1.7rem] border border-white/10 bg-[#0b1627]" />
      </div>
    </div>
  );
}

function HeaderPill({ label, dark }: { label: string; dark: boolean }) {
  return (
    <div
      className={
        dark
          ? "rounded-full border border-white/10 bg-white/[0.05] px-3 py-1.5 text-xs font-medium uppercase tracking-[0.18em] text-white/68"
          : "rounded-full border border-ink/8 bg-white/72 px-3 py-1.5 text-xs font-medium uppercase tracking-[0.18em] text-slate"
      }
    >
      {label}
    </div>
  );
}

function MetricTile({
  label,
  value,
  accent,
  dark,
}: {
  label: string;
  value: string;
  accent: "cyan" | "indigo" | "amber" | "emerald" | "rose";
  dark: boolean;
}) {
  const accentMap = {
    cyan: "bg-[radial-gradient(circle_at_top_left,rgba(95,236,255,0.16),transparent_50%)]",
    indigo: "bg-[radial-gradient(circle_at_top_left,rgba(116,142,255,0.18),transparent_50%)]",
    amber: "bg-[radial-gradient(circle_at_top_left,rgba(255,196,87,0.18),transparent_50%)]",
    emerald: "bg-[radial-gradient(circle_at_top_left,rgba(110,225,165,0.18),transparent_50%)]",
    rose: "bg-[radial-gradient(circle_at_top_left,rgba(255,128,128,0.18),transparent_50%)]",
  };

  return (
    <div
      className={
        dark
          ? "relative overflow-hidden rounded-[1.3rem] border border-white/10 bg-[linear-gradient(180deg,#0f1b2d_0%,#101b2b_100%)] p-4 shadow-[0_18px_44px_rgba(3,10,22,0.2)]"
          : "relative overflow-hidden rounded-[1.3rem] border border-white/65 bg-white/86 p-4 shadow-card"
      }
    >
      <div className={`absolute inset-0 ${dark ? "opacity-55" : "opacity-90"} ${accentMap[accent]}`} />
      <div className="relative">
        <div className={dark ? "text-[0.64rem] uppercase tracking-[0.2em] text-white/48" : "text-[0.64rem] uppercase tracking-[0.2em] text-slate"}>{label}</div>
        <div className={dark ? "mt-3 display-font text-[2rem] font-semibold tracking-[-0.04em] text-white" : "mt-3 display-font text-[2rem] font-semibold tracking-[-0.04em] text-ink"}>{value}</div>
      </div>
    </div>
  );
}

function FocusRow({ label, value, dark }: { label: string; value: string | number; dark: boolean }) {
  return (
    <div className={dark ? "flex items-center justify-between gap-4 rounded-[1rem] border border-white/8 bg-white/[0.05] px-4 py-3" : "flex items-center justify-between gap-4 rounded-[1rem] border border-ink/8 bg-sand/75 px-4 py-3"}>
      <div className={dark ? "text-sm text-white/62" : "text-sm text-slate"}>{label}</div>
      <div className={dark ? "text-sm font-semibold text-white" : "text-sm font-semibold text-ink"}>{value}</div>
    </div>
  );
}

function ChannelCard({
  channel,
  delivered,
  clicks,
  reports,
  dark,
}: {
  channel: string;
  delivered: number;
  clicks: number;
  reports: number;
  dark: boolean;
}) {
  return (
    <div className={dark ? "rounded-[1.2rem] border border-white/8 bg-white/[0.045] p-4" : "rounded-[1.2rem] border border-ink/8 bg-white p-4"}>
      <div className="flex items-center justify-between gap-3">
        <div className={dark ? "display-font text-lg font-semibold uppercase tracking-[-0.02em] text-white" : "display-font text-lg font-semibold uppercase tracking-[-0.02em] text-ink"}>{formatChannel(channel)}</div>
        <div className={dark ? "text-xs uppercase tracking-[0.18em] text-white/54" : "text-xs uppercase tracking-[0.18em] text-slate"}>{delivered} delivered</div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2">
        <MiniVectorMetric label="Clicks" value={clicks} tone="amber" />
        <MiniVectorMetric label="Reports" value={reports} tone="cyan" />
      </div>
    </div>
  );
}

function MiniVectorMetric({
  label,
  value,
  tone,
}: {
  label: string;
  value: number;
  tone: "amber" | "cyan" | "rose";
}) {
  const toneMap = {
    amber: "bg-amber-400/12 text-amber-100",
    cyan: "bg-cyan-400/12 text-cyan-100",
    rose: "bg-rose-400/12 text-rose-100",
  };

  return (
    <div className={`rounded-[0.9rem] px-3 py-3 ${toneMap[tone]}`}>
      <div className="text-[0.58rem] uppercase tracking-[0.16em] opacity-75">{label}</div>
      <div className="mt-1.5 text-lg font-semibold">{value}</div>
    </div>
  );
}

function formatKpi(label: string, value: number) {
  return label === "Total Campaigns" ? String(value) : `${value}%`;
}

function formatChannel(channel: string) {
  if (channel === "sms") return "SMS";
  if (channel === "qr") return "QR";
  return channel.charAt(0).toUpperCase() + channel.slice(1);
}

const primaryActionClass =
  "inline-flex items-center gap-2 rounded-full border border-cyan-200/16 bg-[linear-gradient(180deg,#3f91a4_0%,#27697b_100%)] px-4 py-2.5 text-sm font-semibold text-white shadow-[0_12px_24px_rgba(34,108,126,0.24)]";

const secondaryActionDarkClass =
  "inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.05] px-4 py-2.5 text-sm font-semibold text-white/88";

const secondaryActionLightClass =
  "inline-flex items-center gap-2 rounded-full border border-ink/8 bg-white/74 px-4 py-2.5 text-sm font-semibold text-ink";
