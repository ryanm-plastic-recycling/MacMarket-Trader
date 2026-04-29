import { fetchWorkflowApi, type NormalizedApiResult } from "@/lib/api-client";

export type QueueCandidate = {
  rank: number;
  symbol: string;
  strategy: string;
  strategy_id?: string;
  strategy_status?: string;
  market_mode?: string;
  source?: string;
  workflow_source: string;
  timeframe: string;
  status: string;
  score: number;
  score_breakdown?: Record<string, number>;
  expected_rr: number;
  confidence: number;
  reason_text: string;
  thesis: string;
  trigger?: string;
  entry_zone?: Record<string, unknown>;
  invalidation?: Record<string, unknown>;
  targets?: unknown[];
};

export type StoredRecommendation = {
  id: number;
  created_at: string;
  symbol: string;
  recommendation_id: string;
  // Pass 4 — operator-readable label, e.g. "AAPL-EVCONT-20260429-0830".
  // Backend always populates either the generated value or a "Rec #shortid"
  // fallback for legacy rows; the frontend should prefer this over the raw
  // canonical recommendation_id whenever it is shown to the operator.
  display_id?: string;
  payload: Record<string, unknown>;
  market_data_source?: string;
  fallback_mode?: boolean;
};

export type RecommendationSearchPrefill = {
  symbols: string[];
  recommendationId: string | null;
};

export type OptionsResearchLeg = {
  action?: string | null;
  right?: string | null;
  strike?: number | null;
  premium?: number | null;
  quantity?: number | null;
  multiplier?: number | null;
  label?: string | null;
};

export type OptionsResearchStructure = {
  type?: string | null;
  expiration?: string | null;
  legs?: OptionsResearchLeg[] | null;
  net_credit?: number | null;
  net_debit?: number | null;
  max_profit?: number | null;
  max_loss?: number | null;
  breakeven_low?: number | null;
  breakeven_high?: number | null;
  dte?: number | null;
  iv_snapshot?: number | null;
  theta_context?: number | null;
  vega_context?: number | null;
  event_blockers?: string[] | null;
};

export type OptionsExpectedRange = {
  status: "computed" | "blocked" | "omitted";
  method?: string | null;
  reference_price_type?: string | null;
  absolute_move?: number | null;
  lower_bound?: number | null;
  upper_bound?: number | null;
  horizon_value?: number | null;
  horizon_unit?: string | null;
  snapshot_timestamp?: string | null;
  provenance_notes?: string | null;
  reason?: string | null;
};

export type OptionsChainPreviewRow = {
  strike?: number | null;
  expiry?: string | null;
  last_price?: number | null;
  volume?: number | null;
};

export type OptionsChainPreview = {
  underlying?: string | null;
  expiry?: string | null;
  calls?: OptionsChainPreviewRow[] | null;
  puts?: OptionsChainPreviewRow[] | null;
  data_as_of?: string | null;
  source?: string | null;
  reason?: string | null;
};

export type OptionsResearchSetup = {
  symbol: string;
  market_mode: string;
  timeframe?: string | null;
  workflow_source: string;
  strategy: string;
  operator_disclaimer?: string | null;
  option_structure?: OptionsResearchStructure | null;
  expected_range?: OptionsExpectedRange | null;
  options_chain_preview?: OptionsChainPreview | null;
};

export type OptionsReplayPreviewStructureType =
  | "long_call"
  | "long_put"
  | "vertical_debit_spread"
  | "iron_condor"
  | "custom_defined_risk";

export type OptionsReplayPreviewLegRequest = {
  action?: string | null;
  right?: string | null;
  strike?: number | null;
  premium?: number | null;
  quantity?: number | null;
  multiplier?: number | null;
  label?: string | null;
};

export type OptionsReplayPreviewRequest = {
  structure_type: OptionsReplayPreviewStructureType;
  legs: OptionsReplayPreviewLegRequest[];
  underlying_symbol?: string | null;
  expiration?: string | null;
  notes?: string[];
  source?: string | null;
  workflow_source?: string | null;
  underlying_prices?: number[] | null;
};

export type OptionsReplayPreviewLegPayoff = {
  label: string;
  payoff: number;
};

export type OptionsReplayPreviewPoint = {
  underlying_price: number;
  total_payoff: number;
  leg_payoffs?: OptionsReplayPreviewLegPayoff[] | null;
};

export type OptionsReplayPreviewResponse = {
  execution_enabled: boolean;
  persistence_enabled: boolean;
  market_mode: string;
  preview_type: "expiration_payoff";
  status: "ready" | "blocked" | "unsupported";
  structure_type?: string | null;
  underlying_symbol?: string | null;
  expiration?: string | null;
  replay_run_id?: number | null;
  recommendation_id?: string | null;
  order_id?: string | null;
  is_defined_risk: boolean;
  net_debit?: number | null;
  net_credit?: number | null;
  max_profit?: number | null;
  max_loss?: number | null;
  breakevens?: number[] | null;
  payoff_points?: OptionsReplayPreviewPoint[] | null;
  legs?: OptionsReplayPreviewLegRequest[] | null;
  warnings?: string[] | null;
  caveats?: string[] | null;
  blocked_reason?: string | null;
  operator_disclaimer?: string | null;
  notes?: string[] | null;
  source?: string | null;
  workflow_source?: string | null;
};

export type OptionsReplayPreviewAvailability = {
  request: OptionsReplayPreviewRequest | null;
  reason: string | null;
};

export type OptionsPaperStructureType =
  | "long_call"
  | "long_put"
  | "vertical_debit_spread"
  | "iron_condor";

export type OptionsPaperLegRequest = {
  action: "buy" | "sell";
  right: "call" | "put";
  strike: number;
  expiration: string;
  premium: number;
  quantity: number;
  multiplier: number;
  label?: string | null;
};

export type OptionsPaperOpenRequest = {
  market_mode: "options";
  structure_type: OptionsPaperStructureType;
  underlying_symbol: string;
  expiration?: string | null;
  legs: OptionsPaperLegRequest[];
  net_debit?: number | null;
  net_credit?: number | null;
  max_profit?: number | null;
  max_loss?: number | null;
  breakevens: number[];
  notes?: string | null;
};

export type OptionsPaperPositionLeg = {
  id: number;
  position_id: number;
  action: string;
  right: string;
  strike: number;
  expiration: string;
  quantity: number;
  multiplier: number;
  entry_premium: number;
  exit_premium?: number | null;
  status: string;
  label?: string | null;
};

export type OptionsPaperOpenResponse = {
  order_id: number;
  position_id: number;
  market_mode: "options";
  structure_type: string;
  underlying_symbol: string;
  status: string;
  order_status: string;
  position_status: string;
  opening_net_debit?: number | null;
  opening_net_credit?: number | null;
  commission_per_contract?: number | null;
  opening_commissions?: number | null;
  max_profit?: number | null;
  max_loss?: number | null;
  breakevens?: number[] | null;
  execution_enabled: boolean;
  persistence_enabled: boolean;
  paper_only: boolean;
  operator_disclaimer?: string | null;
  legs: OptionsPaperPositionLeg[];
  order_created_at: string;
  position_opened_at: string;
};

export type OptionsPaperCloseLegRequest = {
  position_leg_id: number;
  exit_premium: number;
};

export type OptionsPaperCloseRequest = {
  settlement_mode: "manual_close";
  legs: OptionsPaperCloseLegRequest[];
  notes?: string | null;
};

export type OptionsPaperTradeLeg = {
  id: number;
  trade_id: number;
  action: string;
  right: string;
  strike: number;
  expiration: string;
  quantity: number;
  multiplier: number;
  entry_premium?: number | null;
  exit_premium?: number | null;
  leg_gross_pnl?: number | null;
  leg_commission?: number | null;
  leg_net_pnl?: number | null;
  label?: string | null;
};

export type OptionsPaperCloseResponse = {
  position_id: number;
  trade_id: number;
  market_mode: "options";
  structure_type: string;
  underlying_symbol: string;
  status: string;
  position_status: string;
  settlement_mode: string;
  commission_per_contract?: number | null;
  opening_commissions?: number | null;
  closing_commissions?: number | null;
  gross_pnl?: number | null;
  net_pnl?: number | null;
  total_commissions?: number | null;
  execution_enabled: boolean;
  persistence_enabled: boolean;
  paper_only: boolean;
  operator_disclaimer?: string | null;
  legs: OptionsPaperTradeLeg[];
  closed_at: string;
};

export type OptionsPaperOpenAvailability = {
  request: OptionsPaperOpenRequest | null;
  reason: string | null;
};

export type OptionsCommissionSettings = {
  commission_per_contract: number | null;
  commission_per_contract_default: number | null;
};

type NormalizedOptionsStructureLeg = {
  action: "buy" | "sell";
  right: "call" | "put";
  strike: number;
  premium: number;
  quantity: number;
  multiplier: number;
  label: string | null;
};

export const OPTIONS_COMMISSION_NOT_PER_SHARE_TEXT = "Not per share. Do not multiply by 100.";
export const OPTIONS_COMMISSION_FORMULA_TEXT =
  "Total options commission = commission per contract x contracts x legs x open/close events.";
export const OPTIONS_COMMISSION_EXAMPLE_TEXT =
  "Example: $0.65 commission, 1 iron condor, 4 legs, open + close = $0.65 x 1 x 4 x 2 = $5.20 total estimated commission.";

export function parseRecommendationSearchParams(params: URLSearchParams): RecommendationSearchPrefill {
  const rawSymbols = [params.get("symbols") ?? "", params.get("symbol") ?? ""]
    .join(",")
    .split(",")
    .map((value) => value.trim().toUpperCase())
    .filter(Boolean);

  const seen = new Set<string>();
  const symbols = rawSymbols.filter((value) => {
    if (seen.has(value)) {
      return false;
    }
    seen.add(value);
    return true;
  });

  const recommendationId = (params.get("recommendation") ?? "").trim() || null;
  return { symbols, recommendationId };
}

export function getRankingProvenance(payload: Record<string, unknown> | null | undefined): Record<string, unknown> | null {
  const workflow = payload?.workflow;
  if (!workflow || typeof workflow !== "object") {
    return null;
  }
  const ranking = (workflow as Record<string, unknown>).ranking_provenance;
  return ranking && typeof ranking === "object" ? (ranking as Record<string, unknown>) : null;
}

export function isFallbackWorkflow(candidate: QueueCandidate | null, recommendation: StoredRecommendation | null): boolean {
  if (recommendation) {
    if (typeof recommendation.fallback_mode === "boolean") {
      return recommendation.fallback_mode;
    }
    const workflow = (recommendation.payload?.workflow ?? null) as Record<string, unknown> | null;
    return Boolean(workflow?.fallback_mode);
  }
  if (!candidate) {
    return false;
  }
  return candidate.workflow_source.toLowerCase().includes("fallback") || candidate.source?.toLowerCase().includes("fallback") === true;
}

export function isOptionsResearchMode(mode: string | null | undefined): boolean {
  return String(mode ?? "").trim().toLowerCase() === "options";
}

export function isReadOnlyResearchMode(mode: string | null | undefined): boolean {
  const normalized = String(mode ?? "").trim().toLowerCase();
  return normalized === "options" || normalized === "crypto";
}

export function shouldShowRecommendationExecutionCtas(mode: string | null | undefined): boolean {
  return !isReadOnlyResearchMode(mode);
}

function normalizeResearchSymbol(symbol: string | null | undefined): string | null {
  const normalized = String(symbol ?? "").trim().toUpperCase();
  return normalized ? normalized : null;
}

function toFiniteNumber(value: unknown): number | null {
  if (typeof value !== "number" || !Number.isFinite(value)) return null;
  return value;
}

function toPositiveInteger(value: unknown, fallback: number): number {
  if (typeof value === "number" && Number.isInteger(value) && value > 0) return value;
  return fallback;
}

function roundPreviewNumber(value: number): number {
  return Math.round(value * 10_000) / 10_000;
}

function normalizeOptionsReplayStructureType(
  value: string | null | undefined,
): OptionsReplayPreviewStructureType | null {
  const normalized = String(value ?? "").trim().toLowerCase();
  switch (normalized) {
    case "bull_call_debit_spread":
    case "bear_put_debit_spread":
    case "vertical_debit_spread":
      return "vertical_debit_spread";
    case "iron_condor":
      return "iron_condor";
    case "long_call":
      return "long_call";
    case "long_put":
      return "long_put";
    case "custom_defined_risk":
      return "custom_defined_risk";
    default:
      return null;
  }
}

function normalizeOptionsPaperStructureType(
  value: string | null | undefined,
): OptionsPaperStructureType | null {
  const normalized = normalizeOptionsReplayStructureType(value);
  if (normalized === "custom_defined_risk") return null;
  return normalized;
}

function buildNormalizedOptionsLegsFromExplicitPremiums(
  structure: OptionsResearchStructure,
): NormalizedOptionsStructureLeg[] | null {
  const rawLegs = structure.legs ?? [];
  if (rawLegs.length === 0) return null;
  const mapped = rawLegs.map((leg) => {
    const action = typeof leg.action === "string" ? leg.action.trim().toLowerCase() : null;
    const right = typeof leg.right === "string" ? leg.right.trim().toLowerCase() : null;
    const strike = toFiniteNumber(leg.strike);
    const premium = toFiniteNumber(leg.premium);
    if (!action || !right || strike == null || premium == null || premium < 0) return null;
    return {
      action: action as "buy" | "sell",
      right: right as "call" | "put",
      strike,
      premium: roundPreviewNumber(premium),
      quantity: toPositiveInteger(leg.quantity, 1),
      multiplier: toPositiveInteger(leg.multiplier, 100),
      label: typeof leg.label === "string" && leg.label.trim() ? leg.label.trim() : null,
    } satisfies NormalizedOptionsStructureLeg;
  });
  return mapped.every(Boolean) ? (mapped as NormalizedOptionsStructureLeg[]) : null;
}

function buildNormalizedOptionsLegsFromStructureAssumptions(
  structure: OptionsResearchStructure,
  structureType: OptionsReplayPreviewStructureType,
): NormalizedOptionsStructureLeg[] | null {
  const rawLegs = structure.legs ?? [];
  if (rawLegs.length === 0) return null;

  const mappedBase = rawLegs.map((leg) => {
    const action = typeof leg.action === "string" ? leg.action.trim().toLowerCase() : null;
    const right = typeof leg.right === "string" ? leg.right.trim().toLowerCase() : null;
    const strike = toFiniteNumber(leg.strike);
    if (!action || !right || strike == null) return null;
    return {
      action: action as "buy" | "sell",
      right: right as "call" | "put",
      strike,
      quantity: toPositiveInteger(leg.quantity, 1),
      multiplier: toPositiveInteger(leg.multiplier, 100),
      label: typeof leg.label === "string" && leg.label.trim() ? leg.label.trim() : null,
    };
  });
  if (!mappedBase.every(Boolean)) return null;
  const baseLegs = mappedBase as Array<Omit<NormalizedOptionsStructureLeg, "premium">>;

  if (structureType === "vertical_debit_spread") {
    const netDebit = toFiniteNumber(structure.net_debit);
    if (netDebit == null || netDebit <= 0) return null;
    const buyCount = baseLegs.filter((leg) => leg.action === "buy").length;
    const sellCount = baseLegs.filter((leg) => leg.action === "sell").length;
    if (baseLegs.length !== 2 || buyCount !== 1 || sellCount !== 1) return null;
    return baseLegs.map((leg) => ({
      ...leg,
      premium: leg.action === "buy" ? roundPreviewNumber(netDebit) : 0,
    }));
  }

  if (structureType === "iron_condor") {
    const netCredit = toFiniteNumber(structure.net_credit);
    if (netCredit == null || netCredit <= 0) return null;
    const shortLegs = baseLegs.filter((leg) => leg.action === "sell");
    if (baseLegs.length !== 4 || shortLegs.length !== 2) return null;
    const shortPremium = roundPreviewNumber(netCredit / shortLegs.length);
    return baseLegs.map((leg) => ({
      ...leg,
      premium: leg.action === "sell" ? shortPremium : 0,
    }));
  }

  if (structureType === "long_call" || structureType === "long_put") {
    if (baseLegs.length !== 1 || baseLegs[0].action !== "buy") return null;
    const maxLoss = toFiniteNumber(structure.max_loss);
    const fallbackPremium =
      maxLoss != null && maxLoss > 0
        ? roundPreviewNumber(maxLoss / (baseLegs[0].quantity! * baseLegs[0].multiplier!))
        : null;
    const premium = toFiniteNumber(structure.net_debit) ?? fallbackPremium;
    if (premium == null || premium <= 0) return null;
    return baseLegs.map((leg) => ({ ...leg, premium }));
  }

  return null;
}

function buildNormalizedOptionsStructureLegs(
  structure: OptionsResearchStructure,
  structureType: OptionsReplayPreviewStructureType,
): NormalizedOptionsStructureLeg[] | null {
  return (
    buildNormalizedOptionsLegsFromExplicitPremiums(structure)
    ?? buildNormalizedOptionsLegsFromStructureAssumptions(structure, structureType)
  );
}

function mapNormalizedLegsToReplayPreviewRequest(
  legs: NormalizedOptionsStructureLeg[],
): OptionsReplayPreviewLegRequest[] {
  return legs.map((leg) => ({ ...leg }));
}

function extractOptionsStructureBreakevens(structure: OptionsResearchStructure | null | undefined): number[] {
  const values = [structure?.breakeven_low, structure?.breakeven_high];
  return values.filter((value): value is number => typeof value === "number" && Number.isFinite(value));
}

export function getOptionsReplayPreviewAvailability(
  setup: OptionsResearchSetup | null | undefined,
): OptionsReplayPreviewAvailability {
  if (!setup) {
    return { request: null, reason: "No options research contract loaded." };
  }
  if (!isOptionsResearchMode(setup.market_mode)) {
    return { request: null, reason: "Replay payoff preview is only available for options research mode." };
  }
  const structure = setup.option_structure;
  if (!structure) {
    return { request: null, reason: "Replay payoff preview requires a visible options structure." };
  }
  if (!structure.legs || structure.legs.length === 0) {
    return { request: null, reason: "Replay payoff preview requires visible option legs." };
  }
  const structureType = normalizeOptionsReplayStructureType(structure.type);
  if (!structureType || structureType === "custom_defined_risk") {
    return {
      request: null,
      reason: "Replay payoff preview is currently supported only for long calls/puts, vertical debit spreads, and iron condors.",
    };
  }

  const legs = buildNormalizedOptionsStructureLegs(structure, structureType);

  if (!legs) {
    return {
      request: null,
      reason: "Replay payoff preview requires complete legs plus usable debit/credit or premium assumptions from the current research contract.",
    };
  }

  return {
    request: {
      structure_type: structureType,
      legs: mapNormalizedLegsToReplayPreviewRequest(legs),
      underlying_symbol: normalizeResearchSymbol(setup.symbol),
      expiration: typeof structure.expiration === "string" && structure.expiration.trim() ? structure.expiration.trim() : null,
      notes: ["Premium assumptions derived from the read-only research contract for expiration payoff preview."],
      source: setup.workflow_source,
      workflow_source: setup.workflow_source,
    },
    reason: null,
  };
}

export function buildOptionsReplayPreviewRequest(
  setup: OptionsResearchSetup | null | undefined,
): OptionsReplayPreviewRequest | null {
  return getOptionsReplayPreviewAvailability(setup).request;
}

export async function fetchOptionsReplayPreview(
  request: OptionsReplayPreviewRequest,
  fetcher: typeof fetchWorkflowApi = fetchWorkflowApi,
): Promise<NormalizedApiResult<OptionsReplayPreviewResponse>> {
  return fetcher<OptionsReplayPreviewResponse>("/api/user/options/replay-preview", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export function getOptionsPaperOpenAvailability(
  setup: OptionsResearchSetup | null | undefined,
): OptionsPaperOpenAvailability {
  if (!setup) {
    return { request: null, reason: "No options research contract loaded." };
  }
  if (!isOptionsResearchMode(setup.market_mode)) {
    return { request: null, reason: "Paper option open is only available for options research mode." };
  }
  const structure = setup.option_structure;
  if (!structure) {
    return { request: null, reason: "Paper option open requires a visible options structure." };
  }
  if (!structure.legs || structure.legs.length === 0) {
    return { request: null, reason: "Paper option open requires visible option legs." };
  }
  const structureType = normalizeOptionsPaperStructureType(structure.type);
  if (!structureType) {
    return {
      request: null,
      reason: "Paper option open currently supports long calls/puts, vertical debit spreads, and iron condors only.",
    };
  }
  const expiration =
    typeof structure.expiration === "string" && structure.expiration.trim()
      ? structure.expiration.trim()
      : null;
  if (!expiration) {
    return { request: null, reason: "Paper option open requires a visible expiration for every leg." };
  }
  const normalizedStructureType = normalizeOptionsReplayStructureType(structureType);
  if (!normalizedStructureType) {
    return { request: null, reason: "Paper option open structure type is unsupported." };
  }
  const legs = buildNormalizedOptionsStructureLegs(structure, normalizedStructureType);
  if (!legs) {
    return {
      request: null,
      reason: "Paper option open requires complete legs plus usable debit/credit or premium assumptions from the current research contract.",
    };
  }
  return {
    request: {
      market_mode: "options",
      structure_type: structureType,
      underlying_symbol: normalizeResearchSymbol(setup.symbol) ?? setup.symbol,
      expiration,
      legs: legs.map((leg) => ({
        ...leg,
        expiration,
      })),
      net_debit: toFiniteNumber(structure.net_debit),
      net_credit: toFiniteNumber(structure.net_credit),
      max_profit: toFiniteNumber(structure.max_profit),
      max_loss: toFiniteNumber(structure.max_loss),
      breakevens: extractOptionsStructureBreakevens(structure),
      notes: "Derived from the read-only options research contract for persisted paper-only lifecycle preview.",
    },
    reason: null,
  };
}

export function buildOptionsPaperOpenRequest(
  setup: OptionsResearchSetup | null | undefined,
): OptionsPaperOpenRequest | null {
  return getOptionsPaperOpenAvailability(setup).request;
}

export async function fetchOptionsPaperOpen(
  request: OptionsPaperOpenRequest,
  fetcher: typeof fetchWorkflowApi = fetchWorkflowApi,
): Promise<NormalizedApiResult<OptionsPaperOpenResponse>> {
  return fetcher<OptionsPaperOpenResponse>("/api/user/options/paper-structures/open", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function fetchOptionsPaperClose(
  positionId: number,
  request: OptionsPaperCloseRequest,
  fetcher: typeof fetchWorkflowApi = fetchWorkflowApi,
): Promise<NormalizedApiResult<OptionsPaperCloseResponse>> {
  return fetcher<OptionsPaperCloseResponse>(`/api/user/options/paper-structures/${positionId}/close`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(request),
  });
}

export async function fetchOptionsCommissionSettings(
  fetcher: typeof fetchWorkflowApi = fetchWorkflowApi,
): Promise<NormalizedApiResult<OptionsCommissionSettings>> {
  return fetcher<OptionsCommissionSettings>("/api/user/me");
}

export function getEffectiveOptionsCommissionPerContract(
  value: OptionsCommissionSettings | null | undefined,
): number | null {
  const configured = toFiniteNumber(value?.commission_per_contract);
  if (configured != null && configured >= 0) return configured;
  const fallback = toFiniteNumber(value?.commission_per_contract_default);
  if (fallback != null && fallback >= 0) return fallback;
  return null;
}

export function estimateOptionsCommissionPerEvent(
  legs: Array<Pick<OptionsPaperLegRequest | OptionsPaperPositionLeg | OptionsPaperTradeLeg, "quantity">> | null | undefined,
  commissionPerContract: number | null | undefined,
): number | null {
  const commission = toFiniteNumber(commissionPerContract);
  if (commission == null || commission < 0) return null;
  const normalizedLegs = (legs ?? []).filter(
    (leg): leg is Pick<OptionsPaperLegRequest | OptionsPaperPositionLeg | OptionsPaperTradeLeg, "quantity"> =>
      typeof leg?.quantity === "number" && Number.isFinite(leg.quantity) && leg.quantity > 0,
  );
  if (normalizedLegs.length === 0) return null;
  const totalContracts = normalizedLegs.reduce((sum, leg) => sum + leg.quantity, 0);
  return roundPreviewNumber(commission * totalContracts);
}

export function estimateOptionsCommissionForEvents(
  legs: Array<Pick<OptionsPaperLegRequest | OptionsPaperPositionLeg | OptionsPaperTradeLeg, "quantity">> | null | undefined,
  commissionPerContract: number | null | undefined,
  eventCount: number,
): number | null {
  const perEvent = estimateOptionsCommissionPerEvent(legs, commissionPerContract);
  if (perEvent == null) return null;
  if (!Number.isFinite(eventCount) || eventCount <= 0) return null;
  return roundPreviewNumber(perEvent * eventCount);
}

export function describeOptionsCommissionEstimate(args: {
  commissionPerContract: number | null | undefined;
  legs: Array<Pick<OptionsPaperLegRequest, "quantity">> | null | undefined;
  eventCount: number;
  eventLabel: string;
}): string | null {
  const commission = toFiniteNumber(args.commissionPerContract);
  if (commission == null || commission < 0) return null;
  const normalizedLegs = (args.legs ?? []).filter(
    (leg): leg is Pick<OptionsPaperLegRequest, "quantity"> =>
      typeof leg?.quantity === "number" && Number.isFinite(leg.quantity) && leg.quantity > 0,
  );
  if (normalizedLegs.length === 0) return null;
  const quantities = normalizedLegs.map((leg) => leg.quantity);
  const uniformContracts = quantities.every((quantity) => quantity === quantities[0]);
  const eventCount = Math.max(1, Math.round(args.eventCount));
  const totalCommission = estimateOptionsCommissionForEvents(normalizedLegs, commission, eventCount);
  if (totalCommission == null) return null;
  if (uniformContracts) {
    return `${formatResearchCurrency(commission)} x ${quantities[0]} contract${quantities[0] === 1 ? "" : "s"} x ${normalizedLegs.length} leg${normalizedLegs.length === 1 ? "" : "s"} x ${eventCount} ${args.eventLabel} event${eventCount === 1 ? "" : "s"} = ${formatResearchCurrency(totalCommission)}.`;
  }
  const totalContracts = quantities.reduce((sum, quantity) => sum + quantity, 0);
  return `${formatResearchCurrency(commission)} x ${totalContracts} total contracts across ${normalizedLegs.length} leg${normalizedLegs.length === 1 ? "" : "s"} x ${eventCount} ${args.eventLabel} event${eventCount === 1 ? "" : "s"} = ${formatResearchCurrency(totalCommission)}.`;
}

export function formatResearchValue(value: unknown, fallback = "Unavailable"): string {
  if (value == null) return fallback;
  if (typeof value === "number") {
    if (!Number.isFinite(value)) return fallback;
    return value.toLocaleString("en-US", {
      minimumFractionDigits: Number.isInteger(value) ? 0 : 2,
      maximumFractionDigits: 2,
    });
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    return trimmed ? trimmed : fallback;
  }
  return String(value);
}

export function formatResearchCell(value: unknown): string {
  return formatResearchValue(value, "—");
}

export function formatResearchCurrency(value: unknown, fallback = "Unavailable"): string {
  const numeric = typeof value === "number" && Number.isFinite(value) ? value : null;
  if (numeric == null) return fallback;
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(numeric);
}

export function formatResearchTimestamp(value: unknown, fallback = "As-of unavailable"): string {
  if (value instanceof Date) {
    if (Number.isNaN(value.getTime())) return fallback;
    return value.toISOString().replace("T", " ").slice(0, 16) + " UTC";
  }
  if (typeof value === "string") {
    const trimmed = value.trim();
    if (!trimmed) return fallback;
    const parsed = new Date(trimmed);
    if (Number.isNaN(parsed.getTime())) return trimmed;
    return parsed.toISOString().replace("T", " ").slice(0, 16) + " UTC";
  }
  return fallback;
}

export function formatOptionsReplayToken(value: unknown, fallback = "Unavailable"): string {
  if (typeof value !== "string") return fallback;
  const trimmed = value.trim();
  if (!trimmed) return fallback;
  return trimmed
    .split(/[_-]+/)
    .map((part) => {
      const normalized = part.trim().toLowerCase();
      if (!normalized) return "";
      if (normalized === "iv") return "IV";
      if (normalized === "dte") return "DTE";
      if (normalized === "pnl") return "P&L";
      return normalized.charAt(0).toUpperCase() + normalized.slice(1);
    })
    .filter(Boolean)
    .join(" ");
}

export function formatOptionsLegLabel(leg: OptionsResearchLeg): string {
  const action = typeof leg.action === "string" && leg.action.trim() ? leg.action.trim() : null;
  const right = typeof leg.right === "string" && leg.right.trim() ? leg.right.trim().toUpperCase() : null;
  const strike = typeof leg.strike === "number" && Number.isFinite(leg.strike) ? formatResearchValue(leg.strike) : null;
  const label = typeof leg.label === "string" && leg.label.trim() ? leg.label.trim() : null;
  const summary = [action, right, strike].filter(Boolean).join(" ");
  if (summary && label) return `${summary} — ${label}`;
  return summary || label || "Unavailable";
}

export function getOptionsPremiumLabel(structure: OptionsResearchStructure | null | undefined): "Net credit" | "Net debit" | "Net premium" {
  if (structure?.net_credit != null) return "Net credit";
  if (structure?.net_debit != null) return "Net debit";
  return "Net premium";
}

export function getOptionsPremiumValue(structure: OptionsResearchStructure | null | undefined): number | null {
  if (structure?.net_credit != null && Number.isFinite(structure.net_credit)) return structure.net_credit;
  if (structure?.net_debit != null && Number.isFinite(structure.net_debit)) return structure.net_debit;
  return null;
}

export function getOptionsLegDisplayLines(structure: OptionsResearchStructure | null | undefined): string[] {
  const legs = structure?.legs ?? [];
  if (legs.length === 0) return ["Leg detail Unavailable."];
  return legs.map((leg) => formatOptionsLegLabel(leg));
}

export function getExpectedRangeReasonText(range: OptionsExpectedRange | null | undefined): string | null {
  if (!range || range.status === "computed") return null;
  if (typeof range.reason === "string" && range.reason.trim()) return range.reason.trim();
  return "Unavailable";
}

export function getOptionsChainUnavailableMessage(preview: OptionsChainPreview | null | undefined): string {
  const reason = preview?.reason;
  if (typeof reason === "string" && reason.trim()) return reason.trim();
  return "Chain preview unavailable on current provider plan or payload.";
}

function isLikelyIndexOptionsSymbol(symbol: string | null | undefined): boolean {
  const normalized = normalizeResearchSymbol(symbol);
  if (!normalized) return false;
  return normalized === "SPX" || normalized.startsWith("SPXW") || normalized === "NDX";
}

function hasIncompleteResearchLeg(leg: OptionsResearchLeg | null | undefined): boolean {
  const action = typeof leg?.action === "string" && leg.action.trim();
  const right = typeof leg?.right === "string" && leg.right.trim();
  const strike = toFiniteNumber(leg?.strike);
  return !action || !right || strike == null;
}

export function getOptionsResearchDataQualityWarnings(
  setup: OptionsResearchSetup | null | undefined,
): string[] {
  if (!setup || !isOptionsResearchMode(setup.market_mode)) return [];

  const warnings = new Set<string>();
  const workflowSource = String(setup.workflow_source ?? "").trim();
  const structure = setup.option_structure ?? null;
  const chainPreview = setup.options_chain_preview ?? null;
  const expectedRange = setup.expected_range ?? null;
  const replayAvailability = getOptionsReplayPreviewAvailability(setup);
  const paperOpenAvailability = getOptionsPaperOpenAvailability(setup);

  if (!workflowSource) {
    warnings.add("Underlying source unavailable.");
  } else if (workflowSource.toLowerCase().includes("fallback")) {
    warnings.add("Underlying research is fallback-sourced. Treat provider-backed chart or chain context as unavailable until provider coverage recovers.");
  }

  if (!structure) {
    warnings.add("Options structure unavailable in the current research payload.");
  } else {
    const legs = structure.legs ?? [];
    if (legs.length === 0) {
      warnings.add("Structure legs unavailable in the current research payload.");
    } else if (legs.some((leg) => hasIncompleteResearchLeg(leg))) {
      warnings.add("Structure legs are incomplete. Replay payoff preview and paper lifecycle stay blocked until every leg has action, right, and strike.");
    }
    if (!(typeof structure.expiration === "string" && structure.expiration.trim())) {
      warnings.add("Expiration unavailable in the current research payload.");
    }
    if (toFiniteNumber(structure.dte) == null) {
      warnings.add("DTE unavailable in the current research payload.");
    }
    if (toFiniteNumber(structure.iv_snapshot) == null) {
      warnings.add("IV snapshot unavailable in the current provider plan or payload.");
    }
    if (toFiniteNumber(structure.theta_context) == null && toFiniteNumber(structure.vega_context) == null) {
      warnings.add("Greeks context unavailable in the current provider plan or payload.");
    }
    warnings.add("Open interest unavailable on the current Recommendations payload.");
  }

  if (!expectedRange) {
    warnings.add("Expected Range unavailable for this setup.");
  } else {
    const expectedRangeReason = getExpectedRangeReasonText(expectedRange);
    if (expectedRange.status === "blocked" || expectedRange.status === "omitted") {
      warnings.add(
        expectedRangeReason
          ? `Expected Range ${formatOptionsReplayToken(expectedRange.status).toLowerCase()}: ${formatOptionsReplayToken(expectedRangeReason)}.`
          : `Expected Range ${formatOptionsReplayToken(expectedRange.status).toLowerCase()}.`,
      );
    }
  }

  if (chainPreview === null || chainPreview.reason) {
    warnings.add(getOptionsChainUnavailableMessage(chainPreview));
  } else {
    if (!chainPreview.source) {
      warnings.add("Chain preview source unavailable.");
    }
    if (!chainPreview.data_as_of) {
      warnings.add("Chain preview as-of unavailable.");
    }
    const hasCallRows = Array.isArray(chainPreview.calls) && chainPreview.calls.length > 0;
    const hasPutRows = Array.isArray(chainPreview.puts) && chainPreview.puts.length > 0;
    if (!hasCallRows && !hasPutRows) {
      warnings.add("Chain preview returned no call or put rows.");
    }
  }

  if (replayAvailability.reason) {
    warnings.add(replayAvailability.reason);
  }
  if (paperOpenAvailability.reason && paperOpenAvailability.reason !== replayAvailability.reason) {
    warnings.add(paperOpenAvailability.reason);
  }

  if (isLikelyIndexOptionsSymbol(setup.symbol)) {
    warnings.add("SPX/NDX may require index data; SPY/QQQ can be practical ETF substitutes.");
  }

  return [...warnings];
}

export function getOptionsReplayPreviewPayoffRows(
  preview: OptionsReplayPreviewResponse | null | undefined,
): OptionsReplayPreviewPoint[] {
  const points = preview?.payoff_points ?? [];
  return points.filter(
    (point) =>
      typeof point?.underlying_price === "number"
      && Number.isFinite(point.underlying_price)
      && typeof point?.total_payoff === "number"
      && Number.isFinite(point.total_payoff),
  );
}

export function getOptionsReplayPreviewBreakevens(
  preview: OptionsReplayPreviewResponse | null | undefined,
): number[] {
  return (preview?.breakevens ?? []).filter(
    (value): value is number => typeof value === "number" && Number.isFinite(value),
  );
}

export function canRenderOptionsResearchChart({
  marketMode,
  requestedSymbol,
  setupSymbol,
  workflowSource,
  chartPayloadSymbol,
  chartFallbackMode,
}: {
  marketMode: string | null | undefined;
  requestedSymbol: string | null | undefined;
  setupSymbol: string | null | undefined;
  workflowSource: string | null | undefined;
  chartPayloadSymbol?: string | null | undefined;
  chartFallbackMode?: boolean;
}): boolean {
  if (!isOptionsResearchMode(marketMode)) return false;
  const normalizedSetup = normalizeResearchSymbol(setupSymbol);
  if (!normalizedSetup) return false;
  const normalizedRequested = normalizeResearchSymbol(requestedSymbol);
  if (normalizedRequested && normalizedRequested !== normalizedSetup) return false;
  if (String(workflowSource ?? "").toLowerCase().includes("fallback")) return false;
  if (chartFallbackMode) return false;
  if (chartPayloadSymbol !== undefined) {
    const normalizedChart = normalizeResearchSymbol(chartPayloadSymbol);
    if (!normalizedChart || normalizedChart !== normalizedSetup) return false;
  }
  return true;
}

/**
 * Returns a Set of queue-row keys (same format as the page's selectedQueueKey:
 * "${symbol}-${strategy}-${rank}") for every stored recommendation that has
 * ranking_provenance, so the queue table can badge already-promoted rows.
 */
export function getPromotedQueueKeys(rows: StoredRecommendation[]): Set<string> {
  const keys = new Set<string>();
  for (const row of rows) {
    const provenance = getRankingProvenance(row.payload);
    if (!provenance) continue;
    const symbol = typeof provenance.symbol === "string" ? provenance.symbol : null;
    const strategy = typeof provenance.strategy === "string" ? provenance.strategy : null;
    const rank = provenance.rank != null ? Number(provenance.rank) : null;
    if (symbol && strategy && rank != null && !Number.isNaN(rank)) {
      keys.add(`${symbol}-${strategy}-${rank}`);
    }
  }
  return keys;
}
