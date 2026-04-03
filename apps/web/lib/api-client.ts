export type NormalizedApiResult<T> = {
  ok: boolean;
  status: number;
  data: T | null;
  items: T[];
  error: string | null;
  raw: unknown;
  authPending?: boolean;
};

type TokenProvider = (() => Promise<string | null>) | undefined;
type AuthMode = "session" | "token";

function coerceMessage(payload: unknown, fallback: string): string {
  if (typeof payload === "string") return payload;
  if (payload && typeof payload === "object") {
    const detail = (payload as Record<string, unknown>).detail;
    if (typeof detail === "string" && detail.trim()) return detail;
    const message = (payload as Record<string, unknown>).message;
    if (typeof message === "string" && message.trim()) return message;
    const error = (payload as Record<string, unknown>).error;
    if (typeof error === "string" && error.trim()) return error;
  }
  return fallback;
}

async function parsePayload(response: Response): Promise<unknown> {
  if (response.status === 204) {
    return null;
  }

  const text = await response.text();
  if (!text.trim()) {
    return null;
  }

  const contentType = response.headers.get("content-type")?.toLowerCase() ?? "";
  if (contentType.includes("application/json")) {
    try {
      return JSON.parse(text);
    } catch {
      return { detail: text };
    }
  }

  try {
    return JSON.parse(text);
  } catch {
    return { detail: text };
  }
}

export async function fetchNormalized<T>(input: RequestInfo | URL, init?: RequestInit, retryCount = 0): Promise<NormalizedApiResult<T>> {
  const response = await fetch(input, { cache: "no-store", credentials: "include", ...init });
  const payload = await parsePayload(response);

  const body = payload as Record<string, unknown> | null;
  const dataCandidate = Array.isArray(payload)
    ? null
    : body && body.data !== undefined
      ? (body.data as T)
      : (payload as T);

  const items = Array.isArray(payload)
    ? (payload as T[])
    : Array.isArray(body?.items)
      ? (body?.items as T[])
      : Array.isArray(body?.results)
        ? (body?.results as T[])
        : dataCandidate
          ? [dataCandidate]
          : [];

  if (!response.ok) {
    const message = coerceMessage(payload, `Request failed (${response.status})`);
    if ((response.status === 425 || response.status === 503) && /auth/i.test(message)) {
      return {
        ok: false,
        status: response.status,
        data: null,
        items: [],
        error: "AUTH_NOT_READY",
        raw: payload,
        authPending: true,
      };
    }
    if (response.status === 401 && retryCount < 1) {
      await new Promise((resolve) => setTimeout(resolve, 150));
      return fetchNormalized<T>(input, { ...init, headers: init?.headers }, retryCount + 1);
    }
    return {
      ok: false,
      status: response.status,
      data: null,
      items: [],
      error: message,
      raw: payload,
    };
  }

  return {
    ok: true,
    status: response.status,
    data: dataCandidate,
    items,
    error: null,
    raw: payload,
  };
}

export async function fetchNormalizedAuthed<T>(
  input: RequestInfo | URL,
  init: RequestInit | undefined,
  getToken: TokenProvider,
): Promise<NormalizedApiResult<T>> {
  let token = await getToken?.();
  let retryCount = 0;
  while (!token && retryCount < 2) {
    retryCount += 1;
    await new Promise((resolve) => setTimeout(resolve, 150 * retryCount));
    token = await getToken?.();
  }
  if (!token) {
    return {
      ok: false,
      status: 401,
      data: null,
      items: [],
      error: "AUTH_NOT_READY",
      raw: { detail: "Authentication initializing" },
      authPending: true,
    };
  }
  const headers = new Headers(init?.headers);
  headers.set("Authorization", `Bearer ${token}`);
  return fetchNormalized<T>(
    input,
    { ...init, headers },
  );
}

export async function fetchWorkflowApi<T>(
  input: RequestInfo | URL,
  init?: RequestInit,
  options?: { authMode?: AuthMode; getToken?: TokenProvider },
): Promise<NormalizedApiResult<T>> {
  const authMode = options?.authMode ?? "session";
  if (authMode === "token") {
    return fetchNormalizedAuthed<T>(input, init, options?.getToken);
  }
  return fetchNormalized<T>(input, init);
}
