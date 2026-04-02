import { auth } from "@clerk/nextjs/server";

export async function resolveAuthToken(request: Request): Promise<string | null> {
  const directToken = request.headers.get("authorization");
  if (directToken?.toLowerCase().startsWith("bearer ")) {
    return directToken.replace(/^bearer\s+/i, "").trim();
  }

  const { userId, getToken } = await auth();
  if (!userId) return null;
  return getToken();
}
