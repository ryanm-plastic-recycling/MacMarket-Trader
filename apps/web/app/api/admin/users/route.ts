import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/backend";

export async function GET() {
  const { userId, getToken } = await auth();
  if (!userId) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ detail: "Unable to obtain Clerk token" }, { status: 401 });
  }

  const response = await fetch(backendUrl("/admin/users"), {
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
