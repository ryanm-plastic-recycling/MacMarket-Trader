import { NextResponse } from "next/server";

import { resolveAuthTokenState } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function POST(request: Request) {
  const resolved = await resolveAuthTokenState(request);
  if (!resolved.token && resolved.authPending) {
    return NextResponse.json({ detail: "Authentication initializing" }, { status: 425 });
  }
  if (!resolved.token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });

  const response = await fetch(backendUrl("/user/recommendations/generate"), {
    method: "POST",
    headers: { Authorization: `Bearer ${resolved.token}`, "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
