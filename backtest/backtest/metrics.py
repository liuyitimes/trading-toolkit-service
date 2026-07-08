# -*- coding: utf-8 -*-
"""Performance metrics and reporting."""

import math
from datetime import datetime
from dataclasses import dataclass, field
from .portfolio import Portfolio
from .models import OrderSide


@dataclass
class PerformanceReport:
    """Backtest performance report."""
    initial_cash: float = 0.0
    final_equity: float = 0.0
    total_return: float = 0.0
    annualized_return: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown: float = 0.0
    max_drawdown_duration: int = 0  # in bars
    win_rate: float = 0.0
    profit_factor: float = 0.0
    total_trades: int = 0
    total_commission: float = 0.0
    total_stamp_tax: float = 0.0
    total_transfer_fee: float = 0.0
    total_cost: float = 0.0
    equity_curve: list[tuple[datetime, float]] = field(default_factory=list)

    def summary(self) -> str:
        return (
            f"=== Backtest Performance ===\n"
            f"Initial Cash:    {self.initial_cash:>14,.2f}\n"
            f"Final Equity:    {self.final_equity:>14,.2f}\n"
            f"Total Return:    {self.total_return:>13.2%}\n"
            f"Annual Return:   {self.annualized_return:>13.2%}\n"
            f"Sharpe Ratio:    {self.sharpe_ratio:>14.3f}\n"
            f"Sortino Ratio:   {self.sortino_ratio:>14.3f}\n"
            f"Max Drawdown:    {self.max_drawdown:>13.2%}\n"
            f"DD Duration:     {self.max_drawdown_duration:>10} bars\n"
            f"Win Rate:        {self.win_rate:>13.2%}\n"
            f"Profit Factor:   {self.profit_factor:>14.3f}\n"
            f"Total Trades:    {self.total_trades:>14}\n"
            f"Commission:      {self.total_commission:>14,.2f}\n"
            f"Stamp Tax:       {self.total_stamp_tax:>14,.2f}\n"
            f"Transfer Fee:    {self.total_transfer_fee:>14,.2f}\n"
            f"Total Cost:      {self.total_cost:>14,.2f}\n"
            f"=============================="
        )


def calc_performance(portfolio: Portfolio) -> PerformanceReport:
    """Calculate performance metrics from portfolio history."""
    report = PerformanceReport()
    report.initial_cash = portfolio.initial_cash
    report.equity_curve = list(portfolio.equity_curve)
    report.total_trades = len(portfolio.trades)
    report.total_commission = portfolio.total_commission
    report.total_stamp_tax = portfolio.total_stamp_tax
    report.total_transfer_fee = portfolio.total_transfer_fee
    report.total_cost = portfolio.total_commission + portfolio.total_stamp_tax + portfolio.total_transfer_fee

    if not portfolio.equity_curve:
        return report

    report.final_equity = portfolio.equity_curve[-1][1]
    report.total_return = (report.final_equity - report.initial_cash) / report.initial_cash

    # Daily returns
    equities = [e for _, e in portfolio.equity_curve]
    if len(equities) < 2:
        return report

    returns = []
    for i in range(1, len(equities)):
        if equities[i - 1] > 0:
            returns.append(equities[i] / equities[i - 1] - 1)

    if not returns:
        return report

    # Annualized return (assume ~240 trading days, ~240 bars per day for 1-min)
    n_days = max(1, len(portfolio.equity_curve) / 240)
    report.annualized_return = (1 + report.total_return) ** (252 / n_days) - 1

    # Sharpe ratio (risk-free rate = 0)
    avg_ret = sum(returns) / len(returns)
    std_ret = math.sqrt(sum((r - avg_ret) ** 2 for r in returns) / len(returns)) if len(returns) > 1 else 0
    report.sharpe_ratio = (avg_ret / std_ret * math.sqrt(252 * 240)) if std_ret > 0 else 0

    # Sortino ratio (downside deviation)
    neg_returns = [r for r in returns if r < 0]
    downside_std = math.sqrt(sum(r ** 2 for r in neg_returns) / len(neg_returns)) if neg_returns else 0
    report.sortino_ratio = (avg_ret / downside_std * math.sqrt(252 * 240)) if downside_std > 0 else 0

    # Max drawdown
    peak = equities[0]
    max_dd = 0
    dd_duration = 0
    current_dd_duration = 0
    for eq in equities:
        if eq >= peak:
            peak = eq
            current_dd_duration = 0
        else:
            dd = (peak - eq) / peak
            current_dd_duration += 1
            if dd > max_dd:
                max_dd = dd
                dd_duration = current_dd_duration

    report.max_drawdown = max_dd
    report.max_drawdown_duration = dd_duration

    # Win rate and profit factor using FIFO pairing per symbol
    from collections import defaultdict
    buy_remaining: dict[str, list[tuple[float, int]]] = defaultdict(list)
    for t in portfolio.trades:
        if t.side == OrderSide.BUY:
            buy_remaining[t.symbol].append([t.price, t.quantity])

    profits = []
    losses = []
    for t in portfolio.trades:
        if t.side != OrderSide.SELL:
            continue
        q = buy_remaining.get(t.symbol)
        if not q:
            continue
        remaining = t.quantity
        sell_pnl = 0.0
        while remaining > 0 and q:
            buy_price, buy_qty = q[0]
            match_qty = min(buy_qty, remaining)
            sell_pnl += (t.price - buy_price) * match_qty
            q[0][1] -= match_qty
            remaining -= match_qty
            if q[0][1] <= 0:
                q.pop(0)
        if sell_pnl >= 0:
            profits.append(sell_pnl)
        else:
            losses.append(abs(sell_pnl))

    total_profit = sum(profits)
    total_loss = sum(losses)
    n_winning = len(profits)
    n_total = n_winning + len(losses)

    report.win_rate = n_winning / n_total if n_total > 0 else 0
    report.profit_factor = total_profit / total_loss if total_loss > 0 else float('inf') if total_profit > 0 else 0

    return report
