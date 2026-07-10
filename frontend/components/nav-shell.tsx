"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode } from "react";
import clsx from "clsx";

import { BrandLogo } from "@/components/brand-logo";
import { SessionUser } from "@/lib/client-api";
import { useTheme } from "@/components/theme-provider";

const links = [
  { href: "/dashboard", label: "Dashboard", meta: "Overview" },
  { href: "/employees", label: "Directory", meta: "People" },
  { href: "/policies", label: "Policies", meta: "Rules" },
  { href: "/scenario-lab", label: "Scenario Lab", meta: "Content" },
  { href: "/campaigns", label: "Campaigns", meta: "Delivery" },
  { href: "/analytics", label: "Analytics", meta: "Summary" },
  { href: "/risk-intelligence", label: "Risk Intelligence", meta: "Deep Dive" },
  { href: "/audit", label: "Audit", meta: "Trace" },
  { href: "/reports", label: "Reports", meta: "Exports" },
  { href: "/settings", label: "Settings", meta: "Workspace" },
];

export function NavShell({
  children,
  user,
  onLogout,
}: {
  children: ReactNode;
  user: SessionUser;
  onLogout: () => void;
}) {
  const pathname = usePathname();
  const { theme, setTheme, mounted } = useTheme();
  const isDark = theme === "dark";

  return (
    <div className="page-shell min-h-screen px-4 py-4 md:px-5">
      <div className="mx-auto grid max-w-[1680px] gap-4 sm:grid-cols-[220px_1fr] xl:grid-cols-[260px_1fr]">
        <aside
          className={clsx(
            "self-start overflow-hidden rounded-lg p-3 transition-colors sm:sticky sm:top-4 sm:max-h-[calc(100vh-2rem)] sm:overflow-y-auto",
            isDark
              ? "glass-dark text-mist"
              : "border border-ink/10 bg-white text-ink shadow-sm",
          )}
        >
          <div className="relative flex h-full flex-col">
            <div className={clsx("rounded-lg p-3", isDark ? "border border-white/10 bg-white/5" : "border border-ink/8 bg-slate-50")}>
              <BrandLogo inverted={isDark} />
              <p className={clsx("mt-2 text-xs leading-5", isDark ? "text-mist/72" : "text-slate")}>
                AI phishing simulations, adaptive retesting, and human-risk intelligence in one control plane.
              </p>
            </div>

            <div className={clsx("mt-3 flex items-center gap-3 rounded-lg px-3 py-2.5", isDark ? "border border-white/10 bg-white/5" : "border border-ink/8 bg-slate-50")}>
              <div
                className={clsx(
                  "grid h-9 w-9 place-items-center rounded-md text-xs font-semibold",
                  isDark ? "bg-white/10 text-mist" : "bg-sand text-ink",
                )}
              >
                {user.full_name
                  .split(" ")
                  .map((part) => part[0] ?? "")
                  .join("")
                  .slice(0, 2)}
              </div>
              <div className="min-w-0">
                <div className={clsx("truncate text-sm font-semibold", isDark ? "text-mist" : "text-ink")}>{user.full_name}</div>
                <div className={clsx("truncate text-xs uppercase tracking-[0.18em]", isDark ? "text-mist/55" : "text-slate")}>{user.roles.join(" / ")}</div>
              </div>
            </div>

            <nav className="mt-3 flex-1 space-y-1 pr-1">
              {links.map((link) => {
                const active = pathname === link.href || pathname?.startsWith(`${link.href}/`);
                return (
                  <Link
                    key={link.href}
                    href={link.href}
                    className={clsx(
                      "group flex items-center justify-between rounded-md border px-3 py-2 transition",
                      isDark
                        ? active
                          ? "border-white/18 bg-white/12 text-white shadow-[0_18px_38px_rgba(0,0,0,0.16)]"
                          : "border-transparent bg-transparent text-mist/72 hover:border-white/10 hover:bg-white/7 hover:text-white"
                        : active
                          ? "border-ink/12 bg-white text-ink shadow-[0_18px_38px_rgba(16,22,37,0.08)]"
                          : "border-transparent bg-transparent text-slate hover:border-ink/8 hover:bg-white/78 hover:text-ink",
                    )}
                  >
                    <div>
                      <div className="text-sm font-semibold">{link.label}</div>
                      <div
                        className={clsx(
                          "mt-0.5 text-[0.66rem] uppercase tracking-[0.16em]",
                          isDark
                            ? active
                              ? "text-mist/55"
                              : "text-mist/40 group-hover:text-mist/55"
                            : active
                              ? "text-slate"
                              : "text-slate/75 group-hover:text-slate",
                        )}
                      >
                        {link.meta}
                      </div>
                    </div>
                    <div
                      className={clsx(
                        "h-2 w-2 rounded-full",
                        isDark
                          ? active
                            ? "bg-emerald-300"
                            : "bg-white/15 group-hover:bg-white/28"
                          : active
                            ? "bg-tide"
                            : "bg-ink/12 group-hover:bg-ink/25",
                      )}
                    />
                  </Link>
                );
              })}
            </nav>

            <div className={clsx("mt-3 rounded-lg p-3", isDark ? "border border-white/10 bg-white/6" : "border border-ink/8 bg-slate-50")}>
              <div className={clsx("text-[0.68rem] uppercase tracking-[0.24em]", isDark ? "text-mist/50" : "text-slate")}>Appearance</div>
              <div className={clsx("mt-3 grid grid-cols-2 gap-2 rounded-md p-1", isDark ? "bg-black/10" : "bg-sand")}>
                <button
                  onClick={() => setTheme("light")}
                  className={clsx(
                    "rounded px-3 py-2 text-sm font-semibold shadow-none",
                    mounted && theme === "light"
                      ? "bg-white text-ink"
                      : isDark
                        ? "bg-transparent text-mist/62"
                        : "bg-transparent text-slate",
                  )}
                >
                  Light
                </button>
                <button
                  onClick={() => setTheme("dark")}
                  className={clsx(
                    "rounded px-3 py-2 text-sm font-semibold shadow-none",
                    mounted && theme === "dark"
                      ? isDark
                        ? "bg-white text-ink"
                        : "bg-ink text-white"
                      : isDark
                        ? "bg-transparent text-mist/62"
                        : "bg-transparent text-slate",
                  )}
                >
                  Dark
                </button>
              </div>

              <div className={clsx("mt-5 text-[0.68rem] uppercase tracking-[0.24em]", isDark ? "text-mist/50" : "text-slate")}>Workspace</div>
              <div className={clsx("mt-3 text-sm font-semibold", isDark ? "text-mist" : "text-ink")}>{user.email}</div>
              <button
                onClick={onLogout}
                className={clsx(
                  "mt-4 w-full rounded-md px-4 py-2.5 text-sm font-semibold",
                  isDark
                    ? "bg-white text-ink shadow-[0_18px_30px_rgba(0,0,0,0.12)]"
                    : "bg-ink text-white shadow-[0_18px_30px_rgba(16,22,37,0.12)]",
                )}
              >
                Logout
              </button>
            </div>
          </div>
        </aside>

        <main className="min-w-0 space-y-5 overflow-x-hidden pb-6">{children}</main>
      </div>
    </div>
  );
}
