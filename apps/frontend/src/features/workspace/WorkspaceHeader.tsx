import { buildLiveFeedLabel } from "./view-models";
import type { LiveFeedState, WorkspaceAccess } from "./types";

export function WorkspaceHeader({
  description,
  kicker,
  liveFeedState,
  title,
  workspace,
}: {
  description: string;
  kicker: string;
  liveFeedState: LiveFeedState;
  title: string;
  workspace: WorkspaceAccess;
}) {
  return (
    <header className="workspace-header">
      <div>
        <p className="section-kicker">{kicker}</p>
        <h1>{title}</h1>
        <p className="section-note workspace-note">{description}</p>
        <p className="workspace-meta">
          API target: <code>{workspace.apiBaseUrl}</code>
        </p>
      </div>

      <div className={`live-indicator live-indicator--${liveFeedState}`} role="status">
        <span className="live-indicator__dot" />
        {buildLiveFeedLabel(liveFeedState)}
      </div>
    </header>
  );
}
