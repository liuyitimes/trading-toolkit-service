# -*- coding: utf-8 -*-
"""Tests for backtest models."""

from datetime import datetime
from backtest.models import (
    Bar, Order, Trade, Position,
    BoardType, OrderSide, OrderType, OrderStatus, TradingPhase,
    get_board_type, get_price_limit_pct, calc_price_range,
)


class TestBar:
    def test_turnover(self):
        bar = Bar(symbol="000001", open=10.0, high=11.0, low=9.0, close=10.5, volume=1000, timestamp=datetime.now())
        assert bar.turnover == 10500.0


class TestOrder:
    def test_remaining(self):
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=500, filled_qty=200)
        assert order.remaining == 300

    def test_is_active_pending(self):
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=500, status=OrderStatus.PENDING)
        assert order.is_active is True

    def test_is_active_filled(self):
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=500, status=OrderStatus.FILLED)
        assert order.is_active is False


class TestTrade:
    def test_total_cost(self):
        trade = Trade(commission=5.0, stamp_tax=10.0, transfer_fee=2.0)
        assert trade.total_cost == 17.0


class TestPosition:
    def test_buy_update(self):
        pos = Position(symbol="000001")
        trade = Trade(side=OrderSide.BUY, price=10.0, quantity=500, timestamp=datetime.now())
        pos.update(trade)
        assert pos.quantity == 500
        assert pos.avg_cost == 10.0

    def test_sell_update(self):
        pos = Position(symbol="000001", quantity=500, avg_cost=10.0)
        trade = Trade(side=OrderSide.SELL, price=12.0, quantity=500, timestamp=datetime.now())
        pos.update(trade)
        assert pos.quantity == 0
        assert pos.realized_pnl == 1000.0

    def test_partial_sell(self):
        pos = Position(symbol="000001", quantity=500, avg_cost=10.0)
        trade = Trade(side=OrderSide.SELL, price=12.0, quantity=300, timestamp=datetime.now())
        pos.update(trade)
        assert pos.quantity == 200
        assert pos.realized_pnl == 600.0


class TestBoardType:
    def test_main_board(self):
        assert get_board_type("000001") == BoardType.MAIN
        assert get_board_type("600000") == BoardType.MAIN

    def test_star_board(self):
        assert get_board_type("688000") == BoardType.STAR

    def test_chinext_board(self):
        assert get_board_type("300000") == BoardType.CHINEXT
        assert get_board_type("301000") == BoardType.CHINEXT

    def test_with_suffix(self):
        assert get_board_type("000001.SZ") == BoardType.MAIN
        assert get_board_type("688000.SH") == BoardType.STAR


class TestPriceLimits:
    def test_main_board_limits(self):
        lower, upper = calc_price_range(10.0, BoardType.MAIN)
        assert lower == 9.0
        assert upper == 11.0

    def test_star_board_limits(self):
        lower, upper = calc_price_range(10.0, BoardType.STAR)
        assert lower == 8.0
        assert upper == 12.0

    def test_price_limit_pct(self):
        assert get_price_limit_pct(BoardType.MAIN) == 0.10
        assert get_price_limit_pct(BoardType.STAR) == 0.20
        assert get_price_limit_pct(BoardType.CHINEXT) == 0.20
        assert get_price_limit_pct(BoardType.ST) == 0.05
