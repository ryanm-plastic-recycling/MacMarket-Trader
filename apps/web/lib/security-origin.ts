const DEFAULT_ALLOWED_ORIGINS = [
  "https://macmarket.io",
  "https://www.macmarket.io",
  "http://localhost:3000",
  "http://127.0.0.1:3000",
  "http://localhost:9500",
  "http://127.0.0.1:9500",
];

const MUTATING_METHODS = new Set(["POST", "PUT", "PATCH", "DELETE"]);

function normalizeOrigin(value: string | null | undefined): string | null {
  if (!value) return null;
  try {
    const parsed = new URL(value);
    if (!["http:", "https:"].includes(parsed.protocol)) return null;
    return `${parsed.protocol}//${parsed.host}`.toLowerCase();
  } catch {
    return null;
  }
}

export function allowedMutationOrigins(): Set<string> {
  const origins = new Set(DEFAULT_ALLOWED_ORIGINS);
  for (const raw of [
    process.env.NEXT_PUBLIC_APP_BASE_URL,
    process.env.NEXT_PUBLIC_ALLOWED_ORIGINS,
    process.env.SECURITY_ALLOWED_ORIGINS,
  ]) {
    if (!raw) continue;
    for (const item of raw.split(",")) {
      const origin = normalizeOrigin(item.trim());
      if (origin) origins.add(origin);
    }
  }
  return origins;
}

export function mutationOriginAllowed({
  method,
  requestUrl,
  origin,
  referer,
}: {
  method: string;
  requestUrl: string;
  origin?: string | null;
  referer?: string | null;
}): boolean {
  if (!MUTATING_METHODS.has(method.toUpperCase())) return true;
  const requestOrigin = normalizeOrigin(origin) ?? normalizeOrigin(referer);
  if (!requestOrigin) return true;
  const sameOrigin = normalizeOrigin(requestUrl);
  return requestOrigin === sameOrigin || allowedMutationOrigins().has(requestOrigin);
}
