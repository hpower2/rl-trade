import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

import App from "../App";

const mockClient = {
  getSession: vi.fn(),
  getSystemStatus: vi.fn(),
  getMT5Status: vi.fn(),
  listApprovedSymbols: vi.fn(),
  listModels: vi.fn(),
  listEvaluationReports: vi.fn(),
  getTradingStatus: vi.fn(),
  listSignals: vi.fn(),
  listPositions: vi.fn(),
  validateSymbol: vi.fn(),
  requestTraining: vi.fn(),
  startPaperTrading: vi.fn(),
  stopPaperTrading: vi.fn(),
  syncPaperTrading: vi.fn(),
};

vi.mock("../api", async () => {
  const actual = await vi.importActual<typeof import("../api")>("../api");
  return {
    ...actual,
    createAPIClient: vi.fn(() => mockClient),
  };
});

class MockWebSocket {
  static instances: MockWebSocket[] = [];

  onopen: (() => void) | null = null;
  onmessage: ((event: MessageEvent<string>) => void) | null = null;
  onerror: (() => void) | null = null;
  onclose: (() => void) | null = null;

  constructor(public url: string) {
    MockWebSocket.instances.push(this);
    queueMicrotask(() => {
      this.onopen?.();
    });
  }

  close() {
    this.onclose?.();
  }
}

function seedWorkspaceData() {
  mockClient.getSession.mockResolvedValue({
    authenticated: true,
    auth_mode: "disabled",
    subject: "operator",
    roles: ["operator"],
  });
  mockClient.getSystemStatus.mockResolvedValue({
    service: "api",
    status: "ok",
    environment: "test",
    paper_trading_only: true,
    components: {},
  });
  mockClient.getMT5Status.mockResolvedValue({
    status: "connected",
    account_login: 123456,
    server_name: "Broker-Demo",
    account_name: "Practice Demo",
    account_currency: "USD",
    leverage: 100,
    is_demo: true,
    trade_allowed: true,
    paper_trading_allowed: true,
    reason: null,
    details: {},
  });
  mockClient.listApprovedSymbols.mockResolvedValue([
    {
      approved_model_id: 7,
      symbol_id: 1,
      symbol_code: "EURUSD",
      model_type: "supervised",
      model_id: 11,
      model_name: "baseline_classifier",
      algorithm: "auto_baseline",
      confidence: 78.6,
      risk_to_reward: 2.4,
      approved_at: "2026-04-04T10:00:00Z",
    },
  ]);
  mockClient.listModels.mockResolvedValue([
    {
      model_type: "supervised",
      model_id: 11,
      symbol_id: 1,
      symbol_code: "EURUSD",
      dataset_version_id: 2,
      feature_set_id: 3,
      training_job_id: 19,
      model_name: "baseline_classifier",
      version_tag: "v1",
      algorithm: "auto_baseline",
      status: "approved",
      storage_uri: "artifacts://baseline",
      approved_model_id: 7,
      is_active_approval: true,
      created_at: "2026-04-04T09:00:00Z",
    },
  ]);
  mockClient.listEvaluationReports.mockResolvedValue([
    {
      evaluation_id: 15,
      model_type: "supervised",
      model_id: 11,
      symbol_id: 1,
      symbol_code: "EURUSD",
      dataset_version_id: 2,
      evaluation_type: "validation",
      confidence: 78.6,
      risk_to_reward: 2.4,
      sample_size: 250,
      max_drawdown: 3.2,
      approved: true,
      decision_reasons: [],
      evaluated_at: "2026-04-04T10:00:00Z",
    },
  ]);
  mockClient.getTradingStatus.mockResolvedValue({
    enabled: false,
    connection_status: "connected",
    account_login: 123456,
    server_name: "Broker-Demo",
    account_name: "Practice Demo",
    is_demo: true,
    is_trade_allowed: true,
    paper_trading_allowed: true,
    reason: null,
    approved_symbol_count: 1,
    accepted_signal_count: 0,
    open_order_count: 0,
    open_position_count: 0,
    last_started_at: null,
    last_started_by: null,
    last_stopped_at: null,
    last_stopped_by: null,
  });
  mockClient.listSignals.mockResolvedValue({ signals: [] });
  mockClient.listPositions.mockResolvedValue({ positions: [] });
}

beforeEach(() => {
  vi.clearAllMocks();
  MockWebSocket.instances = [];
  vi.stubGlobal("WebSocket", MockWebSocket as unknown as typeof WebSocket);
  window.location.hash = "";
  seedWorkspaceData();
});

describe("frontend workspace smoke tests", () => {
  it("renders the login screen by default", () => {
    render(<App />);

    expect(
      screen.getByRole("heading", { name: /operator workspace for the full training-to-paper-trading loop/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/operator email/i)).toBeInTheDocument();
  });

  it("shows the manual walkthrough hint when the query flag is present", () => {
    window.history.pushState({}, "", "/?manualWalkthrough=1");
    render(<App />);

    expect(screen.getByText(/manual walkthrough mode is active/i)).toBeInTheDocument();
  });

  it("opens the overview workspace after session authentication", async () => {
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /enter overview workspace/i }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /training-to-trading control surface/i })).toBeInTheDocument(),
    );
    expect(
      screen.getByRole("heading", { name: /approved symbols ready for the paper desk/i }),
    ).toBeInTheDocument();
  });

  it("renders the models view from the workspace hash", async () => {
    window.location.hash = "#workspace/models";
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /enter overview workspace/i }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /approval and evaluation desk/i })).toBeInTheDocument(),
    );
    expect(screen.getByText(/latest models and evaluation reports/i)).toBeInTheDocument();
    expect(screen.getByText(/approved symbols ready for the paper desk/i)).toBeInTheDocument();
  });

  it("renders the pipeline view from the workspace hash", async () => {
    window.location.hash = "#workspace/pipeline";
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /enter overview workspace/i }));

    await waitFor(() =>
      expect(
        screen.getByRole("heading", { name: /ingestion, preprocessing, and training watch desk/i }),
      ).toBeInTheDocument(),
    );
    expect(screen.getByText(/operator intake and current downstream status/i)).toBeInTheDocument();
    expect(screen.getByText(/stage-specific queue health/i)).toBeInTheDocument();
    expect(screen.getByText(/preprocessing remains idle until a training request opens/i)).toBeInTheDocument();
    expect(screen.getByText(/watch jobs without leaving the workspace/i)).toBeInTheDocument();
  });

  it("renders the system view from the workspace hash", async () => {
    window.location.hash = "#workspace/system";
    render(<App />);

    fireEvent.click(screen.getByRole("button", { name: /enter overview workspace/i }));

    await waitFor(() =>
      expect(screen.getByRole("heading", { name: /broker health and live logs/i })).toBeInTheDocument(),
    );
    expect(screen.getByText(/demo account health snapshot/i)).toBeInTheDocument();
    expect(screen.getByText(/backend protections remain visible/i)).toBeInTheDocument();
  });
});
