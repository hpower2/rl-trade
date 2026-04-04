import type {
  ApprovedSymbolResponse,
  ModelEvaluationSummaryResponse,
  ModelRegistryEntryResponse,
} from "../../../api";
import { formatPercentage, formatRatio, formatShortDateTime } from "../view-models";

export function ModelGatesSection({
  approvedSymbols,
  evaluationReports,
  modelRegistry,
}: {
  approvedSymbols: ApprovedSymbolResponse[];
  evaluationReports: ModelEvaluationSummaryResponse[];
  modelRegistry: ModelRegistryEntryResponse[];
}) {
  return (
    <>
      <section className="detail-panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Model gates</p>
            <h2>Approved symbols ready for the paper desk</h2>
          </div>
          <p className="section-note">
            Trading unlocks only for symbols that have cleared evaluation and approval thresholds.
          </p>
        </div>

        {approvedSymbols.length > 0 ? (
          <div className="data-table" role="table" aria-label="Approved symbols">
            <div className="data-table__head" role="row">
              <span>Symbol</span>
              <span>Model</span>
              <span>Type</span>
              <span>Confidence</span>
              <span>R:R</span>
              <span>Approved</span>
            </div>
            {approvedSymbols.slice(0, 6).map((symbol) => (
              <div className="data-table__row" key={symbol.approved_model_id} role="row">
                <strong>{symbol.symbol_code}</strong>
                <span>{symbol.model_name}</span>
                <span>{symbol.model_type}</span>
                <span>{formatPercentage(symbol.confidence)}</span>
                <span>{formatRatio(symbol.risk_to_reward)}</span>
                <span>{formatShortDateTime(symbol.approved_at)}</span>
              </div>
            ))}
          </div>
        ) : (
          <div className="empty-state">
            <strong>No approved symbols yet.</strong>
            <p>The paper-trading lane stays closed until evaluations promote at least one model into active approval.</p>
          </div>
        )}
      </section>

      <section className="detail-panel">
        <div className="section-header">
          <div>
            <p className="section-kicker">Registry</p>
            <h2>Latest models and evaluation reports</h2>
          </div>
        </div>

        <div className="stack-section">
          <div className="mini-header">
            <strong>Model registry</strong>
            <span>{modelRegistry.length} tracked</span>
          </div>
          {modelRegistry.length > 0 ? (
            <div className="stack-list">
              {modelRegistry.slice(0, 4).map((model) => (
                <article className="stack-item" key={`${model.model_type}-${model.model_id}`}>
                  <div className="stack-item__top">
                    <strong>
                      {model.symbol_code} · {model.model_name}
                    </strong>
                    <span className={`status-pill status-pill--${model.is_active_approval ? "healthy" : "watch"}`}>
                      {model.status}
                    </span>
                  </div>
                  <p>
                    {model.algorithm} · {model.version_tag}
                  </p>
                  <small>
                    {model.model_type} · created {formatShortDateTime(model.created_at)}
                  </small>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state empty-state--compact">
              <strong>No registry entries yet.</strong>
              <p>Training jobs will populate this list once models are materialized.</p>
            </div>
          )}
        </div>

        <div className="stack-section">
          <div className="mini-header">
            <strong>Recent evaluations</strong>
            <span>{evaluationReports.length} reports</span>
          </div>
          {evaluationReports.length > 0 ? (
            <div className="stack-list">
              {evaluationReports.slice(0, 4).map((report) => (
                <article className="stack-item" key={report.evaluation_id}>
                  <div className="stack-item__top">
                    <strong>
                      {report.symbol_code} · {report.evaluation_type}
                    </strong>
                    <span className={`status-pill status-pill--${report.approved ? "healthy" : "blocked"}`}>
                      {report.approved ? "approved" : "blocked"}
                    </span>
                  </div>
                  <p>
                    Confidence {formatPercentage(report.confidence)} · R:R {formatRatio(report.risk_to_reward)}
                  </p>
                  <small>{formatShortDateTime(report.evaluated_at)}</small>
                </article>
              ))}
            </div>
          ) : (
            <div className="empty-state empty-state--compact">
              <strong>No evaluations published yet.</strong>
              <p>The approval gate will stay pending until evaluation reports begin to arrive.</p>
            </div>
          )}
        </div>
      </section>
    </>
  );
}
