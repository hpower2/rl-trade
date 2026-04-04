import type { AlertSnapshot } from "../../../demo-state";

export function AlertSection({ alerts }: { alerts: AlertSnapshot[] }) {
  return (
    <section className="detail-panel">
      <div className="section-header">
        <div>
          <p className="section-kicker">Logs & safeguards</p>
          <h2>Backend protections remain visible</h2>
        </div>
      </div>

      <div className="alert-list">
        {alerts.map((alert) => (
          <article className={`alert-item alert-item--${alert.severity}`} key={alert.title}>
            <strong>{alert.title}</strong>
            <p>{alert.detail}</p>
          </article>
        ))}
      </div>
    </section>
  );
}
