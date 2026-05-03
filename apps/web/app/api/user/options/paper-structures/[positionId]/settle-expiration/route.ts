import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

type RouteContext = {
  params: Promise<{ positionId: string }>;
};

export async function POST(request: Request, context: RouteContext) {
  const { positionId } = await context.params;
  return proxyWorkflowRequest({
    request,
    backendPath: `/user/options/paper-structures/${String(positionId ?? "").trim()}/settle-expiration`,
    bodyText: await request.text(),
  });
}
