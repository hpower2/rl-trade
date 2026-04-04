import { type FormEvent } from "react";

import { workflowStages } from "../../demo-state";

export type LoginState = {
  operatorEmail: string;
  token: string;
  apiBaseUrl: string;
};

export function LoginPanel({
  errorMessage,
  isAuthenticating,
  loginState,
  manualWalkthroughLabel,
  onChange,
  onSubmit,
}: {
  errorMessage: string | null;
  isAuthenticating: boolean;
  loginState: LoginState;
  manualWalkthroughLabel: string | null;
  onChange: (next: LoginState) => void;
  onSubmit: (event: FormEvent<HTMLFormElement>) => void;
}) {
  return (
    <section className="login-screen">
      <div className="login-copy">
        <div>
          <p className="section-kicker">Milestone 13</p>
          <h1>Operator workspace for the full training-to-paper-trading loop.</h1>
          <p className="intro-copy">
            The overview desk now covers the downstream gate too: approved-model visibility,
            trading readiness, and demo-only runtime control all stay anchored to the backend.
          </p>
        </div>

        <div className="runway-preview" aria-label="Primary workflow preview">
          {workflowStages.slice(0, 4).map((stage) => (
            <div className={`runway-step runway-step--${stage.status}`} key={stage.title}>
              <span>{stage.title}</span>
              <small>{stage.metric}</small>
            </div>
          ))}
        </div>
      </div>

      <form className="login-panel" onSubmit={onSubmit}>
        <div className="login-panel__header">
          <p className="section-kicker">Demo operator access</p>
          <h2>Connect the overview desk to the API</h2>
        </div>

        <div className="login-grid">
          <div>
            <label htmlFor="operator-email">Operator email</label>
            <input
              autoComplete="email"
              id="operator-email"
              onChange={(event) =>
                onChange({
                  ...loginState,
                  operatorEmail: event.target.value,
                })
              }
              type="email"
              value={loginState.operatorEmail}
            />
          </div>
          <div>
            <label htmlFor="operator-token">Bearer token</label>
            <input
              autoComplete="current-password"
              id="operator-token"
              onChange={(event) =>
                onChange({
                  ...loginState,
                  token: event.target.value,
                })
              }
              placeholder="Leave blank when auth mode is disabled"
              type="password"
              value={loginState.token}
            />
          </div>
          <div className="login-grid__full">
            <label htmlFor="api-base-url">API base URL</label>
            <input
              id="api-base-url"
              onChange={(event) =>
                onChange({
                  ...loginState,
                  apiBaseUrl: event.target.value,
                })
              }
              type="url"
              value={loginState.apiBaseUrl}
            />
            <p className="helper-copy">
              Default points to the local FastAPI server. Override this when the API runs on a
              different host.
            </p>
            {manualWalkthroughLabel ? (
              <p className="helper-copy helper-copy--accent">{manualWalkthroughLabel}</p>
            ) : null}
          </div>
        </div>

        <ul className="login-rules" aria-label="Backend safety rules">
          <li>Only validated symbols can enter the training request flow.</li>
          <li>Approval requires confidence ≥ 70% and risk-to-reward ≥ 2.0.</li>
          <li>Paper trading remains blocked for live MT5 accounts even if the UI is open.</li>
        </ul>

        {errorMessage ? <p className="form-feedback form-feedback--error">{errorMessage}</p> : null}

        <button className="primary-button" disabled={isAuthenticating} type="submit">
          {isAuthenticating ? "Authenticating…" : "Enter overview workspace"}
        </button>
      </form>
    </section>
  );
}
