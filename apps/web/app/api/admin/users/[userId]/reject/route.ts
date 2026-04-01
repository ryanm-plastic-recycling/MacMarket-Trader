import { auth } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import { backendUrl } from "@/lib/backend";

export async function POST(request: Request, { params }: { params: { userId: string } }) {
  const { userId, getToken } = await auth();
  if (!userId) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }
  const token = await getToken();
  if (!token) {
    return NextResponse.json({ detail: "Unable to obtain Clerk token" }, { status: 401 });
  }
  const response = await fetch(backendUrl(`/admin/users/${params.userId}/reject`), {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${token}`,
    },
    body: await request.text(),
    cache: "no-store",
  });
  const payload = await response.json();
  return NextResponse.json(payload, { status: response.status });
}
