# -*- coding: utf-8 -*-
"""Tests for trading session phase detection."""

from datetime import datetime
from backtest.session import get_trading_phase, is_auction_phase, is_continuous_phase
from backtest.models import TradingPhase


class TestTradingPhase:
    def test_pre_market(self):
        ts = datetime(2024, 1, 2, 8, 0)
        assert get_trading_phase(ts) == TradingPhase.PRE_MARKET

    def test_opening_auction(self):
        ts = datetime(2024, 1, 2, 9, 15)
        assert get_trading_phase(ts) == TradingPhase.OPENING_AUCTION

    def test_auction_no_cancel(self):
        ts = datetime(2024, 1, 2, 9, 20)
        assert get_trading_phase(ts) == TradingPhase.AUCTION_NO_CANCEL

    def test_broken(self):
        ts = datetime(2024, 1, 2, 9, 25)
        assert get_trading_phase(ts) == TradingPhase.BROKEN

    def test_morning(self):
        ts = datetime(2024, 1, 2, 9, 30)
        assert get_trading_phase(ts) == TradingPhase.MORNING

    def test_morning_end(self):
        ts = datetime(2024, 1, 2, 11, 29)
        assert get_trading_phase(ts) == TradingPhase.MORNING

    def test_lunch(self):
        ts = datetime(2024, 1, 2, 11, 30)
        assert get_trading_phase(ts) == TradingPhase.LUNCH

    def test_afternoon(self):
        ts = datetime(2024, 1, 2, 13, 0)
        assert get_trading_phase(ts) == TradingPhase.AFTERNOON

    def test_closing_auction(self):
        ts = datetime(2024, 1, 2, 14, 57)
        assert get_trading_phase(ts) == TradingPhase.CLOSING_AUCTION

    def test_post_market(self):
        ts = datetime(2024, 1, 2, 15, 1)
        assert get_trading_phase(ts) == TradingPhase.POST_MARKET


class TestPhaseHelpers:
    def test_is_auction_phase(self):
        assert is_auction_phase(TradingPhase.OPENING_AUCTION) is True
        assert is_auction_phase(TradingPhase.AUCTION_NO_CANCEL) is True
        assert is_auction_phase(TradingPhase.CLOSING_AUCTION) is True
        assert is_auction_phase(TradingPhase.MORNING) is False
        assert is_auction_phase(TradingPhase.AFTERNOON) is False

    def test_is_continuous_phase(self):
        assert is_continuous_phase(TradingPhase.MORNING) is True
        assert is_continuous_phase(TradingPhase.AFTERNOON) is True
        assert is_continuous_phase(TradingPhase.OPENING_AUCTION) is False
        assert is_continuous_phase(TradingPhase.LUNCH) is False
