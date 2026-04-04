import type {
  ApprovedSymbolResponse,
  ModelEvaluationSummaryResponse,
  ModelRegistryEntryResponse,
  MT5ConnectionStatusResponse,
  PaperTradePositionResponse,
  PaperTradeSignalResponse,
  PaperTradingStatusResponse,
  SessionResponse,
  SystemStatusResponse,
} from "../../api";
import type { QueueRow } from "../../demo-state";

export type LiveFeedState = "connecting" | "live" | "offline";
export type TradingAction = "start" | "stop" | "sync";
export type WorkspaceView = "overview" | "symbols" | "pipeline" | "models" | "trading" | "system";
export type PipelineStageKey = "ingestion" | "preprocessing" | "training";

export type WorkspaceAccess = {
  operatorEmail: string;
  apiBaseUrl: string;
  token: string;
  session: SessionResponse;
};

export type QueueViewModel = QueueRow & {
  key: string;
};

export type PipelineStageSnapshot = {
  key: PipelineStageKey;
  title: string;
  status: QueueRow["status"];
  progress: number;
  detail: string;
  note: string;
  updatedAt: string;
};

export type OperatorDataState = {
  systemStatus: SystemStatusResponse | null;
  mt5Status: MT5ConnectionStatusResponse | null;
  approvedSymbols: ApprovedSymbolResponse[];
  modelRegistry: ModelRegistryEntryResponse[];
  evaluationReports: ModelEvaluationSummaryResponse[];
  tradingStatus: PaperTradingStatusResponse | null;
  signals: PaperTradeSignalResponse[];
  positions: PaperTradePositionResponse[];
};

export const emptyOperatorData: OperatorDataState = {
  systemStatus: null,
  mt5Status: null,
  approvedSymbols: [],
  modelRegistry: [],
  evaluationReports: [],
  tradingStatus: null,
  signals: [],
  positions: [],
};
