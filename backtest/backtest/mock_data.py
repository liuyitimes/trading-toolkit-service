# -*- coding: utf-8 -*-
"""Mock market data provider for testing without network access."""

from datetime import datetime, date, timedelta
from typing import Optional
import math
import random

from .models import Bar


class MockMarketData:
    """Generates synthetic 1-minute bar data for testing."""

    def __init__(self, seed: int = 42):
        self._cache: dict[str, list[Bar]] = {}
        self._prev_close: dict[str, float] = {}
        self._rng = random.Random(seed)

    def load(
        self,
        symbol: str,
        start_date: str,
        end_date: str,
        base_price: float = 10.0,
        volatility: float = 0.02,
    ) -> list[Bar]:
        """Generate synthetic 1-min bars for testing.

        Args:
            symbol: Stock code
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
            base_price: Starting price
            volatility: Daily volatility (std dev of returns)
        """
        code = symbol.split(".")[0]
        cache_key = f"{code}_{start_date}_{end_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        start = datetime.strptime(start_date, "%Y-%m-%d").date()
        end = datetime.strptime(end_date, "%Y-%m-%d").date()

        bars = []
        current_price = base_price
        current_date = start

        while current_date <= end:
            if current_date.weekday() < 5:  # Skip weekends
                bars.extend(self._generate_day_bars(
                    code, current_date, current_price, volatility
                ))
                # Update price for next day
                daily_return = self._rng.gauss(0, volatility)
                current_price *= (1 + daily_return)
            current_date += timedelta(days=1)

        self._cache[cache_key] = bars
        return bars

    def _generate_day_bars(
        self, symbol: str, trade_date: date, open_price: float, volatility: float
    ) -> list[Bar]:
        """Generate 1-minute bars for a single trading day."""
        bars = []
        price = open_price
        minute_vol = volatility / math.sqrt(240)  # Scale to 1-min

        # A-share trading sessions (includes auction periods)
        sessions = [
            (9, 15, 9, 25),    # Opening auction
            (9, 30, 11, 30),   # Morning continuous
            (13, 0, 14, 57),   # Afternoon continuous
            (14, 57, 15, 0),   # Closing auction
        ]

        for start_h, start_m, end_h, end_m in sessions:
            h, m = start_h, start_m
            while h < end_h or (h == end_h and m < end_m):
                ts = datetime(trade_date.year, trade_date.month, trade_date.day, h, m)

                # Generate OHLCV
                ret = self._rng.gauss(0, minute_vol)
                close = price * (1 + ret)
                high = max(price, close) * (1 + abs(self._rng.gauss(0, minute_vol * 0.5)))
                low = min(price, close) * (1 - abs(self._rng.gauss(0, minute_vol * 0.5)))
                volume = self._rng.randint(100, 10000)

                bars.append(Bar(
                    symbol=symbol,
                    open=round(price, 2),
                    high=round(high, 2),
                    low=round(low, 2),
                    close=round(close, 2),
                    volume=volume,
                    timestamp=ts,
                ))

                price = close
                m += 1
                if m >= 60:
                    m = 0
                    h += 1

        return bars

    def load_prev_close(self, symbol: str, trade_date: date) -> float:
        """Get previous day's close price."""
        code = symbol.split(".")[0]
        cache_key = f"{code}_{trade_date}"
        if cache_key in self._prev_close:
            return self._prev_close[cache_key]

        # Use cached bars to find previous close
        prev_date = trade_date - timedelta(days=1)
        while prev_date.weekday() >= 5:
            prev_date -= timedelta(days=1)

        bars = self.load(code, prev_date.strftime("%Y-%m-%d"), prev_date.strftime("%Y-%m-%d"))
        if bars:
            prev_close = bars[-1].close
        else:
            prev_close = 10.0  # Default

        self._prev_close[cache_key] = prev_close
        return prev_close

    def get_bars_for_date(self, symbol: str, trade_date: date) -> list[Bar]:
        """Get bars for a single trading day."""
        date_str = trade_date.strftime("%Y-%m-%d")
        all_bars = self.load(symbol, date_str, date_str)
        return [b for b in all_bars if b.timestamp.date() == trade_date]

    def clear_cache(self):
        self._cache.clear()
        self._prev_close.clear()
