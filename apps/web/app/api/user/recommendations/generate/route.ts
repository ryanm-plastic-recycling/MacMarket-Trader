import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function POST(request: Request) {
  return proxyWorkflowRequest({
    request,
    backendPath: "/user/recommendations/generate",
    bodyText: await request.text(),
  });
}
