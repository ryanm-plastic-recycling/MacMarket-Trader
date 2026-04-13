import { NextResponse } from "next/server";
import { resolveAuthToken } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function GET(request: Request) {
  const token = await resolveAuthToken(request);
  if (!token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  const response = await fetch(backendUrl("/user/onboarding-status"), {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  if (!response.ok) {
    const text = await response.text();
    return NextResponse.json(
      { detail: text || "Backend error" },
      { status: response.status }
    );
  }
  return NextResponse.json(await response.json(), { status: response.status });
}
