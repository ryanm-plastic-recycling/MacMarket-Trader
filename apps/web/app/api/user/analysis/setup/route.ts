import { NextResponse } from "next/server";
import { resolveAuthToken } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function GET(request: Request) {
  const token = await resolveAuthToken(request);
  if (!token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  const url = new URL(request.url);
  const response = await fetch(backendUrl(`/user/analysis/setup?${url.searchParams.toString()}`), { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
  return NextResponse.json(await response.json(), { status: response.status });
}
