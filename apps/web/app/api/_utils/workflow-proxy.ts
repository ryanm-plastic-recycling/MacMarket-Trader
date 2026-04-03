import { NextResponse } from "next/server";

import { resolveAuthTokenState } from "@/app/api/_utils/auth-token";
import { backendUrl } from "@/lib/backend";

type ProxyRequestOptions = {
  request: Request;
  backendPath: string;
  method?: "GET" | "POST" | "PUT" | "PATCH" | "DELETE";
  includeSearchParams?: boolean;
  bodyText?: string;
  authInitializingStatus?: number;
};

function coerceObject(value: unknown): Record<string, unknown> | null {
  return value && typeof value === "object" && !Array.isArray(value)
    ? (value as Record<string, unknown>)
    : null;
}

async function parseUpstreamPayload(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null;
  }

  const text = await response.text();
  if (!text.trim()) {
    return null;
  }

  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (contentType.includes("application/json")) {
    try {
      return JSON.parse(text);
    } catch {
      return { detail: text };
    }
  }

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

export async function proxyWorkflowRequest({
  request,
  backendPath,
  method,
  includeSearchParams = false,
  bodyText,
  authInitializingStatus = 425,
}: ProxyRequestOptions): Promise<NextResponse> {
  const resolved = await resolveAuthTokenState(request);
  if (!resolved.token && resolved.authPending) {
    return NextResponse.json({ detail: "Authentication initializing" }, { status: authInitializingStatus });
  }
  if (!resolved.token) {
    return NextResponse.json({ detail: "Authentication required" }, { status: 401 });
  }

  const sourceUrl = new URL(request.url);
  const targetPath = includeSearchParams && sourceUrl.searchParams.toString()
    ? `${backendPath}?${sourceUrl.searchParams.toString()}`
    : backendPath;

  const headers = new Headers();
  headers.set("Authorization", `Bearer ${resolved.token}`);
  if (bodyText !== undefined) {
    headers.set("Content-Type", request.headers.get("content-type") ?? "application/json");
  }

  const upstream = await fetch(backendUrl(targetPath), {
    method: method ?? request.method,
    headers,
    body: bodyText,
    cache: "no-store",
  });

  const payload = await parseUpstreamPayload(upstream);
  const asObject = coerceObject(payload);
  if (!upstream.ok && !asObject) {
    return NextResponse.json({ detail: `Upstream request failed (${upstream.status})` }, { status: upstream.status });
  }

  return NextResponse.json(payload, { status: upstream.status });
}
