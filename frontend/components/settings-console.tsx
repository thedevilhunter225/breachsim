"use client";

import clsx from "clsx";
import {
  Building2,
  Info,
  KeyRound,
  Loader2,
  Mail,
  MessageSquare,
  Save,
  ShieldAlert,
  ShieldCheck,
  UserPlus,
  UsersRound,
  Video,
  CloudCog,
  type LucideIcon,
} from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useSession } from "@/components/session-provider";
import { EnterpriseSetupConsole } from "@/components/enterprise-setup-console";
import {
  createOperator,
  getCurrentOrg,
  getEmailIntegration,
  getImpersonationSettings,
  getSmsIntegration,
  getOperators,
  resetOperatorPassword,
  updateCurrentOrg,
  updateEmailIntegration,
  updateImpersonationSettings,
  updateSmsIntegration,
  updateOperator,
  type EmailIntegration,
  type ImpersonationSettings,
  type OrganizationProfile,
  type OperatorAccount,
  type SmsIntegration,
} from "@/lib/client-api";

type TabKey = "launch" | "organization" | "operators" | "email" | "sms" | "impersonation";

const TABS: Array<{ key: TabKey; label: string; icon: LucideIcon }> = [
  { key: "launch", label: "Launch setup", icon: CloudCog },
  { key: "organization", label: "Organization", icon: Building2 },
  { key: "operators", label: "Operators", icon: UsersRound },
  { key: "email", label: "Email", icon: Mail },
  { key: "sms", label: "SMS", icon: MessageSquare },
  { key: "impersonation", label: "Impersonation", icon: Video },
];

const defaultEmail: EmailIntegration & { smtp_password: string } = {
  email_provider_enabled: false,
  email_provider_mode: "sandbox",
  smtp_host: "",
  smtp_port: 587,
  smtp_username: "",
  smtp_from_email: "",
  smtp_sender_name: "",
  smtp_recipient_allowlist: [],
  has_password: false,
  smtp_password: "",
};

const defaultSms: SmsIntegration & { sms_auth_token: string } = {
  sms_provider_enabled: false,
  sms_provider_mode: "sandbox",
  sms_api_base_url: "https://api.twilio.com/2010-04-01",
  sms_account_sid: "",
  sms_from_number: "",
  sms_recipient_allowlist: [],
  has_auth_token: false,
  sms_auth_token: "",
};

const defaultOrg: OrganizationProfile = {
  id: "",
  name: "",
  slug: "",
  timezone: "Asia/Karachi",
  retention_days: 365,
  privacy_notice: "Training and security awareness platform.",
  reporting_identity_mode: "pseudonymous",
};

export function SettingsConsole() {
  const { session } = useSession();
  const [tab, setTab] = useState<TabKey>("launch");
  const [org, setOrg] = useState(defaultOrg);
  const [email, setEmail] = useState(defaultEmail);
  const [sms, setSms] = useState(defaultSms);
  const [impersonation, setImpersonation] = useState<ImpersonationSettings | null>(null);
  const [operators, setOperators] = useState<OperatorAccount[]>([]);
  const [operatorForm, setOperatorForm] = useState({
    full_name: "",
    email: "",
    password: "",
    role: "campaign_manager",
  });
  const [resetPasswords, setResetPasswords] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    const isAdmin = session.user.roles.includes("admin");
    const [orgValue, emailValue, smsValue, impersonationValue, operatorValues] = await Promise.all([
      getCurrentOrg(session.access_token),
      getEmailIntegration(session.access_token),
      getSmsIntegration(session.access_token).catch(() => null),
      getImpersonationSettings(session.access_token).catch(() => null),
      isAdmin ? getOperators(session.access_token) : Promise.resolve([]),
    ]);
    setOrg(orgValue);
    setEmail({ ...defaultEmail, ...emailValue, smtp_password: "" });
    if (smsValue) setSms({ ...defaultSms, ...smsValue, sms_auth_token: "" });
    setImpersonation(impersonationValue);
    setOperators(operatorValues);
  }, [session]);

  useEffect(() => {
    let active = true;
    void load().catch((error) => {
      if (active) setNotice({ tone: "error", text: readError(error) });
    });
    return () => {
      active = false;
    };
  }, [load]);

  async function save(key: string, action: () => Promise<unknown>, success: string) {
    setBusy(key);
    setNotice(null);
    try {
      await action();
      setNotice({ tone: "ok", text: success });
    } catch (error) {
      setNotice({ tone: "error", text: readError(error) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <section className="card p-5 md:p-6">
        <div className="section-title">Workspace administration</div>
        <h1 className="display-font mt-1.5 text-2xl font-bold text-ink">Organization, operators and integrations</h1>
        <p className="mt-2 max-w-2xl text-sm leading-relaxed text-muted">
          Workspace identity, data retention, and the delivery providers each simulation channel uses.
        </p>

        <nav className="mt-5 flex flex-wrap gap-1.5">
          {TABS.filter((entry) => entry.key !== "operators" || session?.user.roles.includes("admin")).map((entry) => {
            const Icon = entry.icon;
            const active = tab === entry.key;
            return (
              <button
                key={entry.key}
                type="button"
                onClick={() => setTab(entry.key)}
                className={clsx(
                  "inline-flex items-center gap-2 rounded-lg border px-3.5 py-2 text-[0.82rem] font-semibold transition",
                  active
                    ? "border-brand-500 bg-brand-500/10 text-brand-600"
                    : "border-line bg-surface text-muted hover:border-line-strong hover:text-ink",
                )}
              >
                <Icon size={14} />
                {entry.label}
              </button>
            );
          })}
        </nav>
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

      {tab === "launch" ? <EnterpriseSetupConsole /> : null}

      {tab === "organization" ? (
        <section className="card p-5 md:p-6">
          <SectionHeader title="Organization profile" subtitle="Identity, timezone and retention window." />
          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <div>
              <label className="field-label" htmlFor="org-name">
                Organization name
              </label>
              <input
                id="org-name"
                className="field"
                value={org.name}
                onChange={(event) => setOrg({ ...org, name: event.target.value })}
              />
            </div>
            <div>
              <label className="field-label" htmlFor="org-timezone">
                Timezone
              </label>
              <input
                id="org-timezone"
                className="field"
                value={org.timezone}
                onChange={(event) => setOrg({ ...org, timezone: event.target.value })}
              />
              <p className="field-hint">Used for working-hours guardrails in the policy engine.</p>
            </div>
            <div>
              <label className="field-label" htmlFor="org-retention">
                Retention (days)
              </label>
              <input
                id="org-retention"
                type="number"
                className="field"
                value={org.retention_days}
                onChange={(event) => setOrg({ ...org, retention_days: Number(event.target.value) })}
              />
            </div>
            <div>
              <span className="field-label">Workspace slug</span>
              <div className="numeric field bg-surface-muted font-mono text-muted">{org.slug || "generated"}</div>
            </div>
            <div>
              <label className="field-label" htmlFor="org-reporting-identity">Reporting identity</label>
              <select id="org-reporting-identity" className="field" value={org.reporting_identity_mode} onChange={(event) => setOrg({ ...org, reporting_identity_mode: event.target.value as OrganizationProfile["reporting_identity_mode"] })}>
                <option value="pseudonymous">Pseudonymous (recommended)</option>
                <option value="named">Named · restricted role required</option>
              </select>
              <p className="field-hint">Named exports still require the Risk Identity Viewer role.</p>
            </div>
            <div className="md:col-span-2">
              <label className="field-label" htmlFor="org-privacy">
                Privacy notice
              </label>
              <textarea
                id="org-privacy"
                className="field min-h-28"
                value={org.privacy_notice}
                onChange={(event) => setOrg({ ...org, privacy_notice: event.target.value })}
              />
              <p className="field-hint">Shown to employees in the self-service portal.</p>
            </div>
          </div>
          <button
            type="button"
            className="btn-primary mt-5"
            disabled={busy === "org"}
            onClick={() =>
              void save(
                "org",
                async () => {
                  const next = await updateCurrentOrg(session!.access_token, {
                    name: org.name,
                    timezone: org.timezone,
                    retention_days: org.retention_days,
                    privacy_notice: org.privacy_notice,
                    reporting_identity_mode: org.reporting_identity_mode,
                  });
                  setOrg(next);
                },
                "Organization settings saved.",
              )
            }
          >
            {busy === "org" ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
            Save organization
          </button>
        </section>
      ) : null}

      {tab === "operators" && session?.user.roles.includes("admin") ? (
        <section className="card p-5 md:p-6">
          <SectionHeader
            title="Operator accounts"
            subtitle="Create named accounts, assign least-privilege roles, revoke access, and rotate passwords."
          />

          <div className="mt-5 rounded-xl border border-line bg-surface-muted p-4">
            <div className="flex items-center gap-2 text-sm font-bold text-ink">
              <UserPlus size={16} /> Add operator
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2">
              <TextField
                id="operator-name"
                label="Full name"
                value={operatorForm.full_name}
                onChange={(value) => setOperatorForm({ ...operatorForm, full_name: value })}
              />
              <TextField
                id="operator-email"
                label="Email"
                value={operatorForm.email}
                onChange={(value) => setOperatorForm({ ...operatorForm, email: value })}
              />
              <div>
                <label className="field-label" htmlFor="operator-password">Temporary password</label>
                <input
                  id="operator-password"
                  type="password"
                  className="field"
                  value={operatorForm.password}
                  onChange={(event) => setOperatorForm({ ...operatorForm, password: event.target.value })}
                />
                <p className="field-hint">14+ characters with uppercase, lowercase, number and symbol.</p>
              </div>
              <div>
                <label className="field-label" htmlFor="operator-role">Role</label>
                <select
                  id="operator-role"
                  className="field"
                  value={operatorForm.role}
                  onChange={(event) => setOperatorForm({ ...operatorForm, role: event.target.value })}
                >
                  <option value="campaign_manager">Campaign manager</option>
                  <option value="auditor">Auditor</option>
                  <option value="risk_identity_viewer">Named-report identity viewer</option>
                  <option value="admin">Administrator</option>
                </select>
              </div>
            </div>
            <button
              type="button"
              className="btn-primary mt-4"
              disabled={busy === "operator-create"}
              onClick={() =>
                void save(
                  "operator-create",
                  async () => {
                    await createOperator(session.access_token, {
                      full_name: operatorForm.full_name,
                      email: operatorForm.email,
                      password: operatorForm.password,
                      roles: [operatorForm.role],
                    });
                    setOperators(await getOperators(session.access_token));
                    setOperatorForm({ full_name: "", email: "", password: "", role: "campaign_manager" });
                  },
                  "Operator account created.",
                )
              }
            >
              {busy === "operator-create" ? <Loader2 size={15} className="animate-spin" /> : <UserPlus size={15} />}
              Create operator
            </button>
          </div>

          <div className="mt-5 space-y-3">
            {operators.map((operator) => (
              <div key={operator.id} className="rounded-xl border border-line bg-surface p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <div className="font-bold text-ink">{operator.full_name}</div>
                    <div className="mt-0.5 text-xs text-muted">{operator.email}</div>
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      {operator.roles.map((role) => <span key={role} className="badge badge-neutral">{role.replaceAll("_", " ")}</span>)}
                      <span className={clsx("badge", operator.is_active ? "badge-success" : "badge-warn")}>
                        {operator.is_active ? "active" : "inactive"}
                      </span>
                    </div>
                  </div>
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={busy === `operator-status-${operator.id}` || operator.id === session.user.id}
                    onClick={() =>
                      void save(
                        `operator-status-${operator.id}`,
                        async () => {
                          await updateOperator(session.access_token, operator.id, { is_active: !operator.is_active });
                          setOperators(await getOperators(session.access_token));
                        },
                        operator.is_active ? "Operator deactivated." : "Operator activated.",
                      )
                    }
                  >
                    {operator.is_active ? "Deactivate" : "Activate"}
                  </button>
                </div>
                <div className="mt-4 flex flex-col gap-2 sm:flex-row">
                  <input
                    type="password"
                    className="field flex-1"
                    aria-label={`New password for ${operator.full_name}`}
                    placeholder="New strong password"
                    value={resetPasswords[operator.id] ?? ""}
                    onChange={(event) => setResetPasswords({ ...resetPasswords, [operator.id]: event.target.value })}
                  />
                  <button
                    type="button"
                    className="btn-secondary"
                    disabled={busy === `operator-reset-${operator.id}` || !(resetPasswords[operator.id] ?? "")}
                    onClick={() =>
                      void save(
                        `operator-reset-${operator.id}`,
                        async () => {
                          await resetOperatorPassword(session.access_token, operator.id, resetPasswords[operator.id] ?? "");
                          setResetPasswords({ ...resetPasswords, [operator.id]: "" });
                        },
                        "Password reset and existing sessions revoked.",
                      )
                    }
                  >
                    <KeyRound size={15} /> Reset password
                  </button>
                </div>
              </div>
            ))}
          </div>
        </section>
      ) : null}

      {tab === "email" ? (
        <section className="card p-5 md:p-6">
          <SectionHeader
            title="SMTP demo adapter"
            subtitle="Local/demo use only. Enterprise campaigns use Microsoft Graph or Google Workspace from Launch setup."
          />

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <Toggle
              label="Enable email delivery provider"
              checked={email.email_provider_enabled}
              onChange={(value) => setEmail({ ...email, email_provider_enabled: value })}
            />
            <div>
              <label className="field-label" htmlFor="email-mode">
                Mode
              </label>
              <select
                id="email-mode"
                className="field"
                value={email.email_provider_mode}
                onChange={(event) => setEmail({ ...email, email_provider_mode: event.target.value })}
              >
                <option value="sandbox">Sandbox (preview only)</option>
                <option value="lab">Lab (live delivery)</option>
              </select>
            </div>
            <TextField
              id="smtp-host"
              label="SMTP host"
              value={email.smtp_host ?? ""}
              placeholder="smtp.gmail.com"
              onChange={(value) => setEmail({ ...email, smtp_host: value })}
            />
            <div>
              <label className="field-label" htmlFor="smtp-port">
                SMTP port
              </label>
              <input
                id="smtp-port"
                type="number"
                className="field"
                value={email.smtp_port}
                onChange={(event) => setEmail({ ...email, smtp_port: Number(event.target.value) })}
              />
            </div>
            <TextField
              id="smtp-username"
              label="Username"
              value={email.smtp_username ?? ""}
              onChange={(value) => setEmail({ ...email, smtp_username: value })}
            />
            <div>
              <label className="field-label" htmlFor="smtp-password">
                Password
              </label>
              <input
                id="smtp-password"
                type="password"
                className="field"
                value={email.smtp_password}
                placeholder={email.has_password ? "Saved — enter only to replace" : "App password"}
                onChange={(event) => setEmail({ ...email, smtp_password: event.target.value })}
              />
              <p className="field-hint">Encrypted at rest. Use an app password, never your account password.</p>
            </div>
            <TextField
              id="smtp-from"
              label="From address"
              value={email.smtp_from_email ?? ""}
              onChange={(value) => setEmail({ ...email, smtp_from_email: value })}
            />
            <TextField
              id="smtp-sender"
              label="Sender name"
              value={email.smtp_sender_name ?? ""}
              onChange={(value) => setEmail({ ...email, smtp_sender_name: value })}
            />
            <div className="md:col-span-2">
              <label className="field-label" htmlFor="smtp-allowlist">
                Recipient allowlist
              </label>
              <textarea
                id="smtp-allowlist"
                className="field min-h-28"
                value={email.smtp_recipient_allowlist.join("\n")}
                placeholder="one.address@example.com"
                onChange={(event) =>
                  setEmail({ ...email, smtp_recipient_allowlist: splitLines(event.target.value) })
                }
              />
              <p className="field-hint">
                One address per line. Anything not listed here is refused at send time, so a misconfigured
                campaign cannot reach an unintended mailbox.
              </p>
            </div>
          </div>

          <button
            type="button"
            className="btn-primary mt-5"
            disabled={busy === "email"}
            onClick={() =>
              void save(
                "email",
                async () => {
                  const next = await updateEmailIntegration(session!.access_token, {
                    email_provider_enabled: email.email_provider_enabled,
                    email_provider_mode: email.email_provider_mode,
                    smtp_host: email.smtp_host || null,
                    smtp_port: email.smtp_port,
                    smtp_username: email.smtp_username || null,
                    smtp_password: email.smtp_password || null,
                    smtp_from_email: email.smtp_from_email || null,
                    smtp_sender_name: email.smtp_sender_name || null,
                    smtp_recipient_allowlist: email.smtp_recipient_allowlist,
                  });
                  setEmail({ ...defaultEmail, ...next, smtp_password: "" });
                },
                "Email integration saved.",
              )
            }
          >
            {busy === "email" ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
            Save email integration
          </button>

          <Hint>
            For Gmail use <code className="font-mono">smtp.gmail.com</code> on port{" "}
            <code className="font-mono">587</code> with a Gmail app password. Then use{" "}
            <strong>Send live email</strong> on an approved email campaign.
          </Hint>
        </section>
      ) : null}

      {tab === "sms" ? (
        <section className="card p-5 md:p-6">
          <SectionHeader
            title="SMS delivery (smishing)"
            subtitle="Speaks the Twilio Messages REST shape, so most gateways work unchanged."
          />

          <div className="mt-5 grid gap-4 md:grid-cols-2">
            <Toggle
              label="Enable SMS delivery provider"
              checked={sms.sms_provider_enabled}
              onChange={(value) => setSms({ ...sms, sms_provider_enabled: value })}
            />
            <div>
              <label className="field-label" htmlFor="sms-mode">
                Mode
              </label>
              <select
                id="sms-mode"
                className="field"
                value={sms.sms_provider_mode}
                onChange={(event) => setSms({ ...sms, sms_provider_mode: event.target.value })}
              >
                <option value="sandbox">Sandbox (preview only)</option>
                <option value="lab">Lab (live delivery)</option>
              </select>
            </div>
            <TextField
              id="sms-base"
              label="API base URL"
              value={sms.sms_api_base_url ?? ""}
              placeholder="https://api.twilio.com/2010-04-01"
              onChange={(value) => setSms({ ...sms, sms_api_base_url: value })}
            />
            <TextField
              id="sms-sid"
              label="Account SID"
              value={sms.sms_account_sid ?? ""}
              onChange={(value) => setSms({ ...sms, sms_account_sid: value })}
            />
            <div>
              <label className="field-label" htmlFor="sms-token">
                Auth token
              </label>
              <input
                id="sms-token"
                type="password"
                className="field"
                value={sms.sms_auth_token}
                placeholder={sms.has_auth_token ? "Saved — enter only to replace" : "Provider auth token"}
                onChange={(event) => setSms({ ...sms, sms_auth_token: event.target.value })}
              />
              <p className="field-hint">Encrypted at rest.</p>
            </div>
            <TextField
              id="sms-from"
              label="From number"
              value={sms.sms_from_number ?? ""}
              placeholder="+15550001111"
              onChange={(value) => setSms({ ...sms, sms_from_number: value })}
            />
            <div className="md:col-span-2">
              <label className="field-label" htmlFor="sms-allowlist">
                Recipient allowlist
              </label>
              <textarea
                id="sms-allowlist"
                className="field min-h-28"
                value={sms.sms_recipient_allowlist.join("\n")}
                placeholder="+923001234567"
                onChange={(event) =>
                  setSms({ ...sms, sms_recipient_allowlist: splitLines(event.target.value) })
                }
              />
              <p className="field-hint">
                One number per line in E.164 format. Numbers are normalized before comparison, and anything
                not listed is refused at send time.
              </p>
            </div>
          </div>

          <button
            type="button"
            className="btn-primary mt-5"
            disabled={busy === "sms"}
            onClick={() =>
              void save(
                "sms",
                async () => {
                  const next = await updateSmsIntegration(session!.access_token, {
                    sms_provider_enabled: sms.sms_provider_enabled,
                    sms_provider_mode: sms.sms_provider_mode,
                    sms_api_base_url: sms.sms_api_base_url || null,
                    sms_account_sid: sms.sms_account_sid || null,
                    sms_auth_token: sms.sms_auth_token || null,
                    sms_from_number: sms.sms_from_number || null,
                    sms_recipient_allowlist: sms.sms_recipient_allowlist,
                  });
                  setSms({ ...defaultSms, ...next, sms_auth_token: "" });
                },
                "SMS integration saved.",
              )
            }
          >
            {busy === "sms" ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
            Save SMS integration
          </button>

          <Hint>
            A paid gateway account is required for live SMS. Without one, leave the provider disabled — SMS
            campaigns still run end-to-end in sandbox mode with a full message preview.
          </Hint>
        </section>
      ) : null}

      {tab === "impersonation" && impersonation ? (
        <section className="card p-5 md:p-6">
          <SectionHeader
            title="Voice and synthetic media"
            subtitle="Master switch for the impersonation channels, plus the disclosure shown after every simulation."
          />

          <div
            className={clsx(
              "mt-5 rounded-xl border p-4",
              impersonation.impersonation_enabled
                ? "border-signal/25 bg-signal/6"
                : "border-caution/25 bg-caution/6",
            )}
          >
            <div className="flex items-start gap-2.5">
              {impersonation.impersonation_enabled ? (
                <ShieldCheck size={17} className="mt-0.5 shrink-0 text-signal" />
              ) : (
                <ShieldAlert size={17} className="mt-0.5 shrink-0 text-caution" />
              )}
              <div className="min-w-0">
                <p className="text-[0.88rem] font-bold text-ink">
                  Synthetic media simulations are{" "}
                  {impersonation.impersonation_enabled ? "enabled" : "disabled"}
                </p>
                <p className="mt-1 text-[0.81rem] leading-relaxed text-muted">
                  {impersonation.approved_persona_count} approved persona
                  {impersonation.approved_persona_count === 1 ? "" : "s"} available. Deepfake scenarios also
                  require an in-consent persona, so this switch is a second independent gate.
                </p>
              </div>
            </div>
          </div>

          <div className="mt-4 grid gap-4">
            <Toggle
              label="Enable synthetic media (deepfake) simulations"
              checked={impersonation.impersonation_enabled}
              onChange={(value) => setImpersonation({ ...impersonation, impersonation_enabled: value })}
            />
            <Toggle
              label="Enable external telephony provider for voice"
              checked={impersonation.voice_provider_enabled}
              onChange={(value) => setImpersonation({ ...impersonation, voice_provider_enabled: value })}
            />
            <div>
              <label className="field-label" htmlFor="voice-mode">
                Voice delivery mode
              </label>
              <select
                id="voice-mode"
                className="field"
                value={impersonation.voice_provider_mode}
                onChange={(event) =>
                  setImpersonation({ ...impersonation, voice_provider_mode: event.target.value })
                }
              >
                <option value="simulator">In-browser simulator (recommended)</option>
                <option value="lab">External telephony provider</option>
              </select>
              <p className="field-hint">
                The in-browser simulator places no real call and records no audio, which keeps a convincing
                exercise inside a boundary you fully control.
              </p>
            </div>
            <div>
              <label className="field-label" htmlFor="disclosure">
                Synthetic media disclosure
              </label>
              <textarea
                id="disclosure"
                className="field min-h-24"
                value={impersonation.impersonation_disclosure_text}
                onChange={(event) =>
                  setImpersonation({ ...impersonation, impersonation_disclosure_text: event.target.value })
                }
              />
              <p className="field-hint">Shown on every synthetic-media debrief.</p>
            </div>
          </div>

          <button
            type="button"
            className="btn-primary mt-5"
            disabled={busy === "impersonation"}
            onClick={() =>
              void save(
                "impersonation",
                async () => {
                  const next = await updateImpersonationSettings(session!.access_token, {
                    impersonation_enabled: impersonation.impersonation_enabled,
                    impersonation_disclosure_text: impersonation.impersonation_disclosure_text,
                    voice_provider_enabled: impersonation.voice_provider_enabled,
                    voice_provider_mode: impersonation.voice_provider_mode,
                  });
                  setImpersonation(next);
                },
                "Impersonation settings saved.",
              )
            }
          >
            {busy === "impersonation" ? <Loader2 size={15} className="animate-spin" /> : <Save size={15} />}
            Save impersonation settings
          </button>

          <div className="mt-5 rounded-xl border border-line bg-surface-muted p-4">
            <h3 className="text-[0.72rem] font-bold uppercase tracking-[0.14em] text-muted">
              Real cloning providers
            </h3>
            <div className="mt-3 grid gap-2.5 sm:grid-cols-2">
              <ProviderStatus
                label="Voice cloning"
                provider={impersonation.voice_clone_provider}
                configured={impersonation.voice_clone_configured}
                hint="ElevenLabs"
              />
              <ProviderStatus
                label="Talking-head video"
                provider={impersonation.video_clone_provider}
                configured={impersonation.video_clone_configured}
                hint="D-ID"
              />
            </div>
            <p className="mt-3 text-[0.78rem] leading-relaxed text-muted">
              Provider keys are set as backend environment variables
              (<code className="font-mono text-[0.72rem]">ELEVENLABS_API_KEY</code>,{" "}
              <code className="font-mono text-[0.72rem]">DID_API_KEY</code>). With a provider configured,
              enrolling a persona&apos;s consented voice sample produces real cloned speech in every voice and
              deepfake simulation. Without one, simulations fall back to the in-browser speech engine and still
              run end to end.
            </p>
          </div>
        </section>
      ) : null}
    </div>
  );
}

/* ------------------------------------------------------------ small pieces */

function SectionHeader({ title, subtitle }: { title: string; subtitle: string }) {
  return (
    <div>
      <h2 className="display-font text-lg font-bold text-ink">{title}</h2>
      <p className="mt-1 text-[0.84rem] leading-relaxed text-muted">{subtitle}</p>
    </div>
  );
}

function TextField({
  id,
  label,
  value,
  placeholder,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  placeholder?: string;
  onChange: (value: string) => void;
}) {
  return (
    <div>
      <label className="field-label" htmlFor={id}>
        {label}
      </label>
      <input
        id={id}
        className="field"
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </div>
  );
}

function Toggle({
  label,
  checked,
  onChange,
}: {
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="flex cursor-pointer items-center gap-2.5 rounded-xl border border-line bg-surface-muted px-3.5 py-3">
      <input type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span className="text-[0.84rem] font-semibold text-ink">{label}</span>
    </label>
  );
}

function ProviderStatus({
  label,
  provider,
  configured,
  hint,
}: {
  label: string;
  provider?: string;
  configured?: boolean;
  hint: string;
}) {
  return (
    <div className="flex items-center justify-between gap-2 rounded-lg border border-line bg-surface px-3 py-2.5">
      <div>
        <div className="text-[0.8rem] font-semibold text-ink">{label}</div>
        <div className="text-[0.7rem] text-subtle">
          {configured ? `${provider} connected` : `Not configured · ${hint}`}
        </div>
      </div>
      <span className={clsx("badge", configured ? "badge-success" : "badge-neutral")}>
        {configured ? "Live" : "Off"}
      </span>
    </div>
  );
}

function Hint({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-5 flex gap-2.5 rounded-xl border border-brand-500/20 bg-brand-500/5 p-3.5">
      <Info size={15} className="mt-0.5 shrink-0 text-brand-500" />
      <p className="text-[0.81rem] leading-relaxed text-muted">{children}</p>
    </div>
  );
}

function splitLines(value: string) {
  return value
    .split("\n")
    .map((line) => line.trim())
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
  return "Save failed.";
}
