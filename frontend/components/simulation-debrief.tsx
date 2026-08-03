"use client";

import clsx from "clsx";
import {
  BadgeCheck,
  CircleAlert,
  Eye,
  Flag,
  GraduationCap,
  ShieldCheck,
  TriangleAlert,
} from "lucide-react";

import type { SimulationSummary } from "@/lib/client-api";

const OUTCOME_STYLES: Record<
  SimulationSummary["outcome"],
  { label: string; tone: string; ring: string; icon: typeof ShieldCheck }
> = {
  resilient: {
    label: "Resilient",
    tone: "text-emerald-300",
    ring: "ring-emerald-400/30 bg-emerald-400/10",
    icon: ShieldCheck,
  },
  recovered: {
    label: "Recovered",
    tone: "text-sky-300",
    ring: "ring-sky-400/30 bg-sky-400/10",
    icon: BadgeCheck,
  },
  compromised: {
    label: "Compromised",
    tone: "text-rose-300",
    ring: "ring-rose-400/30 bg-rose-400/10",
    icon: TriangleAlert,
  },
  abandoned: {
    label: "Incomplete",
    tone: "text-amber-300",
    ring: "ring-amber-400/30 bg-amber-400/10",
    icon: CircleAlert,
  },
};

/**
 * Post-simulation debrief. This is the only point at which the employee is told
 * the exercise was a simulation — disclosing earlier would invalidate the result.
 */
export function SimulationDebrief({ summary }: { summary: SimulationSummary }) {
  const style = OUTCOME_STYLES[summary.outcome] ?? OUTCOME_STYLES.abandoned;
  const OutcomeIcon = style.icon;

  return (
    <div className="animate-rise space-y-5">
      <div className={clsx("sim-panel p-6 ring-1 md:p-8", style.ring)}>
        <div className="flex flex-wrap items-start gap-4">
          <div className={clsx("grid h-12 w-12 shrink-0 place-items-center rounded-xl bg-white/10", style.tone)}>
            <OutcomeIcon size={24} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-[0.66rem] font-bold uppercase tracking-[0.2em] text-white/45">
              Security awareness simulation · debrief
            </div>
            <h2 className={clsx("display-font mt-1.5 text-2xl font-bold md:text-[1.75rem]", style.tone)}>
              {style.label}
            </h2>
            <p className="mt-2 max-w-2xl text-[0.95rem] leading-relaxed text-white/78">{summary.headline}</p>
          </div>
        </div>

        <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-4">
          <Stat label="Decisions" value={summary.steps_taken} />
          <Stat label="Safe actions" value={summary.safe_actions} tone="text-emerald-300" />
          <Stat label="Unsafe actions" value={summary.unsafe_actions} tone="text-rose-300" />
          <Stat label="Risk score" value={summary.current_risk_score ?? 0} />
        </div>
      </div>

      {summary.decision_trail.length ? (
        <section className="sim-panel p-5 md:p-6">
          <SectionHeading icon={Eye} title="What you did, step by step" />
          <ol className="mt-4 space-y-2.5">
            {summary.decision_trail.map((step, index) => {
              const isBreak = summary.breaking_point?.step_key === step.step_key;
              return (
                <li
                  key={step.step_key}
                  className={clsx(
                    "rounded-xl border p-3.5",
                    step.safe
                      ? "border-emerald-400/25 bg-emerald-400/[0.07]"
                      : step.risk_weight > 0
                        ? "border-rose-400/25 bg-rose-400/[0.07]"
                        : "border-white/10 bg-white/[0.04]",
                  )}
                >
                  <div className="flex items-start gap-3">
                    <span
                      className={clsx(
                        "mt-0.5 grid h-6 w-6 shrink-0 place-items-center rounded-md text-[0.7rem] font-bold",
                        step.safe ? "bg-emerald-400/20 text-emerald-200" : "bg-rose-400/20 text-rose-200",
                      )}
                    >
                      {index + 1}
                    </span>
                    <div className="min-w-0 flex-1">
                      <div className="text-sm font-semibold text-white/92">{step.response_label}</div>
                      <div className="mt-1 line-clamp-2 text-[0.79rem] leading-relaxed text-white/50">
                        {step.step_prompt}
                      </div>
                      {isBreak ? (
                        <div className="mt-2 inline-flex items-center gap-1.5 rounded-md bg-rose-400/15 px-2 py-1 text-[0.7rem] font-bold uppercase tracking-wide text-rose-200">
                          <TriangleAlert size={12} />
                          Verification would have stopped it here
                        </div>
                      ) : null}
                    </div>
                  </div>
                </li>
              );
            })}
          </ol>
        </section>
      ) : null}

      <div className="grid gap-4 lg:grid-cols-2">
        {summary.red_flags.length ? (
          <section className="sim-panel p-5 md:p-6">
            <SectionHeading icon={Flag} title="Signals that were present" />
            <ul className="mt-3.5 space-y-2.5">
              {summary.red_flags.map((flag) => (
                <li key={flag} className="flex gap-2.5 text-[0.85rem] leading-relaxed text-white/76">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-amber-300" />
                  {flag}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {summary.synthetic_artifacts.length ? (
          <section className="sim-panel p-5 md:p-6">
            <SectionHeading icon={Eye} title="Synthetic media tells" />
            <ul className="mt-3.5 space-y-3">
              {summary.synthetic_artifacts.map((artifact) => (
                <li key={artifact.key} className="rounded-lg border border-white/10 bg-white/[0.035] p-3">
                  <div className="flex items-center justify-between gap-3">
                    <span className="text-[0.82rem] font-bold text-white/92">{artifact.label}</span>
                    {artifact.timestamp_hint ? (
                      <span className="numeric shrink-0 rounded bg-white/10 px-1.5 py-0.5 font-mono text-[0.68rem] text-white/55">
                        {artifact.timestamp_hint}
                      </span>
                    ) : null}
                  </div>
                  <p className="mt-1.5 text-[0.79rem] leading-relaxed text-white/58">{artifact.detail}</p>
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {summary.detection_tells.length ? (
          <section className="sim-panel p-5 md:p-6">
            <SectionHeading icon={GraduationCap} title="What to do next time" />
            <ul className="mt-3.5 space-y-2.5">
              {summary.detection_tells.map((tell) => (
                <li key={tell} className="flex gap-2.5 text-[0.85rem] leading-relaxed text-white/76">
                  <BadgeCheck size={15} className="mt-0.5 shrink-0 text-emerald-300" />
                  {tell}
                </li>
              ))}
            </ul>
          </section>
        ) : null}

        {summary.verification_procedure ? (
          <section className="sim-panel p-5 ring-1 ring-sky-400/25 md:p-6">
            <SectionHeading icon={ShieldCheck} title="The verification procedure" />
            <p className="mt-3 text-[0.88rem] font-medium leading-relaxed text-sky-100">
              {summary.verification_procedure}
            </p>
          </section>
        ) : null}
      </div>

      {summary.debrief ? (
        <p className="rounded-xl border border-white/10 bg-white/[0.035] p-5 text-[0.88rem] leading-relaxed text-white/72">
          {summary.debrief}
        </p>
      ) : null}

      <p className="pb-4 text-center text-[0.74rem] leading-relaxed text-white/38">
        {summary.safety_notice ??
          "This was an authorized security awareness simulation. No credentials were captured."}
      </p>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: number; tone?: string }) {
  return (
    <div className="rounded-lg border border-white/10 bg-white/[0.045] px-3 py-2.5">
      <div className="text-[0.63rem] font-bold uppercase tracking-[0.13em] text-white/40">{label}</div>
      <div className={clsx("numeric display-font mt-0.5 text-xl font-bold", tone ?? "text-white")}>{value}</div>
    </div>
  );
}

function SectionHeading({ icon: Icon, title }: { icon: typeof ShieldCheck; title: string }) {
  return (
    <div className="flex items-center gap-2">
      <Icon size={16} className="text-sky-300" />
      <h3 className="text-[0.7rem] font-bold uppercase tracking-[0.15em] text-white/58">{title}</h3>
    </div>
  );
}
