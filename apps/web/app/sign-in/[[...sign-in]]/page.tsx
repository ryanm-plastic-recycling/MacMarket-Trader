import { SignIn } from "@clerk/nextjs";

import { BrandLockup } from "@/components/brand-lockup";

export default function Page() {
  return (
    <main className="auth-shell">
      <BrandLockup />
      <p>Operator sign-in · Strategy Workbench → Recommendations → Replay → Paper Orders</p>
      <SignIn />
    </main>
  );
}
