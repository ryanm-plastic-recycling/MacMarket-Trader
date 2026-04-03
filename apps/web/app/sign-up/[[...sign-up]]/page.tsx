import { SignUp } from "@clerk/nextjs";

import { BrandLockup } from "@/components/brand-lockup";

export default function Page() {
  return (
    <main className="auth-shell">
      <BrandLockup />
      <p>Private alpha onboarding · invite-first operator access</p>
      <SignUp />
    </main>
  );
}
