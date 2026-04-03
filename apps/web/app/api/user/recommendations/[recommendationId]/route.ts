import { NextResponse } from "next/server";

import { resolveAuthTokenState } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function GET(
  request: Request,
  context: { params: Promise<{ recommendationId: string }> }
) {
  const { recommendationId } = await context.params;

  const resolved = await resolveAuthTokenState(request);
  if (!resolved.token && resolved.authPending) {
    return NextResponse.json({ detail: "Authentication initializing" }, { status: 425 });
  }
  if (!resolved.token) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  const response = await fetch(
    backendUrl(`/user/recommendations/${recommendationId}`),
    {
      method: "GET",
      headers: {
        Authorization: `Bearer ${resolved.token}`,
      },
      cache: "no-store",
    }
  );

  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
