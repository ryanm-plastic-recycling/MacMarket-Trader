import { describe, expect, it } from "vitest";

import nextConfig from "./next.config";

describe("next security headers", () => {
  it("sets centralized browser security headers", async () => {
    expect(nextConfig.headers).toBeTypeOf("function");
    const entries = await nextConfig.headers!();
    const headers = Object.fromEntries(entries[0].headers.map((item) => [item.key, item.value]));

    expect(headers["X-Content-Type-Options"]).toBe("nosniff");
    expect(headers["X-Frame-Options"]).toBe("DENY");
    expect(headers["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
    expect(headers["Permissions-Policy"]).toContain("camera=()");
    expect(headers["Content-Security-Policy-Report-Only"]).toContain("frame-ancestors 'none'");
    expect(headers["Content-Security-Policy-Report-Only"]).toContain("https://*.clerk.com");
  });
});
