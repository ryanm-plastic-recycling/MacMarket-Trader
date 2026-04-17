"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[global error]", { digest: error.digest, message: error.message });
  }, [error]);

  return (
    <html lang="en" data-theme="dark">
      <body style={{ fontFamily: "monospace", padding: "2rem", background: "#111820", color: "#c5d0dc" }}>
        <h1 style={{ fontSize: "1.1rem", marginBottom: "0.5rem" }}>Application error</h1>
        {error.digest && (
          <p style={{ fontSize: "0.82rem", color: "#7a8999" }}>Error code: {error.digest}</p>
        )}
        <p style={{ fontSize: "0.82rem", marginTop: "0.5rem" }}>{error.message}</p>
        <button
          style={{ marginTop: "1rem" }}
          onClick={reset}
        >
          Reload
        </button>
      </body>
    </html>
  );
}
