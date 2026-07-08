# -*- coding: utf-8 -*-
"""A-share strategy backtester with realistic trading mechanics."""

from .models import (
    Bar, Order, Trade, Position,
    BoardType, OrderSide, OrderType, OrderStatus, TradingPhase,
    get_board_type, get_price_limit_pct, calc_price_range,
)
from .exchange import Exchange, OrderBook
from .portfolio import Portfolio
from .strategy import Strategy, BuyAndHold
from .data import MarketData
from .mock_data import MockMarketData
from .engine import Backtester
from .metrics import PerformanceReport, calc_performance
from .session import get_trading_phase, is_auction_phase, is_continuous_phase
from .broker import calc_commission, calc_stamp_tax, calc_transfer_fee, calc_total_cost
from .exceptions import (
    BacktestError, InvalidOrderError, InsufficientFundsError,
    InsufficientPositionError, PriceLimitError, LotSizeError,
)

__all__ = [
    "Bar", "Order", "Trade", "Position",
    "BoardType", "OrderSide", "OrderType", "OrderStatus", "TradingPhase",
    "get_board_type", "get_price_limit_pct", "calc_price_range",
    "Exchange", "OrderBook", "Portfolio",
    "Strategy", "BuyAndHold",
    "MarketData", "MockMarketData", "Backtester",
    "PerformanceReport", "calc_performance",
    "get_trading_phase", "is_auction_phase", "is_continuous_phase",
    "calc_commission", "calc_stamp_tax", "calc_transfer_fee", "calc_total_cost",
    "BacktestError", "InvalidOrderError", "InsufficientFundsError",
    "InsufficientPositionError", "PriceLimitError", "LotSizeError",
]
