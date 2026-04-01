import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { backendUrl } from "@/lib/backend";
import { ConsoleShell } from "@/components/console-shell";
import type { UserProfile } from "@/lib/user-profile";

async function loadProfile(token: string): Promise<UserProfile> {
  const response = await fetch(backendUrl("/user/me"), {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load profile: ${response.status}`);
  }
  return (await response.json()) as UserProfile;
}

export default async function ConsoleLayout({ children }: { children: React.ReactNode }) {
  const { userId, getToken } = await auth();
  if (!userId) {
    redirect("/sign-in");
  }

  const token = await getToken();
  if (!token) {
    redirect("/sign-in");
  }

  const profile = await loadProfile(token);
  if (profile.approval_status === "pending") {
    redirect("/pending-approval");
  }
  if (profile.approval_status === "rejected" || profile.approval_status === "suspended") {
    redirect("/access-denied");
  }

  return <ConsoleShell>{children}</ConsoleShell>;
}
