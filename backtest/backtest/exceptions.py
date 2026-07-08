# -*- coding: utf-8 -*-
"""Custom exceptions for the backtest engine."""


class BacktestError(Exception):
    """Base exception for all backtest errors."""


class InvalidOrderError(BacktestError):
    """Order failed validation."""


class InsufficientFundsError(InvalidOrderError):
    """Not enough cash to place buy order."""


class InsufficientPositionError(InvalidOrderError):
    """Not enough shares to place sell order."""


class PriceLimitError(InvalidOrderError):
    """Order price exceeds daily price limit."""


class LotSizeError(InvalidOrderError):
    """Order quantity is not a multiple of 100."""


class OrderRejectedError(BacktestError):
    """Order was rejected by the exchange."""
