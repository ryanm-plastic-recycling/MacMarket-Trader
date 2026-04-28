import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ tradeId: string }> },
) {
  const { tradeId } = await params;
  const bodyText = await request.text();
  return proxyWorkflowRequest({
    request,
    backendPath: `/user/paper-trades/${tradeId}/reopen`,
    bodyText,
  });
}
