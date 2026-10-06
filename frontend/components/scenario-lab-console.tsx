"use client";

import clsx from "clsx";
import {
  CheckCircle2,
  FileClock,
  Info,
  Loader2,
  Mail,
  MessageSquare,
  PhoneCall,
  QrCode,
  ShieldAlert,
  Sparkles,
  Trash2,
  UserRoundCheck,
  Video,
  WandSparkles,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useCallback, useEffect, useMemo, useState } from "react";

import { StatusBadge } from "@/components/status-badge";
import { useSession } from "@/components/session-provider";
import {
  approveScenario,
  deleteScenario,
  editScenario,
  generateScenario,
  getEmployees,
  getPersonas,
  getScenarios,
  type ChannelPayload,
  type Employee,
  type Persona,
  type Scenario,
} from "@/lib/client-api";

/* ------------------------------------------------------------------ config */

const CHANNELS: Array<{
  value: string;
  label: string;
  icon: LucideIcon;
  blurb: string;
  requiresPersona: boolean;
}> = [
  { value: "email", label: "Email", icon: Mail, blurb: "Classic inbox lure with tracked link.", requiresPersona: false },
  { value: "sms", label: "SMS", icon: MessageSquare, blurb: "Smishing message to an allowlisted number.", requiresPersona: false },
  { value: "qr", label: "QR", icon: QrCode, blurb: "Email with an embedded, uniquely tracked QR code.", requiresPersona: false },
  { value: "vishing", label: "Voice", icon: PhoneCall, blurb: "Branching call script with live pressure.", requiresPersona: true },
  { value: "deepfake", label: "Deepfake", icon: Video, blurb: "Synthetic media impersonation of an approved persona.", requiresPersona: true },
];

const THEMES = [
  "invoice/payment approval",
  "password reset",
  "policy update",
  "client contract",
  "document review",
  "qr verification",
  "mfa notice",
  "leave request",
  "quote request",
  "vendor payment release",
  "executive approval request",
];

const defaultForm = {
  employee_id: "",
  channel: "email",
  theme: "invoice/payment approval",
  difficulty_level: "medium",
  persona_id: "",
  prompt_instructions:
    "Make it look like a normal internal workflow notification for this employee's role. Keep the initial message realistic and concise.",
};

/* ----------------------------------------------------------------- helpers */

function channelMeta(channel: string) {
  return CHANNELS.find((entry) => entry.value === channel) ?? CHANNELS[0];
}

function subjectLabel(channel: string) {
  if (channel === "qr") return "QR email subject";
  if (channel === "sms") return "Message title";
  if (channel === "vishing") return "Call reason";
  if (channel === "deepfake") return "Message subject";
  return "Email subject";
}

function bodyLabel(channel: string) {
  if (channel === "qr") return "QR email body";
  if (channel === "sms") return "SMS copy";
  if (channel === "vishing") return "Caller pretext";
  if (channel === "deepfake") return "Spoken transcript";
  return "Message body";
}

function aiProviderLabel(metadata?: Record<string, unknown>) {
  const provider = typeof metadata?.provider === "string" ? metadata.provider : "rule-based";
  const model = typeof metadata?.model === "string" ? metadata.model : "fallback";
  if (provider === "together") return `Together AI · ${model}`;
  if (metadata?.provider_status === "fallback") return "Built-in fallback";
  return "Built-in generator";
}

function readError(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const raw = String((error as Error).message);
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed === "string") return parsed;
      if (parsed?.errors) return [].concat(parsed.errors).join(" ");
      return raw;
    } catch {
      return raw;
    }
  }
  return "Scenario generation failed.";
}

/* --------------------------------------------------------------- component */

export function ScenarioLabConsole() {
  const { session } = useSession();
  const [employees, setEmployees] = useState<Employee[]>([]);
  const [scenarios, setScenarios] = useState<Scenario[]>([]);
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [form, setForm] = useState(defaultForm);
  const [notice, setNotice] = useState<{ tone: "ok" | "error" | "info"; text: string } | null>(null);
  const [isGenerating, setIsGenerating] = useState(false);
  const [deletingId, setDeletingId] = useState<string | null>(null);
  const [editingScenarioId, setEditingScenarioId] = useState<string | null>(null);
  const [editForm, setEditForm] = useState({
    subject: "",
    body_copy: "",
    cta_text: "",
    landing_page_copy: "",
    notes: "",
  });

  const usablePersonas = useMemo(() => personas.filter((persona) => persona.usable), [personas]);

  // A video persona cannot be used on a voice call, so it should never be offered there.
  // The backend enforces this too; filtering here just avoids a pointless error.
  const compatiblePersonas = useMemo(() => {
    if (form.channel !== "vishing") return usablePersonas;
    return usablePersonas.filter(
      (persona) => persona.modality === "voice_note" || persona.modality === "voicemail",
    );
  }, [usablePersonas, form.channel]);

  const activeChannel = channelMeta(form.channel);
  const needsPersona = activeChannel.requiresPersona;
  const personaMissing = needsPersona && compatiblePersonas.length === 0;

  const loadData = useCallback(async () => {
    if (!session) return;
    const [employeeRows, scenarioRows, personaRows] = await Promise.all([
      getEmployees(session.access_token),
      getScenarios(session.access_token),
      getPersonas(session.access_token).catch(() => [] as Persona[]),
    ]);
    setEmployees(employeeRows);
    setScenarios(scenarioRows);
    setPersonas(personaRows);
    setForm((current) => ({
      ...current,
      employee_id: current.employee_id || (employeeRows[0]?.id ?? ""),
    }));
  }, [session]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  // Keep the persona selection valid whenever the channel changes.
  useEffect(() => {
    if (!needsPersona) {
      setForm((current) => (current.persona_id ? { ...current, persona_id: "" } : current));
      return;
    }
    setForm((current) => {
      const stillValid = compatiblePersonas.some((persona) => persona.id === current.persona_id);
      if (stillValid) return current;
      return { ...current, persona_id: compatiblePersonas[0]?.id ?? "" };
    });
  }, [needsPersona, compatiblePersonas]);

  async function handleGenerate() {
    if (!session) return;
    setIsGenerating(true);
    setNotice({ tone: "info", text: "Generating scenario content and building the interaction script…" });
    try {
      const payload: Record<string, unknown> = {
        employee_id: form.employee_id,
        channel: form.channel,
        theme: form.theme,
        difficulty_level: form.difficulty_level,
        prompt_instructions: form.prompt_instructions,
      };
      if (needsPersona && form.persona_id) payload.persona_id = form.persona_id;

      await generateScenario(session.access_token, payload);
      setNotice({ tone: "ok", text: "Scenario generated. Review the content, then approve it for campaign use." });
      await loadData();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setIsGenerating(false);
    }
  }

  async function handleApprove(scenarioId: string) {
    if (!session) return;
    try {
      await approveScenario(session.access_token, scenarioId);
      setNotice({ tone: "ok", text: "Scenario approved." });
      await loadData();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    }
  }

  function startEditing(scenario: Scenario) {
    if (!scenario.latest_version) return;
    setEditingScenarioId(scenario.id);
    setEditForm({
      subject: scenario.latest_version.subject,
      body_copy: scenario.latest_version.body_copy,
      cta_text: scenario.latest_version.cta_text,
      landing_page_copy: scenario.latest_version.landing_page_copy,
      notes: scenario.latest_version.notes ?? "",
    });
  }

  async function saveEdit(scenarioId: string) {
    if (!session) return;
    try {
      await editScenario(session.access_token, scenarioId, editForm);
      setEditingScenarioId(null);
      setNotice({ tone: "ok", text: "New version saved. Re-approve it before sending." });
      await loadData();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    }
  }

  async function handleDelete(scenario: Scenario) {
    if (!session) return;
    const confirmed = window.confirm(
      `Delete "${scenario.title}"?\n\nThis removes the scenario and all of its versions. ` +
        `It cannot be undone.`,
    );
    if (!confirmed) return;

    setDeletingId(scenario.id);
    setNotice(null);
    try {
      const result = await deleteScenario(session.access_token, scenario.id);
      const versions = result.removed?.scenario_versions ?? 0;
      setNotice({
        tone: "ok",
        text: `Deleted "${result.label}"${versions ? ` and ${versions} version(s)` : ""}.`,
      });
      await loadData();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setDeletingId(null);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <section className="workspace-page-header">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div className="min-w-0">
            <div className="section-title">AI content operations</div>
            <h1 className="display-font mt-1.5 text-2xl font-bold text-ink">Scenario Studio</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
              Generate, review and version simulation content across all five channels before it reaches a campaign.
            </p>
          </div>
          <div className="grid grid-cols-3 gap-2.5">
            <StudioStat icon={WandSparkles} label="Generated" value={scenarios.length} />
            <StudioStat
              icon={CheckCircle2}
              label="Approved"
              value={scenarios.filter((scenario) => scenario.status === "approved").length}
              tone="text-signal"
            />
            <StudioStat
              icon={FileClock}
              label="In review"
              value={scenarios.filter((scenario) => scenario.status !== "approved").length}
              tone="text-caution"
            />
          </div>
        </div>
      </section>

      <div className="grid gap-4 xl:grid-cols-[400px_minmax(0,1fr)]">
        {/* Generator */}
        <section className="card self-start p-5 xl:sticky xl:top-[86px]">
          <div className="flex items-center gap-3">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-brand-500/10 text-brand-500">
              <Sparkles size={18} />
            </div>
            <div>
              <div className="section-title">Generator</div>
              <h2 className="display-font mt-0.5 text-lg font-bold text-ink">Build a scenario</h2>
            </div>
          </div>

          {/* Channel picker */}
          <div className="mt-5">
            <span className="field-label">Channel</span>
            <div className="grid grid-cols-5 gap-1.5">
              {CHANNELS.map((channel) => {
                const Icon = channel.icon;
                const active = form.channel === channel.value;
                return (
                  <button
                    key={channel.value}
                    type="button"
                    onClick={() => setForm({ ...form, channel: channel.value })}
                    title={channel.blurb}
                    className={clsx(
                      "flex flex-col items-center gap-1.5 rounded-lg border px-1 py-2.5 transition",
                      active
                        ? "border-brand-500 bg-brand-500/10 text-brand-600"
                        : "border-line bg-surface text-muted hover:border-line-strong hover:text-ink",
                    )}
                  >
                    <Icon size={16} />
                    <span className="text-[0.62rem] font-bold">{channel.label}</span>
                  </button>
                );
              })}
            </div>
            <p className="field-hint">{activeChannel.blurb}</p>
          </div>

          <div className="mt-4 grid gap-4">
            <div>
              <label className="field-label" htmlFor="gen-employee">
                Target employee
              </label>
              <select
                id="gen-employee"
                className="field"
                value={form.employee_id}
                onChange={(event) => setForm({ ...form, employee_id: event.target.value })}
              >
                {employees.map((employee) => (
                  <option key={employee.id} value={employee.id}>
                    {employee.full_name} · {employee.department_name ?? "Unassigned"}
                  </option>
                ))}
              </select>
            </div>

            {needsPersona ? (
              personaMissing ? (
                <div className="rounded-xl border border-caution/25 bg-caution/8 p-3.5">
                  <div className="flex items-center gap-2 text-caution">
                    <ShieldAlert size={15} />
                    <span className="text-[0.82rem] font-bold">No approved persona available</span>
                  </div>
                  <p className="mt-1.5 text-[0.79rem] leading-relaxed text-muted">
                    {activeChannel.label} simulations imitate a specific identity, so they require a persona that has
                    been registered and approved by a second administrator.
                  </p>
                  <Link href="/personas" className="btn-secondary btn-sm mt-3">
                    <UserRoundCheck size={13} />
                    Open persona registry
                  </Link>
                </div>
              ) : (
                <div>
                  <label className="field-label" htmlFor="gen-persona">
                    Impersonation persona
                  </label>
                  <select
                    id="gen-persona"
                    className="field"
                    value={form.persona_id}
                    onChange={(event) => setForm({ ...form, persona_id: event.target.value })}
                  >
                    {compatiblePersonas.map((persona) => (
                      <option key={persona.id} value={persona.id}>
                        {persona.display_name} · {persona.modality.replace(/_/g, " ")}
                        {persona.is_real_person ? " (consented)" : ""}
                      </option>
                    ))}
                  </select>
                  <p className="field-hint">
                    Only approved personas inside a live consent window appear here.
                  </p>
                </div>
              )
            ) : null}

            <div>
              <label className="field-label" htmlFor="gen-theme">
                Theme
              </label>
              <select
                id="gen-theme"
                className="field"
                value={form.theme}
                onChange={(event) => setForm({ ...form, theme: event.target.value })}
              >
                {THEMES.map((theme) => (
                  <option key={theme} value={theme}>
                    {theme}
                  </option>
                ))}
              </select>
            </div>

            <div>
              <span className="field-label">Difficulty</span>
              <div className="grid grid-cols-3 gap-1.5">
                {["low", "medium", "high"].map((level) => (
                  <button
                    key={level}
                    type="button"
                    onClick={() => setForm({ ...form, difficulty_level: level })}
                    className={clsx(
                      "rounded-lg border px-2 py-2 text-[0.76rem] font-bold capitalize transition",
                      form.difficulty_level === level
                        ? "border-brand-500 bg-brand-500/10 text-brand-600"
                        : "border-line bg-surface text-muted hover:text-ink",
                    )}
                  >
                    {level}
                  </button>
                ))}
              </div>
              {form.channel === "deepfake" ? (
                <p className="field-hint">Higher difficulty reveals fewer synthetic-media tells up front.</p>
              ) : null}
            </div>

            <div>
              <label className="field-label" htmlFor="gen-prompt">
                Prompt instructions
              </label>
              <textarea
                id="gen-prompt"
                className="field min-h-24"
                value={form.prompt_instructions}
                onChange={(event) => setForm({ ...form, prompt_instructions: event.target.value })}
                placeholder="Tell the generator what kind of scenario to produce for this employee context."
              />
            </div>

            {notice ? (
              <div
                className={clsx(
                  "rounded-lg border px-3 py-2.5 text-[0.79rem] leading-relaxed",
                  notice.tone === "ok" && "border-signal/25 bg-signal/8 text-signal",
                  notice.tone === "error" && "border-breach/25 bg-breach/8 text-breach",
                  notice.tone === "info" && "border-brand-500/25 bg-brand-500/8 text-brand-600",
                )}
              >
                {notice.text}
              </div>
            ) : null}

            <button
              type="button"
              onClick={() => void handleGenerate()}
              disabled={isGenerating || personaMissing || !form.employee_id}
              className="btn-primary w-full"
            >
              {isGenerating ? <Loader2 size={15} className="animate-spin" /> : <Sparkles size={15} />}
              {isGenerating ? "Generating…" : "Generate scenario"}
            </button>
          </div>
        </section>

        {/* Library */}
        <section className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <div className="section-title">Content library</div>
              <h2 className="display-font mt-0.5 text-xl font-bold text-ink">Versioned scenarios</h2>
            </div>
            <span className="badge badge-neutral">{scenarios.length} total</span>
          </div>

          {scenarios.length === 0 ? (
            <div className="card px-5 py-16 text-center">
              <WandSparkles className="mx-auto text-subtle" size={30} />
              <p className="mt-3 text-[0.92rem] font-semibold text-ink">No scenarios yet</p>
              <p className="mx-auto mt-1.5 max-w-sm text-[0.83rem] leading-relaxed text-muted">
                Generate your first scenario using the panel on the left.
              </p>
            </div>
          ) : (
            scenarios.map((scenario) => (
              <ScenarioCard
                key={scenario.id}
                scenario={scenario}
                editing={editingScenarioId === scenario.id}
                editForm={editForm}
                onEditFormChange={setEditForm}
                onStartEdit={() => startEditing(scenario)}
                onCancelEdit={() => setEditingScenarioId(null)}
                onSaveEdit={() => void saveEdit(scenario.id)}
                onApprove={() => void handleApprove(scenario.id)}
                onDelete={() => void handleDelete(scenario)}
                deleting={deletingId === scenario.id}
              />
            ))
          )}
        </section>
      </div>
    </div>
  );
}

/* ------------------------------------------------------------ scenario card */

function ScenarioCard({
  scenario,
  editing,
  editForm,
  onEditFormChange,
  onStartEdit,
  onCancelEdit,
  onSaveEdit,
  onApprove,
  onDelete,
  deleting,
}: {
  scenario: Scenario;
  editing: boolean;
  editForm: { subject: string; body_copy: string; cta_text: string; landing_page_copy: string; notes: string };
  onEditFormChange: (value: typeof editForm) => void;
  onStartEdit: () => void;
  onCancelEdit: () => void;
  onSaveEdit: () => void;
  onApprove: () => void;
  onDelete: () => void;
  deleting: boolean;
}) {
  const version = scenario.latest_version;
  const meta = channelMeta(scenario.channel);
  const ChannelIcon = meta.icon;
  const payload = version?.channel_payload;
  const isInteractive = Boolean(payload?.script?.length);

  return (
    <article className="card card-interactive overflow-hidden">
      <div className="flex flex-col gap-3 border-b border-line p-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <span className="badge badge-brand">
              <ChannelIcon size={11} />
              {meta.label}
            </span>
            <StatusBadge value={scenario.status} />
            {scenario.persona_display_name ? (
              <span className="badge badge-violet">
                <UserRoundCheck size={11} />
                {scenario.persona_display_name}
              </span>
            ) : null}
          </div>
          <h3 className="display-font mt-2.5 text-lg font-bold text-ink">{scenario.title}</h3>
          <div className="mt-1 text-[0.82rem] text-muted">
            {scenario.theme} · {scenario.difficulty_level} difficulty
            {version ? ` · v${version.version_number}` : ""}
          </div>
        </div>
      </div>

      <div className="space-y-4 p-5">
        {version ? (
          <>
            <div className="grid gap-3 sm:grid-cols-2">
              <Field label={subjectLabel(scenario.channel)} value={version.subject} strong />
              <Field label="Call to action" value={version.cta_text} strong />
            </div>

            <div>
              <div className="eyebrow">{bodyLabel(scenario.channel)}</div>
              <p className="mt-1.5 whitespace-pre-line rounded-lg bg-surface-muted p-3.5 text-[0.85rem] leading-relaxed text-ink">
                {version.body_copy}
              </p>
            </div>

            {isInteractive ? <InteractionScriptPreview payload={payload!} channel={scenario.channel} /> : null}

            <div className="grid gap-3 border-t border-line pt-4 sm:grid-cols-3">
              <Field label="Generator" value={aiProviderLabel(version.rationale_metadata)} />
              <Field label="Difficulty score" value={`${version.difficulty_score}/100`} />
              <Field
                label="Policy check"
                value={version.validation_result?.passed ? "Passed" : "Needs review"}
                tone={version.validation_result?.passed ? "text-signal" : "text-caution"}
              />
            </div>

            {version.rationale_metadata?.provider_status === "fallback" ? (
              <p role="status" className="rounded-lg border border-caution/25 bg-caution/5 px-3 py-2 text-xs leading-5 text-caution">
                The external AI provider was unavailable, so this draft used the built-in generator. {String(version.rationale_metadata.fallback_reason ?? "")}
              </p>
            ) : null}

            {scenario.detected_persuasion_triggers.length ? (
              <div className="flex flex-wrap gap-1.5">
                {scenario.detected_persuasion_triggers.map((trigger) => (
                  <span key={trigger} className="badge badge-neutral">
                    {trigger}
                  </span>
                ))}
              </div>
            ) : null}

            <details className="group">
              <summary className="inline-flex cursor-pointer list-none items-center gap-1.5 text-[0.78rem] font-semibold text-muted hover:text-ink">
                <Info size={13} />
                Landing page copy
              </summary>
              <p className="mt-2 rounded-lg border border-dashed border-line-strong bg-surface-muted p-3.5 text-[0.82rem] leading-relaxed text-muted">
                {version.landing_page_copy}
              </p>
            </details>
          </>
        ) : null}

        {editing ? (
          <div className="grid gap-3 border-t border-line pt-4">
            <div>
              <label className="field-label">Subject</label>
              <input
                className="field"
                value={editForm.subject}
                onChange={(event) => onEditFormChange({ ...editForm, subject: event.target.value })}
              />
            </div>
            <div>
              <label className="field-label">{bodyLabel(scenario.channel)}</label>
              <textarea
                className="field min-h-36"
                value={editForm.body_copy}
                onChange={(event) => onEditFormChange({ ...editForm, body_copy: event.target.value })}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="field-label">CTA text</label>
                <input
                  className="field"
                  value={editForm.cta_text}
                  onChange={(event) => onEditFormChange({ ...editForm, cta_text: event.target.value })}
                />
              </div>
              <div>
                <label className="field-label">Editor notes</label>
                <input
                  className="field"
                  value={editForm.notes}
                  onChange={(event) => onEditFormChange({ ...editForm, notes: event.target.value })}
                />
              </div>
            </div>
            <div>
              <label className="field-label">Landing page copy</label>
              <textarea
                className="field min-h-24"
                value={editForm.landing_page_copy}
                onChange={(event) => onEditFormChange({ ...editForm, landing_page_copy: event.target.value })}
              />
            </div>
            {isInteractive ? (
              <p className="field-hint">
                Editing copy creates a new version. The branching interaction script stays governed and is carried
                across unchanged.
              </p>
            ) : null}
            <div className="flex flex-wrap gap-2.5">
              <button type="button" className="btn-primary" onClick={onSaveEdit}>
                Save new version
              </button>
              <button type="button" className="btn-secondary" onClick={onCancelEdit}>
                Cancel
              </button>
            </div>
          </div>
        ) : (
          <div className="flex flex-wrap items-center gap-2.5 border-t border-line pt-4">
            <button type="button" className="btn-secondary btn-sm" onClick={onStartEdit}>
              Edit content
            </button>
            {scenario.status !== "approved" ? (
              <button type="button" className="btn-primary btn-sm" onClick={onApprove}>
                <CheckCircle2 size={13} />
                Approve scenario
              </button>
            ) : null}
            <button
              type="button"
              className="btn-danger btn-sm ml-auto"
              onClick={onDelete}
              disabled={deleting}
              title="Delete this scenario and all its versions"
            >
              {deleting ? <Loader2 size={13} className="animate-spin" /> : <Trash2 size={13} />}
              Delete
            </button>
          </div>
        )}
      </div>
    </article>
  );
}

/* --------------------------------------------------- interaction script view */

function InteractionScriptPreview({ payload, channel }: { payload: ChannelPayload; channel: string }) {
  const steps = payload.script ?? [];
  const header = payload.header ?? {};

  return (
    <div className="rounded-xl border border-brand-500/20 bg-brand-500/[0.04] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 text-brand-600">
          {channel === "vishing" ? <PhoneCall size={14} /> : <Video size={14} />}
          <span className="text-[0.7rem] font-bold uppercase tracking-[0.13em]">
            {channel === "vishing" ? "Call script" : "Impersonation brief"}
          </span>
        </div>
        <span className="badge badge-brand">{steps.length} decision points</span>
      </div>

      <div className="mt-3 flex flex-wrap gap-x-5 gap-y-1.5 text-[0.76rem] text-muted">
        {header.caller_id_display ? (
          <span className="numeric font-mono">Caller ID {header.caller_id_display}</span>
        ) : null}
        {header.spoofed_display_name ? <span>Presents as {header.spoofed_display_name}</span> : null}
        {header.modality_noun ? <span>Arrives as a {header.modality_noun}</span> : null}
        {header.requested_action ? <span className="w-full">Ask: {header.requested_action}</span> : null}
      </div>

      <ol className="mt-3.5 space-y-2.5">
        {steps.map((step, index) => (
          <li key={step.key} className="rounded-lg border border-line bg-surface p-3">
            <div className="flex items-start gap-2.5">
              <span className="mt-0.5 grid h-5 w-5 shrink-0 place-items-center rounded bg-brand-500/12 text-[0.65rem] font-bold text-brand-600">
                {index + 1}
              </span>
              <div className="min-w-0 flex-1">
                <p className="text-[0.82rem] leading-relaxed text-ink">{step.speaker_line}</p>
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {step.pressure_tactic ? (
                    <span className="badge badge-warn">{step.pressure_tactic}</span>
                  ) : null}
                  {(step.options ?? []).map((option: Record<string, any>) => (
                    <span
                      key={option.key}
                      className={clsx("badge", option.safe ? "badge-success" : "badge-neutral")}
                    >
                      {option.label}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          </li>
        ))}
      </ol>

      {payload.synthetic_artifacts?.length ? (
        <div className="mt-3.5 border-t border-line pt-3.5">
          <div className="eyebrow">Synthetic tells embedded ({payload.synthetic_artifacts.length})</div>
          <div className="mt-2 flex flex-wrap gap-1.5">
            {payload.synthetic_artifacts.map((artifact) => (
              <span
                key={artifact.key}
                className={clsx("badge", artifact.revealed_upfront ? "badge-brand" : "badge-neutral")}
                title={artifact.detail}
              >
                {artifact.label}
              </span>
            ))}
          </div>
        </div>
      ) : null}

      {payload.safety_notice ? (
        <p className="mt-3.5 rounded-lg bg-surface-muted px-3 py-2 text-[0.75rem] leading-relaxed text-muted">
          {payload.safety_notice}
        </p>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------ small pieces */

function StudioStat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: LucideIcon;
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className="card-muted min-w-[92px] px-3 py-2.5">
      <div className="flex items-center gap-1.5 text-subtle">
        <Icon size={12} />
        <span className="text-[0.58rem] font-bold uppercase tracking-[0.1em]">{label}</span>
      </div>
      <div className={clsx("numeric display-font mt-1 text-lg font-bold", tone ?? "text-ink")}>{value}</div>
    </div>
  );
}

function Field({
  label,
  value,
  strong,
  tone,
}: {
  label: string;
  value: React.ReactNode;
  strong?: boolean;
  tone?: string;
}) {
  return (
    <div>
      <div className="eyebrow">{label}</div>
      <div
        className={clsx(
          "mt-1 text-[0.85rem]",
          strong ? "font-semibold text-ink" : "text-muted",
          tone,
        )}
      >
        {value}
      </div>
    </div>
  );
}
