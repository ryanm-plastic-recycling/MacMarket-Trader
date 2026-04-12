import { NextResponse } from "next/server";
import { resolveAuthToken } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function GET(request: Request, { params }: { params: Promise<{ scheduleId: string; runId: string }> }) {
  const token = await resolveAuthToken(request);
  if (!token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  const { scheduleId, runId } = await params;
  const response = await fetch(backendUrl(`/user/strategy-schedules/${scheduleId}/runs/${runId}`), { headers: { Authorization: `Bearer ${token}` }, cache: "no-store" });
  return NextResponse.json(await response.json(), { status: response.status });
}
