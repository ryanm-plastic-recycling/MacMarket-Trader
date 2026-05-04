import path from "node:path";

export type SmokeStatus = "passed" | "failed" | "skipped";

export type SmokeEnv = Record<string, string | undefined>;

export interface SmokePageDefinition {
  path: string;
  name: string;
  requiredText?: string[];
  anyText?: string[];
  safetyText?: string[];
}

export interface DeployedSmokeConfig {
  baseUrl: string;
  cloudflareAccessHeaders: Record<string, string>;
  hasCloudflareServiceToken: boolean;
  storageStatePath: string | undefined;
  testUserEmail: string | undefined;
  mutationAllowed: boolean;
  evidenceDir: string;
  screenshotsDir: string;
  shouldSkip: boolean;
  skipReason: string | undefined;
  authSummary: {
    cloudflare_service_token: "configured" | "missing";
    storage_state: "configured" | "missing";
    test_user_email: "configured" | "missing";
  };
}

export interface SmokePageResult {
  name: string;
  path: string;
  url?: string;
  status: SmokeStatus;
  screenshot?: string;
  missingText: string[];
  matchedText: string[];
  consoleErrors: string[];
  failedRequests: Array<{ url: string; failure: string }>;
  notes: string[];
}

export interface DeployedSmokeSummary {
  status: SmokeStatus;
  generated_at: string;
  base_url: string;
  auth: DeployedSmokeConfig["authSummary"];
  mutation_allowed: boolean;
  evidence_dir: string;
  screenshots_dir: string;
  skip_reason?: string;
  pages: SmokePageResult[];
  findings: Array<{ severity: "P0" | "P1" | "P2" | "P3"; title: string; detail: string }>;
}

const DEFAULT_BASE_URL = "https://macmarket.io";

export const DEPLOYED_SMOKE_PAGES: SmokePageDefinition[] = [
  {
    path: "/dashboard",
    name: "Dashboard",
    requiredText: ["Dashboard"],
    anyText: ["Index Context", "SPX", "NDX", "RUT", "VIX"],
  },
  {
    path: "/charts/haco",
    name: "HACO Charts",
    anyText: ["HACO", "AAPL", "Session"],
  },
  {
    path: "/analysis",
    name: "Analysis",
    anyText: ["Analysis", "Strategy Workbench"],
    safetyText: ["Paper", "No broker", "No live"],
  },
  {
    path: "/recommendations",
    name: "Recommendations",
    anyText: ["Recommendations", "Analysis Packet", "Opportunity Intelligence"],
  },
  {
    path: "/orders",
    name: "Orders",
    anyText: ["Orders", "Paper"],
    safetyText: ["No automatic exits", "No broker routing", "Paper"],
  },
  {
    path: "/settings",
    name: "Settings",
    anyText: ["Settings", "Account"],
  },
  {
    path: "/admin/provider-health",
    name: "Provider Health",
    requiredText: ["Provider Health"],
    anyText: ["indices data", "index options data", "market data", "options data"],
    safetyText: ["does not enable live trading", "mock broker", "routing disabled"],
  },
];

export function normalizeBaseUrl(value: string | undefined): string {
  const raw = (value || DEFAULT_BASE_URL).trim();
  return raw.replace(/\/+$/, "") || DEFAULT_BASE_URL;
}

export function mutationAllowed(env: SmokeEnv = process.env): boolean {
  return String(env.SMOKE_ALLOW_MUTATION || "").trim().toLowerCase() === "true";
}

export function buildCloudflareAccessHeaders(env: SmokeEnv = process.env): Record<string, string> {
  const clientId = String(env.CF_ACCESS_CLIENT_ID || "").trim();
  const clientSecret = String(env.CF_ACCESS_CLIENT_SECRET || "").trim();
  if (!clientId || !clientSecret) {
    return {};
  }
  return {
    "CF-Access-Client-Id": clientId,
    "CF-Access-Client-Secret": clientSecret,
  };
}

export function redactSmokeValue(value: string | undefined): string {
  if (!value) {
    return "missing";
  }
  const normalized = value.trim();
  if (!normalized) {
    return "missing";
  }
  if (normalized.length <= 8) {
    return "<redacted>";
  }
  return `${normalized.slice(0, 4)}...${normalized.slice(-4)}`;
}

export function redactedCloudflareAccessHeaders(env: SmokeEnv = process.env): Record<string, string> {
  const headers = buildCloudflareAccessHeaders(env);
  if (!Object.keys(headers).length) {
    return {};
  }
  return Object.fromEntries(Object.entries(headers).map(([key, value]) => [key, redactSmokeValue(value)]));
}

export function smokeAuthSummary(env: SmokeEnv = process.env): DeployedSmokeConfig["authSummary"] {
  return {
    cloudflare_service_token: Object.keys(buildCloudflareAccessHeaders(env)).length ? "configured" : "missing",
    storage_state: String(env.SMOKE_AUTH_STORAGE_STATE || "").trim() ? "configured" : "missing",
    test_user_email: String(env.SMOKE_TEST_USER_EMAIL || "").trim() ? "configured" : "missing",
  };
}

export function repoRootFromCwd(cwd = process.cwd()): string {
  const base = path.basename(cwd).toLowerCase();
  const parent = path.basename(path.dirname(cwd)).toLowerCase();
  if (base === "web" && parent === "apps") {
    return path.resolve(cwd, "..", "..");
  }
  return path.resolve(cwd);
}

function timestampForPath(date: Date): string {
  return date.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

export function resolveSmokeEvidenceDir(
  env: SmokeEnv = process.env,
  options: { cwd?: string; now?: Date } = {},
): string {
  const cwd = options.cwd || process.cwd();
  const evidenceRoot = env.SMOKE_EVIDENCE_DIR?.trim()
    ? path.resolve(cwd, env.SMOKE_EVIDENCE_DIR.trim())
    : path.join(repoRootFromCwd(cwd), ".tmp", "evidence");
  return path.join(evidenceRoot, `deployed-ui-smoke-${timestampForPath(options.now || new Date())}`);
}

export function pathIsUnderEvidence(pathToCheck: string, cwd = process.cwd()): boolean {
  const evidenceRoot = path.join(repoRootFromCwd(cwd), ".tmp", "evidence");
  const relative = path.relative(evidenceRoot, path.resolve(pathToCheck));
  return Boolean(relative) && !relative.startsWith("..") && !path.isAbsolute(relative);
}

export function resolveDeployedSmokeConfig(
  env: SmokeEnv = process.env,
  options: { cwd?: string; now?: Date } = {},
): DeployedSmokeConfig {
  const evidenceDir = resolveSmokeEvidenceDir(env, options);
  const cloudflareAccessHeaders = buildCloudflareAccessHeaders(env);
  const storageStatePath = env.SMOKE_AUTH_STORAGE_STATE?.trim() || undefined;
  const hasCloudflareServiceToken = Object.keys(cloudflareAccessHeaders).length > 0;
  const authSummary = smokeAuthSummary(env);
  const hasSomeAuthPath = hasCloudflareServiceToken || Boolean(storageStatePath);
  return {
    baseUrl: normalizeBaseUrl(env.SMOKE_BASE_URL),
    cloudflareAccessHeaders,
    hasCloudflareServiceToken,
    storageStatePath,
    testUserEmail: env.SMOKE_TEST_USER_EMAIL?.trim() || undefined,
    mutationAllowed: mutationAllowed(env),
    evidenceDir,
    screenshotsDir: path.join(evidenceDir, "screenshots"),
    shouldSkip: !hasSomeAuthPath,
    skipReason: hasSomeAuthPath
      ? undefined
      : "Missing smoke auth. Set CF_ACCESS_CLIENT_ID/CF_ACCESS_CLIENT_SECRET or SMOKE_AUTH_STORAGE_STATE.",
    authSummary,
  };
}

export function detectAuthGate(url: string, bodyText: string): string | null {
  const normalizedUrl = url.toLowerCase();
  const normalizedBody = bodyText.toLowerCase();
  if (normalizedUrl.includes("cloudflareaccess.com") || normalizedBody.includes("cloudflare access")) {
    return "cloudflare_access";
  }
  if (
    normalizedUrl.includes("/sign-in")
    || normalizedUrl.includes("/sign-up")
    || normalizedBody.includes("sign in")
    || normalizedBody.includes("clerk")
  ) {
    return "app_identity";
  }
  return null;
}

export function pageTextMatches(bodyText: string, definition: SmokePageDefinition): { missing: string[]; matched: string[] } {
  const lowerBody = bodyText.toLowerCase();
  const missing: string[] = [];
  const matched: string[] = [];
  for (const expected of definition.requiredText || []) {
    if (lowerBody.includes(expected.toLowerCase())) {
      matched.push(expected);
    } else {
      missing.push(expected);
    }
  }
  const anyText = definition.anyText || [];
  if (anyText.length) {
    const anyMatched = anyText.filter((item) => lowerBody.includes(item.toLowerCase()));
    if (anyMatched.length) {
      matched.push(...anyMatched);
    } else {
      missing.push(`one of: ${anyText.join(", ")}`);
    }
  }
  return { missing, matched };
}

export function summaryMarkdown(summary: DeployedSmokeSummary): string {
  const lines = [
    `# Deployed UI Smoke - ${summary.status}`,
    "",
    `- Generated: ${summary.generated_at}`,
    `- Base URL: ${summary.base_url}`,
    `- Cloudflare service token: ${summary.auth.cloudflare_service_token}`,
    `- Storage state: ${summary.auth.storage_state}`,
    `- Mutation allowed: ${summary.mutation_allowed ? "true" : "false"}`,
    `- Evidence directory: ${summary.evidence_dir}`,
  ];
  if (summary.skip_reason) {
    lines.push(`- Skip reason: ${summary.skip_reason}`);
  }
  lines.push("", "## Pages");
  for (const page of summary.pages) {
    lines.push(`- ${page.name} (${page.path}): ${page.status}`);
    if (page.missingText.length) {
      lines.push(`  - Missing markers: ${page.missingText.join("; ")}`);
    }
    if (page.screenshot) {
      lines.push(`  - Screenshot: ${page.screenshot}`);
    }
  }
  lines.push("", "## Findings");
  if (!summary.findings.length) {
    lines.push("- None");
  } else {
    for (const finding of summary.findings) {
      lines.push(`- ${finding.severity}: ${finding.title} - ${finding.detail}`);
    }
  }
  return `${lines.join("\n")}\n`;
}
