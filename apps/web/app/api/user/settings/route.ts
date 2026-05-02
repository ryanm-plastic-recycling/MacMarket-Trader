import { proxyWorkflowRequest } from "@/app/api/_utils/workflow-proxy";

export async function GET(request: Request) {
  return proxyWorkflowRequest({
    request,
    backendPath: "/user/settings",
  });
}

export async function PATCH(request: Request) {
  const bodyText = await request.text();
  return proxyWorkflowRequest({
    request,
    backendPath: "/user/settings",
    method: "PATCH",
    bodyText,
  });
}

export async function POST(request: Request) {
  const bodyText = await request.text();
  return proxyWorkflowRequest({
    request,
    backendPath: "/user/settings",
    method: "POST",
    bodyText,
  });
}
