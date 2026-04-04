import type {
  ApprovedSymbolResponse,
  ModelEvaluationSummaryResponse,
  MT5ConnectionStatusResponse,
  PaperTradingStatusResponse,
  SessionResponse,
  SymbolValidationResponse,
  SystemStatusResponse,
  TrainingRequestResponse,
  WebSocketEventMessage,
} from "../../api";
import type {
  AlertSnapshot,
  EventRow,
  QueueRow,
  SnapshotMetric,
  SymbolSnapshot,
  WorkflowStage,
} from "../../demo-state";
import { alertSnapshots, workflowStages } from "../../demo-state";
import type { LiveFeedState, PipelineStageSnapshot, QueueViewModel } from "./types";

export function buildRuntimeMetrics({
  approvedSymbolCount,
  liveFeedState,
  session,
  systemStatus,
  tradingStatus,
}: {
  approvedSymbolCount: number;
  liveFeedState: LiveFeedState;
  session: SessionResponse;
  systemStatus: SystemStatusResponse | null;
  tradingStatus: PaperTradingStatusResponse | null;
}): SnapshotMetric[] {
  return [
    {
      label: "Operator session",
      value: session.auth_mode === "disabled" ? "Local mode" : "Token mode",
      detail: `${session.subject} · roles: ${session.roles.join(", ") || "operator"}`,
    },
    {
      label: "Approved symbols",
      value: String(approvedSymbolCount),
      detail: approvedSymbolCount
        ? "Only these symbols are eligible for paper-trade execution."
        : "Trading stays blocked until at least one symbol is approved.",
    },
    {
      label: "Paper runtime",
      value: tradingStatus?.enabled ? "Enabled" : tradingStatus?.paper_trading_allowed ? "Ready" : "Blocked",
      detail:
        tradingStatus?.reason ??
        "Demo verification plus approved-model gating decide whether the runtime can start.",
    },
    {
      label: "Realtime feed",
      value: liveFeedState === "live" ? "Connected" : liveFeedState === "connecting" ? "Dialing" : "Offline",
      detail: systemStatus
        ? `${systemStatus.environment} · ${systemStatus.status}`
        : "Waiting for system status response from /api/v1/system/status.",
    },
  ];
}

export function buildWorkflowStages({
  approvedSymbols,
  evaluationReports,
  liveFeedState,
  tradingStatus,
  trainingResult,
  validationResult,
}: {
  approvedSymbols: ApprovedSymbolResponse[];
  evaluationReports: ModelEvaluationSummaryResponse[];
  liveFeedState: LiveFeedState;
  tradingStatus: PaperTradingStatusResponse | null;
  trainingResult: TrainingRequestResponse | null;
  validationResult: SymbolValidationResponse | null;
}): WorkflowStage[] {
  return workflowStages.map((stage) => {
    if (stage.title === "Validate symbol" && validationResult) {
      return {
        ...stage,
        status: validationResult.is_valid ? "done" : "active",
        detail: validationResult.is_valid
          ? `${validationResult.normalized_symbol ?? validationResult.requested_symbol} was normalized and is available for backend workflows.`
          : validationResult.reason ?? "Validation failed for the requested symbol.",
        metric: validationResult.is_valid ? "validated by API" : "fix symbol input",
      };
    }

    if (stage.title === "Ingest candles" && trainingResult) {
      return {
        ...stage,
        status: trainingResult.ingestion_job_status === "succeeded" ? "done" : "active",
        detail: `Training request #${trainingResult.training_request_id} opened ingestion job #${trainingResult.ingestion_job_id} for ${trainingResult.symbol_code}.`,
        metric: `job ${trainingResult.ingestion_job_status}`,
      };
    }

    if (stage.title === "Train" && trainingResult) {
      return {
        ...stage,
        status: liveFeedState === "live" ? "active" : "queued",
        detail: "Worker-side training progress will surface here as soon as downstream jobs begin broadcasting.",
        metric: liveFeedState === "live" ? "watch live rail" : "waiting for feed",
      };
    }

    if (stage.title === "Evaluate") {
      const latestReport = evaluationReports[0];
      return {
        ...stage,
        status: latestReport ? "done" : trainingResult ? "active" : stage.status,
        detail: latestReport
          ? `${latestReport.symbol_code} posted a ${latestReport.evaluation_type} report with ${formatPercentage(latestReport.confidence)} confidence.`
          : stage.detail,
        metric: latestReport ? formatRatio(latestReport.risk_to_reward) : stage.metric,
      };
    }

    if (stage.title === "Approve") {
      const latestApproved = approvedSymbols[0];
      return {
        ...stage,
        status: latestApproved ? "done" : evaluationReports.length > 0 ? "active" : stage.status,
        detail: latestApproved
          ? `${latestApproved.symbol_code} cleared approval with ${formatPercentage(latestApproved.confidence)} confidence and ${formatRatio(latestApproved.risk_to_reward)}.`
          : stage.detail,
        metric: latestApproved ? `${approvedSymbols.length} approved` : stage.metric,
      };
    }

    if (stage.title === "Paper trade") {
      return {
        ...stage,
        status: tradingStatus?.enabled ? "active" : approvedSymbols.length > 0 ? "done" : stage.status,
        detail: tradingStatus?.enabled
          ? "The runtime is active and will continue to enforce approval plus demo-account guards."
          : approvedSymbols.length > 0
            ? "The runtime can be started because approved symbols are present and visible from the UI."
            : stage.detail,
        metric: tradingStatus?.enabled
          ? `${tradingStatus.open_position_count} live positions`
          : approvedSymbols.length > 0
            ? "ready to start runtime"
            : stage.metric,
      };
    }

    return stage;
  });
}

export function buildSymbolSnapshots({
  approvedSymbols,
  validationResult,
}: {
  approvedSymbols: ApprovedSymbolResponse[];
  validationResult: SymbolValidationResponse | null;
}): SymbolSnapshot[] {
  const rows = new Map<string, SymbolSnapshot>();

  for (const approvedSymbol of approvedSymbols) {
    rows.set(approvedSymbol.symbol_code, {
      code: approvedSymbol.symbol_code,
      validation: "Validated",
      approval: "Approved",
      confidence: formatPercentage(approvedSymbol.confidence),
      riskReward: formatRatio(approvedSymbol.risk_to_reward),
      nextAction: "Ready for paper desk",
    });
  }

  if (validationResult) {
    const symbolCode = validationResult.normalized_symbol ?? validationResult.requested_symbol.toUpperCase();
    if (!rows.has(symbolCode)) {
      rows.set(symbolCode, {
        code: symbolCode,
        validation: validationResult.is_valid ? "Validated" : "Rejected",
        approval: validationResult.is_valid ? "Pending" : "Blocked",
        confidence: "—",
        riskReward: "—",
        nextAction: validationResult.is_valid
          ? "Await evaluation and approval"
          : validationResult.reason ?? "Review symbol input",
      });
    }
  }

  return Array.from(rows.values());
}

export function buildAlertSnapshots({
  liveFeedState,
  mt5Status,
  refreshError,
  tradingActionError,
  tradingStatus,
}: {
  liveFeedState: LiveFeedState;
  mt5Status: MT5ConnectionStatusResponse | null;
  refreshError: string | null;
  tradingActionError: string | null;
  tradingStatus: PaperTradingStatusResponse | null;
}): AlertSnapshot[] {
  const runtimeAlerts = [...alertSnapshots];

  if (refreshError) {
    runtimeAlerts.unshift({
      title: "Workspace refresh degraded",
      severity: "warning",
      detail: refreshError,
    });
  }

  if (tradingActionError) {
    runtimeAlerts.unshift({
      title: "Trading action blocked",
      severity: "warning",
      detail: tradingActionError,
    });
  }

  if (liveFeedState === "offline") {
    runtimeAlerts.unshift({
      title: "Live feed disconnected",
      severity: "warning",
      detail: "The workspace can still submit API requests, but worker progress will not stream until the WebSocket reconnects.",
    });
  }

  if (tradingStatus && !tradingStatus.paper_trading_allowed) {
    runtimeAlerts.unshift({
      title: "Paper-trading gate closed",
      severity: "warning",
      detail:
        tradingStatus.reason ??
        "The backend is refusing to start the paper runtime because the safety gates are not satisfied yet.",
    });
  } else if (mt5Status && !mt5Status.paper_trading_allowed) {
    runtimeAlerts.unshift({
      title: "Demo safety guard active",
      severity: "warning",
      detail:
        mt5Status.reason ??
        "The API is refusing to open the paper-trading lane because the MT5 account is not confirmed as demo-safe.",
    });
  }

  return runtimeAlerts.slice(0, 5);
}

export function buildLiveFeedLabel(liveFeedState: LiveFeedState): string {
  if (liveFeedState === "live") {
    return "WebSocket feed connected";
  }
  if (liveFeedState === "connecting") {
    return "Connecting to WebSocket feed";
  }
  return "WebSocket feed unavailable";
}

export function buildPipelineStageSnapshots({
  liveEventRows,
  queueState,
  trainingResult,
  validationResult,
}: {
  liveEventRows: EventRow[];
  queueState: QueueViewModel[];
  trainingResult: TrainingRequestResponse | null;
  validationResult: SymbolValidationResponse | null;
}): PipelineStageSnapshot[] {
  return [
    buildPipelineStageSnapshot({
      eventKeyword: "ingestion_progress",
      fallbackDetail: validationResult?.is_valid
        ? `${validationResult.normalized_symbol ?? validationResult.requested_symbol} is validated and waiting for candle-sync progress.`
        : "Validate a symbol first so the ingestion worker can begin the background handoff.",
      fallbackNote: trainingResult
        ? `Training request #${trainingResult.training_request_id} opened ingestion job #${trainingResult.ingestion_job_id}.`
        : "No ingestion job opened yet.",
      key: "ingestion",
      liveEventRows,
      queueLabelPrefix: "Ingestion queue",
      queueState,
      title: "Ingestion",
    }),
    buildPipelineStageSnapshot({
      eventKeyword: "preprocessing_progress",
      fallbackDetail: trainingResult
        ? `Preprocessing will begin after ingestion closes for ${trainingResult.symbol_code}.`
        : "Preprocessing remains idle until a training request opens a validated downstream workflow.",
      fallbackNote: trainingResult
        ? "Waiting for ingestion-to-preprocessing handoff."
        : "No preprocessing job opened yet.",
      key: "preprocessing",
      liveEventRows,
      queueLabelPrefix: "Preprocessing queue",
      queueState,
      title: "Preprocessing",
    }),
    buildPipelineStageSnapshot({
      eventKeyword: "training_progress",
      fallbackDetail: trainingResult
        ? "Training remains worker-driven and will surface here as soon as preprocessing finishes and models begin broadcasting."
        : "Training stays idle until validation, ingestion, and preprocessing all hand off successfully.",
      fallbackNote: trainingResult ? `Requested mode: ${trainingResult.training_type}.` : "No training job opened yet.",
      key: "training",
      liveEventRows,
      queueLabelPrefix: "Training queue",
      queueState,
      title: "Training",
    }),
  ];
}

export function buildEventRow(message: WebSocketEventMessage): EventRow {
  const payloadStatus = readString(message.event.payload.status);
  const symbolCode = readString(message.event.payload.symbol_code);
  const progressPercent = readNumber(message.event.payload.progress_percent);

  return {
    title: `${message.event.event_type} · ${message.delivery}`,
    tone: mapEventTypeToTone(message.event.event_type, payloadStatus),
    timestamp: formatClockTime(message.event.occurred_at),
    detail: buildEventDetail(message.event.event_type, symbolCode, payloadStatus, progressPercent),
  };
}

export function buildQueueRowFromEvent(message: WebSocketEventMessage): QueueViewModel | null {
  if (
    message.event.event_type !== "ingestion_progress" &&
    message.event.event_type !== "preprocessing_progress" &&
    message.event.event_type !== "training_progress"
  ) {
    return null;
  }

  const jobId = readNumber(message.event.payload.job_id);
  const symbolCode = readString(message.event.payload.symbol_code);
  const progressPercent = readNumber(message.event.payload.progress_percent) ?? 0;
  const status = readString(message.event.payload.status);

  return {
    key: `${message.event.entity_type ?? message.event.event_type}-${message.event.entity_id ?? jobId ?? "live"}`,
    label: buildQueueLabel(message.event.event_type, symbolCode),
    owner: message.event.entity_type ?? "worker",
    progress: progressPercent,
    status: mapJobStatusToQueueStatus(status),
    updatedAt: formatClockTime(message.event.occurred_at),
  };
}

export function upsertQueueRow(
  currentRows: QueueViewModel[],
  nextRow: QueueViewModel,
): QueueViewModel[] {
  const remainingRows = currentRows.filter((row) => row.key !== nextRow.key);
  return [nextRow, ...remainingRows].slice(0, 6);
}

export function shouldRefreshOperatorData(eventType: string): boolean {
  return (
    eventType === "approval_status" ||
    eventType === "signal_event" ||
    eventType === "position_update" ||
    eventType === "equity_update"
  );
}

export function mapJobStatusToQueueStatus(status: string | null): QueueRow["status"] {
  if (status === "succeeded") {
    return "healthy";
  }
  if (status === "failed" || status === "cancelled" || status === "rejected") {
    return "blocked";
  }
  return "watch";
}

export function mapSignalStatusToQueueStatus(status: string): QueueRow["status"] {
  if (status === "accepted" || status === "executed") {
    return "healthy";
  }
  if (status === "rejected" || status === "expired") {
    return "blocked";
  }
  return "watch";
}

export function formatPercentage(value: number): string {
  return `${value.toFixed(1)}%`;
}

export function formatRatio(value: number): string {
  return `${value.toFixed(1)}R`;
}

export function formatClockTime(rawValue: string): string {
  const value = new Date(rawValue);
  return value.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    timeZoneName: "short",
  });
}

export function formatShortDateTime(rawValue: string): string {
  const value = new Date(rawValue);
  return value.toLocaleString([], {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export function formatQuantity(value: number): string {
  return `${value.toFixed(2)} lots`;
}

export function formatPnL(value: number | null): string {
  if (value === null) {
    return "—";
  }
  return `${value >= 0 ? "+" : ""}${value.toFixed(5)}`;
}

export function timeframeSort(left: string, right: string): number {
  return ["1m", "5m", "15m"].indexOf(left) - ["1m", "5m", "15m"].indexOf(right);
}

function buildQueueLabel(eventType: string, symbolCode: string | null): string {
  const prefix =
    eventType === "ingestion_progress"
      ? "Ingestion queue"
      : eventType === "preprocessing_progress"
        ? "Preprocessing queue"
        : "Training queue";
  return symbolCode ? `${prefix} · ${symbolCode}` : prefix;
}

function mapEventTypeToTone(eventType: string, status: string | null): EventRow["tone"] {
  if (status === "failed" || status === "rejected" || eventType === "alert") {
    return "warning";
  }
  if (
    status === "succeeded" ||
    status === "accepted" ||
    status === "executed" ||
    eventType === "approval_status"
  ) {
    return "success";
  }
  return "info";
}

function buildEventDetail(
  eventType: string,
  symbolCode: string | null,
  status: string | null,
  progressPercent: number | null,
): string {
  const subject = symbolCode ?? "The active workflow";
  const progressSuffix = progressPercent !== null ? ` at ${progressPercent}%` : "";

  if (eventType === "approval_status") {
    return `${subject} emitted an approval-state change${status ? ` with status ${status}` : ""}.`;
  }

  if (eventType === "signal_event") {
    return `${subject} published a signal update${status ? ` with status ${status}` : ""}.`;
  }

  if (eventType === "position_update") {
    return `${subject} published a position update${status ? ` with status ${status}` : ""}.`;
  }

  if (eventType === "equity_update") {
    return `${subject} pushed a fresh equity snapshot.`;
  }

  if (eventType === "alert") {
    return `${subject} emitted an operator alert${status ? ` with status ${status}` : ""}.`;
  }

  return `${subject} reported ${eventType.replace("_", " ")}${status ? ` as ${status}` : ""}${progressSuffix}.`;
}

function buildPipelineStageSnapshot({
  eventKeyword,
  fallbackDetail,
  fallbackNote,
  key,
  liveEventRows,
  queueLabelPrefix,
  queueState,
  title,
}: {
  eventKeyword: string;
  fallbackDetail: string;
  fallbackNote: string;
  key: PipelineStageSnapshot["key"];
  liveEventRows: EventRow[];
  queueLabelPrefix: string;
  queueState: QueueViewModel[];
  title: string;
}): PipelineStageSnapshot {
  const queueRow = queueState.find((row) => row.label.startsWith(queueLabelPrefix));
  const latestEvent = liveEventRows.find((row) => row.title.startsWith(eventKeyword));

  if (queueRow) {
    return {
      key,
      title,
      status: queueRow.status,
      progress: queueRow.progress,
      detail: latestEvent?.detail ?? `${queueRow.owner} is currently responsible for this stage.`,
      note: `${queueRow.progress}% complete · ${queueRow.updatedAt}`,
      updatedAt: queueRow.updatedAt,
    };
  }

  return {
    key,
    title,
    status: latestEvent?.tone === "warning" ? "blocked" : "watch",
    progress: 0,
    detail: latestEvent?.detail ?? fallbackDetail,
    note: latestEvent ? latestEvent.timestamp : fallbackNote,
    updatedAt: latestEvent?.timestamp ?? "awaiting queue handoff",
  };
}

function readString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value : null;
}

function readNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}
