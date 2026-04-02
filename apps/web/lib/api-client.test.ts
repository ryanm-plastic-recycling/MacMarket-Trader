import { describe, expect, it, vi } from "vitest";

import { fetchNormalizedAuthed } from "@/lib/api-client";

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
