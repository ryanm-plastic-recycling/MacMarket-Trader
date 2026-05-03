import { describe, expect, it } from "vitest";

import { mutationOriginAllowed } from "@/lib/security-origin";

describe("mutationOriginAllowed", () => {
  it("allows non-mutating requests and same-origin mutations", () => {
    expect(
      mutationOriginAllowed({
        method: "GET",
        requestUrl: "https://macmarket.io/api/user/orders",
        origin: "https://evil.example",
      }),
    ).toBe(true);
    expect(
      mutationOriginAllowed({
        method: "POST",
        requestUrl: "https://macmarket.io/api/user/orders",
        origin: "https://macmarket.io",
      }),
    ).toBe(true);
  });

  it("allows localhost development origins", () => {
    expect(
      mutationOriginAllowed({
        method: "POST",
        requestUrl: "http://localhost:3000/api/user/orders",
        origin: "http://localhost:9500",
      }),
    ).toBe(true);
  });

  it("rejects unexpected browser mutation origins", () => {
    expect(
      mutationOriginAllowed({
        method: "DELETE",
        requestUrl: "https://macmarket.io/api/user/orders/abc",
        origin: "https://evil.example",
      }),
    ).toBe(false);
  });
});
