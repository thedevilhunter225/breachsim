"use client";

import { CheckCircle2, Copy, KeyRound, Loader2, ShieldCheck } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { BrandShield } from "@/components/brand-logo";
import { acceptInvitationRequest, type InvitationAcceptance } from "@/lib/client-api";

export function InvitationAcceptanceForm({ token }: { token: string }) {
  const [fullName, setFullName] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<InvitationAcceptance | null>(null);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    if (!token || busy) return;
    setBusy(true);
    setError(null);
    try {
      setResult(await acceptInvitationRequest({ token, full_name: fullName, password }));
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "The invitation could not be accepted.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="grid min-h-screen place-items-center bg-[#f4f3ef] px-4 py-12 text-[#101828]">
      <section className="w-full max-w-xl overflow-hidden rounded-2xl border border-[#d8d6cf] bg-white shadow-[0_24px_70px_rgba(13,27,45,0.12)]">
        <header className="bg-[#0d1b2d] px-7 py-7 text-white sm:px-9">
          <div className="flex items-center gap-3">
            <div className="grid h-11 w-11 place-items-center rounded-lg border border-white/15 bg-white/[0.06]">
              <BrandShield className="h-6 w-6" />
            </div>
            <div>
              <div className="display-font text-xl font-bold">BreachSim</div>
              <div className="text-[0.65rem] font-semibold uppercase tracking-[0.18em] text-white/50">Organization access</div>
            </div>
          </div>
        </header>

        <div className="p-7 sm:p-9">
          {!token ? (
            <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-800">This invitation link is incomplete.</div>
          ) : result ? (
            <div>
              <CheckCircle2 className="h-10 w-10 text-emerald-600" />
              <h1 className="display-font mt-4 text-2xl font-semibold">Account secured</h1>
              <p className="mt-2 text-sm leading-6 text-slate-600">Add the TOTP URI to your authenticator now, then store the recovery codes in your organization&apos;s approved password vault. They are shown only once.</p>
              <SecretBlock label="Authenticator provisioning URI" value={result.mfa_provisioning_uri} />
              <SecretBlock label="One-time recovery codes" value={result.mfa_recovery_codes.join("\n")} />
              <Link href="/login" className="app-primary-button mt-6 inline-flex">Continue to sign in</Link>
            </div>
          ) : (
            <form onSubmit={submit}>
              <ShieldCheck className="h-9 w-9 text-[#175cd3]" />
              <h1 className="display-font mt-4 text-2xl font-semibold">Activate your administrator account</h1>
              <p className="mt-2 text-sm leading-6 text-slate-600">Create a named account for your organization. Multi-factor authentication is mandatory and will be enrolled on the next step.</p>
              <label className="mt-6 block text-xs font-semibold uppercase tracking-wider text-slate-500">Full name</label>
              <input className="field mt-2 w-full" value={fullName} onChange={(event) => setFullName(event.target.value)} autoComplete="name" required minLength={2} maxLength={255} />
              <label className="mt-4 block text-xs font-semibold uppercase tracking-wider text-slate-500">New password</label>
              <input className="field mt-2 w-full" type="password" value={password} onChange={(event) => setPassword(event.target.value)} autoComplete="new-password" required minLength={14} maxLength={1024} />
              <p className="mt-2 text-xs leading-5 text-slate-500">At least 14 characters with uppercase, lowercase, a number, and a symbol.</p>
              {error ? <div className="mt-4 rounded-lg border border-red-200 bg-red-50 p-3 text-sm text-red-800">{error}</div> : null}
              <button className="app-primary-button mt-6 w-full justify-center" disabled={busy} type="submit">
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />} Activate account
              </button>
            </form>
          )}
        </div>
      </section>
    </main>
  );
}

function SecretBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="mt-5 rounded-xl border border-slate-200 bg-slate-50 p-4">
      <div className="flex items-center justify-between gap-3">
        <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">{label}</span>
        <button type="button" className="text-slate-500 hover:text-slate-900" aria-label={`Copy ${label}`} onClick={() => void navigator.clipboard.writeText(value)}><Copy className="h-4 w-4" /></button>
      </div>
      <pre className="mt-3 max-h-40 overflow-auto whitespace-pre-wrap break-all text-xs leading-5 text-slate-800">{value}</pre>
    </div>
  );
}
