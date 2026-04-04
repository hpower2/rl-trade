import type { TrainingType, WebSocketEventMessage } from "../api";
import {
  applyApprovedModel,
  buildEventMessage,
  createOperatorFixtureState,
  createTrainingRequestResult,
  createValidationResult,
  setPaperTradingRuntime,
} from "./operator-state";

const manualWalkthroughParam = "manualWalkthrough";

declare global {
  interface Window {
    __rlTradeManualWalkthrough?: {
      active: boolean;
      emit: (message: WebSocketEventMessage) => void;
    };
  }
}

export function isManualWalkthroughMode(): boolean {
  if (typeof window === "undefined") {
    return false;
  }

  return new URLSearchParams(window.location.search).get(manualWalkthroughParam) === "1";
}

export function getManualWalkthroughLabel(): string | null {
  return isManualWalkthroughMode()
    ? "Manual walkthrough mode is active. The UI is serving a local demo operator workflow for browser validation."
    : null;
}

export function installManualWalkthroughRuntime(): void {
  if (!isManualWalkthroughMode() || typeof window === "undefined") {
    return;
  }

  const state = createOperatorFixtureState();
  const originalFetch = window.fetch.bind(window);
  const sockets: MockWalkthroughSocket[] = [];

  class MockWalkthroughSocket {
    static readonly CONNECTING = 0;
    static readonly OPEN = 1;
    static readonly CLOSING = 2;
    static readonly CLOSED = 3;

    readonly url: string;
    readyState = MockWalkthroughSocket.CONNECTING;
    onclose: ((event: CloseEvent) => void) | null = null;
    onerror: ((event: Event) => void) | null = null;
    onmessage: ((event: MessageEvent<string>) => void) | null = null;
    onopen: ((event: Event) => void) | null = null;
    private readonly listeners = new Map<string, Set<(event: Event) => void>>();

    constructor(url: string) {
      this.url = url;
      sockets.push(this);
      queueMicrotask(() => {
        this.readyState = MockWalkthroughSocket.OPEN;
        const openEvent = new Event("open");
        this.dispatchEvent("open", openEvent);
        this.onopen?.(openEvent);
      });
    }

    addEventListener(type: string, callback: (event: Event) => void): void {
      const callbacks = this.listeners.get(type) ?? new Set<(event: Event) => void>();
      callbacks.add(callback);
      this.listeners.set(type, callbacks);
    }

    close(): void {
      this.readyState = MockWalkthroughSocket.CLOSED;
      const closeEvent = new CloseEvent("close");
      this.dispatchEvent("close", closeEvent);
      this.onclose?.(closeEvent);
    }

    removeEventListener(type: string, callback: (event: Event) => void): void {
      this.listeners.get(type)?.delete(callback);
    }

    send(): void {}

    private dispatchEvent(type: string, event: Event): void {
      this.listeners.get(type)?.forEach((listener) => listener(event));
    }
  }

  function emit(message: WebSocketEventMessage): void {
    const browserEvent = new MessageEvent("message", {
      data: JSON.stringify(message),
    });

    sockets.forEach((socket) => {
      if (socket.readyState === MockWalkthroughSocket.OPEN) {
        socket.onmessage?.(browserEvent);
      }
    });
  }

  async function mockFetch(input: RequestInfo | URL, init?: RequestInit): Promise<Response> {
    const requestUrl =
      typeof input === "string"
        ? input
        : input instanceof URL
          ? input.toString()
          : input.url;
    const url = new URL(requestUrl, window.location.origin);
    const method = (init?.method ?? (input instanceof Request ? input.method : "GET")).toUpperCase();

    if (!url.pathname.startsWith("/api/v1/")) {
      return originalFetch(input, init);
    }

    if (method === "GET" && url.pathname === "/api/v1/auth/session") {
      return jsonResponse(state.session);
    }

    if (method === "GET" && url.pathname === "/api/v1/system/status") {
      return jsonResponse(state.systemStatus);
    }

    if (method === "GET" && url.pathname === "/api/v1/mt5/status") {
      return jsonResponse(state.mt5Status);
    }

    if (method === "GET" && url.pathname === "/api/v1/evaluations/approved-symbols") {
      return jsonResponse(state.approvedSymbols);
    }

    if (method === "GET" && url.pathname === "/api/v1/evaluations/models") {
      return jsonResponse(state.modelRegistry);
    }

    if (method === "GET" && url.pathname === "/api/v1/evaluations/reports") {
      return jsonResponse(state.evaluationReports);
    }

    if (method === "GET" && url.pathname === "/api/v1/trading/status") {
      return jsonResponse(state.tradingStatus);
    }

    if (method === "GET" && url.pathname === "/api/v1/trading/signals") {
      return jsonResponse({ signals: state.signals });
    }

    if (method === "GET" && url.pathname === "/api/v1/trading/positions") {
      return jsonResponse({ positions: state.positions });
    }

    if (method === "POST" && url.pathname === "/api/v1/symbols/validate") {
      const payload = readJsonBody(init?.body) as { symbol: string };
      const normalized = payload.symbol.trim().toUpperCase();
      state.validationResult = createValidationResult(normalized);
      return jsonResponse(state.validationResult);
    }

    if (method === "POST" && url.pathname === "/api/v1/training/request") {
      if (!state.validationResult?.is_valid || !state.validationResult.normalized_symbol) {
        return jsonResponse(
          { detail: "Validate a symbol successfully before requesting training." },
          { status: 409 },
        );
      }

      const payload = readJsonBody(init?.body) as { training_type: TrainingType };
      const result = createTrainingRequestResult(
        state,
        state.validationResult.normalized_symbol,
        payload.training_type,
      );
      schedulePipelineWalkthrough(result.symbol_code, result.ingestion_job_id);
      return jsonResponse(result);
    }

    if (method === "POST" && url.pathname === "/api/v1/trading/start") {
      if (!state.tradingStatus.paper_trading_allowed) {
        return jsonResponse({ detail: state.tradingStatus.reason }, { status: 409 });
      }

      const tradingStatus = setPaperTradingRuntime(state, true);
      queueMicrotask(() => {
        emit(
          buildEventMessage(state, {
            entityType: "paper_trade_signal",
            entityId: "71",
            eventType: "signal_event",
            payload: {
              symbol_code: "EURUSD",
              status: "accepted",
            },
          }),
        );
      });
      return jsonResponse(tradingStatus);
    }

    if (method === "POST" && url.pathname === "/api/v1/trading/stop") {
      return jsonResponse(setPaperTradingRuntime(state, false));
    }

    if (method === "POST" && url.pathname === "/api/v1/trading/sync") {
      return jsonResponse({
        synced_at: "2026-04-04T11:05:00Z",
        connection_status: "connected",
        paper_trading_allowed: state.tradingStatus.paper_trading_allowed,
        account_login: state.tradingStatus.account_login,
        orders_updated: 1,
        positions_updated: state.positions.length,
        executions_created: 0,
        history_records_seen: 2,
        broker_positions_seen: state.positions.length,
      });
    }

    return jsonResponse({ detail: `Unhandled walkthrough endpoint: ${method} ${url.pathname}` }, { status: 404 });
  }

  function schedulePipelineWalkthrough(symbolCode: string, ingestionJobId: number): void {
    window.setTimeout(() => {
      emit(
        buildEventMessage(state, {
          entityType: "job",
          entityId: String(ingestionJobId),
          eventType: "ingestion_progress",
          payload: {
            job_id: ingestionJobId,
            progress_percent: 35,
            status: "running",
            symbol_code: symbolCode,
          },
        }),
      );
    }, 250);

    window.setTimeout(() => {
      emit(
        buildEventMessage(state, {
          entityType: "job",
          entityId: String(ingestionJobId + 1),
          eventType: "preprocessing_progress",
          payload: {
            job_id: ingestionJobId + 1,
            progress_percent: 65,
            status: "running",
            symbol_code: symbolCode,
          },
        }),
      );
    }, 500);

    window.setTimeout(() => {
      emit(
        buildEventMessage(state, {
          entityType: "job",
          entityId: String(ingestionJobId + 2),
          eventType: "training_progress",
          payload: {
            job_id: ingestionJobId + 2,
            progress_percent: 90,
            status: "running",
            symbol_code: symbolCode,
          },
        }),
      );
    }, 750);

    window.setTimeout(() => {
      applyApprovedModel(state, symbolCode);
      emit(
        buildEventMessage(state, {
          entityType: "approved_model",
          entityId: "81",
          eventType: "approval_status",
          payload: {
            symbol_code: symbolCode,
            status: "approved",
          },
        }),
      );
    }, 1000);
  }

  Object.defineProperty(window, "WebSocket", {
    configurable: true,
    value: MockWalkthroughSocket,
    writable: true,
  });
  window.fetch = mockFetch;
  window.__rlTradeManualWalkthrough = {
    active: true,
    emit,
  };
}

function jsonResponse(payload: unknown, init: ResponseInit = {}): Response {
  return new Response(JSON.stringify(payload), {
    headers: {
      "Content-Type": "application/json",
    },
    status: init.status ?? 200,
    statusText: init.statusText,
  });
}

function readJsonBody(body: RequestInit["body"]): unknown {
  if (typeof body !== "string" || !body.trim()) {
    return {};
  }

  try {
    return JSON.parse(body);
  } catch {
    return {};
  }
}
