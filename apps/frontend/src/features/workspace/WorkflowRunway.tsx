import type { WorkflowStage } from "../../demo-state";

export function WorkflowRunway({ stages }: { stages: WorkflowStage[] }) {
  return (
    <section className="workflow-runway" id="section-2">
      <div className="section-header">
        <div>
          <p className="section-kicker">Workflow runway</p>
          <h2>Follow the exact backend gating path</h2>
        </div>
        <p className="section-note">
          The workspace now reflects the downstream gates too: evaluation output, approved
          symbols, and runtime status can all move from backend state into the operator view.
        </p>
      </div>

      <div className="workflow-grid">
        {stages.map((stage) => (
          <article className={`workflow-card workflow-card--${stage.status}`} key={stage.title}>
            <div className="workflow-card__top">
              <span>{stage.title}</span>
              <small>{stage.metric}</small>
            </div>
            <p>{stage.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
