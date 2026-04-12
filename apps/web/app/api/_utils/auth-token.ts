import { auth } from "@clerk/nextjs/server";

export type ResolvedAuthToken = {
  token: string | null;
  authPending: boolean;
};

const TOKEN_RETRY_MS = [80, 180, 320];

async function sleep(ms: number): Promise<void> {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

/**
 * Decodes the `exp` claim from a JWT payload without verifying the signature.
 * Used only for pre-flight expiry monitoring — the backend performs full verification.
 */
function getTokenExpiry(token: string): number | null {
  try {
    const parts = token.split(".");
    if (parts.length !== 3) return null;
    const payload = JSON.parse(Buffer.from(parts[1], "base64url").toString("utf8")) as Record<string, unknown>;
    return typeof payload.exp === "number" ? payload.exp : null;
  } catch {
    return null;
  }
}

export async function resolveAuthTokenState(request: Request): Promise<ResolvedAuthToken> {
  const { userId, getToken } = await auth();
  if (userId) {
    for (let idx = 0; idx < TOKEN_RETRY_MS.length; idx += 1) {
      const sessionToken = await getToken();
      if (sessionToken) {
        // Pre-flight expiry check: if the token is within 30s of its exp claim, log a
        // warning so transit-expiry events are visible in server logs. The backend's
        // 30s leeway absorbs the remaining transit time — we still forward the token.
        const exp = getTokenExpiry(sessionToken);
        if (exp !== null) {
          const secondsRemaining = exp - Math.floor(Date.now() / 1000);
          if (secondsRemaining < 30) {
            console.warn(`[auth-token] Forwarding token with ${secondsRemaining}s until expiry. Backend leeway will compensate for transit latency.`);
          }
        }
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
