import { describe, expect, it } from "vitest";

import { backendUrl } from "@/lib/backend";

describe("backendUrl", () => {
  it("builds URL against default backend origin", () => {
    expect(backendUrl("/health")).toBe("http://127.0.0.1:9510/health");
  });
});
