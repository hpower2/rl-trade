import type { PipelineStageSnapshot } from "../types";

export function PipelineStageSection({
  stageSnapshots,
}: {
  stageSnapshots: PipelineStageSnapshot[];
}) {
  return (
    <section className="detail-panel">
      <div className="section-header">
        <div>
          <p className="section-kicker">Stage lens</p>
          <h2>Stage-specific queue health</h2>
        </div>
        <p className="section-note">
          Each worker-owned stage stays visible here so operators can follow ingestion,
          preprocessing, and training without reading raw logs first.
        </p>
      </div>

      <div className="pipeline-stage-grid">
        {stageSnapshots.map((stage) => (
          <article className="pipeline-stage-card" key={stage.key}>
            <div className="pipeline-stage-card__top">
              <div>
                <strong>{stage.title}</strong>
                <p>{stage.updatedAt}</p>
              </div>
              <span className={`status-pill status-pill--${stage.status}`}>
                {stage.progress > 0 ? `${stage.progress}%` : "watching"}
              </span>
            </div>

            <p>{stage.detail}</p>
            <small>{stage.note}</small>

            <div className="queue-progress" aria-hidden="true">
              <span style={{ width: `${stage.progress}%` }} />
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
