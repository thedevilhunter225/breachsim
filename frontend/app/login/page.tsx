"use client";

import {
  ArrowRight,
  Eye,
  EyeOff,
  FileLock2,
  Loader2,
  Lock,
  Mail,
  MessageSquare,
  PhoneCall,
  QrCode,
  ScrollText,
  ShieldCheck,
  UserRoundCheck,
  Video,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { BrandShield } from "@/components/brand-logo";
import { useSession } from "@/components/session-provider";

const CHANNELS: Array<{ icon: LucideIcon; label: string }> = [
  { icon: Mail, label: "Email" },
  { icon: MessageSquare, label: "SMS" },
  { icon: QrCode, label: "QR" },
  { icon: PhoneCall, label: "Voice" },
  { icon: Video, label: "Deepfake" },
];

const TRUST: Array<{ icon: LucideIcon; label: string }> = [
  { icon: UserRoundCheck, label: "Consent-governed cloning" },
  { icon: ScrollText, label: "Append-only audit trail" },
  { icon: FileLock2, label: "Field-level encryption" },
];

const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export default function LoginPage() {
  const router = useRouter();
  const { ready, session, signIn } = useSession();
  const [email, setEmail] = useState(demoMode ? "admin@breachsim-lab.com" : "");
  const [password, setPassword] = useState(demoMode ? "Admin123!" : "");
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    if (ready && session) router.replace("/dashboard");
  }, [ready, router, session]);

  async function handleLogin() {
    setSubmitting(true);
    setError(null);
    try {
      await signIn(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="dark-login relative min-h-screen overflow-hidden bg-[#060d1c] text-white">
      {/* Ambient background */}
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-0 bg-[radial-gradient(1100px_620px_at_12%_-8%,rgba(43,139,255,0.22),transparent_60%),radial-gradient(900px_600px_at_100%_110%,rgba(30,111,224,0.18),transparent_55%),linear-gradient(180deg,#081326_0%,#060d1c_55%,#040914_100%)]" />
        <div className="absolute inset-0 opacity-[0.35] [background-image:linear-gradient(rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.05)_1px,transparent_1px)] [background-size:56px_56px] [mask-image:radial-gradient(1000px_700px_at_20%_0%,#000_20%,transparent_75%)]" />
        <div className="login-orb absolute -left-32 top-[-10%] h-[34rem] w-[34rem] rounded-full bg-[radial-gradient(circle,rgba(79,163,255,0.28),transparent_65%)] blur-3xl" />
        <div className="login-orb absolute right-[-10%] bottom-[-15%] h-[30rem] w-[30rem] rounded-full bg-[radial-gradient(circle,rgba(43,139,255,0.2),transparent_65%)] blur-3xl [animation-delay:-6s]" />
      </div>

      <div className="relative mx-auto grid min-h-screen w-full max-w-[1240px] items-center gap-10 px-5 py-10 lg:grid-cols-[1.05fr_0.95fr] lg:gap-16 lg:px-10">
        {/* ---------------------------------------------------------- brand side */}
        <section className="stagger hidden flex-col justify-between lg:flex">
          <div className="flex items-center gap-3">
            <div className="relative grid h-11 w-11 place-items-center overflow-hidden rounded-xl bg-white/[0.06] ring-1 ring-inset ring-white/12">
              <BrandShield className="h-7 w-7" />
              {/* Slow forensic "read" across the mark */}
              <span className="scan-sweep pointer-events-none absolute inset-x-0 h-5 bg-gradient-to-b from-transparent via-brand-300/25 to-transparent" />
            </div>
            <div>
              <div className="display-font text-xl font-bold leading-none">
                Breach<span className="text-brand-400">Sim</span>
              </div>
              <div className="mt-1 font-mono text-[0.58rem] font-medium uppercase tracking-[0.22em] text-white/40">
                Human Risk Intelligence
              </div>
            </div>
          </div>

          <div className="max-w-xl py-10">
            <div className="inline-flex items-center gap-2 rounded-md border border-brand-400/25 bg-brand-400/10 px-3 py-1.5 font-mono text-[0.62rem] font-medium uppercase tracking-[0.16em] text-brand-200">
              <span className="relative flex h-1.5 w-1.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand-300 opacity-75" />
                <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-brand-300" />
              </span>
              ai-driven · multi-channel
            </div>

            <h1 className="display-font mt-6 text-[2.9rem] font-bold leading-[1.04] tracking-[-0.04em] text-white">
              Test your people against{" "}
              <span className="bg-gradient-to-r from-brand-300 to-brand-500 bg-clip-text text-transparent">
                every modern attack.
              </span>
            </h1>
            <p className="mt-5 max-w-md text-[0.95rem] leading-relaxed text-white/60">
              Governed phishing simulation across five channels — including real cloned-voice and deepfake
              impersonation — with human-risk scoring, adaptive training, and evidence-grade reporting.
            </p>

            {/* Channel showcase — the product's differentiator */}
            <div className="mt-8">
              <div className="font-mono text-[0.6rem] font-medium uppercase tracking-[0.16em] text-white/35">
                05 / attack channels
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {CHANNELS.map(({ icon: Icon, label }, index) => (
                  <div
                    key={label}
                    className="group flex items-center gap-2 rounded-lg border border-white/10 bg-white/[0.04] px-3 py-2.5 backdrop-blur-sm transition-colors hover:border-brand-400/40 hover:bg-brand-400/[0.08]"
                  >
                    <span className="font-mono text-[0.6rem] text-white/25">
                      {String(index + 1).padStart(2, "0")}
                    </span>
                    <Icon size={15} className="text-brand-300" />
                    <span className="text-[0.8rem] font-semibold text-white/82">{label}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/* Trust row */}
          <div className="flex flex-wrap gap-x-6 gap-y-2.5">
            {TRUST.map(({ icon: Icon, label }) => (
              <div key={label} className="flex items-center gap-2 text-[0.78rem] text-white/50">
                <Icon size={14} className="text-brand-300/80" />
                {label}
              </div>
            ))}
          </div>
        </section>

        {/* ---------------------------------------------------------- sign-in card */}
        <section className="relative w-full">
          {/* Mobile brand */}
          <div className="mb-7 flex items-center gap-2.5 lg:hidden">
            <div className="grid h-10 w-10 place-items-center rounded-xl bg-white/[0.06] ring-1 ring-inset ring-white/12">
              <BrandShield className="h-6 w-6" />
            </div>
            <div className="display-font text-lg font-bold">
              Breach<span className="text-brand-400">Sim</span>
            </div>
          </div>

          <div className="reveal relative overflow-hidden rounded-2xl border border-white/10 bg-white/[0.035] p-7 shadow-[0_30px_90px_rgba(0,0,0,0.5)] backdrop-blur-xl [animation-delay:200ms] sm:p-9">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-brand-400/50 to-transparent" />

            <div className="font-mono text-[0.62rem] font-medium uppercase tracking-[0.16em] text-brand-300/80">
              secure admin sign-in
            </div>
            <h2 className="display-font mt-2 text-[1.85rem] font-bold tracking-[-0.02em] text-white">
              Welcome back
            </h2>
            <p className="mt-2 text-[0.88rem] leading-relaxed text-white/55">
              Sign in to configure the directory, generate scenarios, and inspect human-risk intelligence.
            </p>

            <form
              className="mt-7 space-y-4"
              onSubmit={(event) => {
                event.preventDefault();
                void handleLogin();
              }}
            >
              <div>
                <label htmlFor="login-email" className="mb-1.5 block text-[0.72rem] font-semibold text-white/55">
                  Email address
                </label>
                <div className="group relative">
                  <Mail
                    size={17}
                    className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-white/35 transition-colors group-focus-within:text-brand-300"
                  />
                  <input
                    id="login-email"
                    type="email"
                    autoComplete="username"
                    value={email}
                    onChange={(event) => setEmail(event.target.value)}
                    placeholder="you@company.com"
                    className="login-input h-12 w-full rounded-xl border border-white/12 bg-white/[0.04] pl-10 pr-3.5 text-[0.95rem] text-white outline-none transition placeholder:text-white/25 focus:border-brand-400/70 focus:bg-white/[0.06]"
                  />
                </div>
              </div>

              <div>
                <label htmlFor="login-password" className="mb-1.5 block text-[0.72rem] font-semibold text-white/55">
                  Password
                </label>
                <div className="group relative">
                  <Lock
                    size={17}
                    className="pointer-events-none absolute left-3.5 top-1/2 -translate-y-1/2 text-white/35 transition-colors group-focus-within:text-brand-300"
                  />
                  <input
                    id="login-password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="current-password"
                    value={password}
                    onChange={(event) => setPassword(event.target.value)}
                    placeholder="••••••••"
                    className="login-input h-12 w-full rounded-xl border border-white/12 bg-white/[0.04] pl-10 pr-11 text-[0.95rem] text-white outline-none transition placeholder:text-white/25 focus:border-brand-400/70 focus:bg-white/[0.06]"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((value) => !value)}
                    className="absolute right-2.5 top-1/2 grid h-8 w-8 -translate-y-1/2 place-items-center rounded-lg text-white/40 transition hover:bg-white/8 hover:text-white/80"
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={16} /> : <Eye size={16} />}
                  </button>
                </div>
              </div>

              {error ? (
                <div className="rounded-xl border border-rose-400/30 bg-rose-400/10 px-3.5 py-2.5 text-[0.82rem] text-rose-100">
                  {error}
                </div>
              ) : null}

              <button
                type="submit"
                disabled={submitting}
                className="group flex h-12 w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-b from-brand-400 to-brand-600 text-[0.95rem] font-bold text-white shadow-[0_14px_30px_rgba(43,139,255,0.35)] transition hover:from-brand-300 hover:to-brand-500 active:translate-y-px disabled:opacity-60"
              >
                {submitting ? (
                  <>
                    <Loader2 size={17} className="animate-spin" />
                    Signing in…
                  </>
                ) : (
                  <>
                    <ShieldCheck size={17} />
                    Enter control center
                    <ArrowRight size={16} className="transition-transform group-hover:translate-x-0.5" />
                  </>
                )}
              </button>
            </form>

            {demoMode ? (
              <button
                type="button"
                onClick={() => {
                  setEmail("admin@breachsim-lab.com");
                  setPassword("Admin123!");
                }}
                className="mt-5 flex w-full items-center justify-between gap-3 rounded-xl border border-dashed border-white/15 bg-white/[0.02] px-4 py-3 text-left transition hover:border-brand-400/40 hover:bg-brand-400/[0.05]"
              >
                <div>
                  <div className="font-mono text-[0.6rem] font-medium uppercase tracking-[0.14em] text-white/40">
                    demo credentials
                  </div>
                  <div className="numeric mt-0.5 font-mono text-[0.82rem] text-white/75">
                    admin@breachsim-lab.com · Admin123!
                  </div>
                </div>
                <span className="shrink-0 rounded-lg bg-brand-400/15 px-2.5 py-1.5 text-[0.72rem] font-bold text-brand-200">
                  Fill
                </span>
              </button>
            ) : null}
          </div>

          <div className="reveal mt-5 flex items-center justify-between px-1 text-[0.8rem] [animation-delay:320ms]">
            <Link
              href="/employee-portal"
              className="font-semibold text-white/60 transition hover:text-white"
            >
              Employee portal →
            </Link>
            <span className="inline-flex items-center gap-1.5 font-mono text-[0.68rem] uppercase tracking-[0.1em] text-white/40">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.7)]" />
              system operational
            </span>
          </div>
        </section>
      </div>
    </main>
  );
}
