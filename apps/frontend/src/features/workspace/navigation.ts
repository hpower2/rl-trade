import type { WorkspaceView } from "./types";

export type WorkspaceNavItem = {
  view: WorkspaceView;
  label: string;
  description: string;
};

export type WorkspacePageMeta = {
  kicker: string;
  title: string;
  description: string;
};

export const workspaceNavItems: WorkspaceNavItem[] = [
  {
    view: "overview",
    label: "Overview",
    description: "Full runway from validation through paper-trading readiness.",
  },
  {
    view: "symbols",
    label: "Symbols",
    description: "Validation-first symbol and training request console.",
  },
  {
    view: "pipeline",
    label: "Pipeline",
    description: "Ingestion, preprocessing, training progress, and live event logs.",
  },
  {
    view: "models",
    label: "Models",
    description: "Registry, evaluations, approvals, and model gates.",
  },
  {
    view: "trading",
    label: "Paper Trading",
    description: "Runtime controls, signals, and positions.",
  },
  {
    view: "system",
    label: "System",
    description: "MT5 health, live events, and safeguard logs.",
  },
];

export const workspacePageMeta: Record<WorkspaceView, WorkspacePageMeta> = {
  overview: {
    kicker: "Primary UX flow",
    title: "Training-to-trading control surface",
    description: "See the full runway at a glance, from validation through runtime readiness.",
  },
  symbols: {
    kicker: "Symbol management",
    title: "Validation and training intake",
    description: "Enter symbols, validate them against the backend, and open training requests.",
  },
  pipeline: {
    kicker: "Pipeline operations",
    title: "Ingestion, preprocessing, and training watch desk",
    description: "Track downstream jobs and operator-facing live events without leaving the workspace.",
  },
  models: {
    kicker: "Model registry",
    title: "Approval and evaluation desk",
    description: "Inspect model outputs, evaluation reports, and the symbols cleared for trading.",
  },
  trading: {
    kicker: "Paper trading",
    title: "Demo runtime control plane",
    description: "Operate the runtime only when backend approval and demo-account guards allow it.",
  },
  system: {
    kicker: "System status",
    title: "Broker health and live logs",
    description: "Track MT5 connectivity, live events, and safeguard messages from one place.",
  },
};

const defaultWorkspaceView: WorkspaceView = "overview";

export function parseWorkspaceViewFromHash(hash: string): WorkspaceView {
  const rawHash = hash.trim().replace(/^#/, "");
  if (!rawHash) {
    return defaultWorkspaceView;
  }

  const normalized = rawHash.replace(/^workspace\//, "");
  if (workspaceNavItems.some((item) => item.view === normalized)) {
    return normalized as WorkspaceView;
  }

  return defaultWorkspaceView;
}

export function buildWorkspaceHash(view: WorkspaceView): string {
  return `#workspace/${view}`;
}
