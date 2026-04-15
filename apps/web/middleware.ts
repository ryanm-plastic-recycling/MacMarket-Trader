import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

const isPublicRoute = createRouteMatcher(["/sign-in(.*)", "/sign-up(.*)", "/pending-approval", "/access-denied"]);

export default clerkMiddleware(async (auth, req) => {
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
