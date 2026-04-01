export function backendOrigin(): string {
  return process.env.BACKEND_API_ORIGIN ?? "http://127.0.0.1:9510";
}

export function backendUrl(path: string): string {
  const base = backendOrigin().replace(/\/$/, "");
  return `${base}${path.startsWith("/") ? path : `/${path}`}`;
}
