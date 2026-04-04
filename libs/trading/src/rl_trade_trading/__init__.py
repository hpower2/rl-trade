"""Trading integration helpers."""

from rl_trade_trading.approval import (
    ApprovalDecision,
    evaluate_model_approval,
    get_active_approved_model,
    is_symbol_tradeable,
)
from rl_trade_trading.paper import PaperTradeDecision, calculate_risk_to_reward, evaluate_paper_trade
from rl_trade_trading.mt5 import (
    MT5CandleRecord,
    MT5ConnectionState,
    MT5Gateway,
    MT5HistoricalOrderRecord,
    MT5IntegrationError,
    MT5OrderResult,
    MT5PositionRecord,
    MT5SymbolRecord,
)
from rl_trade_trading.symbols import (
    SymbolValidationDecision,
    SymbolValidationProvider,
    infer_forex_components,
    is_plausible_symbol_code,
    normalize_symbol_input,
)

__all__ = [
    "ApprovalDecision",
    "MT5CandleRecord",
    "MT5ConnectionState",
    "MT5Gateway",
    "MT5HistoricalOrderRecord",
    "MT5IntegrationError",
    "MT5OrderResult",
    "MT5PositionRecord",
    "MT5SymbolRecord",
    "PaperTradeDecision",
    "SymbolValidationDecision",
    "SymbolValidationProvider",
    "calculate_risk_to_reward",
    "evaluate_model_approval",
    "evaluate_paper_trade",
    "get_active_approved_model",
    "infer_forex_components",
    "is_symbol_tradeable",
    "is_plausible_symbol_code",
    "normalize_symbol_input",
]
