import { NextResponse } from "next/server";

import { resolveAuthToken } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function POST(
  request: Request,
  context: { params: Promise<{ userId: string }> }
) {
  const { userId } = await context.params;

  const token = await resolveAuthToken(request);
  if (!token) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  const response = await fetch(backendUrl(`/admin/users/${userId}/suspend`), {
    method: "POST",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });

  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
