"use client";

import {
  BarChart3, BookOpenCheck, Building2, ChevronDown, ChevronRight, CircleGauge,
  FileChartColumn, FlaskConical, History, LayoutDashboard, LogOut, Menu, Moon,
  Search, Settings, ShieldCheck, Sun, UserRoundCheck, UsersRound, X, type LucideIcon,
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { type ReactNode, useEffect, useRef, useState } from "react";

import { BrandShield } from "@/components/brand-logo";
import { useTheme } from "@/components/theme-provider";
import type { SessionUser } from "@/lib/client-api";

type NavigationItem = { href: string; label: string; description: string; icon: LucideIcon };
const navigationGroups: Array<{ label: string; items: NavigationItem[] }> = [
  {
    label: "Workspace",
    items: [
      { href: "/dashboard", label: "Overview", description: "Organization activity and risk at a glance", icon: LayoutDashboard },
      { href: "/employees", label: "People", description: "Employee directory and departments", icon: UsersRound },
      { href: "/campaigns", label: "Campaigns", description: "Campaign records and approvals", icon: CircleGauge },
      { href: "/scenario-lab", label: "Scenario library", description: "Content and approved scenarios", icon: FlaskConical },
    ],
  },
  {
    label: "Insights",
    items: [
      { href: "/analytics", label: "Analytics", description: "Performance across channels", icon: BarChart3 },
      { href: "/risk-intelligence", label: "Risk insights", description: "Behavior, risk and recommendations", icon: ShieldCheck },
      { href: "/reports", label: "Reports", description: "Reports and evidence exports", icon: FileChartColumn },
    ],
  },
  {
    label: "Governance",
    items: [
      { href: "/policies", label: "Policies", description: "Approval and consent controls", icon: BookOpenCheck },
      { href: "/personas", label: "Personas", description: "Consent and approved identities", icon: UserRoundCheck },
      { href: "/audit", label: "Audit log", description: "Administrative activity and evidence", icon: History },
    ],
  },
];
const settingsItem: NavigationItem = { href: "/settings", label: "Settings", description: "Organization, integrations and access", icon: Settings };
const platformItem: NavigationItem = { href: "/platform", label: "Platform operations", description: "Customer organizations and provisioning", icon: Building2 };
const demoMode = process.env.NEXT_PUBLIC_DEMO_MODE === "true";

export function NavShell({ children, user, onLogout }: {
  children: ReactNode;
  user: SessionUser;
  onLogout: () => void;
}) {
  const pathname = usePathname();
  const { theme, setTheme, mounted } = useTheme();
  const [query, setQuery] = useState("");
  const searchDialog = useRef<HTMLDialogElement>(null);
  const mobileDialog = useRef<HTMLDialogElement>(null);
  const availableItems = [
    ...navigationGroups.flatMap((group) => group.items), settingsItem,
    ...(user.roles.includes("platform_operator") ? [platformItem] : []),
  ];
  const currentPage = availableItems.find((item) => pathname === item.href || pathname.startsWith(item.href + "/")) ?? availableItems[0];
  const matches = availableItems.filter((item) => (item.label + " " + item.description).toLowerCase().includes(query.toLowerCase().trim()));
  const initials = user.full_name.split(" ").map((part) => part[0] ?? "").join("").slice(0, 2).toUpperCase();

  function openSearch() {
    setQuery("");
    searchDialog.current?.showModal();
  }
  useEffect(() => {
    mobileDialog.current?.close();
    searchDialog.current?.close();
  }, [pathname]);
  useEffect(() => {
    function handleShortcut(event: KeyboardEvent) {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        if (searchDialog.current?.open) searchDialog.current.close();
        else {
          setQuery("");
          searchDialog.current?.showModal();
        }
      }
    }
    document.addEventListener("keydown", handleShortcut);
    return () => document.removeEventListener("keydown", handleShortcut);
  }, []);

  function navigate() {
    mobileDialog.current?.close();
    searchDialog.current?.close();
  }
  function sidebar() {
    return (
      <div className="workspace-sidebar-inner">
        <Link href="/dashboard" className="workspace-brand" onClick={navigate} aria-label="BreachSim overview">
          <BrandShield /><span>BreachSim<span className="text-[#8cabdc]">.</span></span>
        </Link>
        <Link href="/settings" className="workspace-switch" onClick={navigate}>
          <span className="workspace-switch-mark"><Building2 size={16} /></span>
          <span className="min-w-0 flex-1">My workspace<small>{demoMode ? "Local demo environment" : "Workspace settings"}</small></span>
          <ChevronDown size={13} aria-hidden="true" />
        </Link>
        <nav aria-label="Main navigation" className="workspace-navigation">
          {navigationGroups.map((group) => (
            <div className="workspace-navigation-group" key={group.label}>
              <div className="workspace-navigation-label">{group.label}</div>
              {group.items.map((item) => <NavigationLink key={item.href} item={item} pathname={pathname} onNavigate={navigate} />)}
            </div>
          ))}
        </nav>
        <div className="workspace-sidebar-footer">
          {user.roles.includes("platform_operator") ? <NavigationLink item={platformItem} pathname={pathname} onNavigate={navigate} /> : null}
          <NavigationLink item={settingsItem} pathname={pathname} onNavigate={navigate} />
          <div className="workspace-profile">
            <span className="workspace-avatar" aria-hidden="true">{initials}</span>
            <div className="min-w-0 flex-1">
              <div className="workspace-profile-name">{user.full_name}</div>
              <div className="workspace-profile-role">{user.roles.join(" / ").replaceAll("_", " ")}</div>
            </div>
            <button className="workspace-logout" type="button" onClick={onLogout} aria-label="Log out" title="Log out"><LogOut size={16} /></button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="page-shell workspace-shell">
      <a href="#workspace-main" className="workspace-skip">Skip to main content</a>
      <aside className="workspace-sidebar">{sidebar()}</aside>
      <dialog ref={mobileDialog} className="workspace-mobile-dialog" aria-label="Navigation"
        onClick={(event) => { if (event.target === event.currentTarget) mobileDialog.current?.close(); }}>
        <button type="button" className="workspace-mobile-close" onClick={() => mobileDialog.current?.close()} aria-label="Close navigation"><X size={19} /></button>
        {sidebar()}
      </dialog>
      <div className="workspace-body">
        <header className="workspace-topbar">
          <div className="flex min-w-0 items-center gap-3">
            <button className="workspace-topbar-icon workspace-mobile-trigger" type="button" aria-label="Open navigation" onClick={() => mobileDialog.current?.showModal()}><Menu size={19} /></button>
            <div className="workspace-breadcrumb"><span>Workspace</span><ChevronRight size={13} aria-hidden="true" /><strong>{currentPage.label}</strong></div>
          </div>
          <div className="workspace-topbar-actions">
            <button className="workspace-search-trigger" type="button" onClick={openSearch} aria-label="Search pages">
              <Search size={15} /><span>Search pages…</span><kbd>Ctrl K</kbd>
            </button>
            <Link href="/audit" className="workspace-topbar-icon" title="Activity log" aria-label="Activity log"><History size={17} /></Link>
            <button className="workspace-topbar-icon" type="button" onClick={() => setTheme(theme === "dark" ? "light" : "dark")}
              aria-label={mounted && theme === "dark" ? "Switch to light mode" : "Switch to dark mode"}>
              {mounted && theme === "dark" ? <Sun size={17} /> : <Moon size={17} />}
            </button>
            <Link href="/settings" className="workspace-avatar" aria-label={"Account settings for " + user.full_name}>{initials}</Link>
          </div>
        </header>
        <main id="workspace-main" className="workspace-content" tabIndex={-1}>{children}</main>
      </div>
      <dialog ref={searchDialog} className="workspace-search-dialog" aria-label="Search pages"
        onClick={(event) => { if (event.target === event.currentTarget) searchDialog.current?.close(); }}>
        <div className="workspace-search-field">
          <Search size={19} className="text-muted" />
          <input aria-label="Find a page" placeholder="Where would you like to go?" value={query} onChange={(event) => setQuery(event.target.value)}
            onKeyDown={(event) => { if (event.key === "ArrowDown") { event.preventDefault(); searchDialog.current?.querySelector<HTMLAnchorElement>(".workspace-search-results a")?.focus(); } }} />
          <button type="button" className="workspace-topbar-icon" onClick={() => searchDialog.current?.close()} aria-label="Close search"><X size={17} /></button>
        </div>
        <div className="workspace-search-results">
          {matches.map((item) => {
            const Icon = item.icon;
            return <Link key={item.href} href={item.href} onClick={navigate}><Icon size={18} className="text-muted" /><div><strong>{item.label}</strong><p>{item.description}</p></div><ChevronRight size={14} className="ml-auto text-subtle" /></Link>;
          })}
          {!matches.length ? <p className="p-5 text-sm text-muted">No pages match “{query}”. Try people, reports, or settings.</p> : null}
        </div>
        <div className="workspace-search-footer">Tab to browse · Enter to open · Esc to close</div>
      </dialog>
    </div>
  );
}

function NavigationLink({ item, pathname, onNavigate }: { item: NavigationItem; pathname: string; onNavigate: () => void }) {
  const active = pathname === item.href || pathname.startsWith(item.href + "/");
  const Icon = item.icon;
  return <Link href={item.href} onClick={onNavigate} className="workspace-nav-link" aria-current={active ? "page" : undefined} title={item.description}><Icon size={17} strokeWidth={1.65} /><span>{item.label}</span></Link>;
}
