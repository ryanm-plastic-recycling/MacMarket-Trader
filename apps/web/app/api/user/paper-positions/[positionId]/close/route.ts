import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ positionId: string }> },
) {
  const { positionId } = await params;
  const bodyText = await request.text();
  return proxyWorkflowRequest({
    request,
    backendPath: `/user/paper-positions/${positionId}/close`,
    bodyText,
  });
}
