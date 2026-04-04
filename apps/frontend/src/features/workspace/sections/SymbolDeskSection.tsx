import { type FormEvent } from "react";

import type { SymbolValidationResponse, Timeframe, TrainingRequestResponse, TrainingType } from "../../../api";
import type { SymbolSnapshot } from "../../../demo-state";

export function SymbolDeskSection({
  isRequestingTraining,
  isValidatingSymbol,
  lookbackBars,
  onRequestTraining,
  onSymbolInputChange,
  onSyncModeChange,
  onTimeframeToggle,
  onTrainingTypeChange,
  onValidateSymbol,
  onLookbackBarsChange,
  onOperatorNotesChange,
  operatorNotes,
  selectedTimeframes,
  symbolInput,
  symbolSnapshots,
  syncMode,
  trainingError,
  trainingResult,
  trainingType,
  validationError,
  validationResult,
}: {
  isRequestingTraining: boolean;
  isValidatingSymbol: boolean;
  lookbackBars: number;
  onRequestTraining: (event: FormEvent<HTMLFormElement>) => void;
  onSymbolInputChange: (value: string) => void;
  onSyncModeChange: (value: "backfill" | "incremental") => void;
  onTimeframeToggle: (timeframe: Timeframe) => void;
  onTrainingTypeChange: (value: TrainingType) => void;
  onValidateSymbol: (event: FormEvent<HTMLFormElement>) => void;
  onLookbackBarsChange: (value: number) => void;
  onOperatorNotesChange: (value: string) => void;
  operatorNotes: string;
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
    <section className="detail-panel">
      <div className="section-header">
        <div>
          <p className="section-kicker">Symbol desk</p>
          <h2>Validate first, then request training</h2>
        </div>
      </div>

      <div className="operator-console">
        <form className="operator-form" onSubmit={onValidateSymbol}>
          <div className="field-grid">
            <div>
              <label htmlFor="symbol-input">Symbol</label>
              <input
                id="symbol-input"
                onChange={(event) => onSymbolInputChange(event.target.value.toUpperCase())}
                placeholder="EURUSD"
                value={symbolInput}
              />
            </div>
            <div>
              <label htmlFor="training-type">Training type</label>
              <select
                id="training-type"
                onChange={(event) => onTrainingTypeChange(event.target.value as TrainingType)}
                value={trainingType}
              >
                <option value="supervised">Supervised</option>
                <option value="rl">RL</option>
              </select>
            </div>
          </div>

          <button className="primary-button" disabled={isValidatingSymbol} type="submit">
            {isValidatingSymbol ? "Validating…" : "Validate symbol"}
          </button>
        </form>

        <form className="operator-form operator-form--secondary" onSubmit={onRequestTraining}>
          <div className="field-grid field-grid--compact">
            <div>
              <label htmlFor="sync-mode">Sync mode</label>
              <select
                id="sync-mode"
                onChange={(event) => onSyncModeChange(event.target.value as "backfill" | "incremental")}
                value={syncMode}
              >
                <option value="incremental">Incremental</option>
                <option value="backfill">Backfill</option>
              </select>
            </div>
            <div>
              <label htmlFor="lookback-bars">Lookback bars</label>
              <input
                id="lookback-bars"
                max={5000}
                min={1}
                onChange={(event) => onLookbackBarsChange(Number(event.target.value))}
                type="number"
                value={lookbackBars}
              />
            </div>
          </div>

          <div>
            <span className="field-label">Timeframes</span>
            <div className="choice-row">
              {(["1m", "5m", "15m"] as Timeframe[]).map((timeframe) => (
                <label className="choice-pill" key={timeframe}>
                  <input
                    checked={selectedTimeframes.includes(timeframe)}
                    onChange={() => onTimeframeToggle(timeframe)}
                    type="checkbox"
                  />
                  <span>{timeframe}</span>
                </label>
              ))}
            </div>
          </div>

          <div>
            <label htmlFor="operator-notes">Operator notes</label>
            <textarea
              id="operator-notes"
              onChange={(event) => onOperatorNotesChange(event.target.value)}
              placeholder="Optional notes for the queued training request"
              rows={3}
              value={operatorNotes}
            />
          </div>

          <button className="primary-button" disabled={isRequestingTraining} type="submit">
            {isRequestingTraining ? "Submitting…" : "Request training"}
          </button>
        </form>
      </div>

      <p className="helper-copy">
        The UI follows the same backend sequence the API enforces: validation first, background
        ingestion second, then evaluation and approval before trading can start.
      </p>

      {validationError ? <p className="form-feedback form-feedback--error">{validationError}</p> : null}
      {trainingError ? <p className="form-feedback form-feedback--error">{trainingError}</p> : null}

      {validationResult ? (
        <article
          className={`response-card response-card--${validationResult.is_valid ? "success" : "warning"}`}
        >
          <div className="response-card__top">
            <strong>{validationResult.is_valid ? "Validation passed" : "Validation blocked"}</strong>
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
      ) : null}

      {trainingResult ? (
        <article className="response-card response-card--info">
          <div className="response-card__top">
            <strong>Training request queued</strong>
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
      ) : null}

      {symbolSnapshots.length > 0 ? (
        <div className="data-table" role="table" aria-label="Symbol status snapshot">
          <div className="data-table__head" role="row">
            <span>Symbol</span>
            <span>Validation</span>
            <span>Approval</span>
            <span>Confidence</span>
            <span>R:R</span>
            <span>Next action</span>
          </div>
          {symbolSnapshots.map((symbol) => (
            <div className="data-table__row" key={symbol.code} role="row">
              <strong>{symbol.code}</strong>
              <span>{symbol.validation}</span>
              <span>{symbol.approval}</span>
              <span>{symbol.confidence}</span>
              <span>{symbol.riskReward}</span>
              <span>{symbol.nextAction}</span>
            </div>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>No symbols in the operator runway yet.</strong>
          <p>Validate a symbol or wait for an approved model to appear in the registry.</p>
        </div>
      )}
    </section>
  );
}
