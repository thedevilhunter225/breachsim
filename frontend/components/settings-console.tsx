"use client";

import { useEffect, useState } from "react";

import { Panel } from "@/components/panel";
import { useSession } from "@/components/session-provider";
import { EmailIntegration, getCurrentOrg, getEmailIntegration, OrganizationProfile, updateCurrentOrg, updateEmailIntegration } from "@/lib/client-api";

const defaultSettings: EmailIntegration & { smtp_password: string } = {
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

const defaultOrg: OrganizationProfile = {
  id: "",
  name: "",
  slug: "",
  timezone: "Asia/Karachi",
  retention_days: 365,
  privacy_notice: "Training and security awareness platform.",
};

export function SettingsConsole() {
  const { session } = useSession();
  const [settings, setSettings] = useState(defaultSettings);
  const [org, setOrg] = useState(defaultOrg);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!session) return;
    void Promise.all([
      getCurrentOrg(session.access_token),
      getEmailIntegration(session.access_token),
    ]).then(([orgValue, emailValue]) => {
      setOrg(orgValue);
      setSettings({ ...defaultSettings, ...emailValue, smtp_password: "" });
    });
  }, [session]);

  async function saveOrg() {
    if (!session) return;
    const next = await updateCurrentOrg(session.access_token, {
      name: org.name,
      timezone: org.timezone,
      retention_days: org.retention_days,
      privacy_notice: org.privacy_notice,
    });
    setOrg(next);
    setMessage("Organization settings saved.");
  }

  async function saveEmail() {
    if (!session) return;
    const next = await updateEmailIntegration(session.access_token, {
      email_provider_enabled: settings.email_provider_enabled,
      email_provider_mode: settings.email_provider_mode,
      smtp_host: settings.smtp_host || null,
      smtp_port: settings.smtp_port,
      smtp_username: settings.smtp_username || null,
      smtp_password: settings.smtp_password || null,
      smtp_from_email: settings.smtp_from_email || null,
      smtp_sender_name: settings.smtp_sender_name || null,
      smtp_recipient_allowlist: settings.smtp_recipient_allowlist,
    });
    setSettings({ ...defaultSettings, ...next, smtp_password: "" });
    setMessage("Email integration saved.");
  }

  return (
    <>
      <Panel>
        <div className="section-title">Admin Settings</div>
        <h2 className="mt-4 text-3xl font-semibold">Configure organization and delivery settings from the admin UI</h2>
      </Panel>

      <div className="grid gap-4 xl:grid-cols-[0.85fr_1.15fr]">
        <Panel>
          <div className="section-title">Organization Profile</div>
          <div className="mt-4 grid gap-4">
            <input value={org.name} onChange={(event) => setOrg({ ...org, name: event.target.value })} placeholder="Organization name" className="rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <div className="rounded-2xl border border-ink/10 bg-sand px-4 py-3 text-sm text-slate">
              Slug: <span className="font-semibold text-ink">{org.slug || "generated"}</span>
            </div>
            <input value={org.timezone} onChange={(event) => setOrg({ ...org, timezone: event.target.value })} placeholder="Timezone" className="rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <input type="number" value={org.retention_days} onChange={(event) => setOrg({ ...org, retention_days: Number(event.target.value) })} placeholder="Retention days" className="rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <textarea value={org.privacy_notice} onChange={(event) => setOrg({ ...org, privacy_notice: event.target.value })} placeholder="Privacy notice" className="min-h-32 rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <button onClick={saveOrg} className="rounded-2xl bg-ink px-4 py-3 font-semibold text-mist">Save Organization Settings</button>
          </div>
        </Panel>

        <Panel>
          <div className="section-title">SMTP Settings</div>
          <div className="mt-4 grid gap-4">
            <label className="flex items-center gap-3 text-sm text-slate">
              <input type="checkbox" checked={settings.email_provider_enabled} onChange={(event) => setSettings({ ...settings, email_provider_enabled: event.target.checked })} />
              Enable email delivery provider
            </label>
            <select value={settings.email_provider_mode} onChange={(event) => setSettings({ ...settings, email_provider_mode: event.target.value })} className="rounded-2xl border border-ink/10 px-4 py-3 outline-none">
              <option value="sandbox">Preview Mode</option>
              <option value="lab">Live Delivery</option>
            </select>
            <input value={settings.smtp_host ?? ""} onChange={(event) => setSettings({ ...settings, smtp_host: event.target.value })} placeholder="SMTP host" className="rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <input type="number" value={settings.smtp_port} onChange={(event) => setSettings({ ...settings, smtp_port: Number(event.target.value) })} placeholder="SMTP port" className="rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <input value={settings.smtp_username ?? ""} onChange={(event) => setSettings({ ...settings, smtp_username: event.target.value })} placeholder="SMTP username" className="rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <input type="password" value={settings.smtp_password} onChange={(event) => setSettings({ ...settings, smtp_password: event.target.value })} placeholder={settings.has_password ? "Password saved, enter only to replace" : "SMTP password or app password"} className="rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <input value={settings.smtp_from_email ?? ""} onChange={(event) => setSettings({ ...settings, smtp_from_email: event.target.value })} placeholder="From email" className="rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <input value={settings.smtp_sender_name ?? ""} onChange={(event) => setSettings({ ...settings, smtp_sender_name: event.target.value })} placeholder="Sender name" className="rounded-2xl border border-ink/10 px-4 py-3 outline-none" />
            <textarea
              value={settings.smtp_recipient_allowlist.join("\n")}
              onChange={(event) => setSettings({ ...settings, smtp_recipient_allowlist: event.target.value.split("\n").map((value) => value.trim()).filter(Boolean) })}
              placeholder="One allowed recipient email per line"
              className="min-h-32 rounded-2xl border border-ink/10 px-4 py-3 outline-none"
            />
            {message ? <div className="rounded-2xl bg-moss/10 px-4 py-3 text-sm text-moss">{message}</div> : null}
            <button onClick={saveEmail} className="rounded-2xl bg-ink px-4 py-3 font-semibold text-mist">Save Email Settings</button>
          </div>
        </Panel>
      </div>

      <Panel>
        <div className="section-title">How to Use</div>
        <div className="mt-4 grid gap-4 text-sm leading-7 text-slate lg:grid-cols-3">
          <p>For Gmail, use `smtp.gmail.com`, port `587`, your Gmail address as the username, and a Gmail app password instead of your normal account password.</p>
          <p>Only addresses in the allowlist can receive live-delivery emails. This keeps the feature controlled and limited to your owned inboxes.</p>
          <p>After saving SMTP, go to the Campaigns page and click `Send Live Email` on an approved email campaign to send the phishing simulation from the UI.</p>
        </div>
      </Panel>
    </>
  );
}
