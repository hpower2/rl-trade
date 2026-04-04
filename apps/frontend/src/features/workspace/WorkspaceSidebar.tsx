import { buildWorkspaceHash, workspaceNavItems } from "./navigation";
import type { WorkspaceAccess, WorkspaceView } from "./types";

export function WorkspaceSidebar({
  currentView,
  onNavigate,
  onSignOut,
  workspace,
}: {
  currentView: WorkspaceView;
  onNavigate: (view: WorkspaceView) => void;
  onSignOut: () => void;
  workspace: WorkspaceAccess;
}) {
  return (
    <aside className="workspace-sidebar">
      <p className="brand-mark">RL Trade</p>
      <h2>Operator workspace</h2>
      <p className="sidebar-copy">
        The frontend is now organized as a workspace with dedicated views, so the remaining
        Milestone 13 pages can grow without collapsing back into one long screen.
      </p>

      <nav aria-label="Workspace views" className="overview-nav">
        {workspaceNavItems.map((item) => (
          <a
            aria-current={currentView === item.view ? "page" : undefined}
            className={currentView === item.view ? "overview-nav__link overview-nav__link--active" : "overview-nav__link"}
            href={buildWorkspaceHash(item.view)}
            key={item.view}
            onClick={(event) => {
              event.preventDefault();
              onNavigate(item.view);
            }}
          >
            <strong>{item.label}</strong>
            <span>{item.description}</span>
          </a>
        ))}
      </nav>

      <div className="sidebar-session">
        <p className="section-kicker">Session</p>
        <strong>{workspace.session.subject}</strong>
        <span>{workspace.operatorEmail}</span>
        <small>{workspace.session.auth_mode} auth mode</small>
      </div>

      <button className="secondary-button" onClick={onSignOut} type="button">
        Sign out
      </button>
    </aside>
  );
}
