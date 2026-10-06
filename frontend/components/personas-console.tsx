"use client";

import clsx from "clsx";
import {
  BadgeCheck,
  Ban,
  CalendarClock,
  FileSignature,
  Loader2,
  Mic,
  Plus,
  ShieldAlert,
  ShieldCheck,
  Trash2,
  UserRoundCheck,
  Video,
  X,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useSession } from "@/components/session-provider";
import {
  approvePersona,
  createPersona,
  deletePersona,
  getImpersonationSettings,
  getMediaProviders,
  getPersonas,
  revokePersona,
  updateImpersonationSettings,
  uploadFaceImage,
  uploadVoiceSample,
  type ImpersonationSettings,
  type MediaModality,
  type MediaProviderStatus,
  type Persona,
  type PersonaStatus,
} from "@/lib/client-api";

const STATUS_META: Record<PersonaStatus, { label: string; badge: string }> = {
  draft: { label: "Draft", badge: "badge-neutral" },
  pending_consent: { label: "Awaiting consent", badge: "badge-warn" },
  approved: { label: "Approved", badge: "badge-success" },
  revoked: { label: "Revoked", badge: "badge-danger" },
  expired: { label: "Consent expired", badge: "badge-danger" },
};

const MODALITY_META: Record<MediaModality, { label: string; icon: typeof Mic }> = {
  voice_note: { label: "Voice note", icon: Mic },
  voicemail: { label: "Voicemail", icon: Mic },
  video_message: { label: "Video message", icon: Video },
  live_video_call: { label: "Live video call", icon: Video },
};

const emptyForm = {
  display_name: "",
  role_title: "",
  relationship_to_targets: "internal colleague",
  modality: "voice_note" as MediaModality,
  is_real_person: false,
  consent_reference: "",
  consent_evidence_note: "",
  consent_expires_at: "",
  detection_tells: "",
};

export function PersonasConsole() {
  const { session } = useSession();
  const [personas, setPersonas] = useState<Persona[]>([]);
  const [settings, setSettings] = useState<ImpersonationSettings | null>(null);
  const [providers, setProviders] = useState<MediaProviderStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [form, setForm] = useState(emptyForm);
  const [showForm, setShowForm] = useState(false);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const isAdmin = session?.user.roles.includes("admin") ?? false;

  const load = useCallback(async () => {
    if (!session) return;
    setLoading(true);
    try {
      const [personaRows, settingsRow, providerRow] = await Promise.all([
        getPersonas(session.access_token),
        getImpersonationSettings(session.access_token).catch(() => null),
        getMediaProviders(session.access_token).catch(() => null),
      ]);
      setPersonas(personaRows);
      setSettings(settingsRow);
      setProviders(providerRow);
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setLoading(false);
    }
  }, [session]);

  useEffect(() => {
    void load();
  }, [load]);

  const counts = useMemo(
    () => ({
      total: personas.length,
      usable: personas.filter((persona) => persona.usable).length,
      realPeople: personas.filter((persona) => persona.is_real_person).length,
      blocked: personas.filter((persona) => ["revoked", "expired"].includes(persona.status)).length,
    }),
    [personas],
  );

  async function submitForm() {
    if (!session) return;
    setBusyId("new");
    setNotice(null);
    try {
      await createPersona(session.access_token, {
        display_name: form.display_name.trim(),
        role_title: form.role_title.trim(),
        relationship_to_targets: form.relationship_to_targets.trim() || "internal colleague",
        modality: form.modality,
        is_real_person: form.is_real_person,
        consent_reference: form.consent_reference.trim() || null,
        consent_evidence_note: form.consent_evidence_note.trim() || null,
        consent_expires_at: form.consent_expires_at ? new Date(form.consent_expires_at).toISOString() : null,
        detection_tells: form.detection_tells
          .split("\n")
          .map((line) => line.trim())
          .filter(Boolean),
      });
      setForm(emptyForm);
      setShowForm(false);
      setNotice({
        tone: "ok",
        text: "Persona registered. A second administrator must approve it before any simulation can use it.",
      });
      await load();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusyId(null);
    }
  }

  async function handleApprove(persona: Persona) {
    if (!session) return;
    setBusyId(persona.id);
    setNotice(null);
    try {
      await approvePersona(session.access_token, persona.id);
      setNotice({ tone: "ok", text: `${persona.display_name} approved for simulation use.` });
      await load();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusyId(null);
    }
  }

  async function handleRevoke(persona: Persona) {
    if (!session) return;
    const reason = window.prompt(`Why is "${persona.display_name}" being revoked?`, "Authorization withdrawn");
    if (reason === null) return;
    setBusyId(persona.id);
    setNotice(null);
    try {
      await revokePersona(session.access_token, persona.id, reason);
      setNotice({ tone: "ok", text: `${persona.display_name} revoked. It can no longer be used.` });
      await load();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusyId(null);
    }
  }

  async function handleDelete(persona: Persona) {
    if (!session) return;
    if (
      !window.confirm(
        `Delete persona "${persona.display_name}"?\n\nThis removes it permanently along with any ` +
          `enrolled voice or face media. Use Revoke instead if it has been used in a simulation.`,
      )
    ) {
      return;
    }
    setBusyId(`${persona.id}-delete`);
    setNotice(null);
    try {
      const result = await deletePersona(session.access_token, persona.id);
      setNotice({ tone: "ok", text: `Deleted persona "${result.label}".` });
      await load();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusyId(null);
    }
  }

  async function handleUpload(persona: Persona, kind: "voice" | "face", file: File) {
    if (!session) return;
    setBusyId(`${persona.id}-${kind}`);
    setNotice(null);
    try {
      if (kind === "voice") {
        const result = await uploadVoiceSample(session.access_token, persona.id, file);
        setNotice({
          tone: "ok",
          text: result.cloned
            ? `Voice cloned for ${persona.display_name} (${result.provider}). Deepfake and voice scenarios will now speak in this voice.`
            : `Voice sample stored for ${persona.display_name}. Configure a voice provider to enable real cloning.`,
        });
      } else {
        await uploadFaceImage(session.access_token, persona.id, file);
        setNotice({ tone: "ok", text: `Face image stored for ${persona.display_name}.` });
      }
      await load();
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusyId(null);
    }
  }

  async function toggleImpersonation(enabled: boolean) {
    if (!session || !settings) return;
    setBusyId("settings");
    try {
      const next = await updateImpersonationSettings(session.access_token, {
        impersonation_enabled: enabled,
        impersonation_disclosure_text: settings.impersonation_disclosure_text,
        voice_provider_enabled: settings.voice_provider_enabled,
        voice_provider_mode: settings.voice_provider_mode,
      });
      setSettings(next);
      setNotice({
        tone: "ok",
        text: enabled
          ? "Synthetic media simulations enabled for this organization."
          : "Synthetic media simulations disabled. Existing deepfake scenarios can no longer be generated.",
      });
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <section className="workspace-page-header">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="min-w-0">
            <div className="section-title">Governance</div>
            <h1 className="display-font mt-1.5 text-2xl font-bold text-ink">Impersonation personas</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
              Voice and synthetic-media simulations imitate somebody. Every persona used in a simulation is
              registered here, approved by a second administrator, and bound to a consent window that expires.
              Nothing outside this registry can be impersonated.
            </p>
          </div>
          {isAdmin ? (
            <button type="button" className="btn-primary shrink-0" onClick={() => setShowForm((value) => !value)}>
              {showForm ? <X size={15} /> : <Plus size={15} />}
              {showForm ? "Cancel" : "Register persona"}
            </button>
          ) : null}
        </div>

        <div className="mt-5 grid grid-cols-2 gap-3 lg:grid-cols-4">
          <Stat icon={UserRoundCheck} label="Registered" value={counts.total} />
          <Stat icon={ShieldCheck} label="Usable now" value={counts.usable} tone="text-signal" />
          <Stat icon={FileSignature} label="Real people" value={counts.realPeople} />
          <Stat icon={Ban} label="Blocked" value={counts.blocked} tone="text-breach" />
        </div>
      </section>

      {/* Org-level switch */}
      {settings ? (
        <section
          className={clsx(
            "card p-4 md:p-5",
            settings.impersonation_enabled ? "rail-signal" : "rail-caution",
          )}
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="min-w-0">
              <div className="flex items-center gap-2">
                {settings.impersonation_enabled ? (
                  <ShieldCheck size={16} className="text-signal" />
                ) : (
                  <ShieldAlert size={16} className="text-caution" />
                )}
                <h2 className="text-[0.95rem] font-bold text-ink">
                  Synthetic media simulations are {settings.impersonation_enabled ? "enabled" : "disabled"}
                </h2>
              </div>
              <p className="mt-1.5 text-[0.82rem] leading-relaxed text-muted">
                {settings.impersonation_enabled
                  ? `Deepfake scenarios can be generated against the ${settings.approved_persona_count} approved persona${settings.approved_persona_count === 1 ? "" : "s"}.`
                  : "Deepfake scenario generation is blocked organization-wide, regardless of persona status."}
              </p>
            </div>
            {isAdmin ? (
              <button
                type="button"
                className={settings.impersonation_enabled ? "btn-danger shrink-0" : "btn-primary shrink-0"}
                disabled={busyId === "settings"}
                onClick={() => void toggleImpersonation(!settings.impersonation_enabled)}
              >
                {busyId === "settings" ? <Loader2 size={15} className="animate-spin" /> : null}
                {settings.impersonation_enabled ? "Disable" : "Enable"}
              </button>
            ) : null}
          </div>
        </section>
      ) : null}

      {notice ? (
        <div
          className={clsx(
            "rounded-xl border px-4 py-3 text-[0.85rem] leading-relaxed",
            notice.tone === "ok"
              ? "border-signal/25 bg-signal/8 text-signal"
              : "border-breach/25 bg-breach/8 text-breach",
          )}
        >
          {notice.text}
        </div>
      ) : null}

      {/* Registration form */}
      {showForm && isAdmin ? (
        <section className="card p-5 md:p-6">
          <h2 className="display-font text-lg font-bold text-ink">Register a persona</h2>
          <p className="mt-1.5 text-[0.83rem] leading-relaxed text-muted">
            Prefer a synthetic composite role over a named individual. A real person may only be used with a
            signed authorization reference and an expiry date on file.
          </p>

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div>
              <label className="field-label" htmlFor="persona-name">
                Display name
              </label>
              <input
                id="persona-name"
                className="field"
                value={form.display_name}
                onChange={(event) => setForm({ ...form, display_name: event.target.value })}
                placeholder="Finance Director"
              />
              <p className="field-hint">How the persona identifies itself to the target.</p>
            </div>

            <div>
              <label className="field-label" htmlFor="persona-role">
                Role title
              </label>
              <input
                id="persona-role"
                className="field"
                value={form.role_title}
                onChange={(event) => setForm({ ...form, role_title: event.target.value })}
                placeholder="Director of Finance"
              />
            </div>

            <div>
              <label className="field-label" htmlFor="persona-relationship">
                Relationship to targets
              </label>
              <input
                id="persona-relationship"
                className="field"
                value={form.relationship_to_targets}
                onChange={(event) => setForm({ ...form, relationship_to_targets: event.target.value })}
                placeholder="senior leadership"
              />
            </div>

            <div>
              <label className="field-label" htmlFor="persona-modality">
                Presentation
              </label>
              <select
                id="persona-modality"
                className="field"
                value={form.modality}
                onChange={(event) => setForm({ ...form, modality: event.target.value as MediaModality })}
              >
                <option value="voice_note">Voice note</option>
                <option value="voicemail">Voicemail</option>
                <option value="video_message">Video message</option>
                <option value="live_video_call">Live video call</option>
              </select>
              <p className="field-hint">Video personas cannot be used on the voice channel.</p>
            </div>

            <div className="md:col-span-2">
              <label className="flex cursor-pointer items-start gap-2.5 rounded-xl border border-line-strong bg-surface-muted p-3.5">
                <input
                  type="checkbox"
                  className="mt-0.5"
                  checked={form.is_real_person}
                  onChange={(event) => setForm({ ...form, is_real_person: event.target.checked })}
                />
                <span>
                  <span className="text-[0.85rem] font-semibold text-ink">
                    This persona represents a real, identifiable person
                  </span>
                  <span className="mt-1 block text-[0.78rem] leading-relaxed text-muted">
                    Requires a signed consent reference and an expiry date. The individual may withdraw at any
                    time, which immediately blocks every scenario using this persona.
                  </span>
                </span>
              </label>
            </div>

            {form.is_real_person ? (
              <>
                <div>
                  <label className="field-label" htmlFor="persona-consent-ref">
                    Consent reference
                  </label>
                  <input
                    id="persona-consent-ref"
                    className="field"
                    value={form.consent_reference}
                    onChange={(event) => setForm({ ...form, consent_reference: event.target.value })}
                    placeholder="HR-AUTH-2026-014"
                  />
                  <p className="field-hint">Identifier for the signed authorization held on file.</p>
                </div>
                <div>
                  <label className="field-label" htmlFor="persona-consent-expiry">
                    Consent expires
                  </label>
                  <input
                    id="persona-consent-expiry"
                    type="date"
                    className="field"
                    value={form.consent_expires_at}
                    onChange={(event) => setForm({ ...form, consent_expires_at: event.target.value })}
                  />
                </div>
                <div className="md:col-span-2">
                  <label className="field-label" htmlFor="persona-consent-note">
                    Consent evidence note
                  </label>
                  <textarea
                    id="persona-consent-note"
                    className="field min-h-20"
                    value={form.consent_evidence_note}
                    onChange={(event) => setForm({ ...form, consent_evidence_note: event.target.value })}
                    placeholder="Where the authorization is stored, who witnessed it, what scope was agreed."
                  />
                  <p className="field-hint">Encrypted at rest.</p>
                </div>
              </>
            ) : null}

            <div className="md:col-span-2">
              <label className="field-label" htmlFor="persona-tells">
                Detection tells (one per line)
              </label>
              <textarea
                id="persona-tells"
                className="field min-h-24"
                value={form.detection_tells}
                onChange={(event) => setForm({ ...form, detection_tells: event.target.value })}
                placeholder={"Recognition is not verification.\nConfirm on a channel you chose yourself."}
              />
              <p className="field-hint">Shown to the employee in the debrief after the simulation resolves.</p>
            </div>
          </div>

          <div className="mt-5 flex flex-wrap gap-2.5">
            <button
              type="button"
              className="btn-primary"
              disabled={busyId === "new" || !form.display_name.trim() || !form.role_title.trim()}
              onClick={() => void submitForm()}
            >
              {busyId === "new" ? <Loader2 size={15} className="animate-spin" /> : <Plus size={15} />}
              Register persona
            </button>
            <button type="button" className="btn-secondary" onClick={() => setShowForm(false)}>
              Cancel
            </button>
          </div>
        </section>
      ) : null}

      {/* Registry */}
      <section className="card overflow-hidden">
        <div className="flex items-center justify-between gap-3 border-b border-line px-5 py-4">
          <h2 className="display-font text-lg font-bold text-ink">Registry</h2>
          <span className="badge badge-neutral">{personas.length} registered</span>
        </div>

        {loading ? (
          <div className="space-y-3 p-5">
            {[0, 1, 2].map((index) => (
              <div key={index} className="skeleton h-24 w-full" />
            ))}
          </div>
        ) : personas.length === 0 ? (
          <div className="px-5 py-14 text-center">
            <UserRoundCheck className="mx-auto text-subtle" size={30} />
            <p className="mt-3 text-[0.9rem] font-semibold text-ink">No personas registered</p>
            <p className="mx-auto mt-1.5 max-w-md text-[0.83rem] leading-relaxed text-muted">
              Voice and deepfake scenarios cannot be generated until at least one persona is registered and
              approved by a second administrator.
            </p>
          </div>
        ) : (
          <ul className="divide-y divide-line">
            {personas.map((persona) => {
              const status = STATUS_META[persona.status];
              const modality = MODALITY_META[persona.modality];
              const ModalityIcon = modality?.icon ?? Mic;
              const busy = busyId === persona.id;

              return (
                <li key={persona.id} className="p-5">
                  <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <h3 className="text-[1rem] font-bold text-ink">{persona.display_name}</h3>
                        <span className={clsx("badge", status?.badge ?? "badge-neutral")}>
                          {status?.label ?? persona.status}
                        </span>
                        {persona.is_real_person ? (
                          <span className="badge badge-violet">
                            <FileSignature size={11} />
                            Real person
                          </span>
                        ) : (
                          <span className="badge badge-neutral">Synthetic role</span>
                        )}
                      </div>

                      <div className="mt-1.5 text-[0.84rem] text-muted">
                        {persona.role_title} · {persona.relationship_to_targets}
                      </div>

                      <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-2 text-[0.78rem] text-muted">
                        <span className="inline-flex items-center gap-1.5">
                          <ModalityIcon size={13} className="text-brand-500" />
                          {modality?.label ?? persona.modality}
                        </span>
                        <span className="numeric font-mono text-subtle">{persona.reference_code}</span>
                        {persona.consent_reference ? (
                          <span className="inline-flex items-center gap-1.5">
                            <FileSignature size={13} className="text-violet" />
                            {persona.consent_reference}
                          </span>
                        ) : null}
                        {persona.consent_expires_at ? (
                          <span className="inline-flex items-center gap-1.5">
                            <CalendarClock size={13} className={persona.usable ? "text-muted" : "text-breach"} />
                            Expires {formatDate(persona.consent_expires_at)}
                          </span>
                        ) : null}
                        <span>
                          Used in {persona.usage_count} scenario{persona.usage_count === 1 ? "" : "s"}
                        </span>
                      </div>

                      {persona.revocation_reason ? (
                        <p className="mt-3 rounded-lg border border-breach/20 bg-breach/6 px-3 py-2 text-[0.79rem] text-breach">
                          Revoked: {persona.revocation_reason}
                        </p>
                      ) : null}

                      {persona.detection_tells.length ? (
                        <ul className="mt-3 space-y-1.5">
                          {persona.detection_tells.map((tell) => (
                            <li key={tell} className="flex gap-2 text-[0.79rem] leading-relaxed text-muted">
                              <BadgeCheck size={13} className="mt-0.5 shrink-0 text-brand-500" />
                              {tell}
                            </li>
                          ))}
                        </ul>
                      ) : null}

                      {isAdmin && persona.is_real_person && persona.status !== "revoked" ? (
                        <MediaEnrollment
                          persona={persona}
                          providers={providers}
                          busyId={busyId}
                          onUpload={handleUpload}
                        />
                      ) : null}
                    </div>

                    {isAdmin ? (
                      <div className="flex shrink-0 flex-wrap gap-2">
                        {persona.status !== "approved" && persona.status !== "revoked" ? (
                          <button
                            type="button"
                            className="btn-secondary btn-sm"
                            disabled={busy}
                            onClick={() => void handleApprove(persona)}
                          >
                            {busy ? <Loader2 size={13} className="animate-spin" /> : <ShieldCheck size={13} />}
                            Approve
                          </button>
                        ) : null}
                        {persona.status !== "revoked" ? (
                          <button
                            type="button"
                            className="btn-danger btn-sm"
                            disabled={busy}
                            onClick={() => void handleRevoke(persona)}
                          >
                            <Ban size={13} />
                            Revoke
                          </button>
                        ) : null}
                        {persona.usage_count === 0 ? (
                          <button
                            type="button"
                            className="btn-ghost btn-sm text-breach"
                            disabled={busyId === `${persona.id}-delete`}
                            onClick={() => void handleDelete(persona)}
                            title="Delete this unused persona"
                          >
                            {busyId === `${persona.id}-delete` ? (
                              <Loader2 size={13} className="animate-spin" />
                            ) : (
                              <Trash2 size={13} />
                            )}
                            Delete
                          </button>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                </li>
              );
            })}
          </ul>
        )}
      </section>
    </div>
  );
}

/** Consent-gated enrolment of a real voice / face for cloning. Only rendered for a
 *  real-person, non-revoked persona and for admins. */
function MediaEnrollment({
  persona,
  providers,
  busyId,
  onUpload,
}: {
  persona: Persona;
  providers: MediaProviderStatus | null;
  busyId: string | null;
  onUpload: (persona: Persona, kind: "voice" | "face", file: File) => void;
}) {
  const voiceConfigured = providers?.voice.configured ?? false;
  const videoConfigured = providers?.video.configured ?? false;
  const wantsVideo = persona.modality === "video_message" || persona.modality === "live_video_call";
  const voiceEnrolled = Boolean(persona.voice_clone_ref);
  const voiceBusy = busyId === `${persona.id}-voice`;
  const faceBusy = busyId === `${persona.id}-face`;

  return (
    <div className="mt-4 rounded-xl border border-violet/25 bg-violet/[0.05] p-3.5">
      <div className="flex items-center gap-2 text-[0.66rem] font-bold uppercase tracking-[0.14em] text-violet">
        <FileSignature size={13} />
        Consented media enrolment
      </div>
      <p className="mt-1.5 text-[0.76rem] leading-relaxed text-muted">
        Upload a short sample of this person&apos;s real voice (and a face photo for video). It is used
        only to clone their likeness for authorized simulations, and is deleted the moment consent is
        revoked.
      </p>

      <div className="mt-3 flex flex-wrap items-center gap-2">
        <label
          className={clsx(
            "btn-secondary btn-sm cursor-pointer",
            voiceBusy && "pointer-events-none opacity-60",
          )}
        >
          {voiceBusy ? <Loader2 size={13} className="animate-spin" /> : <Mic size={13} />}
          {voiceEnrolled ? "Replace voice sample" : "Upload voice sample"}
          <input
            type="file"
            accept="audio/*"
            className="hidden"
            onChange={(event) => {
              const file = event.target.files?.[0];
              if (file) onUpload(persona, "voice", file);
              event.target.value = "";
            }}
          />
        </label>

        {voiceEnrolled ? (
          <span className="badge badge-success">
            <BadgeCheck size={11} />
            Voice cloned
          </span>
        ) : voiceConfigured ? (
          <span className="text-[0.72rem] text-muted">Ready to clone ({providers?.voice.provider})</span>
        ) : (
          <span className="text-[0.72rem] text-caution">Stored only — no voice provider configured</span>
        )}

        {wantsVideo ? (
          <>
            <label
              className={clsx(
                "btn-secondary btn-sm cursor-pointer",
                faceBusy && "pointer-events-none opacity-60",
              )}
            >
              {faceBusy ? <Loader2 size={13} className="animate-spin" /> : <Video size={13} />}
              {persona.voice_clone_ref && videoConfigured ? "Replace face photo" : "Upload face photo"}
              <input
                type="file"
                accept="image/png,image/jpeg"
                className="hidden"
                onChange={(event) => {
                  const file = event.target.files?.[0];
                  if (file) onUpload(persona, "face", file);
                  event.target.value = "";
                }}
              />
            </label>
            {!videoConfigured ? (
              <span className="text-[0.72rem] text-caution">No video provider configured</span>
            ) : null}
          </>
        ) : null}
      </div>
    </div>
  );
}

function Stat({
  icon: Icon,
  label,
  value,
  tone,
}: {
  icon: typeof ShieldCheck;
  label: string;
  value: number;
  tone?: string;
}) {
  return (
    <div className="card-muted px-3.5 py-3">
      <div className="flex items-center gap-1.5 text-subtle">
        <Icon size={13} />
        <span className="text-[0.62rem] font-bold uppercase tracking-[0.12em]">{label}</span>
      </div>
      <div className={clsx("numeric display-font mt-1 text-xl font-bold", tone ?? "text-ink")}>{value}</div>
    </div>
  );
}

function formatDate(value: string) {
  try {
    return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
  } catch {
    return value;
  }
}

function readError(error: unknown): string {
  if (error && typeof error === "object" && "message" in error) {
    const raw = String((error as Error).message);
    try {
      const parsed = JSON.parse(raw);
      if (typeof parsed === "string") return parsed;
      if (parsed?.errors) return String(parsed.errors);
      return raw;
    } catch {
      return raw;
    }
  }
  return "Request failed.";
}
