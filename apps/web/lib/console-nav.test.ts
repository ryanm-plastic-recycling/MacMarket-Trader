import { describe, expect, it } from "vitest";

import { isActivePath } from "@/lib/console-nav";

describe("console nav active route", () => {
  it("matches exact route", () => {
    expect(isActivePath("/analysis", "/analysis")).toBe(true);
  });

  it("matches nested route", () => {
    expect(isActivePath("/admin/users/1", "/admin/users")).toBe(true);
  });

  it("does not match unrelated route", () => {
    expect(isActivePath("/orders", "/replay-runs")).toBe(false);
  });
});
