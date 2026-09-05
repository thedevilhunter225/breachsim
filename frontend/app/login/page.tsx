"use client";

import { Eye, EyeOff, KeyRound, Loader2 } from "lucide-react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { BrandShield } from "@/components/brand-logo";
import { useSession } from "@/components/session-provider";

const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export default function LoginPage() {
  const router = useRouter();
  const { ready, session, signIn } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && session) router.replace("/dashboard");
  }, [ready, router, session]);

  async function handleLogin(loginEmail: string, loginPassword: string, loginMfaCode?: string) {
    if (!loginEmail || !loginPassword || submitting) return;
    setSubmitting(true);
    setError(null);
    try {
      await signIn(loginEmail, loginPassword, loginMfaCode);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to sign in");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="relative grid min-h-screen place-items-center overflow-hidden bg-[#f6f7f9] px-5 py-16 text-[#101828] sm:px-8">
      <div aria-hidden="true" className="absolute inset-x-0 top-0 h-1 bg-[#175cd3]" />

      <div className="w-full max-w-[25rem]">
        <div className="mb-8 flex items-center justify-center gap-2.5">
          <BrandShield className="h-7 w-7" />
          <span className="display-font text-[1.05rem] font-bold tracking-[-0.025em]">BreachSim</span>
        </div>

        <section className="rounded-2xl border border-[#e1e5eb] bg-white px-6 py-7 shadow-[0_16px_45px_rgba(16,24,40,0.07)] sm:px-8 sm:py-8">
          <h1 className="display-font text-[1.65rem] font-semibold tracking-[-0.035em]">Welcome back</h1>
          <p className="mt-1.5 text-[0.86rem] leading-6 text-[#667085]">Sign in to your operator workspace.</p>

          <form
            className="mt-7 space-y-4"
            onSubmit={(event) => {
              event.preventDefault();
              const form = new FormData(event.currentTarget);
              void handleLogin(
                String(form.get("email") ?? ""),
                String(form.get("password") ?? ""),
                String(form.get("mfa_code") ?? ""),
              );
            }}
          >
            <div>
              <label htmlFor="login-email" className="mb-1.5 block text-[0.76rem] font-semibold text-[#344054]">
                Work email
              </label>
              <input
                id="login-email"
                name="email"
                type="email"
                autoComplete="username"
                required
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                placeholder="name@company.com"
                className="h-11 w-full rounded-lg border !border-[#d0d5dd] !bg-white px-3.5 text-[0.9rem] !text-[#101828] shadow-[0_1px_2px_rgba(16,24,40,0.04)] outline-none transition placeholder:!text-[#98a2b3] focus:!border-[#397dc4] focus:ring-[3px] focus:ring-[#397dc4]/10"
              />
            </div>

            <div>
              <label htmlFor="login-password" className="mb-1.5 block text-[0.76rem] font-semibold text-[#344054]">
                Password
              </label>
              <div className="relative">
                <input
                  id="login-password"
                  name="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="current-password"
                  required
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                  placeholder="Enter your password"
                  className="h-11 w-full rounded-lg border !border-[#d0d5dd] !bg-white px-3.5 pr-11 text-[0.9rem] !text-[#101828] shadow-[0_1px_2px_rgba(16,24,40,0.04)] outline-none transition placeholder:!text-[#98a2b3] focus:!border-[#397dc4] focus:ring-[3px] focus:ring-[#397dc4]/10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword((value) => !value)}
                  className="absolute right-1.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-md text-[#667085] transition hover:bg-[#f2f4f7] hover:text-[#101828] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#397dc4]"
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                </button>
              </div>
            </div>

            <details className="group rounded-lg border border-[#e4e7ec] bg-[#fafbfc] px-3.5 py-2.5 open:pb-3.5">
              <summary className="cursor-pointer select-none text-[0.74rem] font-medium text-[#667085] marker:text-[#98a2b3]">
                Use MFA or a recovery code
              </summary>
              <label htmlFor="login-mfa" className="sr-only">
                Authenticator or recovery code
              </label>
              <input
                id="login-mfa"
                name="mfa_code"
                type="text"
                inputMode="numeric"
                autoComplete="one-time-code"
                value={mfaCode}
                onChange={(event) => setMfaCode(event.target.value)}
                placeholder="Authenticator or recovery code"
                className="mt-3 h-10 w-full rounded-md border !border-[#d0d5dd] !bg-white px-3 font-mono text-[0.82rem] tracking-[0.06em] !text-[#101828] outline-none transition placeholder:font-sans placeholder:tracking-normal placeholder:!text-[#98a2b3] focus:!border-[#397dc4] focus:ring-[3px] focus:ring-[#397dc4]/10"
              />
            </details>

            {error ? (
              <div role="alert" className="rounded-lg border border-[#f5c2c7] bg-[#fff5f5] px-3.5 py-3 text-[0.78rem] leading-5 text-[#a3222c]">
                {error}
              </div>
            ) : null}

            <button
              type="submit"
              disabled={submitting}
              className="flex h-11 w-full items-center justify-center gap-2 rounded-lg bg-[#174f88] text-[0.86rem] font-semibold text-white shadow-[0_1px_2px_rgba(16,24,40,0.12)] transition hover:bg-[#123f6d] focus-visible:outline-none focus-visible:ring-4 focus-visible:ring-[#397dc4]/20 active:translate-y-px disabled:cursor-not-allowed disabled:bg-[#9aa7b5]"
            >
              {submitting ? (
                <>
                  <Loader2 size={15} className="animate-spin" />
                  Signing in…
                </>
              ) : (
                "Sign in"
              )}
            </button>
          </form>

          {demoMode ? (
            <div className="mt-5 border-t border-[#eaecf0] pt-5">
              <button
                type="button"
                onClick={() => {
                  setEmail("admin@breachsim-lab.com");
                  setPassword("Admin123!");
                  setError(null);
                }}
                className="flex w-full items-center justify-center gap-2 rounded-lg px-3 py-2 text-[0.76rem] font-medium text-[#475467] transition hover:bg-[#f7f8fa] hover:text-[#174f88]"
              >
                <KeyRound size={14} />
                Fill demo credentials
              </button>
            </div>
          ) : null}
        </section>

        <p className="mt-6 text-center text-[0.68rem] leading-5 text-[#98a2b3]">
          Authorized operators only · Access activity is recorded
        </p>
      </div>
    </main>
  );
}
