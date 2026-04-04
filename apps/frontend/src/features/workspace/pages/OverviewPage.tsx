import type { FormEvent } from "react";

import type { SymbolValidationResponse, Timeframe, TrainingRequestResponse, TrainingType } from "../../../api";
import type { EventRow, SymbolSnapshot, WorkflowStage } from "../../../demo-state";
import type { AlertSnapshot } from "../../../demo-state";
import type { QueueViewModel, TradingAction } from "../types";
import { MetricBand } from "../MetricBand";
import { WorkflowRunway } from "../WorkflowRunway";
import { AlertSection } from "../sections/AlertSection";
import { LiveEventSection } from "../sections/LiveEventSection";
import { MT5StatusSection } from "../sections/MT5StatusSection";
import { ModelGatesSection } from "../sections/ModelGatesSection";
import { PaperTradingSection } from "../sections/PaperTradingSection";
import { PipelineSection } from "../sections/PipelineSection";
import { SymbolDeskSection } from "../sections/SymbolDeskSection";
import type { SnapshotMetric } from "../../../demo-state";
import type {
  ApprovedSymbolResponse,
  ModelEvaluationSummaryResponse,
  ModelRegistryEntryResponse,
  MT5ConnectionStatusResponse,
  PaperTradePositionResponse,
  PaperTradeSignalResponse,
  PaperTradingStatusResponse,
} from "../../../api";

export function OverviewPage(props: {
  activeTradingAction: TradingAction | null;
  alerts: AlertSnapshot[];
  approvedSymbols: ApprovedSymbolResponse[];
  evaluationReports: ModelEvaluationSummaryResponse[];
  isRefreshingOperatorData: boolean;
  isRequestingTraining: boolean;
  isValidatingSymbol: boolean;
  liveEventRows: EventRow[];
  lookbackBars: number;
  metrics: SnapshotMetric[];
  modelRegistry: ModelRegistryEntryResponse[];
  mt5Status: MT5ConnectionStatusResponse | null;
  onLookbackBarsChange: (value: number) => void;
  onOperatorNotesChange: (value: string) => void;
  onRefreshOperatorData: () => void;
  onRequestTraining: (event: FormEvent<HTMLFormElement>) => void;
  onSymbolInputChange: (value: string) => void;
  onSyncModeChange: (value: "backfill" | "incremental") => void;
  onTimeframeToggle: (timeframe: Timeframe) => void;
  onTradingAction: (action: TradingAction) => void;
  onTrainingTypeChange: (value: TrainingType) => void;
  onValidateSymbol: (event: FormEvent<HTMLFormElement>) => void;
  operatorNotes: string;
  positions: PaperTradePositionResponse[];
  queueState: QueueViewModel[];
  refreshError: string | null;
  selectedTimeframes: Timeframe[];
  signals: PaperTradeSignalResponse[];
  symbolInput: string;
  symbolSnapshots: SymbolSnapshot[];
  syncMode: "backfill" | "incremental";
  tradingActionError: string | null;
  trainingError: string | null;
  tradingStatus: PaperTradingStatusResponse | null;
  trainingResult: TrainingRequestResponse | null;
  trainingType: TrainingType;
  validationError: string | null;
  validationResult: SymbolValidationResponse | null;
  workflowStages: WorkflowStage[];
}) {
  return (
    <>
      <MetricBand metrics={props.metrics} />
      <WorkflowRunway stages={props.workflowStages} />

      <div className="detail-layout" id="section-3">
        <SymbolDeskSection
          isRequestingTraining={props.isRequestingTraining}
          isValidatingSymbol={props.isValidatingSymbol}
          lookbackBars={props.lookbackBars}
          onLookbackBarsChange={props.onLookbackBarsChange}
          onOperatorNotesChange={props.onOperatorNotesChange}
          onRequestTraining={props.onRequestTraining}
          onSymbolInputChange={props.onSymbolInputChange}
          onSyncModeChange={props.onSyncModeChange}
          onTimeframeToggle={props.onTimeframeToggle}
          onTrainingTypeChange={props.onTrainingTypeChange}
          onValidateSymbol={props.onValidateSymbol}
          operatorNotes={props.operatorNotes}
          selectedTimeframes={props.selectedTimeframes}
          symbolInput={props.symbolInput}
          symbolSnapshots={props.symbolSnapshots}
          syncMode={props.syncMode}
          trainingError={props.trainingError}
          trainingResult={props.trainingResult}
          trainingType={props.trainingType}
          validationError={props.validationError}
          validationResult={props.validationResult}
        />
        <PipelineSection queueState={props.queueState} />
      </div>

      <div className="detail-layout" id="section-4">
        <ModelGatesSection
          approvedSymbols={props.approvedSymbols}
          evaluationReports={props.evaluationReports}
          modelRegistry={props.modelRegistry}
        />
      </div>

      <div className="detail-layout" id="section-5">
        <PaperTradingSection
          activeTradingAction={props.activeTradingAction}
          isRefreshingOperatorData={props.isRefreshingOperatorData}
          onTradingAction={props.onTradingAction}
          positions={props.positions}
          signals={props.signals}
          tradingActionError={props.tradingActionError}
          tradingStatus={props.tradingStatus}
        />
        <MT5StatusSection
          approvedSymbolCount={props.approvedSymbols.length}
          isRefreshingOperatorData={props.isRefreshingOperatorData}
          mt5Status={props.mt5Status}
          onRefresh={props.onRefreshOperatorData}
          refreshError={props.refreshError}
          tradingStatus={props.tradingStatus}
        />
      </div>

      <div className="detail-layout" id="section-6">
        <LiveEventSection liveEventRows={props.liveEventRows} />
        <AlertSection alerts={props.alerts} />
      </div>
    </>
  );
}
