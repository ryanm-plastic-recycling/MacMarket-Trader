import { NextResponse } from "next/server";

import { resolveAuthTokenState } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function GET(request: Request) {
  const resolved = await resolveAuthTokenState(request);
  if (!resolved.token && resolved.authPending) return NextResponse.json({ detail: "Authentication initializing" }, { status: 425 });
  if (!resolved.token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });

  const response = await fetch(backendUrl("/user/dashboard"), { headers: { Authorization: `Bearer ${resolved.token}` }, cache: "no-store" });
  return NextResponse.json(await response.json(), { status: response.status });
}
