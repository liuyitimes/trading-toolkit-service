# -*- coding: utf-8 -*-
"""Tests for exchange matching engine."""

from datetime import datetime
from backtest.exchange import Exchange, OrderBook
from backtest.models import Order, OrderSide, OrderType, OrderStatus, TradingPhase


class TestOrderBook:
    def test_add_and_get_best_bid(self):
        book = OrderBook()
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        book.add_order(order)
        assert book.get_best_bid() == 10.0

    def test_add_and_get_best_ask(self):
        book = OrderBook()
        order = Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.5, quantity=100)
        book.add_order(order)
        assert book.get_best_ask() == 10.5

    def test_bid_sorted_descending(self):
        book = OrderBook()
        book.add_order(Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=100))
        book.add_order(Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.5, quantity=100))
        assert book.get_best_bid() == 10.5

    def test_ask_sorted_ascending(self):
        book = OrderBook()
        book.add_order(Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.5, quantity=100))
        book.add_order(Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.0, quantity=100))
        assert book.get_best_ask() == 10.0

    def test_remove_order(self):
        book = OrderBook()
        order = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        book.add_order(order)
        book.remove(order)
        assert book.get_best_bid() is None

    def test_clear(self):
        book = OrderBook()
        book.add_order(Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=100))
        book.add_order(Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.5, quantity=100))
        book.clear()
        assert book.get_best_bid() is None
        assert book.get_best_ask() is None


class TestExchangeContinuous:
    def test_buy_matches_sell(self):
        exchange = Exchange()
        ts = datetime(2024, 1, 2, 9, 30)

        # Place sell order first
        sell = Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        exchange.submit_order(sell, TradingPhase.MORNING, ts)

        # Place buy order
        buy = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        trades = exchange.submit_order(buy, TradingPhase.MORNING, ts)

        assert len(trades) == 1
        assert trades[0].price == 10.0
        assert trades[0].quantity == 100
        assert buy.status == OrderStatus.FILLED
        assert sell.status == OrderStatus.FILLED

    def test_buy_no_match_higher_price(self):
        exchange = Exchange()
        ts = datetime(2024, 1, 2, 9, 30)

        # Place sell order at 10.5
        sell = Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.5, quantity=100)
        exchange.submit_order(sell, TradingPhase.MORNING, ts)

        # Place buy order at 10.0 (won't match)
        buy = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        trades = exchange.submit_order(buy, TradingPhase.MORNING, ts)

        assert len(trades) == 0
        assert buy.status == OrderStatus.PENDING

    def test_partial_fill(self):
        exchange = Exchange()
        ts = datetime(2024, 1, 2, 9, 30)

        # Place sell order for 100 shares
        sell = Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        exchange.submit_order(sell, TradingPhase.MORNING, ts)

        # Place buy order for 200 shares
        buy = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=200)
        trades = exchange.submit_order(buy, TradingPhase.MORNING, ts)

        assert len(trades) == 1
        assert trades[0].quantity == 100
        assert buy.status == OrderStatus.PARTIAL
        assert buy.filled_qty == 100

    def test_market_buy_fills_best_ask(self):
        exchange = Exchange()
        ts = datetime(2024, 1, 2, 9, 30)

        # Place sell orders at different prices
        sell1 = Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.5, quantity=100)
        sell2 = Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        exchange.submit_order(sell1, TradingPhase.MORNING, ts)
        exchange.submit_order(sell2, TradingPhase.MORNING, ts)

        # Market buy
        buy = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.MARKET, price=999999, quantity=100)
        trades = exchange.submit_order(buy, TradingPhase.MORNING, ts)

        assert len(trades) == 1
        assert trades[0].price == 10.0  # Best ask


class TestExchangeAuction:
    def test_auction_matching(self):
        exchange = Exchange()
        ts = datetime(2024, 1, 2, 9, 15)

        # Place orders during auction
        buy1 = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        buy2 = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=9.5, quantity=100)
        sell1 = Order(symbol="000001", side=OrderSide.SELL, order_type=OrderType.LIMIT, price=9.8, quantity=100)

        exchange.submit_order(buy1, TradingPhase.OPENING_AUCTION, ts)
        exchange.submit_order(buy2, TradingPhase.OPENING_AUCTION, ts)
        exchange.submit_order(sell1, TradingPhase.OPENING_AUCTION, ts)

        # Match auction
        trades = exchange.match_auction("000001")

        assert len(trades) == 1
        # Clearing price should maximize volume
        assert trades[0].quantity == 100

    def test_no_match_without_both_sides(self):
        exchange = Exchange()
        ts = datetime(2024, 1, 2, 9, 15)

        # Only buy orders
        buy1 = Order(symbol="000001", side=OrderSide.BUY, order_type=OrderType.LIMIT, price=10.0, quantity=100)
        exchange.submit_order(buy1, TradingPhase.OPENING_AUCTION, ts)

        trades = exchange.match_auction("000001")
        assert len(trades) == 0
