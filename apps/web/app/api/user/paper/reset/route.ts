import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function POST(request: Request) {
  const bodyText = await request.text();
  return proxyWorkflowRequest({
    request,
    backendPath: "/user/paper/reset",
    method: "POST",
    bodyText,
  });
}
