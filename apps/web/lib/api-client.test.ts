import { describe, expect, it, vi } from "vitest";

import { fetchNormalized, fetchNormalizedAuthed, fetchWorkflowApi } from "@/lib/api-client";

describe("fetchNormalizedAuthed", () => {
  it("returns authPending without issuing request when token unavailable", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch");
    const result = await fetchNormalizedAuthed("/api/user/orders", undefined, async () => null);
    expect(result.ok).toBe(false);
    expect(result.authPending).toBe(true);
    expect(result.error).toBe("AUTH_NOT_READY");
    expect(fetchSpy).not.toHaveBeenCalled();
    fetchSpy.mockRestore();
  });
});

describe("fetchNormalized", () => {
  it("normalizes successful payloads and extracts items", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ items: [{ id: 1 }] }), { status: 200 }),
    );
    const result = await fetchNormalized<{ id: number }>("/api/user/recommendations");
    expect(result.ok).toBe(true);
    expect(result.items).toHaveLength(1);
    expect(result.error).toBeNull();
    fetchSpy.mockRestore();
  });
});

describe("fetchWorkflowApi", () => {
  it("uses session auth by default for same-origin workflow routes", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([{ id: "abc" }]), { status: 200 }),
    );
    const result = await fetchWorkflowApi<{ id: string }>("/api/user/orders");
    expect(result.ok).toBe(true);
    expect(result.items[0]?.id).toBe("abc");
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    fetchSpy.mockRestore();
  });

  it("supports token mode when explicitly requested", async () => {
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ data: { id: 4 } }), { status: 200 }),
    );
    const result = await fetchWorkflowApi<{ id: number }>(
      "/api/user/replay-runs",
      undefined,
      { authMode: "token", getToken: async () => "test-token" },
    );
    expect(result.ok).toBe(true);
    expect(result.data?.id).toBe(4);
    fetchSpy.mockRestore();
  });
});
