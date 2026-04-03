import { NextResponse } from "next/server";
import { resolveAuthToken } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function POST(request: Request, { params }: { params: Promise<{ scheduleId: string }> }) {
  const token = await resolveAuthToken(request);
  if (!token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  const { scheduleId } = await params;
  const response = await fetch(backendUrl(`/user/strategy-schedules/${scheduleId}/run`), { method: 'POST', headers: { Authorization: `Bearer ${token}` }, cache: 'no-store' });
  return NextResponse.json(await response.json(), { status: response.status });
}
