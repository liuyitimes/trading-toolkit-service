# -*- coding: utf-8 -*-
"""Backtester engine: orchestrates data loading, strategy execution, and metrics."""

from datetime import date, datetime, timedelta
from itertools import groupby

from .models import TradingPhase, OrderStatus, BoardType, Bar
from .data import MarketData
from .exchange import Exchange
from .portfolio import Portfolio
from .strategy import Strategy
from .metrics import PerformanceReport, calc_performance
from .session import get_trading_phase, is_auction_phase, is_continuous_phase
from .broker import validate_order, get_board_type
from .exceptions import InsufficientPositionError


class Backtester:
    """Main backtester loop."""

    def __init__(
        self,
        strategy: Strategy,
        start_date: str,
        end_date: str,
        initial_cash: float = 1_000_000.0,
    ):
        self.strategy = strategy
        self.start_date = start_date
        self.end_date = end_date
        self.initial_cash = initial_cash

        self.data = MarketData()
        self.exchange = Exchange()
        self.portfolio = Portfolio(initial_cash)
        self.errors: list[str] = []

    def run(self) -> PerformanceReport:
        """Run the backtest and return performance report."""
        self.strategy.on_init(self.data, self.portfolio)

        # Get trading days
        trading_days = self._get_trading_days()

        for day in trading_days:
            self._run_day(day)

        self.strategy.on_finish()
        return calc_performance(self.portfolio)

    def _get_trading_days(self) -> list[date]:
        """Get list of trading days between start and end dates."""
        start = datetime.strptime(self.start_date, "%Y-%m-%d").date()
        end = datetime.strptime(self.end_date, "%Y-%m-%d").date()
        days = []
        current = start
        while current <= end:
            # Skip weekends
            if current.weekday() < 5:
                days.append(current)
            current += timedelta(days=1)
        return days

    def _run_day(self, trade_date: date):
        """Run a single trading day."""
        date_str = trade_date.strftime("%Y-%m-%d")
        symbols = self.strategy.symbols
        if not symbols:
            return

        # Load bars for all symbols
        symbol_bars: dict[str, list[Bar]] = {}
        for sym in symbols:
            bars = self.data.get_bars_for_date(sym, trade_date)
            if bars:
                symbol_bars[sym] = bars

        if not symbol_bars:
            return

        # Get prev close for each symbol
        prev_closes: dict[str, float] = {}
        board_types = {}
        for sym in symbols:
            prev_closes[sym] = self.data.load_prev_close(sym, trade_date)
            board_types[sym] = get_board_type(sym)

        # Merge all bars into a single timeline sorted by timestamp
        all_bars: list[Bar] = []
        for bars in symbol_bars.values():
            all_bars.extend(bars)
        all_bars.sort(key=lambda b: b.timestamp)

        # Group bars by timestamp to process all symbols at each time step
        for ts, ts_bars in groupby(all_bars, key=lambda b: b.timestamp):
            bars_list = list(ts_bars)
            phase = get_trading_phase(ts)

            if is_auction_phase(phase):
                # During auction: strategy generates orders for each symbol
                for bar in bars_list:
                    orders = self.strategy.on_bar(bar, self.portfolio, phase)
                    for order in orders:
                        try:
                            # T+1 check for sell orders
                            if order.side.value == "sell":
                                if not self.portfolio.is_t1_available(bar.symbol, trade_date):
                                    raise InsufficientPositionError(
                                        f"T+1 rule: cannot sell {bar.symbol} on {date_str}"
                                    )
                            validate_order(
                                order, self.portfolio.cash,
                                self.portfolio.get_position_qty(bar.symbol),
                                prev_closes.get(bar.symbol, 0),
                                board_types.get(bar.symbol, BoardType.MAIN),
                            )
                            self.exchange.submit_order(order, phase, ts)
                        except Exception as e:
                            self.errors.append(f"{date_str} {ts}: {e}")

            elif is_continuous_phase(phase):
                # First: match any pending auction (if we just left auction)
                if phase == TradingPhase.MORNING and ts.hour == 9 and ts.minute == 30:
                    for sym in symbols:
                        trades = self.exchange.match_auction(sym)
                        for t in trades:
                            self._process_trade(t, trade_date)

                # Strategy generates orders for each symbol
                for bar in bars_list:
                    orders = self.strategy.on_bar(bar, self.portfolio, phase)
                    for order in orders:
                        try:
                            # T+1 check for sell orders
                            if order.side.value == "sell":
                                if not self.portfolio.is_t1_available(bar.symbol, trade_date):
                                    raise InsufficientPositionError(
                                        f"T+1 rule: cannot sell {bar.symbol} on {date_str}"
                                    )
                            validate_order(
                                order, self.portfolio.cash,
                                self.portfolio.get_position_qty(bar.symbol),
                                prev_closes.get(bar.symbol, 0),
                                board_types.get(bar.symbol, BoardType.MAIN),
                            )
                            trades = self.exchange.submit_order(order, phase, ts)
                            for t in trades:
                                self._process_trade(t, trade_date)
                        except Exception as e:
                            self.errors.append(f"{date_str} {ts}: {e}")

            # Snapshot equity periodically (every 5 minutes)
            if ts.minute % 5 == 0:
                prices = {bar.symbol: bar.close for bar in bars_list}
                self.portfolio.snapshot(ts, prices)

        # End of day: match closing auction for all symbols, then discard unmatched
        for sym in symbols:
            closing_trades = self.exchange.match_auction(sym)
            for t in closing_trades:
                self._process_trade(t, trade_date)
            self.exchange.clear_auction_orders(sym)

        # Final snapshot with last prices from each symbol
        last_prices = {}
        for sym, bars in symbol_bars.items():
            if bars:
                last_prices[sym] = bars[-1].close
        if last_prices:
            last_ts = max(bars[-1].timestamp for bars in symbol_bars.values())
            self.portfolio.snapshot(last_ts, last_prices)

        # Clear order books for new day
        for sym in symbols:
            self.exchange.clear_book(sym)

    def _process_trade(self, trade, trade_date: date):
        """Process a matched trade: update portfolio and notify strategy."""
        if trade.timestamp is None:
            trade.timestamp = datetime.combine(trade_date, datetime.min.time())
        self.portfolio.execute_trade(trade)
        self.strategy.on_trade(trade)
