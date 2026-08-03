"use client";

import clsx from "clsx";
import {
  BarChart3,
  Bell,
  BookOpenCheck,
  ChevronRight,
  CircleGauge,
  FileChartColumn,
  FlaskConical,
  LayoutDashboard,
  LogOut,
  Menu,
  Moon,
  PanelLeftClose,
  Settings,
  ShieldCheck,
  Sparkles,
  Sun,
  UserRoundCheck,
  UsersRound,
  X,
  type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { ReactNode, useEffect, useMemo, useRef, useState } from "react";

import { BrandLogo } from "@/components/brand-logo";
import { useTheme } from "@/components/theme-provider";
import { SessionUser } from "@/lib/client-api";

type NavigationItem = {
  href: string;
  label: string;
  description: string;
  icon: LucideIcon;
};

const navigationGroups: Array<{ label: string; items: NavigationItem[] }> = [
  {
    label: "Operate",
    items: [
      { href: "/dashboard", label: "Command Center", description: "Security posture overview", icon: LayoutDashboard },
      { href: "/employees", label: "Directory", description: "People and departments", icon: UsersRound },
      { href: "/scenario-lab", label: "Scenario Studio", description: "AI simulation content", icon: FlaskConical },
      { href: "/campaigns", label: "Campaigns", description: "Approvals and delivery", icon: CircleGauge },
    ],
  },
  {
    label: "Intelligence",
    items: [
      { href: "/analytics", label: "Analytics", description: "Campaign performance", icon: BarChart3 },
      { href: "/risk-intelligence", label: "Risk Intelligence", description: "Adaptive employee risk", icon: Sparkles },
    ],
  },
  {
    label: "Governance",
    items: [
      { href: "/policies", label: "Controls", description: "Simulation guardrails", icon: ShieldCheck },
      { href: "/personas", label: "Personas", description: "Impersonation consent registry", icon: UserRoundCheck },
      { href: "/audit", label: "Audit Trail", description: "Immutable activity record", icon: BookOpenCheck },
      { href: "/reports", label: "Reports", description: "Evidence and exports", icon: FileChartColumn },
    ],
  },
];

const systemItem: NavigationItem = {
  href: "/settings",
  label: "Workspace Settings",
  description: "Organization and delivery",
  icon: Settings,
};

const allItems = [...navigationGroups.flatMap((group) => group.items), systemItem];

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
  const [mobileOpen, setMobileOpen] = useState(false);
  const navigationScrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    setMobileOpen(false);
    navigationScrollRef.current?.scrollTo({ top: 0 });
  }, [pathname]);

  const currentPage = useMemo(
    () => allItems.find((item) => pathname === item.href || pathname?.startsWith(`${item.href}/`)) ?? allItems[0],
    [pathname],
  );

  const initials = user.full_name
    .split(" ")
    .map((part) => part[0] ?? "")
    .join("")
    .slice(0, 2)
    .toUpperCase();

  const sidebar = (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex h-[72px] shrink-0 items-center justify-between border-b border-white/[0.08] px-5">
        <BrandLogo inverted className="[&>div:first-child]:h-10 [&>div:first-child]:w-10 [&>div:first-child]:rounded-xl [&_svg]:h-7 [&_svg]:w-7" />
        <button
          type="button"
          onClick={() => setMobileOpen(false)}
          className="grid h-9 w-9 place-items-center rounded-lg text-white/55 hover:bg-white/[0.08] hover:text-white lg:hidden"
          aria-label="Close navigation"
        >
          <PanelLeftClose size={18} />
        </button>
      </div>

      <div ref={navigationScrollRef} className="min-h-0 flex-1 overflow-y-auto px-3 py-4">
        <div className="mb-5 flex items-center gap-2 rounded-lg border border-brand-200/10 bg-brand-400/[0.06] px-3 py-2.5 text-[0.68rem] font-semibold uppercase tracking-[0.13em] text-brand-100/72">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-300 shadow-[0_0_0_4px_rgba(110,231,183,0.08)]" />
          Workspace operational
        </div>

        <nav aria-label="Main navigation" className="space-y-5">
          {navigationGroups.map((group) => (
            <div key={group.label}>
              <div className="mb-1.5 px-3 text-[0.62rem] font-semibold uppercase tracking-[0.19em] text-white/30">
                {group.label}
              </div>
              <div className="space-y-1">
                {group.items.map((item) => (
                  <NavigationLink key={item.href} item={item} pathname={pathname} />
                ))}
              </div>
            </div>
          ))}
        </nav>
      </div>

      <div className="shrink-0 border-t border-white/[0.08] p-3">
        <NavigationLink item={systemItem} pathname={pathname} />

        <div className="mt-3 rounded-xl border border-white/[0.08] bg-white/[0.045] p-3">
          <div className="flex items-center gap-3">
            <div className="grid h-9 w-9 shrink-0 place-items-center rounded-lg bg-brand-200/10 text-xs font-bold text-brand-50">
              {initials}
            </div>
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-semibold text-white">{user.full_name}</div>
              <div className="mt-0.5 truncate text-[0.65rem] uppercase tracking-[0.13em] text-white/38">
                {user.roles.join(" / ")}
              </div>
            </div>
            <button
              type="button"
              onClick={onLogout}
              className="grid h-8 w-8 shrink-0 place-items-center rounded-lg text-white/40 hover:bg-white/[0.08] hover:text-white"
              aria-label="Log out"
            >
              <LogOut size={16} />
            </button>
          </div>
        </div>
      </div>
    </div>
  );

  return (
    <div className="page-shell min-h-screen">
      {mobileOpen ? (
        <button
          className="fixed inset-0 z-40 bg-slate-950/55 backdrop-blur-[2px] lg:hidden"
          onClick={() => setMobileOpen(false)}
          aria-label="Close navigation overlay"
        />
      ) : null}

      <aside
        className={clsx(
          "app-nav fixed inset-y-0 left-0 z-50 w-[264px] text-white transition-transform duration-200 lg:translate-x-0",
          mobileOpen ? "translate-x-0" : "-translate-x-full",
        )}
      >
        {sidebar}
      </aside>

      <div className="min-w-0 lg:pl-[264px]">
        <header className="app-topbar sticky top-0 z-30 flex h-[72px] items-center justify-between gap-4 px-4 md:px-6 xl:px-8">
          <div className="flex min-w-0 items-center gap-3">
            <button
              type="button"
              onClick={() => setMobileOpen(true)}
              className="app-icon-button lg:hidden"
              aria-label="Open navigation"
            >
              <Menu size={18} />
            </button>
            <div className="min-w-0">
              <div className="flex items-center gap-1.5 text-[0.68rem] font-semibold uppercase tracking-[0.14em] text-slate">
                BreachSim
                <ChevronRight size={12} />
                <span className="truncate">{currentPage.label}</span>
              </div>
              <div className="mt-0.5 truncate font-display text-lg font-semibold tracking-[-0.025em] text-ink">
                {currentPage.description}
              </div>
            </div>
          </div>

          <div className="flex shrink-0 items-center gap-2">
            <div className="mr-1 hidden items-center gap-2 rounded-full border border-ink/[0.08] bg-white/70 px-3 py-1.5 text-xs font-semibold text-slate md:flex">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500" />
              Live workspace
            </div>
            <button type="button" className="app-icon-button hidden sm:grid" aria-label="Notifications">
              <Bell size={17} />
            </button>
            <button
              type="button"
              className="app-icon-button"
              onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label={mounted && theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}
            >
              {mounted && theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <Link href="/scenario-lab" className="app-primary-button hidden md:inline-flex">
              <Sparkles size={15} />
              New scenario
            </Link>
          </div>
        </header>

        <main className="mx-auto min-h-[calc(100vh-72px)] w-full max-w-[1680px] space-y-4 px-4 py-4 md:px-6 md:py-6 xl:px-8">
          {children}
        </main>
      </div>
    </div>
  );
}

function NavigationLink({ item, pathname }: { item: NavigationItem; pathname: string }) {
  const active = pathname === item.href || pathname?.startsWith(`${item.href}/`);
  const Icon = item.icon;

  return (
    <Link
      href={item.href}
      className={clsx(
        "group flex min-h-10 items-center gap-3 rounded-lg px-3 py-2 text-sm font-semibold transition-colors",
        active
          ? "bg-brand-400/[0.12] text-white shadow-[inset_2px_0_0_#4FA3FF]"
          : "text-white/58 hover:bg-white/[0.055] hover:text-white/92",
      )}
      title={item.description}
    >
      <Icon size={17} strokeWidth={active ? 2.2 : 1.8} className={active ? "text-brand-200" : "text-white/38 group-hover:text-white/70"} />
      <span className="truncate">{item.label}</span>
    </Link>
  );
}
