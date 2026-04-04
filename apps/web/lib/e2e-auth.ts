export function isE2EAuthBypassEnabled(): boolean {
  return process.env.NEXT_PUBLIC_E2E_BYPASS_AUTH === "true";
}
