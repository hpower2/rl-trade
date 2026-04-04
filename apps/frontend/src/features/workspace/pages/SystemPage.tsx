import type {
  MT5ConnectionStatusResponse,
  PaperTradingStatusResponse,
} from "../../../api";
import type { AlertSnapshot, EventRow } from "../../../demo-state";
import { AlertSection } from "../sections/AlertSection";
import { LiveEventSection } from "../sections/LiveEventSection";
import { MT5StatusSection } from "../sections/MT5StatusSection";

export function SystemPage(props: {
  alerts: AlertSnapshot[];
  approvedSymbolCount: number;
  isRefreshingOperatorData: boolean;
  liveEventRows: EventRow[];
  mt5Status: MT5ConnectionStatusResponse | null;
  onRefreshOperatorData: () => void;
  refreshError: string | null;
  tradingStatus: PaperTradingStatusResponse | null;
}) {
  return (
    <>
      <div className="page-intro">
        <p className="section-note">
          Keep the broker connection, safeguard messages, and live event stream in one operational
          surface so paper trading never relies on hidden state.
        </p>
      </div>
      <div className="detail-layout">
        <MT5StatusSection
          approvedSymbolCount={props.approvedSymbolCount}
          isRefreshingOperatorData={props.isRefreshingOperatorData}
          mt5Status={props.mt5Status}
          onRefresh={props.onRefreshOperatorData}
          refreshError={props.refreshError}
          tradingStatus={props.tradingStatus}
        />
        <LiveEventSection liveEventRows={props.liveEventRows} />
      </div>
      <div className="detail-layout detail-layout--single">
        <AlertSection alerts={props.alerts} />
      </div>
    </>
  );
}
