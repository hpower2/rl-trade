import { type FormEvent, startTransition, useState } from "react";

import { APIError, createAPIClient, normalizeBaseUrl } from "./api";
import { LoginPanel, type LoginState } from "./features/auth/LoginPanel";
import { OverviewWorkspace } from "./features/workspace/OverviewWorkspace";
import type { WorkspaceAccess } from "./features/workspace/types";
import { getManualWalkthroughLabel } from "./mock-operator/runtime";
import "./app.css";

const defaultAPIBaseUrl = normalizeBaseUrl(
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000",
);

export function App() {
  const manualWalkthroughLabel = getManualWalkthroughLabel();
  const [workspace, setWorkspace] = useState<WorkspaceAccess | null>(null);
  const [loginState, setLoginState] = useState<LoginState>({
    operatorEmail: "ops@rl-trade.demo",
    token: "",
    apiBaseUrl: defaultAPIBaseUrl,
  });
  const [isAuthenticating, setIsAuthenticating] = useState(false);
  const [loginError, setLoginError] = useState<string | null>(null);

  async function handleEnterWorkspace(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setIsAuthenticating(true);
    setLoginError(null);

    try {
      const normalizedBaseUrl = normalizeBaseUrl(loginState.apiBaseUrl);
      const client = createAPIClient({
        baseUrl: normalizedBaseUrl,
        token: loginState.token,
      });
      const session = await client.getSession();

      startTransition(() => {
        setWorkspace({
          operatorEmail: loginState.operatorEmail,
          apiBaseUrl: normalizedBaseUrl,
          token: loginState.token,
          session,
        });
      });
    } catch (error) {
      const message =
        error instanceof APIError ? error.message : "Unable to establish an operator session.";
      setLoginError(message);
    } finally {
      setIsAuthenticating(false);
    }
  }

  return (
    <main className="app-shell">
      {workspace ? (
        <OverviewWorkspace onSignOut={() => setWorkspace(null)} workspace={workspace} />
      ) : (
        <LoginPanel
          errorMessage={loginError}
          isAuthenticating={isAuthenticating}
          loginState={loginState}
          manualWalkthroughLabel={manualWalkthroughLabel}
          onChange={setLoginState}
          onSubmit={handleEnterWorkspace}
        />
      )}
    </main>
  );
}

export default App;
