"""Shared symbol normalization and validation contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Protocol

from rl_trade_common import Settings

_SYMBOL_SEPARATOR_PATTERN = re.compile(r"[\s/_-]+")
_VALID_SYMBOL_PATTERN = re.compile(r"^[A-Z0-9]{6,32}$")


@dataclass(frozen=True, slots=True)
class SymbolValidationDecision:
    requested_symbol: str
    normalized_input: str
    normalized_symbol: str | None
    provider: str
    is_valid: bool
    reason: str | None = None
    base_currency: str | None = None
    quote_currency: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


class SymbolValidationProvider(Protocol):
    def validate_symbol(self, settings: Settings, requested_symbol: str) -> SymbolValidationDecision:
        ...


def normalize_symbol_input(requested_symbol: str) -> str:
    normalized = _SYMBOL_SEPARATOR_PATTERN.sub("", requested_symbol.strip().upper())
    return normalized


def is_plausible_symbol_code(symbol_code: str) -> bool:
    return bool(_VALID_SYMBOL_PATTERN.fullmatch(symbol_code))


def infer_forex_components(symbol_code: str) -> tuple[str | None, str | None]:
    if len(symbol_code) < 6:
        return None, None

    core = symbol_code[:6]
    if not core.isalpha():
        return None, None

    return core[:3], core[3:6]
