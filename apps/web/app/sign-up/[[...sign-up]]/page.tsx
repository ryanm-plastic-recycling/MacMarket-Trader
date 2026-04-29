import { SignUp } from "@clerk/nextjs";

import { BrandHeader } from "@/components/brand-header";
import { BrandLockup } from "@/components/brand-lockup";

export default function Page() {
  return (
    <>
      <BrandHeader tagline="Request access" />
      <main className="auth-shell">
        <BrandLockup />
        <p>Private alpha onboarding · invite-first operator access</p>
        <SignUp />
      </main>
    </>
  );
}
