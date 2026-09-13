import type { ContractQuote } from "../types";

export type PositionStrategy = "CSP" | "COVERED_CALL";

export type PositionStatus = "OPEN" | "CLOSED" | "ROLLED";

export type PositionOptionType = "PUT" | "CALL";

export type Position = {
  id: string;
  ticker: string;
  strategy: PositionStrategy;
  optionType: PositionOptionType;
  expiry: string;
  strike: number;
  contracts: number;
  entryPremium: number;
  openedAt: string;
  status: PositionStatus;
  assignmentOk: boolean;
  shares?: number;
  costBasis?: number;
  closedAt?: string;
  closePrice?: number;
  closeFees?: number;
  realizedPnl?: number;
  rolledFromPositionId?: string;
  rolledToPositionId?: string;
  note?: string;
};

export type PositionDraft = {
  ticker: string;
  strategy: PositionStrategy;
  optionType: PositionOptionType;
  expiry: string;
  strike: number;
  contracts: number;
  entryPremium: number;
  assignmentOk: boolean;
  openedAt?: string;
  shares?: number;
  costBasis?: number;
  note?: string;
  fromRecommendation?: boolean;
};

export type PositionManagementAction = "HOLD" | "CLOSE" | "ROLL";

export type PositionEvaluation = {
  positionId: string;
  fetchedAt: string;
  marketOpen: boolean;
  underlyingSpot: number | null;
  contract: ContractQuote | null;
  estimatedClosePrice: number | null;
  markPnl: number | null;
  estimatedClosePnl: number | null;
  profitCapture: number | null;
  itm: boolean | null;
  management: {
    action: PositionManagementAction | null;
    reasons: string[];
  };
  warnings: string[];
};

export type PositionSettings = {
  profitTarget: number;
  nearExpiryDte: number;
  nearExpiryProfitTarget: number;
};

export type PositionsExport = {
  schemaVersion: 1;
  exportedAt: string;
  positions: Position[];
};

export type RollCandidate = {
  contract: ContractQuote;
  estimatedNetPerShare: number | null;
  estimatedNet: number | null;
  recommended: boolean;
};

export type EvaluateResponse = {
  evaluations: PositionEvaluation[];
  fetchedAt: string;
  marketOpen: boolean;
};

export type RollCandidatesResponse = {
  candidates: RollCandidate[];
  fetchedAt: string;
  marketOpen: boolean;
  current: ContractQuote | null;
};
