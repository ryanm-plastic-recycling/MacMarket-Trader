export const dynamic = "force-dynamic";

import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { backendUrl } from "@/lib/backend";
import { ConsoleShell } from "@/components/console-shell";
import { isE2EAuthBypassEnabled } from "@/lib/e2e-auth";
import type { UserProfile } from "@/lib/user-profile";

async function loadProfile(token: string): Promise<UserProfile | null> {
  // Returns null on any non-OK response or network/parse failure. The caller
  // treats null as "profile unknown" and redirects to /pending-approval, which
  // is the safe landing page for new users whose backend account is still
  // being provisioned or whose Clerk session is not yet trusted by the
  // backend. Throwing here previously produced an unhandled 500 with digest
  // 3582682868 in the Server Component render path.
  try {
    const response = await fetch(backendUrl("/user/me"), {
      headers: { Authorization: `Bearer ${token}` },
      cache: "no-store",
    });
    if (!response.ok) return null;
    return (await response.json()) as UserProfile;
  } catch {
    return null;
  }
}

export default async function ConsoleLayout({ children }: { children: React.ReactNode }) {
  // Skip auth checks in E2E test runs — bypass flag set by playwright.config.ts
  if (isE2EAuthBypassEnabled()) {
    return <ConsoleShell>{children}</ConsoleShell>;
  }

  const { userId, getToken } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }

  const token = await getToken();
  if (!token) {
    redirect("/sign-in");
  }

  const profile = await loadProfile(token);
  if (profile === null) {
    // 401 / 403 / network error — treat as "not yet approved" rather than
    // crashing the route. The /pending-approval page surfaces the correct
    // operator-facing copy and a path forward.
    redirect("/pending-approval");
  }
  if (profile.approval_status === "pending") {
    redirect("/pending-approval");
  }
  if (profile.approval_status === "rejected" || profile.approval_status === "suspended") {
    redirect("/access-denied");
  }

  return <ConsoleShell>{children}</ConsoleShell>;
}
