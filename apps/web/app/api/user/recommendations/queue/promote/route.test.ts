import { describe, expect, it, vi } from "vitest";

const proxyWorkflowRequestMock = vi.fn();

vi.mock("@/app/api/_utils/workflow-proxy", () => ({
  proxyWorkflowRequest: proxyWorkflowRequestMock,
}));

describe("/api/user/recommendations/queue/promote route", () => {
  it("proxies promotion payload to same-origin workflow helper", async () => {
    proxyWorkflowRequestMock.mockResolvedValue(new Response(null, { status: 200 }));
    const { POST } = await import("@/app/api/user/recommendations/queue/promote/route");

    await POST(new Request("http://localhost/api/user/recommendations/queue/promote", { method: "POST", body: JSON.stringify({ symbol: "AAPL" }) }));

    expect(proxyWorkflowRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        backendPath: "/user/recommendations/queue/promote",
        bodyText: JSON.stringify({ symbol: "AAPL" }),
      }),
    );
  });
});
