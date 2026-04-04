export type AuthMode = "disabled" | "static_token";
export type ComponentStatus = "ok" | "unavailable" | "degraded";
export type TrainingType = "supervised" | "rl";
export type Timeframe = "1m" | "5m" | "15m";
export type ModelType = "supervised" | "rl";
export type EvaluationType = "validation" | "backtest" | "paper_trading";
export type TradeSide = "long" | "short";
export type SignalStatus = "pending" | "accepted" | "expired" | "rejected" | "executed";
export type PositionStatus = "open" | "closed";

export type SessionResponse = {
  authenticated: true;
  auth_mode: AuthMode;
  subject: string;
  roles: string[];
};

export type ComponentHealthResponse = {
  name: string;
  status: ComponentStatus;
  details: Record<string, unknown>;
};

export type SystemStatusResponse = {
  service: "api";
  status: "ok" | "degraded";
  environment: string;
  paper_trading_only: boolean;
  components: Record<string, ComponentHealthResponse>;
};

export type MT5ConnectionStatusResponse = {
  status: string;
  account_login: number | null;
  server_name: string | null;
  account_name: string | null;
  account_currency: string | null;
  leverage: number | null;
  is_demo: boolean | null;
  trade_allowed: boolean | null;
  paper_trading_allowed: boolean;
  reason: string | null;
  details: Record<string, unknown>;
};

export type SymbolValidationResponse = {
  validation_result_id: number;
  symbol_id: number | null;
  requested_symbol: string;
  normalized_input: string;
  normalized_symbol: string | null;
  provider: string;
  is_valid: boolean;
  reason: string | null;
  base_currency: string | null;
  quote_currency: string | null;
  details: Record<string, unknown>;
};

export type TrainingRequestPayload = {
  symbol_code: string;
  training_type: TrainingType;
  timeframes: Timeframe[];
  sync_mode: "backfill" | "incremental";
  lookback_bars: number;
  priority: number;
  notes?: string | null;
};

export type TrainingRequestResponse = {
  training_request_id: number;
  symbol_id: number;
  symbol_code: string;
  training_type: TrainingType;
  status: string;
  requested_timeframes: Timeframe[];
  ingestion_job_id: number;
  ingestion_job_status: string;
};

export type ModelRegistryEntryResponse = {
  model_type: ModelType;
  model_id: number;
  symbol_id: number;
  symbol_code: string;
  dataset_version_id: number | null;
  feature_set_id: number | null;
  training_job_id: number;
  model_name: string;
  version_tag: string;
  algorithm: string;
  status: string;
  storage_uri: string | null;
  approved_model_id: number | null;
  is_active_approval: boolean;
  created_at: string;
};

export type ModelEvaluationSummaryResponse = {
  evaluation_id: number;
  model_type: ModelType;
  model_id: number;
  symbol_id: number;
  symbol_code: string;
  dataset_version_id: number | null;
  evaluation_type: EvaluationType;
  confidence: number;
  risk_to_reward: number;
  sample_size: number | null;
  max_drawdown: number | null;
  approved: boolean;
  decision_reasons: string[];
  evaluated_at: string;
};

export type ApprovedSymbolResponse = {
  approved_model_id: number;
  symbol_id: number;
  symbol_code: string;
  model_type: ModelType;
  model_id: number;
  model_name: string;
  algorithm: string;
  confidence: number;
  risk_to_reward: number;
  approved_at: string;
};

export type PaperTradingStatusResponse = {
  enabled: boolean;
  connection_status: string;
  account_login: number | null;
  server_name: string | null;
  account_name: string | null;
  is_demo: boolean | null;
  is_trade_allowed: boolean | null;
  paper_trading_allowed: boolean;
  reason: string | null;
  approved_symbol_count: number;
  accepted_signal_count: number;
  open_order_count: number;
  open_position_count: number;
  last_started_at: string | null;
  last_started_by: string | null;
  last_stopped_at: string | null;
  last_stopped_by: string | null;
};

export type PaperTradingSyncResponse = {
  synced_at: string;
  connection_status: string;
  paper_trading_allowed: boolean;
  account_login: number | null;
  orders_updated: number;
  positions_updated: number;
  executions_created: number;
  history_records_seen: number;
  broker_positions_seen: number;
};

export type PaperTradeSignalResponse = {
  signal_id: number;
  approved_model_id: number;
  symbol_id: number;
  symbol_code: string;
  timeframe: Timeframe;
  side: TradeSide;
  status: SignalStatus;
  signal_time: string;
  confidence: number;
  risk_to_reward: number;
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  rationale: Record<string, unknown>;
};

export type PaperTradeSignalListResponse = {
  signals: PaperTradeSignalResponse[];
};

export type PaperTradePositionResponse = {
  position_id: number;
  order_id: number;
  symbol_id: number;
  symbol_code: string;
  side: TradeSide;
  status: PositionStatus;
  opened_at: string;
  closed_at: string | null;
  quantity: number;
  open_price: number;
  close_price: number | null;
  stop_loss: number | null;
  take_profit: number | null;
  unrealized_pnl: number | null;
  realized_pnl: number | null;
};

export type PaperTradePositionListResponse = {
  positions: PaperTradePositionResponse[];
};

export type EventEnvelope = {
  cursor: number;
  event_id: string;
  event_type: string;
  occurred_at: string;
  entity_type: string | null;
  entity_id: string | null;
  payload: Record<string, unknown>;
};

export type WebSocketEventMessage = {
  delivery: "live" | "replay";
  event: EventEnvelope;
};

type APIErrorPayload = {
  detail?: string;
};

export class APIError extends Error {
  status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "APIError";
    this.status = status;
  }
}

export type APIClientConfig = {
  baseUrl: string;
  token: string;
};

export function createAPIClient(config: APIClientConfig) {
  return {
    getSession: () => requestJson<SessionResponse>(config, "/api/v1/auth/session"),
    getSystemStatus: () => requestJson<SystemStatusResponse>(config, "/api/v1/system/status"),
    getMT5Status: () => requestJson<MT5ConnectionStatusResponse>(config, "/api/v1/mt5/status"),
    listApprovedSymbols: () =>
      requestJson<ApprovedSymbolResponse[]>(config, "/api/v1/evaluations/approved-symbols"),
    listModels: () => requestJson<ModelRegistryEntryResponse[]>(config, "/api/v1/evaluations/models"),
    listEvaluationReports: () =>
      requestJson<ModelEvaluationSummaryResponse[]>(config, "/api/v1/evaluations/reports"),
    getTradingStatus: () =>
      requestJson<PaperTradingStatusResponse>(config, "/api/v1/trading/status"),
    startPaperTrading: () =>
      requestJson<PaperTradingStatusResponse>(config, "/api/v1/trading/start", {
        method: "POST",
      }),
    stopPaperTrading: () =>
      requestJson<PaperTradingStatusResponse>(config, "/api/v1/trading/stop", {
        method: "POST",
      }),
    syncPaperTrading: () =>
      requestJson<PaperTradingSyncResponse>(config, "/api/v1/trading/sync", {
        method: "POST",
      }),
    listSignals: () =>
      requestJson<PaperTradeSignalListResponse>(config, "/api/v1/trading/signals"),
    listPositions: () =>
      requestJson<PaperTradePositionListResponse>(config, "/api/v1/trading/positions"),
    validateSymbol: (symbol: string) =>
      requestJson<SymbolValidationResponse>(config, "/api/v1/symbols/validate", {
        method: "POST",
        body: { symbol },
      }),
    requestTraining: (payload: TrainingRequestPayload) =>
      requestJson<TrainingRequestResponse>(config, "/api/v1/training/request", {
        method: "POST",
        body: payload,
      }),
  };
}

export function buildEventsWebSocketUrl(config: APIClientConfig, topics: string[]): string {
  const endpoint = new URL("/ws/events", normalizeBaseUrl(config.baseUrl));
  if (config.token.trim()) {
    endpoint.searchParams.set("token", config.token.trim());
  }
  if (topics.length > 0) {
    endpoint.searchParams.set("topics", topics.join(","));
  }
  if (endpoint.protocol === "https:") {
    endpoint.protocol = "wss:";
  } else if (endpoint.protocol === "http:") {
    endpoint.protocol = "ws:";
  }
  return endpoint.toString();
}

export function normalizeBaseUrl(rawValue: string): string {
  const trimmed = rawValue.trim();
  if (!trimmed) {
    return "http://127.0.0.1:8000";
  }
  return trimmed.replace(/\/+$/, "");
}

async function requestJson<T>(
  config: APIClientConfig,
  path: string,
  init: {
    method?: "GET" | "POST";
    body?: Record<string, unknown>;
  } = {},
): Promise<T> {
  const response = await fetch(new URL(path, normalizeBaseUrl(config.baseUrl)), {
    method: init.method ?? "GET",
    headers: buildHeaders(config.token, init.body !== undefined),
    body: init.body === undefined ? undefined : JSON.stringify(init.body),
  });

  if (!response.ok) {
    let message = `Request failed with status ${response.status}.`;
    try {
      const payload = (await response.json()) as APIErrorPayload;
      if (payload.detail) {
        message = payload.detail;
      }
    } catch {
      // Keep the generic message when the API returns a non-JSON error body.
    }
    throw new APIError(message, response.status);
  }

  return (await response.json()) as T;
}

function buildHeaders(token: string, hasBody: boolean): HeadersInit {
  const headers: Record<string, string> = {
    Accept: "application/json",
  };
  if (hasBody) {
    headers["Content-Type"] = "application/json";
  }
  if (token.trim()) {
    headers.Authorization = `Bearer ${token.trim()}`;
  }
  return headers;
}
