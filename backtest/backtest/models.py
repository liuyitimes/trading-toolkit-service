# -*- coding: utf-8 -*-
"""Core data models for the backtest engine."""

from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
from typing import Optional
import uuid


class BoardType(Enum):
    """Stock board type, determines price limit percentage."""
    MAIN = "main"          # 主板: ±10%
    STAR = "star"          # 科创板: ±20%
    CHINEXT = "chinext"    # 创业板: ±20%
    ST = "st"              # ST股: ±5%


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


class OrderType(Enum):
    LIMIT = "limit"
    MARKET = "market"


class OrderStatus(Enum):
    PENDING = "pending"
    PARTIAL = "partial"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class TradingPhase(Enum):
    """Trading session phases."""
    PRE_MARKET = "pre_market"
    OPENING_AUCTION = "opening_auction"      # 09:15-09:25
    AUCTION_NO_CANCEL = "auction_no_cancel"  # 09:20-09:25
    BROKEN = "broken"                        # 09:25-09:30
    MORNING = "morning"                      # 09:30-11:30
    LUNCH = "lunch"                          # 11:30-13:00
    AFTERNOON = "afternoon"                  # 13:00-14:57
    CLOSING_AUCTION = "closing_auction"      # 14:57-15:00
    POST_MARKET = "post_market"


@dataclass
class Bar:
    """1-minute OHLCV bar."""
    symbol: str
    open: float
    high: float
    low: float
    close: float
    volume: int
    timestamp: datetime

    @property
    def turnover(self) -> float:
        return self.close * self.volume


@dataclass
class Order:
    """Trading order."""
    symbol: str
    side: OrderSide
    order_type: OrderType
    price: float
    quantity: int
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    filled_qty: int = 0
    status: OrderStatus = OrderStatus.PENDING
    timestamp: Optional[datetime] = None
    filled_price: float = 0.0

    @property
    def remaining(self) -> int:
        return self.quantity - self.filled_qty

    @property
    def is_active(self) -> bool:
        return self.status in (OrderStatus.PENDING, OrderStatus.PARTIAL)


@dataclass
class Trade:
    """Executed trade record."""
    id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    order_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    price: float = 0.0
    quantity: int = 0
    timestamp: Optional[datetime] = None
    commission: float = 0.0
    stamp_tax: float = 0.0
    transfer_fee: float = 0.0

    @property
    def total_cost(self) -> float:
        return self.commission + self.stamp_tax + self.transfer_fee


@dataclass
class Position:
    """Stock position."""
    symbol: str
    quantity: int = 0
    avg_cost: float = 0.0
    realized_pnl: float = 0.0
    buy_date: Optional[datetime] = None  # For T+1 enforcement

    def update(self, trade: Trade):
        if trade.side == OrderSide.BUY:
            total_cost = self.avg_cost * self.quantity + trade.price * trade.quantity
            self.quantity += trade.quantity
            self.avg_cost = total_cost / self.quantity if self.quantity else 0
            self.buy_date = trade.timestamp
        else:
            pnl = (trade.price - self.avg_cost) * trade.quantity
            self.realized_pnl += pnl
            self.quantity -= trade.quantity
            if self.quantity <= 0:
                self.quantity = 0
                self.avg_cost = 0.0


# --- Price limit helpers ---

_PRICE_LIMITS = {
    BoardType.MAIN: 0.10,
    BoardType.STAR: 0.20,
    BoardType.CHINEXT: 0.20,
    BoardType.ST: 0.05,
}


def get_board_type(code: str) -> BoardType:
    """Auto-detect board type from stock code prefix."""
    code = str(code).replace(".SH", "").replace(".SZ", "")
    if code.startswith("688"):
        return BoardType.STAR
    if code.startswith("300") or code.startswith("301"):
        return BoardType.CHINEXT
    return BoardType.MAIN


def get_price_limit_pct(board_type: BoardType) -> float:
    return _PRICE_LIMITS.get(board_type, 0.10)


def calc_price_range(prev_close: float, board_type: BoardType):
    """Return (lower_limit, upper_limit) for the day."""
    pct = get_price_limit_pct(board_type)
    lower = round(prev_close * (1 - pct), 2)
    upper = round(prev_close * (1 + pct), 2)
    return lower, upper
