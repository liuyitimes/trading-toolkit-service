# -*- coding: utf-8 -*-
"""Tests for mock market data provider."""

from datetime import date
from backtest.mock_data import MockMarketData
from backtest.models import Bar


class TestMockMarketData:
    def setup_method(self):
        self.data = MockMarketData(seed=42)

    def test_load_generates_bars(self):
        bars = self.data.load("000001", "2024-01-02", "2024-01-05")
        assert len(bars) > 0
        assert all(isinstance(b, Bar) for b in bars)

    def test_bars_have_correct_symbol(self):
        bars = self.data.load("000001", "2024-01-02", "2024-01-02")
        assert all(b.symbol == "000001" for b in bars)

    def test_bars_have_valid_ohlc(self):
        bars = self.data.load("000001", "2024-01-02", "2024-01-02")
        for bar in bars:
            assert bar.high >= bar.low
            assert bar.high >= bar.open
            assert bar.high >= bar.close
            assert bar.low <= bar.open
            assert bar.low <= bar.close

    def test_bars_sorted_by_time(self):
        bars = self.data.load("000001", "2024-01-02", "2024-01-05")
        timestamps = [b.timestamp for b in bars]
        assert timestamps == sorted(timestamps)

    def test_cache_returns_same_data(self):
        bars1 = self.data.load("000001", "2024-01-02", "2024-01-02")
        bars2 = self.data.load("000001", "2024-01-02", "2024-01-02")
        assert bars1 is bars2

    def test_get_bars_for_date(self):
        bars = self.data.get_bars_for_date("000001", date(2024, 1, 2))
        assert all(b.timestamp.date() == date(2024, 1, 2) for b in bars)

    def test_prev_close(self):
        prev = self.data.load_prev_close("000001", date(2024, 1, 3))
        assert prev > 0

    def test_clear_cache(self):
        self.data.load("000001", "2024-01-02", "2024-01-02")
        self.data.clear_cache()
        # Should regenerate (not return cached)
        bars = self.data.load("000001", "2024-01-02", "2024-01-02")
        assert len(bars) > 0

    def test_skips_weekends(self):
        bars = self.data.load("000001", "2024-01-05", "2024-01-08")  # Fri to Mon
        dates = set(b.timestamp.date() for b in bars)
        assert date(2024, 1, 6) not in dates  # Saturday
        assert date(2024, 1, 7) not in dates  # Sunday
