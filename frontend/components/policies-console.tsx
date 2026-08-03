"use client";

import clsx from "clsx";
import {
  AlertTriangle,
  Ban,
  Clock,
  Gauge,
  Loader2,
  Mail,
  MessageSquare,
  PhoneCall,
  Plus,
  QrCode,
  Save,
  ShieldCheck,
  UserRoundCheck,
  Video,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { useSession } from "@/components/session-provider";
import { getPolicy, updatePolicy, type Policy } from "@/lib/client-api";

/** Every channel the platform can run, with the governance weight of enabling it. */
const CHANNEL_CATALOGUE: Array<{
  value: string;
  label: string;
  icon: LucideIcon;
  description: string;
  sensitive?: string;
}> = [
  {
    value: "email",
    label: "Email",
    icon: Mail,
    description: "Inbox lure with a tracked link. Sends only to allowlisted mailboxes.",
  },
  {
    value: "sms",
    label: "SMS / smishing",
    icon: MessageSquare,
    description: "Text message to an allowlisted number via the configured gateway.",
  },
  {
    value: "qr",
    label: "QR",
    icon: QrCode,
    description: "Printable poster with a tracked scan code. Nothing is sent outbound.",
  },
  {
    value: "vishing",
    label: "Voice / vishing",
    icon: PhoneCall,
    description: "Branching call script rendered in the browser. No real call is placed.",
    sensitive: "Requires an approved impersonation persona.",
  },
  {
    value: "deepfake",
    label: "Synthetic media",
    icon: Video,
    description: "Impersonation simulation using an approved persona. No media file is stored.",
    sensitive: "Requires an approved, in-consent persona and the organization-level switch.",
  },
];

const THEME_CATALOGUE = [
  "invoice/payment approval",
  "policy update",
  "leave request",
  "password reset",
  "mfa notice",
  "client contract",
  "quote request",
  "document review",
  "qr verification",
  "vendor payment release",
  "executive approval request",
];

export function PoliciesConsole() {
  const { session } = useSession();
  const [policy, setPolicy] = useState<Policy | null>(null);
  const [busy, setBusy] = useState(false);
  const [customTheme, setCustomTheme] = useState("");
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const isAdmin = session?.user.roles.includes("admin") ?? false;

  const load = useCallback(async () => {
    if (!session) return;
    try {
      setPolicy(await getPolicy(session.access_token));
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    }
  }, [session]);

  useEffect(() => {
    void load();
  }, [load]);

  async function save() {
    if (!session || !policy) return;
    setBusy(true);
    setNotice(null);
    try {
      const next = await updatePolicy(session.access_token, {
        ...policy,
        id: undefined,
        organization_id: undefined,
      });
      setPolicy(next);
      setNotice({ tone: "ok", text: "Controls saved. A new policy version was recorded in the audit trail." });
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusy(false);
    }
  }

  function toggleChannel(channel: string) {
    if (!policy) return;
    const enabled = policy.allowed_delivery_channels.includes(channel);
    setPolicy({
      ...policy,
      allowed_delivery_channels: enabled
        ? policy.allowed_delivery_channels.filter((entry) => entry !== channel)
        : [...policy.allowed_delivery_channels, channel],
    });
  }

  function toggleTheme(theme: string) {
    if (!policy) return;
    const enabled = policy.allowed_themes.includes(theme);
    setPolicy({
      ...policy,
      allowed_themes: enabled
        ? policy.allowed_themes.filter((entry) => entry !== theme)
        : [...policy.allowed_themes, theme],
    });
  }

  function addCustomTheme() {
    const value = customTheme.trim().toLowerCase();
    if (!policy || !value || policy.allowed_themes.includes(value)) return;
    setPolicy({ ...policy, allowed_themes: [...policy.allowed_themes, value] });
    setCustomTheme("");
  }

  if (!policy) {
    return (
      <div className="space-y-4">
        <div className="skeleton h-28 rounded-xl" />
        <div className="skeleton h-96 rounded-xl" />
      </div>
    );
  }

  const extraThemes = policy.allowed_themes.filter((theme) => !THEME_CATALOGUE.includes(theme));

  return (
    <div className="space-y-4">
      <section className="card p-5 md:p-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="section-title">Simulation governance</div>
            <h1 className="display-font mt-1.5 text-2xl font-bold text-ink">Controls and launch rules</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
              These guardrails are enforced server-side before any content is generated. A scenario that violates
              them is refused, not warned about.
            </p>
          </div>
          {isAdmin ? (
            <button type="button" className="btn-primary shrink-0" disabled={busy} onClick={() => void save()}>
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
              Save controls
            </button>
          ) : null}
        </div>
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

      {/* Channels */}
      <section className="card p-5 md:p-6">
        <div className="flex items-center gap-2">
          <ShieldCheck size={17} className="text-brand-500" />
          <h2 className="display-font text-lg font-bold text-ink">Permitted delivery channels</h2>
        </div>
        <p className="mt-1.5 text-[0.84rem] leading-relaxed text-muted">
          A channel that is switched off here cannot be used to generate a scenario, regardless of any other
          setting. New capabilities ship disabled so an upgrade never silently widens what your organization runs.
        </p>

        <div className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {CHANNEL_CATALOGUE.map((channel) => {
            const Icon = channel.icon;
            const enabled = policy.allowed_delivery_channels.includes(channel.value);
            return (
              <button
                key={channel.value}
                type="button"
                disabled={!isAdmin}
                onClick={() => toggleChannel(channel.value)}
                className={clsx(
                  "rounded-xl border p-4 text-left transition disabled:cursor-not-allowed",
                  enabled
                    ? "border-brand-500/45 bg-brand-500/[0.06]"
                    : "border-line bg-surface-muted hover:border-line-strong",
                )}
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <Icon size={16} className={enabled ? "text-brand-500" : "text-subtle"} />
                    <span className={clsx("text-[0.88rem] font-bold", enabled ? "text-ink" : "text-muted")}>
                      {channel.label}
                    </span>
                  </div>
                  <span className={clsx("badge shrink-0", enabled ? "badge-success" : "badge-neutral")}>
                    {enabled ? "Allowed" : "Blocked"}
                  </span>
                </div>
                <p className="mt-2 text-[0.78rem] leading-relaxed text-muted">{channel.description}</p>
                {channel.sensitive ? (
                  <p className="mt-2 flex gap-1.5 text-[0.74rem] leading-relaxed text-caution">
                    <AlertTriangle size={12} className="mt-0.5 shrink-0" />
                    {channel.sensitive}
                  </p>
                ) : null}
              </button>
            );
          })}
        </div>

        {policy.allowed_delivery_channels.some((channel) => channel === "vishing" || channel === "deepfake") ? (
          <div className="mt-4 flex flex-wrap items-center gap-3 rounded-xl border border-violet/25 bg-violet/6 p-3.5">
            <UserRoundCheck size={16} className="shrink-0 text-violet" />
            <p className="min-w-0 flex-1 text-[0.81rem] leading-relaxed text-muted">
              Impersonation channels are enabled. They still require a persona that a second administrator has
              approved and whose consent window is open.
            </p>
            <Link href="/personas" className="btn-secondary btn-sm shrink-0">
              Persona registry
            </Link>
          </div>
        ) : null}
      </section>

      {/* Themes */}
      <section className="card p-5 md:p-6">
        <h2 className="display-font text-lg font-bold text-ink">Permitted scenario themes</h2>
        <p className="mt-1.5 text-[0.84rem] leading-relaxed text-muted">
          The generator may only build content around a theme selected here.
        </p>

        <div className="mt-4 flex flex-wrap gap-2">
          {THEME_CATALOGUE.map((theme) => {
            const enabled = policy.allowed_themes.includes(theme);
            return (
              <button
                key={theme}
                type="button"
                disabled={!isAdmin}
                onClick={() => toggleTheme(theme)}
                className={clsx(
                  "rounded-full border px-3 py-1.5 text-[0.78rem] font-semibold transition disabled:cursor-not-allowed",
                  enabled
                    ? "border-brand-500/45 bg-brand-500/10 text-brand-600"
                    : "border-line bg-surface-muted text-muted hover:border-line-strong",
                )}
              >
                {theme}
              </button>
            );
          })}
          {extraThemes.map((theme) => (
            <button
              key={theme}
              type="button"
              disabled={!isAdmin}
              onClick={() => toggleTheme(theme)}
              className="inline-flex items-center gap-1.5 rounded-full border border-violet/40 bg-violet/10 px-3 py-1.5 text-[0.78rem] font-semibold text-violet disabled:cursor-not-allowed"
            >
              {theme}
              <X size={12} />
            </button>
          ))}
        </div>

        {isAdmin ? (
          <div className="mt-4 flex flex-wrap gap-2">
            <input
              className="field max-w-xs"
              value={customTheme}
              placeholder="Add a custom theme"
              onChange={(event) => setCustomTheme(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter") {
                  event.preventDefault();
                  addCustomTheme();
                }
              }}
            />
            <button type="button" className="btn-secondary" onClick={addCustomTheme} disabled={!customTheme.trim()}>
              <Plus size={14} />
              Add
            </button>
          </div>
        ) : null}
      </section>

      <div className="grid gap-4 lg:grid-cols-2">
        {/* Never-use list */}
        <section className="card p-5 md:p-6">
          <div className="flex items-center gap-2">
            <Ban size={17} className="text-breach" />
            <h2 className="display-font text-lg font-bold text-ink">Hard blocks</h2>
          </div>
          <p className="mt-1.5 text-[0.84rem] leading-relaxed text-muted">
            Content containing any of these is rejected outright, before a scenario is ever saved.
          </p>

          <div className="mt-4">
            <label className="field-label" htmlFor="prohibited-words">
              Prohibited words
            </label>
            <textarea
              id="prohibited-words"
              className="field min-h-24"
              disabled={!isAdmin}
              value={policy.prohibited_words.join(", ")}
              onChange={(event) =>
                setPolicy({ ...policy, prohibited_words: splitList(event.target.value) })
              }
            />
            <p className="field-hint">Comma separated. Keep anything with legal, HR, medical or safety risk.</p>
          </div>

          <div className="mt-4">
            <label className="field-label" htmlFor="prohibited-topics">
              Prohibited topics
            </label>
            <textarea
              id="prohibited-topics"
              className="field min-h-28"
              disabled={!isAdmin}
              value={policy.prohibited_topics.join(", ")}
              onChange={(event) =>
                setPolicy({ ...policy, prohibited_topics: splitList(event.target.value) })
              }
            />
          </div>

          <div className="mt-4">
            <label className="field-label" htmlFor="training-domains">
              Approved training domains
            </label>
            <textarea
              id="training-domains"
              className="field min-h-20"
              disabled={!isAdmin}
              value={policy.approved_training_domains.join(", ")}
              onChange={(event) =>
                setPolicy({ ...policy, approved_training_domains: splitList(event.target.value) })
              }
            />
            <p className="field-hint">Where landing pages and tracked links may be hosted.</p>
          </div>
        </section>

        {/* Launch controls */}
        <section className="card p-5 md:p-6">
          <div className="flex items-center gap-2">
            <Gauge size={17} className="text-brand-500" />
            <h2 className="display-font text-lg font-bold text-ink">Launch controls</h2>
          </div>
          <p className="mt-1.5 text-[0.84rem] leading-relaxed text-muted">
            Frequency, timing and the two-person rule.
          </p>

          <div className="mt-4 grid gap-4 sm:grid-cols-2">
            <div>
              <label className="field-label" htmlFor="hours-start">
                <Clock size={11} className="mr-1 inline" />
                Earliest send hour
              </label>
              <input
                id="hours-start"
                type="number"
                min={0}
                max={23}
                className="field"
                disabled={!isAdmin}
                value={policy.working_hours_start}
                onChange={(event) => setPolicy({ ...policy, working_hours_start: Number(event.target.value) })}
              />
            </div>
            <div>
              <label className="field-label" htmlFor="hours-end">
                <Clock size={11} className="mr-1 inline" />
                Latest send hour
              </label>
              <input
                id="hours-end"
                type="number"
                min={0}
                max={23}
                className="field"
                disabled={!isAdmin}
                value={policy.working_hours_end}
                onChange={(event) => setPolicy({ ...policy, working_hours_end: Number(event.target.value) })}
              />
            </div>
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="max-frequency">
                Maximum simulations per employee
              </label>
              <input
                id="max-frequency"
                type="number"
                min={1}
                className="field"
                disabled={!isAdmin}
                value={policy.maximum_frequency_per_employee}
                onChange={(event) =>
                  setPolicy({ ...policy, maximum_frequency_per_employee: Number(event.target.value) })
                }
              />
              <p className="field-hint">Protects individuals from being repeatedly targeted.</p>
            </div>
          </div>

          <div className="mt-4 space-y-2.5">
            <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-line bg-surface-muted p-3.5">
              <input
                type="checkbox"
                className="mt-0.5"
                disabled={!isAdmin}
                checked={policy.second_approval_required}
                onChange={(event) => setPolicy({ ...policy, second_approval_required: event.target.checked })}
              />
              <span>
                <span className="text-[0.85rem] font-semibold text-ink">Require a second approval</span>
                <span className="mt-0.5 block text-[0.78rem] leading-relaxed text-muted">
                  Two different administrators must approve before a campaign can launch.
                </span>
              </span>
            </label>

            <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-line bg-surface-muted p-3.5">
              <input
                type="checkbox"
                className="mt-0.5"
                disabled={!isAdmin}
                checked={policy.opt_out_respected}
                onChange={(event) => setPolicy({ ...policy, opt_out_respected: event.target.checked })}
              />
              <span>
                <span className="text-[0.85rem] font-semibold text-ink">Respect employee opt-out</span>
                <span className="mt-0.5 block text-[0.78rem] leading-relaxed text-muted">
                  Employees who opt out through the portal are excluded from targeting.
                </span>
              </span>
            </label>
          </div>

          {isAdmin ? (
            <button type="button" className="btn-primary mt-5 w-full" disabled={busy} onClick={() => void save()}>
              {busy ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
              Save controls
            </button>
          ) : (
            <p className="mt-5 rounded-lg border border-line bg-surface-muted px-3 py-2.5 text-[0.8rem] text-muted">
              Controls are read-only for your role. An administrator can change them.
            </p>
          )}
        </section>
      </div>
    </div>
  );
}

function splitList(value: string) {
  return value
    .split(",")
    .map((entry) => entry.trim())
    .filter(Boolean);
}

function readError(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const raw = String((error as Error).message);
    try {
      const parsed = JSON.parse(raw);
      return typeof parsed === "string" ? parsed : raw;
    } catch {
      return raw;
    }
  }
  return "Policy request failed.";
}
