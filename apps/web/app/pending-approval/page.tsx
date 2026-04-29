import Link from "next/link";

import { BrandHeader } from "@/components/brand-header";

export default function Page() {
  return (
    <>
      <BrandHeader tagline="Private Alpha" />
      <section style={{ maxWidth: 720, margin: "80px auto", padding: 24, border: "1px solid #2b3642", background: "#111922" }}>
        <h1 style={{ marginTop: 0 }}>Pending approval</h1>
        <p>Your identity is verified, but operator desk access is pending admin review.</p>
        <p style={{ color: "#9fb0c3" }}>You will receive an approval email when your status changes.</p>
        <Link href="/sign-in" style={{ color: "#4b8cff" }}>Return to sign in</Link>
      </section>
    </>
  );
}
