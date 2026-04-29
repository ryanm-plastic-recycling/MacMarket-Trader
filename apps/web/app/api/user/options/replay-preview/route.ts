import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function POST(request: Request) {
  return proxyWorkflowRequest({
    request,
    backendPath: "/user/options/replay-preview",
    bodyText: await request.text(),
  });
}
