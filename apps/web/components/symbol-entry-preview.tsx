import React from "react";

import type { ParsedManualSymbols } from "@/lib/symbol-entry";
import { formatParsedSymbolCount, formatParsedSymbols } from "@/lib/symbol-entry";

type SymbolEntryPreviewProps = {
  parsed: ParsedManualSymbols;
};

export function SymbolEntryPreview({ parsed }: SymbolEntryPreviewProps) {
  return (
    <div
      data-testid="symbol-entry-preview"
      style={{ marginTop: 6, color: "var(--op-muted, #7a8999)", fontSize: "0.82rem", lineHeight: 1.45 }}
    >
      <div><strong>Parsed symbols:</strong> {formatParsedSymbols(parsed)}</div>
      <div>{formatParsedSymbolCount(parsed)}</div>
      <div>Blank separators ignored.</div>
      {parsed.duplicateCount ? (
        <div>Duplicate ignored: {parsed.duplicates.join(", ")}</div>
      ) : null}
    </div>
  );
}
