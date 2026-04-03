import { auth } from "@clerk/nextjs/server";

export type ResolvedAuthToken = {
  token: string | null;
  authPending: boolean;
};

const TOKEN_RETRY_MS = [80, 180, 320];

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

export async function resolveAuthTokenState(request: Request): Promise<ResolvedAuthToken> {
  const { userId, getToken } = await auth();
  if (userId) {
    for (let idx = 0; idx < TOKEN_RETRY_MS.length; idx += 1) {
      const sessionToken = await getToken();
      if (sessionToken) {
        return { token: sessionToken, authPending: false };
      }
      if (idx < TOKEN_RETRY_MS.length - 1) {
        await sleep(TOKEN_RETRY_MS[idx]);
      }
    }
    return { token: null, authPending: true };
  }

  const directToken = request.headers.get("authorization");
  if (directToken?.toLowerCase().startsWith("bearer ")) {
    return {
      token: directToken.replace(/^bearer\s+/i, "").trim(),
      authPending: false,
    };
  }
  return { token: null, authPending: false };
}

export async function resolveAuthToken(request: Request): Promise<string | null> {
  const resolved = await resolveAuthTokenState(request);
  return resolved.token;
}
