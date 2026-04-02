import { NextResponse } from "next/server";

import { resolveAuthToken } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function POST(request: Request) {
  const token = await resolveAuthToken(request);
  if (!token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });

  const response = await fetch(backendUrl("/user/recommendations/generate"), {
    method: "POST",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
