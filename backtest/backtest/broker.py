# -*- coding: utf-8 -*-
"""Fee calculation and order validation."""

from datetime import date
from .models import (
    Order, OrderSide, OrderType, OrderStatus, BoardType,
    calc_price_range, get_board_type,
)
from .exceptions import (
    InvalidOrderError, InsufficientFundsError, InsufficientPositionError,
    PriceLimitError, LotSizeError,
)


# A-share fee structure
COMMISSION_RATE = 0.0003       # 万3
COMMISSION_MIN = 5.0           # 最低5元
STAMP_TAX_RATE = 0.001         # 千1 (sell only)
TRANSFER_FEE_RATE = 0.00002    # 万0.2 (both sides)


def calc_commission(amount: float) -> float:
    """Calculate commission, minimum 5 yuan."""
    fee = amount * COMMISSION_RATE
    return max(fee, COMMISSION_MIN)


def calc_stamp_tax(amount: float) -> float:
    """Stamp tax on sell side only."""
    return amount * STAMP_TAX_RATE


def calc_transfer_fee(amount: float) -> float:
    """Transfer fee, both sides."""
    return amount * TRANSFER_FEE_RATE


def calc_total_cost(amount: float, side: OrderSide) -> float:
    """Total transaction cost for a given trade amount."""
    commission = calc_commission(amount)
    stamp = calc_stamp_tax(amount) if side == OrderSide.SELL else 0.0
    transfer = calc_transfer_fee(amount)
    return commission + stamp + transfer


def validate_order(
    order: Order,
    cash: float,
    position_qty: int,
    prev_close: float,
    board_type: BoardType = BoardType.MAIN,
    today: date = None,
    position_buy_date: date = None,
):
    """Validate an order. Raises InvalidOrderError subclass on failure."""
    # Lot size check
    if order.quantity % 100 != 0:
        raise LotSizeError(f"Order quantity {order.quantity} is not a multiple of 100")

    if order.quantity <= 0:
        raise InvalidOrderError("Order quantity must be positive")

    # Price limit check
    if order.order_type == OrderType.LIMIT and prev_close > 0:
        lower, upper = calc_price_range(prev_close, board_type)
        if order.price < lower or order.price > upper:
            raise PriceLimitError(
                f"Price {order.price:.2f} outside limit range [{lower:.2f}, {upper:.2f}]"
            )

    # Cash check for buy
    if order.side == OrderSide.BUY:
        amount = order.price * order.quantity
        cost = calc_total_cost(amount, order.side)
        if cash < amount + cost:
            raise InsufficientFundsError(
                f"Need {amount + cost:.2f}, have {cash:.2f}"
            )

    # Position check for sell
    if order.side == OrderSide.SELL:
        if position_qty < order.quantity:
            raise InsufficientPositionError(
                f"Have {position_qty} shares, trying to sell {order.quantity}"
            )
