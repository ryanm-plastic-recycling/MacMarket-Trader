import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function POST(
  request: Request,
  { params }: { params: Promise<{ orderId: string }> },
) {
  const { orderId } = await params;
  const bodyText = await request.text();
  return proxyWorkflowRequest({
    request,
    backendPath: `/user/orders/${orderId}/close`,
    bodyText,
  });
}
