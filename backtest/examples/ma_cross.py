# -*- coding: utf-8 -*-
"""Example: Moving average crossover strategy for A-share backtesting."""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backtest import (
    Strategy, Backtester, Order, OrderSide, OrderType,
    Bar, TradingPhase, Portfolio,
)


class MACrossStrategy(Strategy):
    """Simple MA crossover: buy when short MA crosses above long MA."""

    def __init__(self, symbols: list[str], short_window: int = 5, long_window: int = 20):
        super().__init__(symbols)
        self.short_window = short_window
        self.long_window = long_window
        self._prices: dict[str, list[float]] = {s: [] for s in symbols}
        self._position_held: dict[str, bool] = {s: False for s in symbols}

    def on_bar(self, bar: Bar, portfolio: Portfolio, phase: TradingPhase) -> list[Order]:
        prices = self._prices[bar.symbol]
        prices.append(bar.close)

        if len(prices) < self.long_window:
            return []

        short_ma = sum(prices[-self.short_window:]) / self.short_window
        long_ma = sum(prices[-self.long_window:]) / self.long_window

        orders = []

        if not self._position_held[bar.symbol] and short_ma > long_ma:
            # Buy signal
            orders.append(Order(
                symbol=bar.symbol,
                side=OrderSide.BUY,
                order_type=OrderType.LIMIT,
                price=bar.close,
                quantity=100,
            ))
            self._position_held[bar.symbol] = True

        elif self._position_held[bar.symbol] and short_ma < long_ma:
            # Sell signal
            qty = portfolio.get_position_qty(bar.symbol)
            if qty > 0:
                orders.append(Order(
                    symbol=bar.symbol,
                    side=OrderSide.SELL,
                    order_type=OrderType.LIMIT,
                    price=bar.close,
                    quantity=qty,
                ))
                self._position_held[bar.symbol] = False

        return orders


def main():
    strategy = MACrossStrategy(
        symbols=["000001"],
        short_window=5,
        long_window=20,
    )

    bt = Backtester(
        strategy=strategy,
        start_date="2024-01-02",
        end_date="2024-01-31",
        initial_cash=100_000.0,
    )

    report = bt.run()
    print(report.summary())

    if bt.errors:
        print(f"\nErrors ({len(bt.errors)}):")
        for err in bt.errors[:10]:
            print(f"  {err}")


if __name__ == "__main__":
    main()
