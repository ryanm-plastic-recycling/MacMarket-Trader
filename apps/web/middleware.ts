import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";
import { NextResponse } from "next/server";

import { mutationOriginAllowed } from "@/lib/security-origin";

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/pending-approval", "/access-denied"]);

export default clerkMiddleware(async (auth, req) => {
  if (
    req.nextUrl.pathname.startsWith("/api/") &&
    !mutationOriginAllowed({
      method: req.method,
      requestUrl: req.url,
      origin: req.headers.get("origin"),
      referer: req.headers.get("referer"),
    })
  ) {
    return NextResponse.json({ detail: "Request origin is not allowed." }, { status: 403 });
  }

  // Skip auth entirely in E2E test runs — set by playwright.config.ts webServer env
  if (process.env.NEXT_PUBLIC_E2E_BYPASS_AUTH === "true") {
    return;
  }
  if (isPublicRoute(req)) {
    return;
  }
  await auth.protect();
});

export const config = {
  matcher: ["/((?!_next|.*\\..*).*)", "/(api|trpc)(.*)"],
};
