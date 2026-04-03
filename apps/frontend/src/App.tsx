import "./app.css";

const pillars = [
  {
    title: "API",
    text: "FastAPI will expose health, orchestration, model approval, and paper trading controls.",
  },
  {
    title: "Workers",
    text: "Celery workers will isolate ingestion, preprocessing, training, evaluation, and trading loops.",
  },
  {
    title: "Shared libs",
    text: "Common config and domain packages keep safety rules and trading thresholds consistent.",
  },
  {
    title: "Dashboard",
    text: "The frontend will surface jobs, models, positions, and live paper trading telemetry.",
  },
];

export function App() {
  return (
    <main className="shell">
      <section className="hero">
        <p className="eyebrow">Milestone 1</p>
        <h1>Forex Trainer &amp; Paper Trading Dashboard</h1>
        <p className="lede">
          Monorepo scaffold for a paper-only trading platform with shared safety guards,
          service bootstrap code, and a dashboard shell.
        </p>
      </section>

      <section className="grid">
        {pillars.map((pillar) => (
          <article className="card" key={pillar.title}>
            <p className="card-label">{pillar.title}</p>
            <p>{pillar.text}</p>
          </article>
        ))}
      </section>
    </main>
  );
}

export default App;
