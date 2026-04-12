import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ recommendationId: string }> },
) {
  const { recommendationId } = await params;
  const bodyText = await request.text();
  return proxyWorkflowRequest({
    request,
    backendPath: `/user/recommendations/${recommendationId}/approve`,
    method: "PATCH",
    bodyText,
  });
}
