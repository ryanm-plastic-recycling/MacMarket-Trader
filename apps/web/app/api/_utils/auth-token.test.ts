import { beforeEach, describe, expect, it, vi } from "vitest";

const authMock = vi.fn();

vi.mock("@clerk/nextjs/server", () => ({
  auth: authMock,
}));

describe("resolveAuthTokenState", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("marks authPending when Clerk session exists but token churn never settles", async () => {
    authMock.mockResolvedValue({ userId: "clerk_user", getToken: vi.fn().mockResolvedValue(null) });
    const { resolveAuthTokenState } = await import("@/app/api/_utils/auth-token");

    const result = await resolveAuthTokenState(new Request("http://localhost/api/user/orders"));
    expect(result).toEqual({ token: null, authPending: true });
  });

  it("accepts bearer fallback when no Clerk user session is available", async () => {
    authMock.mockResolvedValue({ userId: null, getToken: vi.fn() });
    const { resolveAuthTokenState } = await import("@/app/api/_utils/auth-token");

    const result = await resolveAuthTokenState(new Request("http://localhost/api/user/orders", { headers: { authorization: "Bearer fallback-token" } }));
    expect(result).toEqual({ token: "fallback-token", authPending: false });
  });
});
