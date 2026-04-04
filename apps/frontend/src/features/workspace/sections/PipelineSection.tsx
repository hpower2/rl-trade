import type { QueueViewModel } from "../types";

export function PipelineSection({ queueState }: { queueState: QueueViewModel[] }) {
  return (
    <section className="detail-panel">
      <div className="section-header">
        <div>
          <p className="section-kicker">Pipeline</p>
          <h2>Watch jobs without leaving the workspace</h2>
        </div>
        <span className="status-pill status-pill--watch">Realtime only</span>
      </div>

      {queueState.length > 0 ? (
        <div className="queue-list">
          {queueState.map((queue) => (
            <article className="queue-item" key={queue.key}>
              <div className="queue-item__header">
                <div>
                  <strong>{queue.label}</strong>
                  <p>{queue.owner}</p>
                </div>
                <span className={`status-pill status-pill--${queue.status}`}>{queue.updatedAt}</span>
              </div>
              <div className="queue-progress" aria-hidden="true">
                <span style={{ width: `${queue.progress}%` }} />
              </div>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>No live queue snapshots yet.</strong>
          <p>Open a training request or wait for worker progress events to arrive over the WebSocket feed.</p>
        </div>
      )}
    </section>
  );
}
