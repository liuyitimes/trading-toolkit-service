# -*- coding: utf-8 -*-
"""A-share trading session timeline and phase detection."""

from datetime import datetime, time
from .models import TradingPhase


# A-share trading hours (Beijing time)
_OPENING_AUCTION_START = time(9, 15)
_OPENING_AUCTION_END = time(9, 25)
_CONTINUOUS_START_AM = time(9, 30)
_CONTINUOUS_END_AM = time(11, 30)
_CONTINUOUS_START_PM = time(13, 0)
_CLOSING_AUCTION_START = time(14, 57)
_CLOSING_AUCTION_END = time(15, 0)


def get_trading_phase(ts: datetime) -> TradingPhase:
    """Determine the trading phase for a given timestamp."""
    t = ts.time()

    if t < _OPENING_AUCTION_START:
        return TradingPhase.PRE_MARKET
    elif _OPENING_AUCTION_START <= t < time(9, 20):
        return TradingPhase.OPENING_AUCTION
    elif time(9, 20) <= t < _OPENING_AUCTION_END:
        return TradingPhase.AUCTION_NO_CANCEL
    elif _OPENING_AUCTION_END <= t < _CONTINUOUS_START_AM:
        return TradingPhase.BROKEN
    elif _CONTINUOUS_START_AM <= t < _CONTINUOUS_END_AM:
        return TradingPhase.MORNING
    elif _CONTINUOUS_END_AM <= t < _CONTINUOUS_START_PM:
        return TradingPhase.LUNCH
    elif _CONTINUOUS_START_PM <= t < _CLOSING_AUCTION_START:
        return TradingPhase.AFTERNOON
    elif _CLOSING_AUCTION_START <= t <= _CLOSING_AUCTION_END:
        return TradingPhase.CLOSING_AUCTION
    else:
        return TradingPhase.POST_MARKET


def is_auction_phase(phase: TradingPhase) -> bool:
    return phase in (
        TradingPhase.OPENING_AUCTION,
        TradingPhase.AUCTION_NO_CANCEL,
        TradingPhase.CLOSING_AUCTION,
    )


def is_continuous_phase(phase: TradingPhase) -> bool:
    return phase in (TradingPhase.MORNING, TradingPhase.AFTERNOON)
