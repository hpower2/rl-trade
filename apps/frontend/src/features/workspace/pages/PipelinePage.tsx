import type { SymbolValidationResponse, TrainingRequestResponse } from "../../../api";
import type { EventRow, WorkflowStage } from "../../../demo-state";
import { WorkflowRunway } from "../WorkflowRunway";
import { LiveEventSection } from "../sections/LiveEventSection";
import { PipelineSection } from "../sections/PipelineSection";
import { PipelineStageSection } from "../sections/PipelineStageSection";
import type { PipelineStageSnapshot, QueueViewModel } from "../types";

export function PipelinePage({
  liveEventRows,
  pipelineStages,
  queueState,
  trainingResult,
  validationResult,
  workflowStages,
}: {
  liveEventRows: EventRow[];
  pipelineStages: PipelineStageSnapshot[];
  queueState: QueueViewModel[];
  trainingResult: TrainingRequestResponse | null;
  validationResult: SymbolValidationResponse | null;
  workflowStages: WorkflowStage[];
}) {
  return (
    <>
      <div className="page-intro">
        <p className="section-note">
          This page is the downstream watch desk for the core milestone flow: ingestion,
          preprocessing, training, and the live operator log stay visible in one place while the
          backend workers continue to own the long-running work.
        </p>
      </div>

      <div className="detail-layout">
        <section className="detail-panel">
          <div className="section-header">
            <div>
              <p className="section-kicker">Pipeline handoff</p>
              <h2>Operator intake and current downstream status</h2>
            </div>
            <p className="section-note">
              Requests still begin in the symbol desk, but this surface keeps the worker-driven
              stages readable once background jobs take over.
            </p>
          </div>

          {validationResult ? (
            <article
              className={`response-card response-card--${validationResult.is_valid ? "success" : "warning"}`}
            >
              <div className="response-card__top">
                <strong>{validationResult.is_valid ? "Validated symbol intake" : "Validation blocked"}</strong>
                <span>{validationResult.provider}</span>
              </div>
              <p>
                Requested <code>{validationResult.requested_symbol}</code>
                {validationResult.normalized_symbol ? ` normalized to ${validationResult.normalized_symbol}.` : "."}
              </p>
              <small>
                {validationResult.reason ??
                  `${validationResult.base_currency ?? "?"}/${validationResult.quote_currency ?? "?"}`}
              </small>
            </article>
          ) : (
            <div className="empty-state empty-state--compact">
              <strong>No symbol intake yet.</strong>
              <p>Validate a symbol from the Symbols page before expecting downstream queue activity here.</p>
            </div>
          )}

          {trainingResult ? (
            <article className="response-card response-card--info">
              <div className="response-card__top">
                <strong>Current downstream handoff</strong>
                <span>{trainingResult.training_type}</span>
              </div>
              <p>
                Request #{trainingResult.training_request_id} opened ingestion job #
                {trainingResult.ingestion_job_id} for <code>{trainingResult.symbol_code}</code>.
              </p>
              <small>
                Timeframes: {trainingResult.requested_timeframes.join(", ")} · ingestion status:{" "}
                {trainingResult.ingestion_job_status}
              </small>
            </article>
          ) : (
            <div className="empty-state empty-state--compact">
              <strong>No training request has been queued yet.</strong>
              <p>The pipeline timeline fills in here once a validated symbol enters the background job flow.</p>
            </div>
          )}
        </section>

        <PipelineSection queueState={queueState} />
      </div>

      <div className="detail-layout detail-layout--single">
        <PipelineStageSection stageSnapshots={pipelineStages} />
      </div>

      <WorkflowRunway stages={workflowStages} />

      <div className="detail-layout detail-layout--single">
        <LiveEventSection liveEventRows={liveEventRows} />
      </div>
    </>
  );
}
