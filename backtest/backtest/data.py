# -*- coding: utf-8 -*-
"""Market data loader using akshare for 1-minute bars."""

from datetime import datetime, date
from typing import Optional

from .models import Bar


class MarketData:
    """Loads and caches 1-minute bar data from akshare."""

    def __init__(self):
        self._cache: dict[str, list[Bar]] = {}
        self._prev_close: dict[str, float] = {}

    def load(self, symbol: str, start_date: str, end_date: str):
        """Load 1-min bars for a symbol.

        Args:
            symbol: Stock code like '000001' or '000001.SZ'
            start_date: 'YYYY-MM-DD'
            end_date: 'YYYY-MM-DD'
        """
        import akshare as ak
        import pandas as pd

        code = symbol.split(".")[0]
        cache_key = f"{code}_{start_date}_{end_date}"
        if cache_key in self._cache:
            return self._cache[cache_key]

        df = ak.stock_zh_a_hist_min_em(
            symbol=code,
            period="1",
            start_date=f"{start_date} 09:30:00",
            end_date=f"{end_date} 15:00:00",
            adjust="qfq",
        )

        bars = []
        for _, row in df.iterrows():
            ts = pd.Timestamp(row["时间"]).to_pydatetime()
            bars.append(Bar(
                symbol=code,
                open=float(row["开盘"]),
                high=float(row["最高"]),
                low=float(row["最低"]),
                close=float(row["收盘"]),
                volume=int(row["成交量"]),
                timestamp=ts,
            ))

        self._cache[cache_key] = bars
        return bars

    def load_prev_close(self, symbol: str, trade_date: date) -> float:
        """Get previous day's close price for price limit calculation."""
        import akshare as ak
        import pandas as pd

        code = symbol.split(".")[0]
        cache_key = f"{code}_{trade_date}"
        if cache_key in self._prev_close:
            return self._prev_close[cache_key]

        try:
            df = ak.stock_zh_a_hist(
                symbol=code,
                period="daily",
                start_date=(trade_date - pd.Timedelta(days=10)).strftime("%Y%m%d"),
                end_date=trade_date.strftime("%Y%m%d"),
                adjust="qfq",
            )
            if len(df) >= 2:
                prev_close = float(df.iloc[-2]["收盘"])
            elif len(df) == 1:
                prev_close = float(df.iloc[-1]["收盘"])
            else:
                prev_close = 0.0
        except Exception:
            prev_close = 0.0

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
