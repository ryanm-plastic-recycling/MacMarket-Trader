import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function GET(request: Request) {
  return proxyWorkflowRequest({ request, backendPath: "/user/orders" });
}

export async function POST(request: Request) {
  return proxyWorkflowRequest({
    request,
    backendPath: "/user/orders",
    bodyText: await request.text(),
  });
}
