import fs from "node:fs";
import path from "node:path";

import { Card, PageHeader } from "@/components/operator-ui";
import { WelcomeClient } from "@/components/welcome-client";

// Server component: reads docs/alpha-user-welcome.md from the repo at build /
// request time and hands the raw markdown to a client component for rendering.
// Resolves relative to process.cwd() (= apps/web/ during next dev / next build),
// going up two levels to the repo root.
function readWelcomeMarkdown(): { markdown: string; error: string | null } {
  const candidates = [
    path.resolve(process.cwd(), "..", "..", "docs", "alpha-user-welcome.md"),
    path.resolve(process.cwd(), "docs", "alpha-user-welcome.md"),
  ];
  for (const candidate of candidates) {
    try {
      const markdown = fs.readFileSync(candidate, "utf8");
      return { markdown, error: null };
    } catch {
      continue;
    }
  }
  return {
    markdown: "",
    error: `Welcome guide not found. Expected docs/alpha-user-welcome.md at one of: ${candidates.join(", ")}`,
  };
}

export default function WelcomePage() {
  const { markdown, error } = readWelcomeMarkdown();
  return (
    <section className="op-stack">
      <PageHeader
        title="Welcome guide"
        subtitle="Five-minute orientation for the MacMarket-Trader private alpha. Read this before your first workflow."
      />
      {error ? (
        <Card title="Welcome guide unavailable">
          <div style={{ color: "var(--op-warn, #f2a03f)", fontSize: 13 }}>{error}</div>
        </Card>
      ) : (
        <WelcomeClient markdown={markdown} />
      )}
    </section>
  );
}
