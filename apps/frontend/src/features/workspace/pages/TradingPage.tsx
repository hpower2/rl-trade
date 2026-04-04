import type {
  PaperTradePositionResponse,
  PaperTradeSignalResponse,
  PaperTradingStatusResponse,
} from "../../../api";
import type { TradingAction } from "../types";
import { PaperTradingSection } from "../sections/PaperTradingSection";

export function TradingPage(props: {
  activeTradingAction: TradingAction | null;
  isRefreshingOperatorData: boolean;
  onTradingAction: (action: TradingAction) => void;
  positions: PaperTradePositionResponse[];
  signals: PaperTradeSignalResponse[];
  tradingActionError: string | null;
  tradingStatus: PaperTradingStatusResponse | null;
}) {
  return (
    <>
      <div className="page-intro">
        <p className="section-note">
          The runtime controls live here on purpose: the operator can see whether backend approval
          and demo verification permit trading before they try to start anything.
        </p>
      </div>
      <div className="detail-layout detail-layout--single">
        <PaperTradingSection
          activeTradingAction={props.activeTradingAction}
          isRefreshingOperatorData={props.isRefreshingOperatorData}
          onTradingAction={props.onTradingAction}
          positions={props.positions}
          signals={props.signals}
          tradingActionError={props.tradingActionError}
          tradingStatus={props.tradingStatus}
        />
      </div>
    </>
  );
}
