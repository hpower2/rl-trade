import type {
  PaperTradePositionResponse,
  PaperTradeSignalResponse,
  PaperTradingStatusResponse,
} from "../../../api";
import { formatPercentage, formatPnL, formatQuantity, formatRatio, formatShortDateTime, mapSignalStatusToQueueStatus } from "../view-models";

type TradingAction = "start" | "stop" | "sync";

export function PaperTradingSection({
  activeTradingAction,
  isRefreshingOperatorData,
  onTradingAction,
  positions,
  signals,
  tradingActionError,
  tradingStatus,
}: {
  activeTradingAction: TradingAction | null;
  isRefreshingOperatorData: boolean;
  onTradingAction: (action: TradingAction) => void;
  positions: PaperTradePositionResponse[];
  signals: PaperTradeSignalResponse[];
  tradingActionError: string | null;
  tradingStatus: PaperTradingStatusResponse | null;
}) {
  return (
    <section className="detail-panel">
      <div className="section-header">
        <div>
          <p className="section-kicker">Paper trading</p>
          <h2>Runtime readiness and control plane</h2>
        </div>
        <p className="section-note">
          {isRefreshingOperatorData
            ? "Refreshing runtime status…"
            : tradingActionError ??
              tradingStatus?.reason ??
              "Use backend-controlled runtime actions only after approved symbols are available."}
        </p>
      </div>

      <div className="trading-banner">
        <div>
          <span
            className={`status-pill status-pill--${
              tradingStatus?.enabled ? "healthy" : tradingStatus?.paper_trading_allowed ? "watch" : "blocked"
            }`}
          >
            {tradingStatus?.enabled
              ? "Runtime enabled"
              : tradingStatus?.paper_trading_allowed
                ? "Ready to start"
                : "Trading blocked"}
          </span>
          <p>
            Approved-model gating and demo-account checks remain enforced on the backend before any trade flow can proceed.
          </p>
        </div>
        <div className="trading-banner__metrics">
          <strong>{tradingStatus?.accepted_signal_count ?? 0} accepted signals</strong>
          <span>{tradingStatus?.open_position_count ?? 0} open positions</span>
        </div>
      </div>

      <div className="action-row">
        <button
          className="primary-button"
          disabled={activeTradingAction !== null || tradingStatus?.enabled === true || !tradingStatus?.paper_trading_allowed}
          onClick={() => onTradingAction("start")}
          type="button"
        >
          {activeTradingAction === "start" ? "Starting…" : "Start runtime"}
        </button>
        <button
          className="secondary-button"
          disabled={activeTradingAction !== null || tradingStatus?.enabled !== true}
          onClick={() => onTradingAction("stop")}
          type="button"
        >
          {activeTradingAction === "stop" ? "Stopping…" : "Stop runtime"}
        </button>
        <button
          className="secondary-button"
          disabled={activeTradingAction !== null || !tradingStatus?.paper_trading_allowed}
          onClick={() => onTradingAction("sync")}
          type="button"
        >
          {activeTradingAction === "sync" ? "Syncing…" : "Sync broker state"}
        </button>
      </div>

      {signals.length > 0 ? (
        <div className="stack-section">
          <div className="mini-header">
            <strong>Recent signals</strong>
            <span>{signals.length} total</span>
          </div>
          <div className="stack-list">
            {signals.slice(0, 3).map((signal) => (
              <article className="stack-item" key={signal.signal_id}>
                <div className="stack-item__top">
                  <strong>
                    {signal.symbol_code} · {signal.side} · {signal.timeframe}
                  </strong>
                  <span className={`status-pill status-pill--${mapSignalStatusToQueueStatus(signal.status)}`}>
                    {signal.status}
                  </span>
                </div>
                <p>
                  Confidence {formatPercentage(signal.confidence)} · R:R {formatRatio(signal.risk_to_reward)}
                </p>
                <small>{formatShortDateTime(signal.signal_time)}</small>
              </article>
            ))}
          </div>
        </div>
      ) : (
        <div className="empty-state empty-state--compact">
          <strong>No paper-trade signals yet.</strong>
          <p>Signals will appear here only after the runtime is enabled and approved symbols generate eligible setups.</p>
        </div>
      )}

      {positions.length > 0 ? (
        <div className="position-list">
          {positions.slice(0, 4).map((position) => (
            <article className="position-item" key={position.position_id}>
              <div>
                <strong>
                  {position.symbol_code} · {position.side}
                </strong>
                <p>
                  {formatQuantity(position.quantity)} · {position.status}
                </p>
              </div>
              <span>{formatPnL(position.unrealized_pnl ?? position.realized_pnl)}</span>
            </article>
          ))}
        </div>
      ) : (
        <div className="empty-state empty-state--compact">
          <strong>No open or historical positions yet.</strong>
          <p>Once orders are accepted and filled, positions will show up here with live or realized PnL.</p>
        </div>
      )}
    </section>
  );
}
