# -*- coding: utf-8 -*-
"""Tests for performance metrics."""

from datetime import datetime
from backtest.metrics import PerformanceReport, calc_performance
from backtest.portfolio import Portfolio
from backtest.models import Trade, OrderSide


class TestPerformanceReport:
    def test_summary_format(self):
        report = PerformanceReport(
            initial_cash=100_000,
            final_equity=110_000,
            total_return=0.10,
            annualized_return=0.25,
            sharpe_ratio=1.5,
            max_drawdown=0.05,
            win_rate=0.6,
            profit_factor=2.0,
            total_trades=10,
            total_commission=30.0,
            total_stamp_tax=100.0,
            total_transfer_fee=2.0,
            total_cost=132.0,
        )
        summary = report.summary()
        assert "100,000.00" in summary
        assert "110,000.00" in summary
        assert "10.00%" in summary


class TestCalcPerformance:
    def test_empty_portfolio(self):
        portfolio = Portfolio(initial_cash=100_000)
        report = calc_performance(portfolio)
        assert report.initial_cash == 100_000
        assert report.total_trades == 0

    def test_with_trades(self):
        portfolio = Portfolio(initial_cash=100_000)

        # Buy
        buy = Trade(symbol="000001", side=OrderSide.BUY, price=10.0, quantity=1000, commission=5.0, stamp_tax=0.0, transfer_fee=2.0)
        portfolio.execute_trade(buy)

        # Add equity snapshots
        ts1 = datetime(2024, 1, 2, 9, 30)
        ts2 = datetime(2024, 1, 2, 10, 0)
        portfolio.snapshot(ts1, {"000001": 10.0})
        portfolio.snapshot(ts2, {"000001": 11.0})

        report = calc_performance(portfolio)
        assert report.total_trades == 1
        assert report.total_commission == 5.0
        assert report.final_equity > 100_000  # Price went up

    def test_win_rate_calculation(self):
        portfolio = Portfolio(initial_cash=100_000)

        # Buy 1000 shares at 10
        buy = Trade(symbol="000001", side=OrderSide.BUY, price=10.0, quantity=1000, timestamp=datetime(2024, 1, 2, 9, 30))
        portfolio.execute_trade(buy)

        # Sell 500 at 12 (profit)
        sell1 = Trade(symbol="000001", side=OrderSide.SELL, price=12.0, quantity=500, timestamp=datetime(2024, 1, 3, 10, 0))
        portfolio.execute_trade(sell1)

        # Sell 500 at 8 (loss)
        sell2 = Trade(symbol="000001", side=OrderSide.SELL, price=8.0, quantity=500, timestamp=datetime(2024, 1, 4, 10, 0))
        portfolio.execute_trade(sell2)

        # Add equity snapshots
        for i, price in enumerate([10.0, 11.0, 9.0, 8.0]):
            ts = datetime(2024, 1, 2 + i, 10, 0)
            portfolio.snapshot(ts, {"000001": price})

        report = calc_performance(portfolio)
        assert report.win_rate == 0.5  # 1 win, 1 loss
