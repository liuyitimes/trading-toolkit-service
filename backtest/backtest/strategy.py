# -*- coding: utf-8 -*-
"""Strategy base class and example strategy."""

from abc import ABC, abstractmethod
from typing import Optional
from .models import Bar, Order, OrderSide, OrderType, TradingPhase
from .data import MarketData
from .portfolio import Portfolio


class Strategy(ABC):
    """Base class for all trading strategies."""

    def __init__(self, symbols: list[str]):
        self.symbols = symbols
        self.data: Optional[MarketData] = None
        self.portfolio: Optional[Portfolio] = None

    def on_init(self, data: MarketData, portfolio: Portfolio):
        """Called once before backtesting starts."""
        self.data = data
        self.portfolio = portfolio

    @abstractmethod
    def on_bar(self, bar: Bar, portfolio: Portfolio, phase: TradingPhase) -> list[Order]:
        """Called on each 1-minute bar. Return orders to submit."""
        ...

    def on_trade(self, trade):
        """Called after each executed trade."""
        pass

    def on_finish(self):
        """Called after backtesting completes."""
        pass


class BuyAndHold(Strategy):
    """Example: buy a fixed amount on the first bar, hold forever."""

    def __init__(self, symbols: list[str], buy_qty: int = 500):
        super().__init__(symbols)
        self.buy_qty = buy_qty
        self._bought: set[str] = set()

    def on_bar(self, bar: Bar, portfolio: Portfolio, phase: TradingPhase) -> list[Order]:
        if bar.symbol in self._bought:
            return []

        if portfolio.get_position_qty(bar.symbol) >= self.buy_qty:
            self._bought.add(bar.symbol)
            return []

        return [Order(
            symbol=bar.symbol,
            side=OrderSide.BUY,
            order_type=OrderType.LIMIT,
            price=bar.close,
            quantity=self.buy_qty,
        )]
