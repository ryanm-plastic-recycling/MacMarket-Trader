import { describe, expect, it, vi } from "vitest";

const proxyWorkflowRequestMock = vi.fn();

vi.mock("@/app/api/_utils/workflow-proxy", () => ({
  proxyWorkflowRequest: proxyWorkflowRequestMock,
}));

describe("/api/user/options/paper-structures/review route", () => {
  it("proxies review requests to the protected workflow helper", async () => {
    proxyWorkflowRequestMock.mockResolvedValue(new Response(null, { status: 200 }));
    const { GET } = await import("@/app/api/user/options/paper-structures/review/route");

    await GET(
      new Request("http://localhost/api/user/options/paper-structures/review", {
        method: "GET",
      }),
    );

    expect(proxyWorkflowRequestMock).toHaveBeenCalledWith(
      expect.objectContaining({
        backendPath: "/user/options/paper-structures/review",
      }),
    );
  });
});
