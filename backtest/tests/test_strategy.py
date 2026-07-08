# -*- coding: utf-8 -*-
"""Tests for strategy base class and examples."""

from datetime import datetime
from backtest.strategy import BuyAndHold
from backtest.models import Bar, Order, OrderSide, OrderType, TradingPhase
from backtest.portfolio import Portfolio


class TestBuyAndHold:
    def setup_method(self):
        self.strategy = BuyAndHold(symbols=["000001"], buy_qty=500)
        self.portfolio = Portfolio(initial_cash=100_000)

    def test_buy_on_first_bar(self):
        bar = Bar(symbol="000001", open=10.0, high=10.5, low=9.5, close=10.0, volume=1000, timestamp=datetime.now())
        orders = self.strategy.on_bar(bar, self.portfolio, TradingPhase.MORNING)

        assert len(orders) == 1
        assert orders[0].side == OrderSide.BUY
        assert orders[0].quantity == 500
        assert orders[0].price == 10.0

    def test_no_buy_after_initial(self):
        bar = Bar(symbol="000001", open=10.0, high=10.5, low=9.5, close=10.0, volume=1000, timestamp=datetime.now())

        # First bar - should buy
        orders = self.strategy.on_bar(bar, self.portfolio, TradingPhase.MORNING)
        assert len(orders) == 1

        # Simulate trade execution
        from backtest.models import Trade
        trade = Trade(symbol="000001", side=OrderSide.BUY, price=10.0, quantity=500)
        self.portfolio.execute_trade(trade)

        # Second bar - should not buy again
        orders = self.strategy.on_bar(bar, self.portfolio, TradingPhase.MORNING)
        assert len(orders) == 0

    def test_no_buy_if_position_sufficient(self):
        # Pre-set position
        from backtest.models import Position
        self.portfolio.positions["000001"] = Position(symbol="000001", quantity=500)

        bar = Bar(symbol="000001", open=10.0, high=10.5, low=9.5, close=10.0, volume=1000, timestamp=datetime.now())
        orders = self.strategy.on_bar(bar, self.portfolio, TradingPhase.MORNING)

        assert len(orders) == 0
