"use client";

import clsx from "clsx";
import {
  CheckCircle2,
  Clipboard,
  Cloud,
  Globe2,
  KeyRound,
  Loader2,
  MailCheck,
  Palette,
  RefreshCw,
  Send,
  ShieldCheck,
} from "lucide-react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { useSession } from "@/components/session-provider";
import {
  addOrganizationDomain,
  checkEnterpriseEmailConnection,
  createEnterpriseEmailConnection,
  createDeliverySuppression,
  createScimCredential,
  createSsoConnection,
  getEnterpriseEmailConnections,
  getDeliverySuppressions,
  getGoogleDomainWideDelegationSetup,
  getOrganizationBranding,
  getOrganizationDomains,
  getScimCredentials,
  getSsoConnections,
  rotateOrganizationDomainVerification,
  deactivateDeliverySuppression,
  setPrimaryOrganizationDomain,
  startMicrosoftAdminConsent,
  testEnterpriseEmailConnection,
  updateOrganizationBranding,
  verifyOrganizationDomain,
  type EnterpriseEmailConnection,
  type DeliverySuppression,
  type GoogleDomainWideDelegationSetup,
  type OrganizationBranding,
  type OrganizationDomain,
  type ScimCredential,
  type SsoConnection,
} from "@/lib/client-api";

const DEFAULT_BRANDING: OrganizationBranding = {
  id: "",
  organization_id: "",
  logo_url: "",
  primary_color: "#173B73",
  accent_color: "#175CD3",
  sender_name: "Security Awareness",
  legal_footer: "Authorized security-awareness simulation.",
  approved_template_ids: [],
};

export function EnterpriseSetupConsole() {
  const { session } = useSession();
  const [domains, setDomains] = useState<OrganizationDomain[]>([]);
  const [branding, setBranding] = useState(DEFAULT_BRANDING);
  const [connections, setConnections] = useState<EnterpriseEmailConnection[]>([]);
  const [suppressions, setSuppressions] = useState<DeliverySuppression[]>([]);
  const [googleSetups, setGoogleSetups] = useState<Record<string, GoogleDomainWideDelegationSetup>>({});
  const [scimCredentials, setScimCredentials] = useState<ScimCredential[]>([]);
  const [ssoConnections, setSsoConnections] = useState<SsoConnection[]>([]);
  const [domainForm, setDomainForm] = useState({ hostname: "", purpose: "recipient" });
  const [connectionForm, setConnectionForm] = useState({
    provider: "microsoft_graph",
    display_name: "Microsoft 365",
    sender_email: "",
    sender_name: "Security Awareness",
    customer_tenant_id: "",
    delegated_subject: "",
    rate_limit_per_minute: 120,
  });
  const [exclusionEmail, setExclusionEmail] = useState("");
  const [ssoForm, setSsoForm] = useState({
    provider: "entra",
    issuer: "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0",
    client_id: "",
    client_secret_ref: "",
    allowed_domain: "",
  });
  const [oneTimeSecret, setOneTimeSecret] = useState<{ label: string; value: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<{ tone: "ok" | "error"; text: string } | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    const [domainRows, brand, emailRows, suppressionRows, scimRows, ssoRows] = await Promise.all([
      getOrganizationDomains(session.access_token),
      getOrganizationBranding(session.access_token),
      getEnterpriseEmailConnections(session.access_token),
      getDeliverySuppressions(session.access_token),
      getScimCredentials(session.access_token),
      getSsoConnections(session.access_token),
    ]);
    setDomains(domainRows);
    setBranding(brand);
    setConnections(emailRows);
    setSuppressions(suppressionRows);
    setScimCredentials(scimRows);
    setSsoConnections(ssoRows);
    setNotice((current) => (current?.tone === "error" ? null : current));
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

  async function run(key: string, action: () => Promise<void>, success: string) {
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

  const readiness = useMemo(
    () => [
      { label: "Managed landing domain", ready: domains.some((row) => row.purpose === "landing" && row.status === "active") },
      { label: "Recipient domain", ready: domains.some((row) => row.purpose === "recipient" && row.status === "active") },
      { label: "Sender domain", ready: domains.some((row) => row.purpose === "sender" && row.status === "active") },
      { label: "Customer mail connection", ready: connections.some((row) => row.status === "healthy") },
      { label: "Single sign-on", ready: ssoConnections.some((row) => row.status !== "revoked") },
      { label: "SCIM provisioning", ready: scimCredentials.some((row) => !row.revoked_at) },
    ],
    [connections, domains, scimCredentials, ssoConnections],
  );
  const readyCount = readiness.filter((item) => item.ready).length;

  return (
    <div className="space-y-4">
      {notice ? (
        <div className={clsx("rounded-xl border px-4 py-3 text-sm", notice.tone === "ok" ? "border-signal/25 bg-signal/8 text-signal" : "border-breach/25 bg-breach/8 text-breach")}>
          {notice.text}
        </div>
      ) : null}

      <section className="card overflow-hidden">
        <div className="grid gap-6 border-b border-line p-5 md:grid-cols-[1fr_auto] md:p-6">
          <div>
            <div className="section-title">Enterprise launch control</div>
            <h2 className="display-font mt-1.5 text-xl font-bold text-ink">Customer readiness</h2>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">
              Live campaign controls stay locked until recipient ownership, sender authorization, identity, and delivery health are verified.
            </p>
          </div>
          <div className="min-w-44 rounded-xl border border-line bg-surface-subtle px-4 py-3">
            <div className="numeric text-2xl font-bold text-ink">{readyCount}/{readiness.length}</div>
            <div className="mt-1 text-xs font-semibold uppercase tracking-[0.12em] text-muted">controls ready</div>
          </div>
        </div>
        <div className="grid gap-px bg-line sm:grid-cols-2 xl:grid-cols-3">
          {readiness.map((item) => (
            <div key={item.label} className="flex items-center gap-3 bg-surface px-5 py-4">
              <CheckCircle2 size={17} className={item.ready ? "text-signal" : "text-muted/45"} />
              <span className="text-sm font-semibold text-ink">{item.label}</span>
            </div>
          ))}
        </div>
      </section>

      <section className="card p-5 md:p-6">
        <SectionTitle icon={Globe2} title="Verified domains" subtitle="The campaign chooses from these approved domains; operators never paste arbitrary destination URLs." />
        <form
          className="mt-5 grid gap-3 md:grid-cols-[1fr_170px_auto]"
          onSubmit={(event) => {
            event.preventDefault();
            void run("add-domain", async () => {
              const created = await addOrganizationDomain(session!.access_token, domainForm);
              if (created.verification_value) {
                setOneTimeSecret({ label: `${created.hostname} TXT value`, value: created.verification_value });
              }
              setDomainForm((value) => ({ ...value, hostname: "" }));
              await load();
            }, "Domain added. Publish the one-time TXT value, then verify.");
          }}
        >
          <Field value={domainForm.hostname} onChange={(value) => setDomainForm({ ...domainForm, hostname: value })} placeholder="training.company.com" required />
          <select className="field" value={domainForm.purpose} onChange={(event) => setDomainForm({ ...domainForm, purpose: event.target.value })}>
            <option value="recipient">Recipient</option>
            <option value="sender">Sender</option>
            <option value="landing">Landing</option>
          </select>
          <ActionButton busy={busy === "add-domain"}>Add domain</ActionButton>
        </form>

        <div className="mt-5 overflow-hidden rounded-xl border border-line">
          {domains.map((domain) => (
            <div key={domain.id} className="grid gap-3 border-b border-line px-4 py-4 last:border-b-0 lg:grid-cols-[1fr_130px_140px_auto] lg:items-center">
              <div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="font-mono text-sm font-semibold text-ink">{domain.hostname}</span>
                  {domain.is_primary ? <span className="badge">Primary</span> : null}
                </div>
                <div className="mt-1 text-xs text-muted">
                  {domain.dns_instructions.txt_name ? `TXT ${domain.dns_instructions.txt_name}` : "Platform managed"}
                </div>
                {domain.validation_error ? <div className="mt-1 text-xs text-breach">{domain.validation_error}</div> : null}
              </div>
              <span className="text-xs font-bold uppercase tracking-[0.12em] text-muted">{domain.purpose}</span>
              <Status value={domain.status} />
              <div className="flex flex-wrap gap-2 lg:justify-end">
                {domain.kind === "custom" && domain.status !== "active" ? (
                  <>
                    <SmallButton
                      label="Rotate TXT"
                      onClick={() => void run(`rotate-${domain.id}`, async () => {
                        const updated = await rotateOrganizationDomainVerification(session!.access_token, domain.id);
                        if (updated.verification_value) setOneTimeSecret({ label: `${updated.hostname} TXT value`, value: updated.verification_value });
                        await load();
                      }, "A new one-time verification value was issued.")}
                    />
                    <SmallButton label="Verify" onClick={() => void run(`verify-${domain.id}`, async () => { await verifyOrganizationDomain(session!.access_token, domain.id); await load(); }, "Domain ownership verified.")} />
                  </>
                ) : null}
                {domain.status === "active" && !domain.is_primary ? (
                  <SmallButton label="Set primary" onClick={() => void run(`primary-${domain.id}`, async () => { await setPrimaryOrganizationDomain(session!.access_token, domain.id); await load(); }, "Primary domain updated.")} />
                ) : null}
              </div>
            </div>
          ))}
        </div>
      </section>

      {oneTimeSecret ? (
        <section className="rounded-xl border border-amber-300 bg-amber-50 p-5 text-amber-950">
          <div className="flex items-start justify-between gap-4">
            <div>
              <div className="text-xs font-bold uppercase tracking-[0.13em]">Copy once</div>
              <div className="mt-1 text-sm font-semibold">{oneTimeSecret.label}</div>
              <code className="mt-3 block break-all rounded-lg bg-white px-3 py-2 text-xs">{oneTimeSecret.value}</code>
            </div>
            <button type="button" className="app-secondary-button" onClick={() => void navigator.clipboard.writeText(oneTimeSecret.value)}>
              <Clipboard size={14} /> Copy
            </button>
          </div>
        </section>
      ) : null}

      <section className="card p-5 md:p-6">
        <SectionTitle icon={MailCheck} title="Customer-owned email" subtitle="Microsoft Graph or Google Workspace submits from the customer-authorized sender mailbox." />
        <form
          className="mt-5 grid gap-3 md:grid-cols-2 xl:grid-cols-3"
          onSubmit={(event) => {
            event.preventDefault();
            void run("add-connection", async () => {
              await createEnterpriseEmailConnection(session!.access_token, {
                ...connectionForm,
                customer_tenant_id: connectionForm.customer_tenant_id || null,
                delegated_subject: connectionForm.delegated_subject || null,
              });
              await load();
            }, "Email connection created. Complete authorization and run the health check.");
          }}
        >
          <select className="field" value={connectionForm.provider} onChange={(event) => setConnectionForm({ ...connectionForm, provider: event.target.value, display_name: event.target.value === "microsoft_graph" ? "Microsoft 365" : "Google Workspace" })}>
            <option value="microsoft_graph">Microsoft 365</option>
            <option value="google_workspace">Google Workspace</option>
          </select>
          <Field value={connectionForm.sender_email} onChange={(value) => setConnectionForm({ ...connectionForm, sender_email: value })} placeholder="awareness@company.com" type="email" required />
          <Field value={connectionForm.sender_name} onChange={(value) => setConnectionForm({ ...connectionForm, sender_name: value })} placeholder="Security Awareness" required />
          {connectionForm.provider === "microsoft_graph" ? (
            <Field value={connectionForm.customer_tenant_id} onChange={(value) => setConnectionForm({ ...connectionForm, customer_tenant_id: value })} placeholder="Microsoft tenant ID" required />
          ) : (
            <Field value={connectionForm.delegated_subject} onChange={(value) => setConnectionForm({ ...connectionForm, delegated_subject: value })} placeholder="Delegated Workspace sender" type="email" required />
          )}
          <Field value={String(connectionForm.rate_limit_per_minute)} onChange={(value) => setConnectionForm({ ...connectionForm, rate_limit_per_minute: Number(value) || 1 })} placeholder="Messages/minute" type="number" required />
          <ActionButton busy={busy === "add-connection"}>Create connection</ActionButton>
        </form>

        <div className="mt-5 grid gap-3">
          {connections.map((connection) => (
            <div key={connection.id} className="rounded-xl border border-line p-4">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-semibold text-ink">{connection.display_name}</div>
                  <div className="mt-1 text-sm text-muted">{connection.sender_name} · {connection.sender_email}</div>
                  {connection.reconciliation_secret_ref ? (
                    <div className="mt-2 text-xs text-muted">Reconciliation secret: <code>{connection.reconciliation_secret_ref}</code></div>
                  ) : null}
                  {connection.last_error ? <div className="mt-2 text-xs text-breach">{connection.last_error}</div> : null}
                </div>
                <Status value={connection.status} />
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                {connection.provider === "microsoft_graph" && !connection.authorized_at ? (
                  <SmallButton label="Admin consent" onClick={() => void run(`consent-${connection.id}`, async () => {
                    const result = await startMicrosoftAdminConsent(session!.access_token, connection.id);
                    window.location.assign(result.authorization_url);
                  }, "Opening Microsoft admin consent.")} />
                ) : null}
                {connection.provider === "google_workspace" ? (
                  <SmallButton label="Workspace authorization" onClick={() => void run(`google-${connection.id}`, async () => {
                    const setup = await getGoogleDomainWideDelegationSetup(session!.access_token, connection.id);
                    setGoogleSetups((current) => ({ ...current, [connection.id]: setup }));
                    window.open(setup.admin_console_url, "_blank", "noopener,noreferrer");
                  }, "Workspace Admin Console opened. Add the client ID and exact gmail.send scope shown below.")} />
                ) : null}
                <SmallButton label="Health check" onClick={() => void run(`health-${connection.id}`, async () => { await checkEnterpriseEmailConnection(session!.access_token, connection.id); await load(); }, "Connection health checked.")} />
                <SmallButton label="Send test" onClick={() => void run(`test-${connection.id}`, async () => { await testEnterpriseEmailConnection(session!.access_token, connection.id); await load(); }, "Provider accepted the administrative test message.")} />
              </div>
              {googleSetups[connection.id] ? (
                <div className="mt-4 rounded-lg border border-line bg-surface-muted p-3 text-xs text-muted">
                  <div>OAuth client ID: <code className="break-all">{googleSetups[connection.id].oauth_client_id}</code></div>
                  <div className="mt-2">OAuth scope: <code className="break-all">{googleSetups[connection.id].oauth_scope}</code></div>
                  <div className="mt-2">Delegated sender: <code>{googleSetups[connection.id].delegated_subject}</code></div>
                </div>
              ) : null}
            </div>
          ))}
        </div>

        <div className="mt-6 border-t border-line pt-5">
          <div className="font-semibold text-ink">Manual delivery exclusions</div>
          <p className="mt-1 text-xs leading-5 text-muted">
            Enter an address that must never receive a live campaign. The platform stores only a keyed digest and shows an opaque reference.
          </p>
          <form className="mt-3 flex flex-col gap-3 sm:flex-row" onSubmit={(event) => {
            event.preventDefault();
            void run("exclude-recipient", async () => {
              await createDeliverySuppression(session!.access_token, exclusionEmail);
              setExclusionEmail("");
              await load();
            }, "Recipient added to the tenant exclusion list.");
          }}>
            <Field value={exclusionEmail} onChange={setExclusionEmail} placeholder="excluded.employee@company.com" type="email" required />
            <ActionButton busy={busy === "exclude-recipient"}>Exclude recipient</ActionButton>
          </form>
          {suppressions.length ? (
            <div className="mt-4 overflow-hidden rounded-xl border border-line">
              {suppressions.map((suppression) => (
                <div key={suppression.id} className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-4 py-3 last:border-b-0">
                  <div>
                    <code className="text-xs font-semibold text-ink">{suppression.reference}</code>
                    <div className="mt-1 text-xs text-muted">{suppression.reason.replaceAll("_", " ")}</div>
                  </div>
                  <div className="flex items-center gap-2">
                    <Status value={suppression.active ? "active" : "deactivated"} />
                    {suppression.active ? (
                      <SmallButton label="Remove exclusion" onClick={() => void run(`unsuppress-${suppression.id}`, async () => {
                        await deactivateDeliverySuppression(session!.access_token, suppression.id);
                        await load();
                      }, "Delivery exclusion removed.")} />
                    ) : null}
                  </div>
                </div>
              ))}
            </div>
          ) : null}
        </div>
      </section>

      <section className="grid gap-4 xl:grid-cols-2">
        <div className="card p-5 md:p-6">
          <SectionTitle icon={Palette} title="Campaign branding" subtitle="Snapshotted when a run launches so later edits cannot change active mail." />
          <div className="mt-5 grid gap-3 sm:grid-cols-2">
            <Field value={branding.sender_name} onChange={(value) => setBranding({ ...branding, sender_name: value })} placeholder="Sender display name" />
            <Field value={branding.logo_url || ""} onChange={(value) => setBranding({ ...branding, logo_url: value })} placeholder="HTTPS logo URL" type="url" />
            <ColorField label="Primary" value={branding.primary_color} onChange={(value) => setBranding({ ...branding, primary_color: value })} />
            <ColorField label="Accent" value={branding.accent_color} onChange={(value) => setBranding({ ...branding, accent_color: value })} />
            <textarea className="field min-h-24 sm:col-span-2" value={branding.legal_footer} onChange={(event) => setBranding({ ...branding, legal_footer: event.target.value })} />
            <div className="sm:col-span-2">
              <label className="field-label" htmlFor="approved-template-ids">Approved scenario or version IDs</label>
              <textarea
                id="approved-template-ids"
                className="field min-h-24"
                value={branding.approved_template_ids.join("\n")}
                placeholder="One approved scenario/version UUID per line. Leave empty to allow any separately approved scenario."
                onChange={(event) => setBranding({
                  ...branding,
                  approved_template_ids: event.target.value.split(/\r?\n|,/).map((value) => value.trim()).filter(Boolean),
                })}
              />
            </div>
            <button type="button" className="app-primary-button sm:col-span-2" disabled={busy === "branding"} onClick={() => void run("branding", async () => { setBranding(await updateOrganizationBranding(session!.access_token, branding)); }, "Branding saved.")}>
              {busy === "branding" ? <Loader2 size={14} className="animate-spin" /> : <Palette size={14} />} Save branding
            </button>
          </div>
        </div>

        <div className="card p-5 md:p-6">
          <SectionTitle icon={ShieldCheck} title="Identity provisioning" subtitle="Use SSO for operators and a scoped, rotatable bearer token for SCIM 2.0." />
          <div className="mt-5 space-y-4">
            <div className="rounded-xl border border-line p-4">
              <div className="font-semibold text-ink">SCIM 2.0</div>
              <div className="mt-1 text-xs text-muted">Endpoint: <code>/api/v1/scim/v2</code></div>
              <button type="button" className="app-secondary-button mt-3" onClick={() => void run("scim", async () => {
                const created = await createScimCredential(session!.access_token, "Enterprise directory provisioning");
                if (created.token) setOneTimeSecret({ label: "SCIM bearer token", value: created.token });
                await load();
              }, "SCIM token created. It will not be shown again.")}>
                <KeyRound size={14} /> Generate SCIM token
              </button>
            </div>
            <form className="rounded-xl border border-line p-4" onSubmit={(event) => {
              event.preventDefault();
              void run("sso", async () => {
                await createSsoConnection(session!.access_token, {
                  provider: ssoForm.provider,
                  issuer: ssoForm.issuer,
                  client_id: ssoForm.client_id,
                  client_secret_ref: ssoForm.client_secret_ref,
                  allowed_domains: [ssoForm.allowed_domain],
                  group_role_mappings: {},
                });
                await load();
              }, "SSO configuration saved. Sign-in remains closed until the first validated callback.");
            }}>
              <div className="font-semibold text-ink">OIDC single sign-on</div>
              <div className="mt-3 grid gap-3">
                <select className="field" value={ssoForm.provider} onChange={(event) => setSsoForm({ ...ssoForm, provider: event.target.value, issuer: event.target.value === "entra" ? "https://login.microsoftonline.com/00000000-0000-0000-0000-000000000000/v2.0" : "https://accounts.google.com" })}>
                  <option value="entra">Microsoft Entra ID</option>
                  <option value="google">Google Workspace</option>
                </select>
                <Field value={ssoForm.issuer} onChange={(value) => setSsoForm({ ...ssoForm, issuer: value })} placeholder="OIDC issuer" type="url" required />
                <p className="-mt-1 text-xs text-muted">For Entra, replace the zero GUID with the customer tenant ID. Common and organizations issuers are rejected.</p>
                <Field value={ssoForm.client_id} onChange={(value) => setSsoForm({ ...ssoForm, client_id: value })} placeholder="OIDC client ID" required />
                <Field value={ssoForm.client_secret_ref} onChange={(value) => setSsoForm({ ...ssoForm, client_secret_ref: value })} placeholder="kv://customer-oidc-secret" required />
                <Field value={ssoForm.allowed_domain} onChange={(value) => setSsoForm({ ...ssoForm, allowed_domain: value })} placeholder="company.com" required />
                <ActionButton busy={busy === "sso"}>Save SSO</ActionButton>
              </div>
            </form>
          </div>
        </div>
      </section>
    </div>
  );
}

function SectionTitle({ icon: Icon, title, subtitle }: { icon: typeof Cloud; title: string; subtitle: string }) {
  return (
    <div className="flex items-start gap-3">
      <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg border border-line bg-surface-subtle text-brand-600"><Icon size={17} /></div>
      <div><h3 className="font-semibold text-ink">{title}</h3><p className="mt-1 text-sm leading-5 text-muted">{subtitle}</p></div>
    </div>
  );
}

function Field({ value, onChange, placeholder, type = "text", required = false }: { value: string; onChange: (value: string) => void; placeholder: string; type?: string; required?: boolean }) {
  return <input className="field" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} type={type} required={required} />;
}

function ColorField({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return <label className="flex items-center gap-3 rounded-lg border border-line px-3 py-2 text-sm text-muted"><input type="color" value={value} onChange={(event) => onChange(event.target.value)} /><span>{label}</span><code className="ml-auto text-xs">{value}</code></label>;
}

function ActionButton({ busy, children }: { busy: boolean; children: React.ReactNode }) {
  return <button type="submit" className="app-primary-button" disabled={busy}>{busy ? <Loader2 size={14} className="animate-spin" /> : <Send size={14} />}{children}</button>;
}

function SmallButton({ label, onClick }: { label: string; onClick: () => void }) {
  return <button type="button" onClick={onClick} className="app-secondary-button px-2.5 py-1.5 text-xs"><RefreshCw size={12} />{label}</button>;
}

function Status({ value }: { value: string }) {
  const good = value === "active" || value === "healthy" || value === "verified";
  return <span className={clsx("inline-flex w-fit items-center rounded-full px-2.5 py-1 text-[0.68rem] font-bold uppercase tracking-[0.1em]", good ? "bg-signal/10 text-signal" : value === "failed" || value === "degraded" ? "bg-breach/10 text-breach" : "bg-surface-subtle text-muted")}>{value}</span>;
}

function readError(error: unknown): string {
  if (!(error instanceof Error)) return "The request could not be completed.";
  try {
    const parsed = JSON.parse(error.message);
    return typeof parsed === "string" ? parsed : parsed?.detail || error.message;
  } catch {
    return error.message;
  }
}
