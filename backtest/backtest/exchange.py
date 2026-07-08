# -*- coding: utf-8 -*-
"""Matching engine: OrderBook, call auction, and continuous auction."""

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Optional
from datetime import datetime

from .models import (
    Order, Trade, OrderSide, OrderType, OrderStatus,
    Bar, TradingPhase,
)
from .broker import calc_commission, calc_stamp_tax, calc_transfer_fee


@dataclass
class _PriceLevel:
    """Orders at a single price level, FIFO queue."""
    price: float
    orders: deque

    @property
    def total_qty(self) -> int:
        return sum(o.remaining for o in self.orders)


class OrderBook:
    """Single-side order book for one symbol."""

    def __init__(self):
        self.bids: list[_PriceLevel] = []  # sorted desc by price
        self.asks: list[_PriceLevel] = []  # sorted asc by price

    def add_order(self, order: Order):
        """Add a limit order to the book."""
        levels = self.bids if order.side == OrderSide.BUY else self.asks
        self._insert_level(levels, order)

    def _insert_level(self, levels: list, order: Order):
        for level in levels:
            if abs(level.price - order.price) < 1e-8:
                level.orders.append(order)
                return
        new_level = _PriceLevel(price=order.price, orders=deque([order]))
        levels.append(new_level)
        if order.side == OrderSide.BUY:
            levels.sort(key=lambda x: -x.price)
        else:
            levels.sort(key=lambda x: x.price)

    def remove(self, order: Order):
        levels = self.bids if order.side == OrderSide.BUY else self.asks
        for level in levels:
            for i, o in enumerate(level.orders):
                if o.id == order.id:
                    level.orders.remove(o)
                    if not level.orders:
                        levels.remove(level)
                    return

    def get_best_bid(self) -> Optional[float]:
        return self.bids[0].price if self.bids else None

    def get_best_ask(self) -> Optional[float]:
        return self.asks[0].price if self.asks else None

    def clear(self):
        self.bids.clear()
        self.asks.clear()


class Exchange:
    """A-share matching engine with auction and continuous modes."""

    def __init__(self):
        self._books: dict[str, OrderBook] = defaultdict(OrderBook)
        self._auction_orders: dict[str, list[Order]] = defaultdict(list)

    def submit_order(self, order: Order, phase: TradingPhase, timestamp: datetime = None) -> list[Trade]:
        """Submit an order to the exchange.

        During auction: queue for batch matching.
        During continuous: attempt immediate fill, then rest on book.
        """
        order.timestamp = timestamp or datetime.now()

        if order.order_type == OrderType.MARKET and order.side == OrderSide.BUY:
            order.price = 999999.0  # Market buy: will match best ask

        from .session import is_auction_phase, is_continuous_phase

        if is_auction_phase(phase):
            self._auction_orders[order.symbol].append(order)
            return []

        if is_continuous_phase(phase):
            return self._match_continuous(order)

        return []

    def match_auction(self, symbol: str) -> list[Trade]:
        """Match auction orders at a single clearing price.

        Finds the price that maximizes matched volume.
        """
        orders = self._auction_orders.pop(symbol, [])
        if not orders:
            return []

        buy_orders = sorted(
            [o for o in orders if o.side == OrderSide.BUY],
            key=lambda x: -x.price,
        )
        sell_orders = sorted(
            [o for o in orders if o.side == OrderSide.SELL],
            key=lambda x: x.price,
        )

        if not buy_orders or not sell_orders:
            return []

        # Collect all candidate prices
        prices = set()
        for o in buy_orders:
            prices.add(o.price)
        for o in sell_orders:
            prices.add(o.price)

        best_price = 0.0
        best_volume = 0

        for price in sorted(prices):
            buy_vol = sum(o.remaining for o in buy_orders if o.price >= price)
            sell_vol = sum(o.remaining for o in sell_orders if o.price <= price)
            matched = min(buy_vol, sell_vol)
            if matched > best_volume or (matched == best_volume and matched > 0):
                best_volume = matched
                best_price = price

        if best_volume == 0:
            return []

        # Execute at clearing price: match buy→sell greedily
        trades = []
        remaining_volume = best_volume

        for buy in buy_orders:
            if remaining_volume <= 0:
                break
            buy_fill = min(buy.remaining, remaining_volume)
            if buy_fill <= 0:
                continue

            buy.filled_qty += buy_fill
            buy.filled_price = best_price
            buy.status = OrderStatus.FILLED if buy.filled_qty >= buy.quantity else OrderStatus.PARTIAL
            remaining_volume -= buy_fill

            # Match against sell orders
            to_fill = buy_fill
            for sell in sell_orders:
                if to_fill <= 0:
                    break
                sell_fill = min(sell.remaining, to_fill)
                if sell_fill <= 0:
                    continue

                sell.filled_qty += sell_fill
                sell.filled_price = best_price
                sell.status = OrderStatus.FILLED if sell.filled_qty >= sell.quantity else OrderStatus.PARTIAL
                to_fill -= sell_fill

                amount = best_price * sell_fill
                trades.append(Trade(
                    order_id=buy.id,
                    symbol=symbol,
                    side=OrderSide.BUY,
                    price=best_price,
                    quantity=sell_fill,
                    timestamp=buy.timestamp,
                    commission=calc_commission(amount),
                    stamp_tax=calc_stamp_tax(amount),
                    transfer_fee=calc_transfer_fee(amount),
                ))

        return trades

    def _match_continuous(self, order: Order) -> list[Trade]:
        """Match a single order against the book (continuous auction)."""
        book = self._books[order.symbol]
        trades = []

        if order.side == OrderSide.BUY:
            while order.remaining > 0 and book.asks:
                best_ask = book.asks[0]
                if order.order_type == OrderType.LIMIT and order.price < best_ask.price:
                    break
                fill_qty = min(order.remaining, best_ask.orders[0].remaining)
                fill_price = best_ask.orders[0].price

                counter = best_ask.orders[0]
                counter.filled_qty += fill_qty
                order.filled_qty += fill_qty
                order.filled_price = fill_price

                if counter.filled_qty >= counter.quantity:
                    counter.status = OrderStatus.FILLED
                    best_ask.orders.popleft()
                    if not best_ask.orders:
                        book.asks.pop(0)
                else:
                    counter.status = OrderStatus.PARTIAL

                amount = fill_price * fill_qty
                trades.append(Trade(
                    order_id=order.id,
                    symbol=order.symbol,
                    side=OrderSide.BUY,
                    price=fill_price,
                    quantity=fill_qty,
                    timestamp=order.timestamp,
                    commission=calc_commission(amount),
                    stamp_tax=0.0,
                    transfer_fee=calc_transfer_fee(amount),
                ))

            if order.remaining > 0 and order.order_type == OrderType.LIMIT:
                order.status = OrderStatus.PARTIAL if order.filled_qty > 0 else OrderStatus.PENDING
                book.add_order(order)

        else:  # SELL
            while order.remaining > 0 and book.bids:
                best_bid = book.bids[0]
                if order.order_type == OrderType.LIMIT and order.price > best_bid.price:
                    break
                fill_qty = min(order.remaining, best_bid.orders[0].remaining)
                fill_price = best_bid.orders[0].price

                counter = best_bid.orders[0]
                counter.filled_qty += fill_qty
                order.filled_qty += fill_qty
                order.filled_price = fill_price

                if counter.filled_qty >= counter.quantity:
                    counter.status = OrderStatus.FILLED
                    best_bid.orders.popleft()
                    if not best_bid.orders:
                        book.bids.pop(0)
                else:
                    counter.status = OrderStatus.PARTIAL

                amount = fill_price * fill_qty
                trades.append(Trade(
                    order_id=order.id,
                    symbol=order.symbol,
                    side=OrderSide.SELL,
                    price=fill_price,
                    quantity=fill_qty,
                    timestamp=order.timestamp,
                    commission=calc_commission(amount),
                    stamp_tax=calc_stamp_tax(amount),
                    transfer_fee=calc_transfer_fee(amount),
                ))

            if order.remaining > 0 and order.order_type == OrderType.LIMIT:
                order.status = OrderStatus.PARTIAL if order.filled_qty > 0 else OrderStatus.PENDING
                book.add_order(order)

        if order.filled_qty >= order.quantity:
            order.status = OrderStatus.FILLED
        elif order.filled_qty > 0:
            order.status = OrderStatus.PARTIAL

        return trades

    def clear_auction_orders(self, symbol: str):
        """Discard unmatched auction orders."""
        self._auction_orders.pop(symbol, None)

    def clear_book(self, symbol: str):
        """Clear the order book for a symbol (end of day)."""
        self._books[symbol].clear()
