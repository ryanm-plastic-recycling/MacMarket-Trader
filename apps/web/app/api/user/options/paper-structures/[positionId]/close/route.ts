import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

type RouteContext = {
  params: Promise<{ positionId: string }> | { positionId: string };
};

export async function POST(request: Request, context: RouteContext) {
  const params = await Promise.resolve(context.params);
  const positionId = String(params.positionId ?? "").trim();
  return proxyWorkflowRequest({
    request,
    backendPath: `/user/options/paper-structures/${positionId}/close`,
    bodyText: await request.text(),
  });
}
