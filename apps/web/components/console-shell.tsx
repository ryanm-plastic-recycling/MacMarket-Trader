"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { ThemeToggle } from "@/components/theme-toggle";
import { BrandLockup } from "@/components/brand-lockup";
import { isActivePath } from "@/lib/console-nav";

const navSections = [
  {
    title: "Workflow",
    links: [
      ["/dashboard", "Dashboard"],
      ["/analysis", "Analyze"],
      ["/recommendations", "Recommendation"],
      ["/replay-runs", "Replay"],
      ["/orders", "Paper Order"],
    ],
  },
  {
    title: "Research",
    links: [
      ["/analyze", "Symbol Snapshot"],
      ["/charts/haco", "HACO Context"],
    ],
  },
  {
    title: "Reports",
    links: [["/schedules", "Scheduled Reports"]],
  },
  {
    title: "Admin",
    links: [
      ["/admin/pending-users", "Admin / Invites"],
      ["/admin/users", "Admin / Users"],
      ["/admin/provider-health", "Provider Health"],
      ["/account", "Account"],
    ],
  },
] as const;

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const buildStamp = process.env.NEXT_PUBLIC_BUILD_STAMP ?? "dev-local";

  return (
    <div className="op-shell">
      <aside className="op-aside">
        <div className="op-brand-block">
          <BrandLockup />
          <p className="op-brand-caption">Invite-only private alpha console</p>
        </div>
        <nav className="op-nav">
          {navSections.map((section) => (
            <section key={section.title} className="op-nav-section">
              <div className="op-nav-section-title">{section.title}</div>
              <div className="op-nav-links">
                {section.links.map(([href, label]) => {
                  const active = isActivePath(pathname, href);
                  return <Link key={href} href={href} className={active ? "is-active" : ""}>{label}</Link>;
                })}
              </div>
            </section>
          ))}
        </nav>
      </aside>
      <section className="op-main">
        <header className="op-topbar">
          <div className="op-topbar-brand">
            <BrandLockup compact />
            <span>Workflow: Analyze → Recommendation → Replay → Paper Order</span>
          </div>
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <span style={{ fontSize: "0.74rem", color: "var(--op-muted, #7a8999)" }}>build: {buildStamp}</span>
            <ThemeToggle />
          </div>
        </header>
        <main className="op-content">{children}</main>
      </section>
    </div>
  );
}
