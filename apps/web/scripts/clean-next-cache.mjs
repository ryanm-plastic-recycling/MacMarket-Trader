import { existsSync, rmSync } from "node:fs";
import { resolve } from "node:path";

const nextDir = resolve(process.cwd(), ".next");

if (!existsSync(nextDir)) {
  process.exit(0);
}

try {
  rmSync(nextDir, { recursive: true, force: true });
  console.log("[playwright] cleared stale .next cache before webServer startup");
} catch (error) {
  console.warn("[playwright] warning: unable to clear .next cache", error);
}
