export type QueueStatus = "healthy" | "watch" | "blocked";
export type StageStatus = "done" | "active" | "queued";
export type EventTone = "info" | "success" | "warning";

export type SnapshotMetric = {
  label: string;
  value: string;
  detail: string;
};

export type WorkflowStage = {
  title: string;
  status: StageStatus;
  detail: string;
  metric: string;
};

export type QueueRow = {
  label: string;
  status: QueueStatus;
  progress: number;
  owner: string;
  updatedAt: string;
};

export type EventRow = {
  title: string;
  tone: EventTone;
  timestamp: string;
  detail: string;
};

export type SymbolSnapshot = {
  code: string;
  validation: string;
  approval: string;
  confidence: string;
  riskReward: string;
  nextAction: string;
};

export type PositionSnapshot = {
  symbol: string;
  side: string;
  quantity: string;
  status: string;
  pnl: string;
};

export type AlertSnapshot = {
  title: string;
  severity: "warning" | "info";
  detail: string;
};

export const snapshotMetrics: SnapshotMetric[] = [
  {
    label: "Approved symbols",
    value: "4",
    detail: "Only symbols with threshold-cleared models can enter the paper desk.",
  },
  {
    label: "Live pipeline jobs",
    value: "7",
    detail: "Ingestion, preprocessing, training, and evaluation remain off the API thread.",
  },
  {
    label: "Paper trading runtime",
    value: "Enabled",
    detail: "Demo-only MT5 account with backend gating still enforcing approval status.",
  },
  {
    label: "Realtime feed",
    value: "12 events/min",
    detail: "Milestone 12 WebSocket stream is already shaping the operator view.",
  },
];

export const workflowStages: WorkflowStage[] = [
  {
    title: "Validate symbol",
    status: "done",
    detail: "EURUSD was normalized against MT5 and stored as trade-eligible metadata.",
    metric: "demo-only account confirmed",
  },
  {
    title: "Ingest candles",
    status: "done",
    detail: "1m / 5m / 15m candles are deduplicated and stored with UTC timestamps.",
    metric: "18,420 recent candles",
  },
  {
    title: "Preprocess",
    status: "done",
    detail: "Candlestick patterns and multi-timeframe features were packed into dataset versions.",
    metric: "dataset v2026.04.04-eu",
  },
  {
    title: "Train",
    status: "active",
    detail: "Torch MLP and PPO jobs are streaming progress through the worker broadcaster.",
    metric: "supervised 75%, rl 42%",
  },
  {
    title: "Evaluate",
    status: "queued",
    detail: "Pending automatic review against confidence, RR, and drawdown thresholds.",
    metric: "next evaluation in queue",
  },
  {
    title: "Approve",
    status: "queued",
    detail: "Approval remains blocked until confidence reaches 70% and RR reaches 2.0.",
    metric: "policy-enforced backend gate",
  },
  {
    title: "Paper trade",
    status: "queued",
    detail: "Trading lane opens only after approval and demo-account verification stay green.",
    metric: "runtime waits on approval",
  },
];

export const queueRows: QueueRow[] = [
  {
    label: "Ingestion queue",
    status: "healthy",
    progress: 100,
    owner: "worker/ingestion",
    updatedAt: "04 Apr 14:18 UTC",
  },
  {
    label: "Preprocessing queue",
    status: "healthy",
    progress: 100,
    owner: "worker/preprocessing",
    updatedAt: "04 Apr 14:21 UTC",
  },
  {
    label: "Supervised training",
    status: "watch",
    progress: 75,
    owner: "worker/supervised_training",
    updatedAt: "04 Apr 14:27 UTC",
  },
  {
    label: "RL training",
    status: "watch",
    progress: 42,
    owner: "worker/rl_training",
    updatedAt: "04 Apr 14:25 UTC",
  },
];

export const eventRows: EventRow[] = [
  {
    title: "training_progress",
    tone: "info",
    timestamp: "14:27:13 UTC",
    detail: "Supervised training job 19 emitted a 75% checkpoint with artifact write phase active.",
  },
  {
    title: "ingestion_progress",
    tone: "success",
    timestamp: "14:24:52 UTC",
    detail: "EURUSD ingestion job 41 closed successfully after UTC-normalized candle persistence.",
  },
  {
    title: "approval_status",
    tone: "warning",
    timestamp: "14:22:10 UTC",
    detail: "GBPUSD remains blocked because confidence slipped under the 70% approval floor.",
  },
  {
    title: "alert",
    tone: "warning",
    timestamp: "14:21:31 UTC",
    detail: "Paper trading sync refused to run until the account was confirmed as demo-only.",
  },
];

export const symbolSnapshots: SymbolSnapshot[] = [
  {
    code: "EURUSD",
    validation: "Validated",
    approval: "Approved",
    confidence: "78.6%",
    riskReward: "2.4R",
    nextAction: "Ready for paper desk",
  },
  {
    code: "GBPUSD",
    validation: "Validated",
    approval: "Blocked",
    confidence: "66.1%",
    riskReward: "1.9R",
    nextAction: "Retrain before approval",
  },
  {
    code: "USDJPY",
    validation: "Pending refresh",
    approval: "Queued",
    confidence: "—",
    riskReward: "—",
    nextAction: "Re-ingest 15m candles",
  },
];

export const positionSnapshots: PositionSnapshot[] = [
  {
    symbol: "EURUSD",
    side: "Long",
    quantity: "0.25 lots",
    status: "Open",
    pnl: "+0.00038",
  },
  {
    symbol: "AUDUSD",
    side: "Short",
    quantity: "0.15 lots",
    status: "Closed",
    pnl: "+0.00022",
  },
];

export const alertSnapshots: AlertSnapshot[] = [
  {
    title: "Approval gate active",
    severity: "info",
    detail: "Symbols without an approved model remain invisible to the trading runtime.",
  },
  {
    title: "Live trading blocked",
    severity: "warning",
    detail: "Backend safety guard still rejects non-demo MT5 accounts regardless of UI state.",
  },
];

export const mt5Snapshot = {
  server: "Broker-Demo",
  login: "123456",
  accountName: "Practice Demo",
  balance: "$10,000.38",
  equity: "$10,000.38",
  leverage: "1:100",
};
