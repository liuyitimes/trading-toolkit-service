# -*- coding: utf-8 -*-
"""Position tracking, equity curve, and trade history."""

from datetime import datetime, date
from typing import Optional
from .models import Trade, Position, OrderSide


class Portfolio:
    """Tracks cash, positions, and equity over time."""

    def __init__(self, initial_cash: float = 1_000_000.0):
        self.initial_cash = initial_cash
        self.cash = initial_cash
        self.positions: dict[str, Position] = {}
        self.trades: list[Trade] = []
        self.equity_curve: list[tuple[datetime, float]] = []

    def execute_trade(self, trade: Trade):
        """Update portfolio state after a trade."""
        self.trades.append(trade)
        amount = trade.price * trade.quantity
        total_cost = trade.commission + trade.stamp_tax + trade.transfer_fee

        if trade.side == OrderSide.BUY:
            self.cash -= amount + total_cost
            pos = self.positions.get(trade.symbol)
            if pos is None:
                pos = Position(symbol=trade.symbol)
                self.positions[trade.symbol] = pos
            pos.update(trade)
        else:
            self.cash += amount - total_cost
            pos = self.positions.get(trade.symbol)
            if pos:
                pos.update(trade)
                if pos.quantity <= 0:
                    del self.positions[trade.symbol]

    def get_position(self, symbol: str) -> Optional[Position]:
        return self.positions.get(symbol)

    def get_position_qty(self, symbol: str) -> int:
        pos = self.positions.get(symbol)
        return pos.quantity if pos else 0

    def get_equity(self, current_prices: dict[str, float] = None) -> float:
        """Total portfolio value = cash + market value of positions."""
        equity = self.cash
        for sym, pos in self.positions.items():
            price = (current_prices or {}).get(sym, pos.avg_cost)
            equity += pos.quantity * price
        return equity

    def snapshot(self, ts: datetime, current_prices: dict[str, float] = None):
        """Record equity at a point in time."""
        eq = self.get_equity(current_prices)
        self.equity_curve.append((ts, eq))

    @property
    def total_realized_pnl(self) -> float:
        return sum(p.realized_pnl for p in self.positions.values())

    @property
    def total_commission(self) -> float:
        return sum(t.commission for t in self.trades)

    @property
    def total_stamp_tax(self) -> float:
        return sum(t.stamp_tax for t in self.trades)

    @property
    def total_transfer_fee(self) -> float:
        return sum(t.transfer_fee for t in self.trades)

    def is_t1_available(self, symbol: str, current_date: date) -> bool:
        """Check if position is available for selling (T+1 rule)."""
        pos = self.positions.get(symbol)
        if not pos or pos.quantity <= 0:
            return False
        if pos.buy_date is None:
            return True
        return pos.buy_date.date() < current_date
