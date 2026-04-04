import type { MT5ConnectionStatusResponse, PaperTradingStatusResponse } from "../../../api";
import { formatShortDateTime } from "../view-models";

export function MT5StatusSection({
  approvedSymbolCount,
  isRefreshingOperatorData,
  mt5Status,
  onRefresh,
  refreshError,
  tradingStatus,
}: {
  approvedSymbolCount: number;
  isRefreshingOperatorData: boolean;
  mt5Status: MT5ConnectionStatusResponse | null;
  onRefresh: () => void;
  refreshError: string | null;
  tradingStatus: PaperTradingStatusResponse | null;
}) {
  return (
    <section className="detail-panel">
      <div className="section-header">
        <div>
          <p className="section-kicker">MT5 status</p>
          <h2>Demo account health snapshot</h2>
        </div>
        <button className="secondary-button secondary-button--compact" onClick={onRefresh} type="button">
          {isRefreshingOperatorData ? "Refreshing…" : "Refresh"}
        </button>
      </div>

      <dl className="status-grid">
        <div>
          <dt>Server</dt>
          <dd>{mt5Status?.server_name ?? "—"}</dd>
        </div>
        <div>
          <dt>Login</dt>
          <dd>{mt5Status?.account_login?.toString() ?? "—"}</dd>
        </div>
        <div>
          <dt>Account</dt>
          <dd>{mt5Status?.account_name ?? "—"}</dd>
        </div>
        <div>
          <dt>Connection</dt>
          <dd>{tradingStatus?.connection_status ?? mt5Status?.status ?? "checking"}</dd>
        </div>
        <div>
          <dt>Demo verified</dt>
          <dd>{mt5Status?.is_demo == null ? "—" : mt5Status.is_demo ? "yes" : "no"}</dd>
        </div>
        <div>
          <dt>Paper trading</dt>
          <dd>{tradingStatus?.paper_trading_allowed ? "allowed" : "blocked"}</dd>
        </div>
      </dl>

      <div className="stack-section">
        <div className="mini-header">
          <strong>Runtime counters</strong>
          <span>live snapshot</span>
        </div>
        <div className="kpi-pair-grid">
          <div className="kpi-pair">
            <span>Approved symbols</span>
            <strong>{tradingStatus?.approved_symbol_count ?? approvedSymbolCount}</strong>
          </div>
          <div className="kpi-pair">
            <span>Open orders</span>
            <strong>{tradingStatus?.open_order_count ?? 0}</strong>
          </div>
          <div className="kpi-pair">
            <span>Open positions</span>
            <strong>{tradingStatus?.open_position_count ?? 0}</strong>
          </div>
          <div className="kpi-pair">
            <span>Last started</span>
            <strong>{tradingStatus?.last_started_at ? formatShortDateTime(tradingStatus.last_started_at) : "—"}</strong>
          </div>
        </div>
      </div>

      {refreshError ? <p className="form-feedback form-feedback--error">{refreshError}</p> : null}
    </section>
  );
}
