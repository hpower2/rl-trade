import { expect, test as base, type Page, type Route } from "@playwright/test";

import type { TrainingType, WebSocketEventMessage } from "../../../src/api";
import {
  applyApprovedModel,
  buildEventMessage,
  createOperatorFixtureState,
  createTrainingRequestResult,
  createValidationResult,
  setPaperTradingRuntime,
  type OperatorFixtureState,
} from "./operator-state";

declare global {
  interface Window {
    __rlTradePlaywrightEmit?: (message: WebSocketEventMessage) => void;
  }
}

class MockOperatorWorkspace {
  readonly state = createOperatorFixtureState();

  constructor(private readonly page: Page) {}

  async install(): Promise<void> {
    await this.page.addInitScript(() => {
      const sockets: MockWebSocket[] = [];

      class MockWebSocket {
        static readonly CONNECTING = 0;
        static readonly OPEN = 1;
        static readonly CLOSING = 2;
        static readonly CLOSED = 3;

        readonly url: string;
        readyState = MockWebSocket.CONNECTING;
        onclose: ((event: CloseEvent) => void) | null = null;
        onerror: ((event: Event) => void) | null = null;
        onmessage: ((event: MessageEvent<string>) => void) | null = null;
        onopen: ((event: Event) => void) | null = null;
        private readonly listeners = new Map<string, Set<(event: Event) => void>>();

        constructor(url: string) {
          this.url = url;
          sockets.push(this);
          queueMicrotask(() => {
            this.readyState = MockWebSocket.OPEN;
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
          this.readyState = MockWebSocket.CLOSED;
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

      window.__rlTradePlaywrightEmit = (message: WebSocketEventMessage) => {
        const browserEvent = new MessageEvent("message", {
          data: JSON.stringify(message),
        });

        sockets.forEach((socket) => {
          if (socket.readyState !== MockWebSocket.OPEN) {
            return;
          }
          socket.onmessage?.(browserEvent);
        });
      };

      Object.defineProperty(window, "WebSocket", {
        configurable: true,
        value: MockWebSocket,
        writable: true,
      });
    });

    await this.page.route("**/api/v1/**", async (route) => {
      await this.fulfillAPI(route);
    });
  }

  async emitApproval(symbolCode: string): Promise<void> {
    applyApprovedModel(this.state, symbolCode);
    await this.emitEvent(
      buildEventMessage(this.state, {
        entityType: "approved_model",
        entityId: "81",
        eventType: "approval_status",
        payload: {
          symbol_code: symbolCode,
          status: "approved",
        },
      }),
    );
  }

  async emitPipelineProgress(input: {
    eventType: "ingestion_progress" | "preprocessing_progress" | "training_progress";
    jobId: number;
    progressPercent: number;
    status: string;
    symbolCode: string;
  }): Promise<void> {
    await this.emitEvent(
      buildEventMessage(this.state, {
        entityType: "job",
        entityId: String(input.jobId),
        eventType: input.eventType,
        payload: {
          job_id: input.jobId,
          progress_percent: input.progressPercent,
          status: input.status,
          symbol_code: input.symbolCode,
        },
      }),
    );
  }

  async login(): Promise<void> {
    await this.page.goto("/");
    await this.page.getByRole("button", { name: /enter overview workspace/i }).click();
    await expect(
      this.page.getByRole("heading", { name: /training-to-trading control surface/i }),
    ).toBeVisible();
  }

  private async emitEvent(message: WebSocketEventMessage): Promise<void> {
    await this.page.evaluate((payload) => {
      window.__rlTradePlaywrightEmit?.(payload);
    }, message);
  }

  private async fulfillAPI(route: Route): Promise<void> {
    const request = route.request();
    const url = new URL(request.url());
    const path = url.pathname;

    if (request.method() === "GET" && path === "/api/v1/auth/session") {
      await route.fulfill({ json: this.state.session, status: 200 });
      return;
    }

    if (request.method() === "GET" && path === "/api/v1/system/status") {
      await route.fulfill({ json: this.state.systemStatus, status: 200 });
      return;
    }

    if (request.method() === "GET" && path === "/api/v1/mt5/status") {
      await route.fulfill({ json: this.state.mt5Status, status: 200 });
      return;
    }

    if (request.method() === "GET" && path === "/api/v1/evaluations/approved-symbols") {
      await route.fulfill({ json: this.state.approvedSymbols, status: 200 });
      return;
    }

    if (request.method() === "GET" && path === "/api/v1/evaluations/models") {
      await route.fulfill({ json: this.state.modelRegistry, status: 200 });
      return;
    }

    if (request.method() === "GET" && path === "/api/v1/evaluations/reports") {
      await route.fulfill({ json: this.state.evaluationReports, status: 200 });
      return;
    }

    if (request.method() === "GET" && path === "/api/v1/trading/status") {
      await route.fulfill({ json: this.state.tradingStatus, status: 200 });
      return;
    }

    if (request.method() === "GET" && path === "/api/v1/trading/signals") {
      await route.fulfill({ json: { signals: this.state.signals }, status: 200 });
      return;
    }

    if (request.method() === "GET" && path === "/api/v1/trading/positions") {
      await route.fulfill({ json: { positions: this.state.positions }, status: 200 });
      return;
    }

    if (request.method() === "POST" && path === "/api/v1/symbols/validate") {
      const payload = request.postDataJSON() as { symbol: string };
      const normalized = payload.symbol.trim().toUpperCase();
      this.state.validationResult = createValidationResult(normalized);
      await route.fulfill({ json: this.state.validationResult, status: 200 });
      return;
    }

    if (request.method() === "POST" && path === "/api/v1/training/request") {
      if (!this.state.validationResult?.is_valid || !this.state.validationResult.normalized_symbol) {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({ detail: "Validate a symbol successfully before requesting training." }),
          status: 409,
        });
        return;
      }

      const payload = request.postDataJSON() as { training_type: TrainingType };
      const result = createTrainingRequestResult(
        this.state,
        this.state.validationResult.normalized_symbol,
        payload.training_type,
      );
      await route.fulfill({ json: result, status: 200 });
      return;
    }

    if (request.method() === "POST" && path === "/api/v1/trading/start") {
      if (!this.state.tradingStatus.paper_trading_allowed) {
        await route.fulfill({
          contentType: "application/json",
          body: JSON.stringify({ detail: this.state.tradingStatus.reason }),
          status: 409,
        });
        return;
      }

      await route.fulfill({
        json: setPaperTradingRuntime(this.state, true),
        status: 200,
      });
      return;
    }

    if (request.method() === "POST" && path === "/api/v1/trading/stop") {
      await route.fulfill({
        json: setPaperTradingRuntime(this.state, false),
        status: 200,
      });
      return;
    }

    if (request.method() === "POST" && path === "/api/v1/trading/sync") {
      await route.fulfill({
        json: {
          synced_at: "2026-04-04T11:05:00Z",
          connection_status: "connected",
          paper_trading_allowed: this.state.tradingStatus.paper_trading_allowed,
          account_login: this.state.tradingStatus.account_login,
          orders_updated: 1,
          positions_updated: this.state.positions.length,
          executions_created: 0,
          history_records_seen: 2,
          broker_positions_seen: this.state.positions.length,
        },
        status: 200,
      });
      return;
    }

    await route.fulfill({
      contentType: "application/json",
      body: JSON.stringify({ detail: `Unhandled mock endpoint: ${request.method()} ${path}` }),
      status: 404,
    });
  }
}

export const test = base.extend<{ operatorWorkspace: MockOperatorWorkspace }>({
  operatorWorkspace: async ({ page }, use) => {
    const operatorWorkspace = new MockOperatorWorkspace(page);
    await operatorWorkspace.install();
    await use(operatorWorkspace);
  },
});

export { expect } from "@playwright/test";
