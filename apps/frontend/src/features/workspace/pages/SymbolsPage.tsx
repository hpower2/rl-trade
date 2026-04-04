import type { FormEvent } from "react";

import type { SymbolValidationResponse, Timeframe, TrainingRequestResponse, TrainingType } from "../../../api";
import type { EventRow, SymbolSnapshot } from "../../../demo-state";
import type { QueueViewModel } from "../types";
import { LiveEventSection } from "../sections/LiveEventSection";
import { PipelineSection } from "../sections/PipelineSection";
import { SymbolDeskSection } from "../sections/SymbolDeskSection";

export function SymbolsPage(props: {
  isRequestingTraining: boolean;
  isValidatingSymbol: boolean;
  liveEventRows: EventRow[];
  lookbackBars: number;
  onLookbackBarsChange: (value: number) => void;
  onOperatorNotesChange: (value: string) => void;
  onRequestTraining: (event: FormEvent<HTMLFormElement>) => void;
  onSymbolInputChange: (value: string) => void;
  onSyncModeChange: (value: "backfill" | "incremental") => void;
  onTimeframeToggle: (timeframe: Timeframe) => void;
  onTrainingTypeChange: (value: TrainingType) => void;
  onValidateSymbol: (event: FormEvent<HTMLFormElement>) => void;
  operatorNotes: string;
  queueState: QueueViewModel[];
  selectedTimeframes: Timeframe[];
  symbolInput: string;
  symbolSnapshots: SymbolSnapshot[];
  syncMode: "backfill" | "incremental";
  trainingError: string | null;
  trainingResult: TrainingRequestResponse | null;
  trainingType: TrainingType;
  validationError: string | null;
  validationResult: SymbolValidationResponse | null;
}) {
  return (
    <>
      <div className="page-intro">
        <p className="section-note">
          Use this page for the first half of the workflow: validate a symbol, open a training
          request, and watch ingestion or preprocessing progress arrive over the live feed.
        </p>
      </div>
      <div className="detail-layout">
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
      <div className="detail-layout detail-layout--single">
        <LiveEventSection liveEventRows={props.liveEventRows} />
      </div>
    </>
  );
}
