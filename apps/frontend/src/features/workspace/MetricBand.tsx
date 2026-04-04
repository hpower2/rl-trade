import type { SnapshotMetric } from "../../demo-state";

export function MetricBand({ metrics }: { metrics: SnapshotMetric[] }) {
  return (
    <section className="metric-band" id="section-1">
      {metrics.map((metric) => (
        <article className="metric-band__item" key={metric.label}>
          <p>{metric.label}</p>
          <strong>{metric.value}</strong>
          <span>{metric.detail}</span>
        </article>
      ))}
    </section>
  );
}
