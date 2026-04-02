import Link from "next/link";

const links = [
  ["/dashboard", "Dashboard"],
  ["/recommendations", "Recommendations"],
  ["/replay-runs", "Replay runs"],
  ["/orders", "Orders"],
  ["/charts/haco", "HACO charts"],
  ["/admin/pending-users", "Admin pending users"],
  ["/admin/provider-health", "Provider health"],
  ["/account", "Account"],
] as const;

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  return (
    <div style={{ display: "grid", gridTemplateColumns: "270px 1fr", minHeight: "100vh", letterSpacing: "0.1px" }}>
      <aside style={{ borderRight: "1px solid #2b3642", padding: 22, background: "#0d141d" }}>
        <h2 style={{ marginTop: 0, fontSize: 18, marginBottom: 14 }}>MacMarket Trader</h2>
        <p style={{ color: "#8da1b8", marginTop: 0, fontSize: 12 }}>Operator console</p>
        <nav style={{ display: "grid", gap: 10 }}>
          {links.map(([href, label]) => (
            <Link key={href} href={href} style={{ color: "#cbd6e2", textDecoration: "none", padding: "6px 8px", border: "1px solid transparent" }}>
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <section>
        <header style={{ borderBottom: "1px solid #2b3642", padding: "14px 20px", background: "#0f1722" }}>Private alpha operator console</header>
        <main style={{ padding: 20 }}>{children}</main>
      </section>
    </div>
  );
}
