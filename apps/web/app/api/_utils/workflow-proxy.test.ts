import { beforeEach, describe, expect, it, vi } from "vitest";

const resolveAuthTokenStateMock = vi.fn();

vi.mock("@/app/api/_utils/auth-token", () => ({
  resolveAuthTokenState: resolveAuthTokenStateMock,
}));

describe("proxyWorkflowRequest", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("returns auth-initializing status during Clerk token churn", async () => {
    resolveAuthTokenStateMock.mockResolvedValue({ token: null, authPending: true });
    const { proxyWorkflowRequest } = await import("@/app/api/_utils/workflow-proxy");

    const response = await proxyWorkflowRequest({ request: new Request("http://localhost/api/user/recommendations"), backendPath: "/user/recommendations" });
    expect(response.status).toBe(425);
    await expect(response.json()).resolves.toEqual({ detail: "Authentication initializing" });
  });

  it("preserves upstream status/body for protected same-origin routes", async () => {
    resolveAuthTokenStateMock.mockResolvedValue({ token: "session-token", authPending: false });
    const fetchSpy = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ detail: "Configured provider unavailable" }), { status: 503, headers: { "content-type": "application/json" } }),
    );
    const { proxyWorkflowRequest } = await import("@/app/api/_utils/workflow-proxy");

    const response = await proxyWorkflowRequest({ request: new Request("http://localhost/api/user/orders"), backendPath: "/user/orders" });
    expect(fetchSpy).toHaveBeenCalledTimes(1);
    expect(response.status).toBe(503);
    await expect(response.json()).resolves.toEqual({ detail: "Configured provider unavailable" });
    fetchSpy.mockRestore();
  });
});
