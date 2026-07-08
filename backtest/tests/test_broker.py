# -*- coding: utf-8 -*-
"""Tests for broker fee calculation and order validation."""

import pytest
from backtest.broker import (
    calc_commission, calc_stamp_tax, calc_transfer_fee, calc_total_cost,
    validate_order,
)
from backtest.models import Order, OrderSide, OrderType, BoardType
from backtest.exceptions import (
    InvalidOrderError, InsufficientFundsError, InsufficientPositionError,
    PriceLimitError, LotSizeError,
)


class TestFeeCalculation:
    def test_commission_minimum(self):
        # Small amount should hit minimum 5 yuan
        assert calc_commission(1000) == 5.0

    def test_commission_above_minimum(self):
        # 10000 * 0.0003 = 3.0, but min is 5.0
        assert calc_commission(10000) == 5.0

    def test_commission_large_amount(self):
        # 100000 * 0.0003 = 30.0
        assert calc_commission(100000) == pytest.approx(30.0)

    def test_stamp_tax(self):
        assert calc_stamp_tax(100000) == 100.0

    def test_transfer_fee(self):
        assert calc_transfer_fee(100000) == 2.0

    def test_total_cost_buy(self):
        cost = calc_total_cost(100000, OrderSide.BUY)
        # commission(30) + stamp(0 for buy) + transfer(2) = 32
        assert cost == pytest.approx(32.0)

    def test_total_cost_sell(self):
        cost = calc_total_cost(100000, OrderSide.SELL)
        # commission(30) + stamp(100) + transfer(2) = 132
        assert cost == 132.0


class TestOrderValidation:
    def test_valid_buy_order(self):
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        # Should not raise
        validate_order(order, cash=2000, position_qty=0, prev_close=10.0)

    def test_lot_size_error(self):
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=150)
        with pytest.raises(LotSizeError):
            validate_order(order, cash=10000, position_qty=0, prev_close=10.0)

    def test_zero_quantity_error(self):
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=0)
        with pytest.raises(InvalidOrderError):
            validate_order(order, cash=10000, position_qty=0, prev_close=10.0)

    def test_price_limit_error(self):
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=12.0, quantity=100)
        with pytest.raises(PriceLimitError):
            validate_order(order, cash=100000, position_qty=0, prev_close=10.0, board_type=BoardType.MAIN)

    def test_insufficient_funds_error(self):
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=1000)
        with pytest.raises(InsufficientFundsError):
            validate_order(order, cash=5000, position_qty=0, prev_close=10.0)

    def test_insufficient_position_error(self):
        order = Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        with pytest.raises(InsufficientPositionError):
            validate_order(order, cash=10000, position_qty=50, prev_close=10.0)

    def test_market_buy_with_market_type(self):
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.MARKET, price=0, quantity=100)
        # Market orders skip price limit check
        validate_order(order, cash=10000, position_qty=0, prev_close=10.0)
