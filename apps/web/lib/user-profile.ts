export type ApprovalStatus = "pending" | "approved" | "rejected" | "suspended";

export type UserProfile = {
  id: number;
  email: string;
  display_name: string;
  approval_status: ApprovalStatus;
  app_role: "user" | "admin" | "analyst";
  mfa_enabled: boolean;
};

export async function getUserProfileFromProxy(): Promise<UserProfile> {
  const response = await fetch("/api/user/me", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Failed to load user profile: ${response.status}`);
  }
  return (await response.json()) as UserProfile;
}
