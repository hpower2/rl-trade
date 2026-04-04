import type {
  ApprovedSymbolResponse,
  EventEnvelope,
  ModelEvaluationSummaryResponse,
  ModelRegistryEntryResponse,
  MT5ConnectionStatusResponse,
  PaperTradePositionResponse,
  PaperTradeSignalResponse,
  PaperTradingStatusResponse,
  SessionResponse,
  SymbolValidationResponse,
  SystemStatusResponse,
  TrainingRequestResponse,
  TrainingType,
  WebSocketEventMessage,
} from "../../../src/api";

export type OperatorFixtureState = {
  approvedSymbols: ApprovedSymbolResponse[];
  evaluationReports: ModelEvaluationSummaryResponse[];
  modelRegistry: ModelRegistryEntryResponse[];
  mt5Status: MT5ConnectionStatusResponse;
  nextCursor: number;
  nextEvaluationId: number;
  nextTrainingRequestId: number;
  nextTrainingJobId: number;
  positions: PaperTradePositionResponse[];
  session: SessionResponse;
  signals: PaperTradeSignalResponse[];
  systemStatus: SystemStatusResponse;
  tradingStatus: PaperTradingStatusResponse;
  validationResult: SymbolValidationResponse | null;
};

export function createOperatorFixtureState(): OperatorFixtureState {
  return {
    approvedSymbols: [],
    evaluationReports: [],
    modelRegistry: [],
    mt5Status: {
      status: "connected",
      account_login: 123456,
      server_name: "Broker-Demo",
      account_name: "Practice Demo",
      account_currency: "USD",
      leverage: 100,
      is_demo: true,
      trade_allowed: true,
      paper_trading_allowed: true,
      reason: null,
      details: {},
    },
    nextCursor: 1,
    nextEvaluationId: 300,
    nextTrainingRequestId: 600,
    nextTrainingJobId: 900,
    positions: [],
    session: {
      authenticated: true,
      auth_mode: "disabled",
      subject: "operator",
      roles: ["operator"],
    },
    signals: [],
    systemStatus: {
      service: "api",
      status: "ok",
      environment: "test",
      paper_trading_only: true,
      components: {},
    },
    tradingStatus: {
      enabled: false,
      connection_status: "connected",
      account_login: 123456,
      server_name: "Broker-Demo",
      account_name: "Practice Demo",
      is_demo: true,
      is_trade_allowed: true,
      paper_trading_allowed: false,
      reason: "Trading stays blocked until a model is approved for the requested symbol.",
      approved_symbol_count: 0,
      accepted_signal_count: 0,
      open_order_count: 0,
      open_position_count: 0,
      last_started_at: null,
      last_started_by: null,
      last_stopped_at: null,
      last_stopped_by: null,
    },
    validationResult: null,
  };
}

export function createValidationResult(symbolCode: string): SymbolValidationResponse {
  return {
    validation_result_id: 501,
    symbol_id: 41,
    requested_symbol: symbolCode,
    normalized_input: symbolCode,
    normalized_symbol: symbolCode,
    provider: "mock_mt5",
    is_valid: true,
    reason: null,
    base_currency: symbolCode.slice(0, 3),
    quote_currency: symbolCode.slice(3, 6),
    details: {
      source: "playwright-fixture",
    },
  };
}

export function createTrainingRequestResult(
  state: OperatorFixtureState,
  symbolCode: string,
  trainingType: TrainingType,
): TrainingRequestResponse {
  const trainingRequestId = state.nextTrainingRequestId++;
  const ingestionJobId = state.nextTrainingJobId++;

  return {
    training_request_id: trainingRequestId,
    symbol_id: 41,
    symbol_code: symbolCode,
    training_type: trainingType,
    status: "queued",
    requested_timeframes: ["1m", "5m", "15m"],
    ingestion_job_id: ingestionJobId,
    ingestion_job_status: "running",
  };
}

export function applyApprovedModel(state: OperatorFixtureState, symbolCode: string): void {
  const evaluatedAt = "2026-04-04T10:00:00Z";

  state.approvedSymbols = [
    {
      approved_model_id: 81,
      symbol_id: 41,
      symbol_code: symbolCode,
      model_type: "supervised",
      model_id: 18,
      model_name: "candlestick_supervised_v2",
      algorithm: "xgboost",
      confidence: 78.6,
      risk_to_reward: 2.4,
      approved_at: evaluatedAt,
    },
  ];

  state.modelRegistry = [
    {
      model_type: "supervised",
      model_id: 18,
      symbol_id: 41,
      symbol_code: symbolCode,
      dataset_version_id: 12,
      feature_set_id: 22,
      training_job_id: 915,
      model_name: "candlestick_supervised_v2",
      version_tag: "v2",
      algorithm: "xgboost",
      status: "approved",
      storage_uri: "artifacts://candlestick-supervised-v2",
      approved_model_id: 81,
      is_active_approval: true,
      created_at: "2026-04-04T09:40:00Z",
    },
  ];

  state.evaluationReports = [
    {
      evaluation_id: state.nextEvaluationId++,
      model_type: "supervised",
      model_id: 18,
      symbol_id: 41,
      symbol_code: symbolCode,
      dataset_version_id: 12,
      evaluation_type: "validation",
      confidence: 78.6,
      risk_to_reward: 2.4,
      sample_size: 250,
      max_drawdown: 3.2,
      approved: true,
      decision_reasons: [],
      evaluated_at: evaluatedAt,
    },
  ];

  state.tradingStatus = {
    ...state.tradingStatus,
    paper_trading_allowed: true,
    reason: null,
    approved_symbol_count: 1,
  };
}

export function setPaperTradingRuntime(
  state: OperatorFixtureState,
  enabled: boolean,
): PaperTradingStatusResponse {
  const timestamp = "2026-04-04T11:00:00Z";

  state.tradingStatus = {
    ...state.tradingStatus,
    enabled,
    last_started_at: enabled ? timestamp : state.tradingStatus.last_started_at,
    last_started_by: enabled ? "playwright-operator" : state.tradingStatus.last_started_by,
    last_stopped_at: enabled ? state.tradingStatus.last_stopped_at : timestamp,
    last_stopped_by: enabled ? state.tradingStatus.last_stopped_by : "playwright-operator",
  };

  if (enabled) {
    state.signals = [
      {
        signal_id: 71,
        approved_model_id: 81,
        symbol_id: 41,
        symbol_code: "EURUSD",
        timeframe: "5m",
        side: "long",
        status: "accepted",
        signal_time: timestamp,
        confidence: 78.6,
        risk_to_reward: 2.4,
        entry_price: 1.0831,
        stop_loss: 1.0821,
        take_profit: 1.0855,
        rationale: {
          pattern: "bullish_engulfing",
        },
      },
    ];
    state.positions = [
      {
        position_id: 19,
        order_id: 44,
        symbol_id: 41,
        symbol_code: "EURUSD",
        side: "long",
        status: "open",
        opened_at: timestamp,
        closed_at: null,
        quantity: 0.1,
        open_price: 1.0831,
        close_price: null,
        stop_loss: 1.0821,
        take_profit: 1.0855,
        unrealized_pnl: 0.0019,
        realized_pnl: null,
      },
    ];
    state.tradingStatus = {
      ...state.tradingStatus,
      accepted_signal_count: 1,
      open_order_count: 1,
      open_position_count: 1,
    };
  } else {
    state.tradingStatus = {
      ...state.tradingStatus,
      accepted_signal_count: 0,
      open_order_count: 0,
      open_position_count: 0,
    };
  }

  return state.tradingStatus;
}

export function buildEventMessage(
  state: OperatorFixtureState,
  input: {
    entityId: string;
    entityType: string;
    eventType: string;
    payload: EventEnvelope["payload"];
  },
): WebSocketEventMessage {
  return {
    delivery: "live",
    event: {
      cursor: state.nextCursor++,
      event_id: `evt-${state.nextCursor}`,
      event_type: input.eventType,
      occurred_at: "2026-04-04T10:30:00Z",
      entity_type: input.entityType,
      entity_id: input.entityId,
      payload: input.payload,
    },
  };
}
