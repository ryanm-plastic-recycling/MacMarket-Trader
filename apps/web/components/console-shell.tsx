import Link from "next/link";

import { ThemeToggle } from "@/components/theme-toggle";

const links = [
  ["/dashboard", "Dashboard"],
  ["/recommendations", "Recommendations"],
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
        <h2 style={{ marginTop: 0, marginBottom: 8 }}>MacMarket Trader</h2>
        <p style={{ color: "#8da1b8", marginTop: 0, fontSize: 12 }}>Invite-only private alpha console</p>
        <nav className="op-nav">
          {links.map(([href, label]) => (
            <Link key={href} href={href}>{label}</Link>
          ))}
        </nav>
      </aside>
      <section className="op-main">
        <header className="op-topbar"><span>Flagship workflow: Recommendations → Replay → Paper Orders</span><ThemeToggle /></header>
        <main className="op-content">{children}</main>
      </section>
    </div>
  );
}
