import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function GET(
  request: Request,
  context: { params: Promise<{ recommendationId: string }> },
) {
  const { recommendationId } = await context.params;
  return proxyWorkflowRequest({ request, backendPath: `/user/recommendations/${recommendationId}` });
}
