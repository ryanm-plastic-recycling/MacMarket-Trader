import { NextResponse } from "next/server";
import { resolveAuthToken } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function PUT(request: Request, { params }: { params: Promise<{ scheduleId: string }> }) {
  const token = await resolveAuthToken(request);
  if (!token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  const { scheduleId } = await params;
  const response = await fetch(backendUrl(`/user/strategy-schedules/${scheduleId}`), { method: 'PUT', headers: { Authorization: `Bearer ${token}`, 'Content-Type': 'application/json' }, body: await request.text(), cache: 'no-store' });
  return NextResponse.json(await response.json(), { status: response.status });
}
