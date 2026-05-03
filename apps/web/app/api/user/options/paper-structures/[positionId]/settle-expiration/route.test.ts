import { describe, expect, it, vi } from "vitest";

const proxyWorkflowRequestMock = vi.fn();

vi.mock("@/app/api/_utils/workflow-proxy", () => ({
  proxyWorkflowRequest: proxyWorkflowRequestMock,
}));

describe("/api/user/options/paper-structures/[positionId]/settle-expiration route", () => {
  it("proxies manual paper expiration settlement payloads to the workflow helper", async () => {
    proxyWorkflowRequestMock.mockResolvedValue(new Response(null, { status: 200 }));
    const { POST } = await import("@/app/api/user/options/paper-structures/[positionId]/settle-expiration/route");

    await POST(
      new Request("http://localhost/api/user/options/paper-structures/42/settle-expiration", {
        method: "POST",
        body: JSON.stringify({ confirmation: "SETTLE", underlying_settlement_price: 100 }),
      }),
      { params: Promise.resolve({ positionId: "42" }) },
    );

    expect(proxyWorkflowRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        backendPath: "/user/options/paper-structures/42/settle-expiration",
        bodyText: JSON.stringify({ confirmation: "SETTLE", underlying_settlement_price: 100 }),
      }),
    );
  });
});
