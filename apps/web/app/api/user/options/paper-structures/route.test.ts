import { describe, expect, it, vi } from "vitest";

const proxyWorkflowRequestMock = vi.fn();

vi.mock("@/app/api/_utils/workflow-proxy", () => ({
  proxyWorkflowRequest: proxyWorkflowRequestMock,
}));

describe("/api/user/options/paper-structures route", () => {
  it("proxies list requests to the protected workflow helper", async () => {
    proxyWorkflowRequestMock.mockResolvedValue(new Response(null, { status: 200 }));
    const { GET } = await import("@/app/api/user/options/paper-structures/route");

    await GET(
      new Request("http://localhost/api/user/options/paper-structures", {
        method: "GET",
      }),
    );

    expect(proxyWorkflowRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        backendPath: "/user/options/paper-structures",
      }),
    );
  });

  it("passes through protected-route failures safely", async () => {
    proxyWorkflowRequestMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    );
    const { GET } = await import("@/app/api/user/options/paper-structures/route");

    const response = await GET(
      new Request("http://localhost/api/user/options/paper-structures", {
        method: "GET",
      }),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ detail: "Authentication required" });
  });
});
