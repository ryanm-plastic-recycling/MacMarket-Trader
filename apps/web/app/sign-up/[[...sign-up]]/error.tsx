"use client";

import { useEffect } from "react";

export default function SignUpError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    // Log to browser console so operators can see the real error
    console.error("[sign-up render error]", { digest: error.digest, message: error.message });
  }, [error]);

  return (
    <main className="auth-shell">
      <p style={{ fontWeight: 600 }}>Something went wrong loading the sign-up page.</p>
      {error.digest && (
        <p style={{ fontFamily: "monospace", fontSize: "0.8rem", color: "var(--op-muted, #7a8999)" }}>
          Error code: {error.digest}
        </p>
      )}
      <div style={{ display: "flex", gap: 12, marginTop: 12 }}>
        <button onClick={reset}>Try again</button>
        <a href="/sign-in">Go to sign in</a>
      </div>
    </main>
  );
}
