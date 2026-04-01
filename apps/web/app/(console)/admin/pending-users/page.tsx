import { auth } from "@clerk/nextjs/server";
import { redirect } from "next/navigation";

import { PendingUsersPanel } from "@/components/admin/pending-users-panel";
import { backendUrl } from "@/lib/backend";
import type { UserProfile } from "@/lib/user-profile";

export default async function Page() {
  const { userId, getToken } = await auth();
  if (!userId) redirect("/sign-in");
  const token = await getToken();
  if (!token) redirect("/sign-in");

  const response = await fetch(backendUrl("/user/me"), {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) redirect("/access-denied");
  const profile = (await response.json()) as UserProfile;
  if (profile.app_role !== "admin") redirect("/access-denied");

  return <PendingUsersPanel />;
}
