import type { EventRow } from "../../../demo-state";

export function LiveEventSection({ liveEventRows }: { liveEventRows: EventRow[] }) {
  return (
    <section className="detail-panel">
      <div className="section-header">
        <div>
          <p className="section-kicker">Live event rail</p>
          <h2>WebSocket events in operator language</h2>
        </div>
      </div>

      {liveEventRows.length > 0 ? (
        <div className="event-rail">
          {liveEventRows.map((event) => (
            <article className={`event-item event-item--${event.tone}`} key={`${event.timestamp}-${event.title}`}>
              <div className="event-item__top">
                <strong>{event.title}</strong>
                <span>{event.timestamp}</span>
              </div>
              <p>{event.detail}</p>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state">
          <strong>Waiting for live events.</strong>
          <p>As jobs, approvals, signals, or positions update, they will land here through the WebSocket feed.</p>
        </div>
      )}
    </section>
  );
}
