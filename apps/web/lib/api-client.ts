export type NormalizedApiResult<T> = {
  ok: boolean;
  status: number;
  data: T | null;
  items: T[];
  error: string | null;
  raw: unknown;
};

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

export async function fetchNormalized<T>(input: RequestInfo | URL, init?: RequestInit): Promise<NormalizedApiResult<T>> {
  const response = await fetch(input, { cache: "no-store", ...init });
  let payload: unknown = null;
  try {
    payload = await response.json();
  } catch {
    payload = null;
  }

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
    return {
      ok: false,
      status: response.status,
      data: null,
      items: [],
      error: coerceMessage(payload, `Request failed (${response.status})`),
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
