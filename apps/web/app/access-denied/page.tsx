import Link from "next/link";

import { BrandHeader } from "@/components/brand-header";

export default function Page() {
  return (
    <>
      <BrandHeader />
      <section style={{ maxWidth: 720, margin: "80px auto", padding: 24, border: "1px solid #2b3642", background: "#111922" }}>
        <h1 style={{ marginTop: 0 }}>Access denied</h1>
        <p>Your account is authenticated but does not have the required privileges for this route.</p>
        <p style={{ color: "#9fb0c3" }}>If you believe this is an error, contact an administrator.</p>
        <Link href="/dashboard" style={{ color: "#4b8cff" }}>Back to dashboard</Link>
      </section>
    </>
  );
}
