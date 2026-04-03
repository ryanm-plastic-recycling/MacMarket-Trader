import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function GET(request: Request) {
  return proxyWorkflowRequest({ request, backendPath: "/user/replay-runs" });
}

export async function POST(request: Request) {
  return proxyWorkflowRequest({
    request,
    backendPath: "/user/replay-runs",
    bodyText: await request.text(),
  });
}
