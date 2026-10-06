"use client";

import { Building2, CheckCircle2, Clipboard, Loader2, PauseCircle, PlayCircle, Plus } from "lucide-react";
import { useCallback, useEffect, useState } from "react";

import { useSession } from "@/components/session-provider";
import {
  createPlatformOrganization,
  getPlatformOrganizations,
  setPlatformOrganizationState,
  type PlatformOrganization,
} from "@/lib/client-api";

export function PlatformOperationsConsole() {
  const { session } = useSession();
  const [organizations, setOrganizations] = useState<PlatformOrganization[]>([]);
  const [form, setForm] = useState({ name: "", slug: "", timezone: "UTC", admin_email: "", admin_name: "" });
  const [invite, setInvite] = useState<string | null>(null);
  const [busy, setBusy] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const load = useCallback(async () => {
    if (!session) return;
    setOrganizations(await getPlatformOrganizations(session.access_token));
  }, [session]);

  useEffect(() => {
    void load().catch((error) => setNotice(error instanceof Error ? error.message : "Unable to load organizations"));
  }, [load]);

  async function execute(key: string, action: () => Promise<void>) {
    setBusy(key);
    setNotice(null);
    try {
      await action();
    } catch (error) {
      setNotice(error instanceof Error ? error.message : "Action failed");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="space-y-4">
      <section className="workspace-page-header">
        <div className="section-title">Platform operations</div>
        <h1 className="display-font mt-1.5 text-2xl font-bold text-ink">Sales-led tenant provisioning</h1>
        <p className="mt-2 max-w-2xl text-sm leading-6 text-muted">Create a tenant boundary, managed training hostname, default branding record, and a time-limited administrator invitation.</p>
      </section>

      {notice ? <div className="rounded-xl border border-breach/25 bg-breach/8 px-4 py-3 text-sm text-breach">{notice}</div> : null}
      {invite ? (
        <section className="rounded-xl border border-caution/30 bg-caution/8 p-5">
          <div className="text-xs font-bold uppercase tracking-[0.12em] text-caution">Administrator invitation · copy once</div>
          <code className="mt-3 block break-all rounded-lg border border-line bg-surface px-3 py-2 text-xs text-ink">{invite}</code>
          <button type="button" className="app-secondary-button mt-3" onClick={() => void navigator.clipboard.writeText(invite)}><Clipboard size={14} />Copy invitation link</button>
        </section>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[360px_1fr]">
        <section className="card self-start p-5">
          <div className="flex items-center gap-3"><div className="grid h-9 w-9 place-items-center rounded-lg bg-brand-500/10 text-brand-500"><Plus size={17} /></div><div><div className="section-title">Provision</div><h2 className="font-semibold text-ink">New customer</h2></div></div>
          <form className="mt-5 space-y-3" onSubmit={(event) => {
            event.preventDefault();
            void execute("create", async () => {
              const created = await createPlatformOrganization(session!.access_token, form);
              setInvite(created.invite_url || created.invite_token || null);
              setForm({ name: "", slug: "", timezone: "UTC", admin_email: "", admin_name: "" });
              await load();
            });
          }}>
            <Field label="Organization" value={form.name} onChange={(value) => setForm({ ...form, name: value })} placeholder="Contoso Ltd" />
            <Field label="Tenant slug" value={form.slug} onChange={(value) => setForm({ ...form, slug: value.toLowerCase().replace(/[^a-z0-9-]/g, "") })} placeholder="contoso" />
            <Field label="Timezone" value={form.timezone} onChange={(value) => setForm({ ...form, timezone: value })} placeholder="Europe/London" />
            <Field label="Administrator name" value={form.admin_name} onChange={(value) => setForm({ ...form, admin_name: value })} placeholder="Security Administrator" />
            <Field label="Administrator email" value={form.admin_email} onChange={(value) => setForm({ ...form, admin_email: value })} placeholder="security@contoso.com" type="email" />
            <button className="app-primary-button w-full" disabled={busy === "create"}>{busy === "create" ? <Loader2 size={14} className="animate-spin" /> : <Building2 size={14} />}Provision customer</button>
          </form>
        </section>

        <section className="card overflow-hidden">
          <div className="border-b border-line px-5 py-4"><h2 className="display-font text-lg font-bold text-ink">Organizations</h2><p className="mt-1 text-sm text-muted">Platform operators can manage lifecycle without entering tenant campaign data.</p></div>
          <div className="divide-y divide-line">
            {organizations.map((org) => {
              const controls = Object.values(org.onboarding);
              const ready = controls.filter(Boolean).length;
              return (
                <div key={org.id} className="p-5">
                  <div className="flex flex-wrap items-start justify-between gap-4">
                    <div><div className="flex items-center gap-2"><h3 className="font-semibold text-ink">{org.name}</h3>{org.suspended_at ? <span className="badge badge-danger">Suspended</span> : <span className="badge badge-success">Active</span>}</div><a href={org.platform_url} target="_blank" rel="noreferrer" className="mt-1 block font-mono text-xs text-brand-500">{org.platform_url}</a></div>
                    <button type="button" className="app-secondary-button" disabled={busy === org.id} onClick={() => void execute(org.id, async () => { await setPlatformOrganizationState(session!.access_token, org.id, org.suspended_at ? "reactivate" : "suspend"); await load(); })}>{org.suspended_at ? <PlayCircle size={14} /> : <PauseCircle size={14} />}{org.suspended_at ? "Reactivate" : "Suspend"}</button>
                  </div>
                  <div className="mt-4 flex items-center gap-3"><div className="h-2 flex-1 overflow-hidden rounded-full bg-surface-muted"><div className="h-full bg-signal" style={{ width: `${controls.length ? (ready / controls.length) * 100 : 0}%` }} /></div><span className="numeric text-xs font-semibold text-muted">{ready}/{controls.length} ready</span>{ready === controls.length ? <CheckCircle2 size={15} className="text-signal" /> : null}</div>
                </div>
              );
            })}
          </div>
        </section>
      </div>
    </div>
  );
}

function Field({ label, value, onChange, placeholder, type = "text" }: { label: string; value: string; onChange: (value: string) => void; placeholder: string; type?: string }) {
  return <label className="block"><span className="field-label">{label}</span><input className="field" value={value} onChange={(event) => onChange(event.target.value)} placeholder={placeholder} type={type} required /></label>;
}
