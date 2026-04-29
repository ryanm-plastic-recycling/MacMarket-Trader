import { SignIn } from "@clerk/nextjs";

import { BrandHeader } from "@/components/brand-header";
import { BrandLockup } from "@/components/brand-lockup";

export default function Page() {
  return (
    <>
      <BrandHeader tagline="Operator sign-in" />
      <main className="auth-shell">
        <BrandLockup />
        <p>Operator sign-in · Trade Setup → Recommendations → Replay → Paper Orders</p>
        <SignIn />
      </main>
    </>
  );
}
