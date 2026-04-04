import { type FormEvent, useEffect, useState } from "react";

import type {
  SymbolValidationResponse,
  Timeframe,
  TrainingRequestResponse,
  TrainingType,
  WebSocketEventMessage,
} from "../../api";
import { APIError, buildEventsWebSocketUrl, createAPIClient } from "../../api";
import { workspacePageMeta, parseWorkspaceViewFromHash } from "./navigation";
import { WorkspaceHeader } from "./WorkspaceHeader";
import { WorkspaceSidebar } from "./WorkspaceSidebar";
import { OverviewPage } from "./pages/OverviewPage";
import { ModelsPage } from "./pages/ModelsPage";
import { PipelinePage } from "./pages/PipelinePage";
import { SymbolsPage } from "./pages/SymbolsPage";
import { SystemPage } from "./pages/SystemPage";
import { TradingPage } from "./pages/TradingPage";
import {
  emptyOperatorData,
  type LiveFeedState,
  type QueueViewModel,
  type TradingAction,
  type WorkspaceAccess,
  type WorkspaceView,
} from "./types";
import {
  buildAlertSnapshots,
  buildEventRow,
  buildPipelineStageSnapshots,
  buildQueueRowFromEvent,
  buildRuntimeMetrics,
  buildSymbolSnapshots,
  buildWorkflowStages,
  shouldRefreshOperatorData,
  timeframeSort,
  upsertQueueRow,
} from "./view-models";

const eventTopics = [
  "ingestion_progress",
  "preprocessing_progress",
  "training_progress",
  "approval_status",
  "signal_event",
  "position_update",
  "equity_update",
  "alert",
];

export function OverviewWorkspace({
  onSignOut,
  workspace,
}: {
  onSignOut: () => void;
  workspace: WorkspaceAccess;
}) {
  const [currentView, setCurrentView] = useState<WorkspaceView>(() =>
    typeof window === "undefined" ? "overview" : parseWorkspaceViewFromHash(window.location.hash),
  );
  const [operatorData, setOperatorData] = useState(emptyOperatorData);
  const [refreshError, setRefreshError] = useState<string | null>(null);
  const [isRefreshingOperatorData, setIsRefreshingOperatorData] = useState(true);
  const [liveFeedState, setLiveFeedState] = useState<LiveFeedState>("connecting");
  const [liveEventRows, setLiveEventRows] = useState<ReturnType<typeof buildEventRow>[]>([]);
  const [queueState, setQueueState] = useState<QueueViewModel[]>([]);
  const [symbolInput, setSymbolInput] = useState("EURUSD");
  const [trainingType, setTrainingType] = useState<TrainingType>("supervised");
  const [syncMode, setSyncMode] = useState<"backfill" | "incremental">("incremental");
  const [lookbackBars, setLookbackBars] = useState(500);
  const [selectedTimeframes, setSelectedTimeframes] = useState<Timeframe[]>(["1m", "5m", "15m"]);
  const [operatorNotes, setOperatorNotes] = useState("");
  const [isValidatingSymbol, setIsValidatingSymbol] = useState(false);
  const [validationError, setValidationError] = useState<string | null>(null);
  const [validationResult, setValidationResult] = useState<SymbolValidationResponse | null>(null);
  const [isRequestingTraining, setIsRequestingTraining] = useState(false);
  const [trainingError, setTrainingError] = useState<string | null>(null);
  const [trainingResult, setTrainingResult] = useState<TrainingRequestResponse | null>(null);
  const [activeTradingAction, setActiveTradingAction] = useState<TradingAction | null>(null);
  const [tradingActionError, setTradingActionError] = useState<string | null>(null);

  const {
    approvedSymbols,
    evaluationReports,
    modelRegistry,
    mt5Status,
    positions,
    signals,
    systemStatus,
    tradingStatus,
  } = operatorData;

  useEffect(() => {
    if (typeof window === "undefined") {
      return;
    }

    const handleHashChange = () => {
      setCurrentView(parseWorkspaceViewFromHash(window.location.hash));
    };

    handleHashChange();
    window.addEventListener("hashchange", handleHashChange);
    return () => {
      window.removeEventListener("hashchange", handleHashChange);
    };
  }, []);

  async function refreshOperatorData(options?: { quiet?: boolean }) {
    const quiet = options?.quiet ?? false;

    if (!quiet) {
      setIsRefreshingOperatorData(true);
    }
    setRefreshError(null);

    try {
      const client = createAPIClient({
        baseUrl: workspace.apiBaseUrl,
        token: workspace.token,
      });

      const [
        nextSystemStatus,
        nextMT5Status,
        nextApprovedSymbols,
        nextModelRegistry,
        nextEvaluationReports,
        nextTradingStatus,
        nextSignals,
        nextPositions,
      ] = await Promise.all([
        client.getSystemStatus(),
        client.getMT5Status(),
        client.listApprovedSymbols(),
        client.listModels(),
        client.listEvaluationReports(),
        client.getTradingStatus(),
        client.listSignals(),
        client.listPositions(),
      ]);

      setOperatorData({
        systemStatus: nextSystemStatus,
        mt5Status: nextMT5Status,
        approvedSymbols: nextApprovedSymbols,
        modelRegistry: nextModelRegistry,
        evaluationReports: nextEvaluationReports,
        tradingStatus: nextTradingStatus,
        signals: nextSignals.signals,
        positions: nextPositions.positions,
      });
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Unable to refresh operator workspace data.";
      setRefreshError(message);
    } finally {
      if (!quiet) {
        setIsRefreshingOperatorData(false);
      }
    }
  }

  useEffect(() => {
    void refreshOperatorData();
  }, [workspace.apiBaseUrl, workspace.token]);

  useEffect(() => {
    const websocket = new WebSocket(
      buildEventsWebSocketUrl(
        {
          baseUrl: workspace.apiBaseUrl,
          token: workspace.token,
        },
        eventTopics,
      ),
    );

    setLiveFeedState("connecting");

    websocket.onopen = () => {
      setLiveFeedState("live");
    };

    websocket.onmessage = (messageEvent) => {
      const message = JSON.parse(messageEvent.data) as WebSocketEventMessage;
      const eventRow = buildEventRow(message);
      const queueRow = buildQueueRowFromEvent(message);

      setLiveEventRows((currentRows) => [eventRow, ...currentRows].slice(0, 8));

      if (queueRow) {
        setQueueState((currentRows) => upsertQueueRow(currentRows, queueRow));
      }

      if (shouldRefreshOperatorData(message.event.event_type)) {
        void refreshOperatorData({ quiet: true });
      }
    };

    websocket.onerror = () => {
      setLiveFeedState("offline");
    };

    websocket.onclose = () => {
      setLiveFeedState("offline");
    };

    return () => {
      websocket.close();
    };
  }, [workspace.apiBaseUrl, workspace.token]);

  async function handleValidateSymbol(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsValidatingSymbol(true);
    setValidationError(null);
    setTrainingError(null);

    try {
      const client = createAPIClient({
        baseUrl: workspace.apiBaseUrl,
        token: workspace.token,
      });
      const result = await client.validateSymbol(symbolInput);
      setValidationResult(result);
      if (result.normalized_symbol) {
        setSymbolInput(result.normalized_symbol);
      }
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Unable to validate the requested symbol.";
      setValidationError(message);
    } finally {
      setIsValidatingSymbol(false);
    }
  }

  async function handleRequestTraining(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!validationResult?.is_valid || !validationResult.normalized_symbol) {
      setTrainingError("Validate a symbol successfully before requesting training.");
      return;
    }

    if (selectedTimeframes.length === 0) {
      setTrainingError("Choose at least one timeframe before requesting training.");
      return;
    }

    setIsRequestingTraining(true);
    setTrainingError(null);

    try {
      const client = createAPIClient({
        baseUrl: workspace.apiBaseUrl,
        token: workspace.token,
      });
      const result = await client.requestTraining({
        symbol_code: validationResult.normalized_symbol,
        training_type: trainingType,
        timeframes: selectedTimeframes,
        sync_mode: syncMode,
        lookback_bars: lookbackBars,
        notes: operatorNotes.trim() || null,
        priority: 100,
      });
      setTrainingResult(result);
      setQueueState((currentRows) =>
        upsertQueueRow(currentRows, {
          key: `ingestion_job-${result.ingestion_job_id}`,
          label: `Ingestion queue · ${result.symbol_code}`,
          owner: `training_request/${result.training_request_id}`,
          progress: 0,
          status: result.ingestion_job_status === "succeeded" ? "healthy" : "watch",
          updatedAt: "just now",
        }),
      );
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Unable to create a training request.";
      setTrainingError(message);
    } finally {
      setIsRequestingTraining(false);
    }
  }

  async function handleTradingAction(action: TradingAction) {
    setActiveTradingAction(action);
    setTradingActionError(null);

    try {
      const client = createAPIClient({
        baseUrl: workspace.apiBaseUrl,
        token: workspace.token,
      });

      if (action === "start") {
        await client.startPaperTrading();
      } else if (action === "stop") {
        await client.stopPaperTrading();
      } else {
        await client.syncPaperTrading();
      }

      await refreshOperatorData({ quiet: true });
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Unable to change paper-trading state.";
      setTradingActionError(message);
    } finally {
      setActiveTradingAction(null);
    }
  }

  function toggleTimeframe(timeframe: Timeframe) {
    setSelectedTimeframes((currentTimeframes) =>
      currentTimeframes.includes(timeframe)
        ? currentTimeframes.filter((item) => item !== timeframe)
        : [...currentTimeframes, timeframe].sort(timeframeSort),
    );
  }

  function handleNavigate(view: WorkspaceView) {
    setCurrentView(view);
    if (typeof window !== "undefined") {
      window.location.hash = `workspace/${view}`;
    }
  }

  const runtimeMetrics = buildRuntimeMetrics({
    approvedSymbolCount: approvedSymbols.length,
    liveFeedState,
    session: workspace.session,
    systemStatus,
    tradingStatus,
  });
  const visibleWorkflowStages = buildWorkflowStages({
    approvedSymbols,
    evaluationReports,
    liveFeedState,
    tradingStatus,
    trainingResult,
    validationResult,
  });
  const visiblePipelineStages = buildPipelineStageSnapshots({
    liveEventRows,
    queueState,
    trainingResult,
    validationResult,
  });
  const visibleSymbolSnapshots = buildSymbolSnapshots({
    approvedSymbols,
    validationResult,
  });
  const visibleAlerts = buildAlertSnapshots({
    liveFeedState,
    mt5Status,
    refreshError,
    tradingActionError,
    tradingStatus,
  });
  const pageMeta = workspacePageMeta[currentView];

  return (
    <div className="workspace">
      <WorkspaceSidebar
        currentView={currentView}
        onNavigate={handleNavigate}
        onSignOut={onSignOut}
        workspace={workspace}
      />

      <section className="workspace-main">
        <WorkspaceHeader
          description={pageMeta.description}
          kicker={pageMeta.kicker}
          liveFeedState={liveFeedState}
          title={pageMeta.title}
          workspace={workspace}
        />

        {currentView === "overview" ? (
          <OverviewPage
            activeTradingAction={activeTradingAction}
            alerts={visibleAlerts}
            approvedSymbols={approvedSymbols}
            evaluationReports={evaluationReports}
            isRefreshingOperatorData={isRefreshingOperatorData}
            isRequestingTraining={isRequestingTraining}
            isValidatingSymbol={isValidatingSymbol}
            liveEventRows={liveEventRows}
            lookbackBars={lookbackBars}
            metrics={runtimeMetrics}
            modelRegistry={modelRegistry}
            mt5Status={mt5Status}
            onLookbackBarsChange={setLookbackBars}
            onOperatorNotesChange={setOperatorNotes}
            onRefreshOperatorData={() => {
              void refreshOperatorData();
            }}
            onRequestTraining={handleRequestTraining}
            onSymbolInputChange={setSymbolInput}
            onSyncModeChange={setSyncMode}
            onTimeframeToggle={toggleTimeframe}
            onTradingAction={(action) => {
              void handleTradingAction(action);
            }}
            onTrainingTypeChange={setTrainingType}
            onValidateSymbol={handleValidateSymbol}
            operatorNotes={operatorNotes}
            positions={positions}
            queueState={queueState}
            refreshError={refreshError}
            selectedTimeframes={selectedTimeframes}
            signals={signals}
            symbolInput={symbolInput}
            symbolSnapshots={visibleSymbolSnapshots}
            syncMode={syncMode}
            tradingActionError={tradingActionError}
            trainingError={trainingError}
            tradingStatus={tradingStatus}
            trainingResult={trainingResult}
            trainingType={trainingType}
            validationError={validationError}
            validationResult={validationResult}
            workflowStages={visibleWorkflowStages}
          />
        ) : null}

        {currentView === "symbols" ? (
          <SymbolsPage
            isRequestingTraining={isRequestingTraining}
            isValidatingSymbol={isValidatingSymbol}
            liveEventRows={liveEventRows}
            lookbackBars={lookbackBars}
            onLookbackBarsChange={setLookbackBars}
            onOperatorNotesChange={setOperatorNotes}
            onRequestTraining={handleRequestTraining}
            onSymbolInputChange={setSymbolInput}
            onSyncModeChange={setSyncMode}
            onTimeframeToggle={toggleTimeframe}
            onTrainingTypeChange={setTrainingType}
            onValidateSymbol={handleValidateSymbol}
            operatorNotes={operatorNotes}
            queueState={queueState}
            selectedTimeframes={selectedTimeframes}
            symbolInput={symbolInput}
            symbolSnapshots={visibleSymbolSnapshots}
            syncMode={syncMode}
            trainingError={trainingError}
            trainingResult={trainingResult}
            trainingType={trainingType}
            validationError={validationError}
            validationResult={validationResult}
          />
        ) : null}

        {currentView === "pipeline" ? (
          <PipelinePage
            liveEventRows={liveEventRows}
            pipelineStages={visiblePipelineStages}
            queueState={queueState}
            trainingResult={trainingResult}
            validationResult={validationResult}
            workflowStages={visibleWorkflowStages}
          />
        ) : null}

        {currentView === "models" ? (
          <ModelsPage
            approvedSymbols={approvedSymbols}
            evaluationReports={evaluationReports}
            modelRegistry={modelRegistry}
          />
        ) : null}

        {currentView === "trading" ? (
          <TradingPage
            activeTradingAction={activeTradingAction}
            isRefreshingOperatorData={isRefreshingOperatorData}
            onTradingAction={(action) => {
              void handleTradingAction(action);
            }}
            positions={positions}
            signals={signals}
            tradingActionError={tradingActionError}
            tradingStatus={tradingStatus}
          />
        ) : null}

        {currentView === "system" ? (
          <SystemPage
            alerts={visibleAlerts}
            approvedSymbolCount={approvedSymbols.length}
            isRefreshingOperatorData={isRefreshingOperatorData}
            liveEventRows={liveEventRows}
            mt5Status={mt5Status}
            onRefreshOperatorData={() => {
              void refreshOperatorData();
            }}
            refreshError={refreshError}
            tradingStatus={tradingStatus}
          />
        ) : null}
      </section>
    </div>
  );
}
