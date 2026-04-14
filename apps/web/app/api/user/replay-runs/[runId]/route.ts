import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function GET(
  request: Request,
  context: { params: Promise<{ runId: string }> },
) {
  const { runId } = await context.params;
  return proxyWorkflowRequest({ request, backendPath: `/user/replay-runs/${runId}` });
}
