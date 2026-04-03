import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function GET(
  request: Request,
  { params }: { params: Promise<{ symbol: string }> },
) {
  const { symbol } = await params;
  return proxyWorkflowRequest({ request, backendPath: `/user/analyze/${symbol}` });
}
