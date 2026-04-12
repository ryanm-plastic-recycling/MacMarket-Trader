import { NextResponse } from "next/server";
import { resolveAuthToken } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

export async function PUT(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = await resolveAuthToken(request);
  if (!token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  const response = await fetch(backendUrl(`/user/watchlists/${id}`), {
    method: "PUT",
    headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" },
    body: await request.text(),
    cache: "no-store",
  });
  return NextResponse.json(await response.json(), { status: response.status });
}

export async function DELETE(request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const token = await resolveAuthToken(request);
  if (!token) return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  const response = await fetch(backendUrl(`/user/watchlists/${id}`), {
    method: "DELETE",
    headers: { Authorization: `Bearer ${token}` },
    cache: "no-store",
  });
  return NextResponse.json(await response.json(), { status: response.status });
}
