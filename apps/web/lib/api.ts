export type ApprovalStatus = "pending" | "approved" | "rejected" | "suspended";

export type UserProfile = {
  id: number;
  email: string;
  display_name: string;
  approval_status: ApprovalStatus;
  app_role: "user" | "admin" | "analyst";
  mfa_enabled: boolean;
};

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:9510";

export async function getUserProfile(token: string): Promise<UserProfile> {
  const response = await fetch(`${API_BASE_URL}/user/me`, {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    throw new Error(`Failed to load user profile: ${response.status}`);
  }
  return (await response.json()) as UserProfile;
}
