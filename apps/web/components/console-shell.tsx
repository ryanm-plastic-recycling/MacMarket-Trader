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
    <div style={{ display: "grid", gridTemplateColumns: "260px 1fr", minHeight: "100vh" }}>
      <aside style={{ borderRight: "1px solid #2b3642", padding: 20, background: "#111922" }}>
        <h2 style={{ marginTop: 0, fontSize: 18 }}>MacMarket Trader</h2>
        <nav style={{ display: "grid", gap: 10 }}>
          {links.map(([href, label]) => (
            <Link key={href} href={href} style={{ color: "#cbd6e2", textDecoration: "none" }}>
              {label}
            </Link>
          ))}
        </nav>
      </aside>
      <section>
        <header style={{ borderBottom: "1px solid #2b3642", padding: "14px 20px" }}>Private alpha operator console</header>
        <main style={{ padding: 20 }}>{children}</main>
      </section>
    </div>
  );
}
