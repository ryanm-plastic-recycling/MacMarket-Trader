import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function PATCH(request: Request) {
  const bodyText = await request.text();
  return proxyWorkflowRequest({
    request,
    backendPath: "/user/settings",
    method: "PATCH",
    bodyText,
  });
}
