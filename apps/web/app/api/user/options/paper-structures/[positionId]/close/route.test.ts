import { describe, expect, it, vi } from "vitest";

const proxyWorkflowRequestMock = vi.fn();

vi.mock("@/app/api/_utils/workflow-proxy", () => ({
  proxyWorkflowRequest: proxyWorkflowRequestMock,
}));

describe("/api/user/options/paper-structures/[positionId]/close route", () => {
  it("proxies close payloads to the protected workflow helper", async () => {
    proxyWorkflowRequestMock.mockResolvedValue(new Response(null, { status: 200 }));
    const { POST } = await import("@/app/api/user/options/paper-structures/[positionId]/close/route");

    await POST(
      new Request("http://localhost/api/user/options/paper-structures/42/close", {
        method: "POST",
        body: JSON.stringify({ settlement_mode: "manual_close" }),
      }),
      { params: Promise.resolve({ positionId: "42" }) },
    );

    expect(proxyWorkflowRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        backendPath: "/user/options/paper-structures/42/close",
        bodyText: JSON.stringify({ settlement_mode: "manual_close" }),
      }),
    );
  });

  it("passes through blocked close responses safely", async () => {
    proxyWorkflowRequestMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "option_position_not_open" }), {
        status: 409,
        headers: { "content-type": "application/json" },
      }),
    );
    const { POST } = await import("@/app/api/user/options/paper-structures/[positionId]/close/route");

    const response = await POST(
      new Request("http://localhost/api/user/options/paper-structures/42/close", {
        method: "POST",
        body: JSON.stringify({ settlement_mode: "manual_close" }),
      }),
      { params: Promise.resolve({ positionId: "42" }) },
    );

    expect(response.status).toBe(409);
    await expect(response.json()).resolves.toEqual({ detail: "option_position_not_open" });
  });
});
