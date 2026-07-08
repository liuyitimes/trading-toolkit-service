# -*- coding: utf-8 -*-
"""Tests for portfolio tracking."""

from datetime import datetime, date
from backtest.portfolio import Portfolio
from backtest.models import Trade, OrderSide


class TestPortfolio:
    def test_initial_state(self):
        portfolio = Portfolio(initial_cash=100_000)
        assert portfolio.cash == 100_000
        assert len(portfolio.positions) == 0
        assert len(portfolio.trades) == 0

    def test_buy_trade(self):
        portfolio = Portfolio(initial_cash=100_000)
        trade = Trade(
            symbol="000001",
            side=OrderSide.BUY,
            price=10.0,
            quantity=1000,
            commission=5.0,
            stamp_tax=0.0,
            transfer_fee=2.0,
        )
        portfolio.execute_trade(trade)

        assert portfolio.cash == 100_000 - 10_000 - 7.0  # 89_993.0
        assert portfolio.get_position_qty("000001") == 1000
        assert len(portfolio.trades) == 1

    def test_sell_trade(self):
        portfolio = Portfolio(initial_cash=100_000)
        # Buy first
        buy = Trade(symbol="000001", side=OrderSide.BUY, price=10.0, quantity=1000, commission=5.0, stamp_tax=0.0, transfer_fee=2.0)
        portfolio.execute_trade(buy)

        # Sell
        sell = Trade(symbol="000001", side=OrderSide.SELL, price=12.0, quantity=1000, commission=5.0, stamp_tax=12.0, transfer_fee=2.4)
        portfolio.execute_trade(sell)

        assert portfolio.get_position_qty("000001") == 0
        assert "000001" not in portfolio.positions
        assert len(portfolio.trades) == 2

    def test_get_equity(self):
        portfolio = Portfolio(initial_cash=100_000)
        buy = Trade(symbol="000001", side=OrderSide.BUY, price=10.0, quantity=1000, commission=5.0, stamp_tax=0.0, transfer_fee=2.0)
        portfolio.execute_trade(buy)

        equity = portfolio.get_equity({"000001": 12.0})
        # cash(89_993) + position(1000 * 12 = 12000) = 101_993
        assert equity == pytest.approx(101_993.0, rel=1e-3)

    def test_snapshot(self):
        portfolio = Portfolio(initial_cash=100_000)
        ts = datetime(2024, 1, 2, 9, 30)
        portfolio.snapshot(ts, {})
        assert len(portfolio.equity_curve) == 1
        assert portfolio.equity_curve[0] == (ts, 100_000.0)

    def test_realized_pnl(self):
        portfolio = Portfolio(initial_cash=100_000)
        buy = Trade(symbol="000001", side=OrderSide.BUY, price=10.0, quantity=1000, commission=5.0, stamp_tax=0.0, transfer_fee=2.0)
        portfolio.execute_trade(buy)

        sell = Trade(symbol="000001", side=OrderSide.SELL, price=12.0, quantity=1000, commission=5.0, stamp_tax=12.0, transfer_fee=2.4)
        portfolio.execute_trade(sell)

        # Realized PnL should be tracked in position
        assert "000001" not in portfolio.positions  # Position deleted after full sell

    def test_t1_available(self):
        portfolio = Portfolio(initial_cash=100_000)
        ts = datetime(2024, 1, 2, 9, 30)
        buy = Trade(symbol="000001", side=OrderSide.BUY, price=10.0, quantity=1000, timestamp=ts)
        portfolio.execute_trade(buy)

        # Same day - not available
        assert portfolio.is_t1_available("000001", date(2024, 1, 2)) is False

        # Next day - available
        assert portfolio.is_t1_available("000001", date(2024, 1, 3)) is True

    def test_t1_no_position(self):
        portfolio = Portfolio(initial_cash=100_000)
        assert portfolio.is_t1_available("000001", date(2024, 1, 2)) is False


import pytest
