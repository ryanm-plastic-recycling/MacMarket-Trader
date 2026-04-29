import { describe, expect, it, vi } from "vitest";

const proxyWorkflowRequestMock = vi.fn();

vi.mock("@/app/api/_utils/workflow-proxy", () => ({
  proxyWorkflowRequest: proxyWorkflowRequestMock,
}));

describe("/api/user/options/paper-structures/open route", () => {
  it("proxies open payloads to the protected workflow helper", async () => {
    proxyWorkflowRequestMock.mockResolvedValue(new Response(null, { status: 200 }));
    const { POST } = await import("@/app/api/user/options/paper-structures/open/route");

    await POST(
      new Request("http://localhost/api/user/options/paper-structures/open", {
        method: "POST",
        body: JSON.stringify({ structure_type: "vertical_debit_spread" }),
      }),
    );

    expect(proxyWorkflowRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        backendPath: "/user/options/paper-structures/open",
        bodyText: JSON.stringify({ structure_type: "vertical_debit_spread" }),
      }),
    );
  });

  it("passes through proxy failures without exposing additional data", async () => {
    proxyWorkflowRequestMock.mockResolvedValue(
      new Response(JSON.stringify({ detail: "Authentication required" }), {
        status: 401,
        headers: { "content-type": "application/json" },
      }),
    );
    const { POST } = await import("@/app/api/user/options/paper-structures/open/route");

    const response = await POST(
      new Request("http://localhost/api/user/options/paper-structures/open", {
        method: "POST",
        body: JSON.stringify({ structure_type: "vertical_debit_spread" }),
      }),
    );

    expect(response.status).toBe(401);
    await expect(response.json()).resolves.toEqual({ detail: "Authentication required" });
  });
});
