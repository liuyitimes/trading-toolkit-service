# -*- coding: utf-8 -*-
"""Example: Run backtest with mock data (no network required)."""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import (
    Strategy, Backtester, MockMarketData, Order, OrderSide, OrderType,
    Bar, TradingPhase, Portfolio,
)


class DayTradeStrategy(Strategy):
    """Buy at opening auction on day 1, sell at opening auction on day 2.

    Respects T+1: cannot sell on the same day as purchase.
    Uses auction matching which handles both sides in one batch.
    """

    def __init__(self, symbols: list[str], qty: int = 500):
        super().__init__(symbols)
        self.qty = qty
        self._day = 0
        self._bought = False

    def on_bar(self, bar: Bar, portfolio: Portfolio, phase: TradingPhase) -> list[Order]:
        if phase != TradingPhase.OPENING_AUCTION:
            return []

        # Track trading days via opening auction bars
        if not hasattr(self, '_last_auction_date'):
            self._last_auction_date = bar.timestamp.date()
        if bar.timestamp.date() != self._last_auction_date:
            self._day += 1
            self._last_auction_date = bar.timestamp.date()

        # Day 0: buy
        if self._day == 0 and not self._bought:
            self._bought = True
            return [Order(
                symbol=bar.symbol, side=OrderSide.BUY,
                order_type=OrderType.LIMIT, price=bar.close, quantity=self.qty,
            )]

        # Day 1: sell (T+1 satisfied)
        if self._day == 1 and self._bought:
            held = portfolio.get_position_qty(bar.symbol)
            if held > 0:
                self._bought = False
                return [Order(
                    symbol=bar.symbol, side=OrderSide.SELL,
                    order_type=OrderType.LIMIT, price=bar.close, quantity=held,
                )]

        return []


def main():
    data = MockMarketData(seed=42)
    strategy = DayTradeStrategy(symbols=["000001"], qty=500)

    bt = Backtester(
        strategy=strategy,
        start_date="2024-01-02",
        end_date="2024-01-31",
        initial_cash=100_000.0,
    )
    bt.data = data

    report = bt.run()
    print(report.summary())

    if bt.errors:
        print(f"\nErrors ({len(bt.errors)}):")
        for err in bt.errors[:10]:
            print(f"  {err}")

    print(f"\nTotal trades: {len(bt.portfolio.trades)}")
    for t in bt.portfolio.trades:
        print(f"  {t.side.value.upper()} {t.quantity} @ {t.price:.2f}  cost={t.total_cost:.2f}")


if __name__ == "__main__":
    main()
