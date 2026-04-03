import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";
import { BrandLockup } from "@/components/brand-lockup";

const links = [
  ["/dashboard", "Dashboard"],
  ["/analysis", "Strategy Workbench"],
  ["/analyze", "Symbol Analyze"],
  ["/recommendations", "Recommendations"],
  ["/schedules", "Scheduled Reports"],
  ["/replay-runs", "Replay"],
  ["/orders", "Orders"],
  ["/charts/haco", "HACO Context"],
  ["/admin/pending-users", "Admin / Invites"],
  ["/admin/users", "Admin / Users"],
  ["/admin/provider-health", "Provider Health"],
  ["/account", "Account"],
] as const;

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  return (
    <div className="op-shell">
      <aside className="op-aside">
        <div className="op-brand-block">
          <BrandLockup />
          <p style={{ color: "#8da1b8", marginTop: 10, fontSize: 12 }}>Invite-only private alpha console</p>
        </div>
        <nav className="op-nav">
          {links.map(([href, label]) => (
            <Link key={href} href={href}>{label}</Link>
          ))}
        </nav>
      </aside>
      <section className="op-main">
        <header className="op-topbar"><span>Workflow: Strategy Workbench → Recommendations → Replay → Paper Orders</span><ThemeToggle /></header>
        <main className="op-content">{children}</main>
      </section>
    </div>
  );
}
