"""
백테스트 성과 지표 모듈
수익률, MDD, 샤프비율 등 계산
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class TradeRecord:
    """개별 거래 기록"""
    code: str
    name: str
    strategy: str
    entry_date: datetime
    entry_price: float
    exit_date: Optional[datetime] = None
    exit_price: Optional[float] = None
    quantity: int = 0
    side: str = 'long'  # 'long' or 'short'
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    exit_reason: str = ""
    pnl: float = 0.0
    pnl_percent: float = 0.0
    holding_days: int = 0


@dataclass
class PerformanceMetrics:
    """성과 지표"""
    # 기본 수익률
    total_return: float = 0.0
    total_return_percent: float = 0.0
    annualized_return: float = 0.0

    # 거래 통계
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0

    # 손익 통계
    avg_profit: float = 0.0
    avg_loss: float = 0.0
    avg_profit_percent: float = 0.0
    avg_loss_percent: float = 0.0
    profit_factor: float = 0.0
    avg_holding_days: float = 0.0

    # 리스크 지표
    max_drawdown: float = 0.0
    max_drawdown_percent: float = 0.0
    max_drawdown_duration: int = 0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    calmar_ratio: float = 0.0

    # 기타
    best_trade: float = 0.0
    worst_trade: float = 0.0
    avg_trade: float = 0.0
    std_returns: float = 0.0

    # 기간
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    trading_days: int = 0


def calculate_returns(equity_curve: pd.Series) -> pd.Series:
    """수익률 시계열 계산"""
    return equity_curve.pct_change().dropna()


def calculate_total_return(equity_curve: pd.Series) -> float:
    """총 수익률 계산"""
    if len(equity_curve) < 2:
        return 0.0

    initial = equity_curve.iloc[0]
    final = equity_curve.iloc[-1]

    if initial == 0:
        return 0.0

    return (final - initial) / initial


def calculate_annualized_return(total_return: float, days: int) -> float:
    """연환산 수익률 계산"""
    if days <= 0:
        return 0.0

    years = days / 252  # 거래일 기준
    if years <= 0:
        return 0.0

    return (1 + total_return) ** (1 / years) - 1


def calculate_max_drawdown(equity_curve: pd.Series) -> tuple:
    """
    최대 낙폭(MDD) 계산

    Returns:
        (MDD 금액, MDD 비율, MDD 기간(일))
    """
    if len(equity_curve) < 2:
        return 0.0, 0.0, 0

    # 누적 최고점
    cummax = equity_curve.cummax()

    # 드로우다운
    drawdown = equity_curve - cummax
    drawdown_pct = drawdown / cummax

    # 최대 드로우다운
    mdd = drawdown.min()
    mdd_pct = drawdown_pct.min()

    # MDD 기간 계산
    mdd_idx = drawdown.idxmin()
    peak_idx = cummax[:mdd_idx].idxmax() if len(cummax[:mdd_idx]) > 0 else mdd_idx

    try:
        mdd_duration = (mdd_idx - peak_idx).days
    except (TypeError, AttributeError):
        # 인덱스가 날짜가 아닌 경우
        mdd_duration = 0

    return abs(mdd), abs(mdd_pct), mdd_duration


def calculate_sharpe_ratio(returns: pd.Series,
                           risk_free_rate: float = 0.02) -> float:
    """
    샤프 비율 계산

    Args:
        returns: 일별 수익률
        risk_free_rate: 무위험 수익률 (연율)

    Returns:
        샤프 비율
    """
    if len(returns) < 2 or returns.std() == 0:
        return 0.0

    # 일별 무위험 수익률
    daily_rf = risk_free_rate / 252

    excess_returns = returns - daily_rf
    return np.sqrt(252) * excess_returns.mean() / excess_returns.std()


def calculate_sortino_ratio(returns: pd.Series,
                            risk_free_rate: float = 0.02) -> float:
    """
    소르티노 비율 계산 (하방 위험만 고려)

    Args:
        returns: 일별 수익률
        risk_free_rate: 무위험 수익률 (연율)

    Returns:
        소르티노 비율
    """
    if len(returns) < 2:
        return 0.0

    daily_rf = risk_free_rate / 252
    excess_returns = returns - daily_rf

    # 음수 수익률만 추출
    downside_returns = excess_returns[excess_returns < 0]

    if len(downside_returns) == 0 or downside_returns.std() == 0:
        return float('inf') if excess_returns.mean() > 0 else 0.0

    downside_std = downside_returns.std()
    return np.sqrt(252) * excess_returns.mean() / downside_std


def calculate_calmar_ratio(annualized_return: float,
                           max_drawdown_pct: float) -> float:
    """
    칼마 비율 계산 (연환산 수익률 / MDD)

    Args:
        annualized_return: 연환산 수익률
        max_drawdown_pct: 최대 낙폭 비율

    Returns:
        칼마 비율
    """
    if max_drawdown_pct == 0:
        return float('inf') if annualized_return > 0 else 0.0

    return annualized_return / abs(max_drawdown_pct)


def calculate_profit_factor(trades: List[TradeRecord]) -> float:
    """
    수익 팩터 계산 (총 수익 / 총 손실)

    Args:
        trades: 거래 기록 리스트

    Returns:
        수익 팩터
    """
    total_profit = sum(t.pnl for t in trades if t.pnl > 0)
    total_loss = sum(abs(t.pnl) for t in trades if t.pnl < 0)

    if total_loss == 0:
        return float('inf') if total_profit > 0 else 0.0

    return total_profit / total_loss


def calculate_win_rate(trades: List[TradeRecord]) -> float:
    """승률 계산"""
    if not trades:
        return 0.0

    winning = sum(1 for t in trades if t.pnl > 0)
    return winning / len(trades)


def calculate_trade_stats(trades: List[TradeRecord]) -> Dict[str, float]:
    """거래 통계 계산"""
    if not trades:
        return {
            'avg_profit': 0.0,
            'avg_loss': 0.0,
            'avg_profit_pct': 0.0,
            'avg_loss_pct': 0.0,
            'best_trade': 0.0,
            'worst_trade': 0.0,
            'avg_trade': 0.0,
            'avg_holding_days': 0.0,
        }

    profits = [t.pnl for t in trades if t.pnl > 0]
    losses = [t.pnl for t in trades if t.pnl < 0]
    profit_pcts = [t.pnl_percent for t in trades if t.pnl_percent > 0]
    loss_pcts = [t.pnl_percent for t in trades if t.pnl_percent < 0]
    all_pnl = [t.pnl for t in trades]
    holding_days = [t.holding_days for t in trades]

    return {
        'avg_profit': np.mean(profits) if profits else 0.0,
        'avg_loss': np.mean(losses) if losses else 0.0,
        'avg_profit_pct': np.mean(profit_pcts) if profit_pcts else 0.0,
        'avg_loss_pct': np.mean(loss_pcts) if loss_pcts else 0.0,
        'best_trade': max(all_pnl) if all_pnl else 0.0,
        'worst_trade': min(all_pnl) if all_pnl else 0.0,
        'avg_trade': np.mean(all_pnl) if all_pnl else 0.0,
        'avg_holding_days': np.mean(holding_days) if holding_days else 0.0,
    }


def calculate_all_metrics(equity_curve: pd.Series,
                          trades: List[TradeRecord],
                          initial_capital: float = 10000000) -> PerformanceMetrics:
    """
    모든 성과 지표 계산

    Args:
        equity_curve: 자산 곡선
        trades: 거래 기록
        initial_capital: 초기 자본

    Returns:
        PerformanceMetrics
    """
    metrics = PerformanceMetrics()

    if len(equity_curve) < 2:
        return metrics

    # 기간 정보
    metrics.start_date = equity_curve.index[0] if hasattr(equity_curve.index[0], 'date') else None
    metrics.end_date = equity_curve.index[-1] if hasattr(equity_curve.index[-1], 'date') else None
    metrics.trading_days = len(equity_curve)

    # 수익률 계산
    returns = calculate_returns(equity_curve)
    total_return = calculate_total_return(equity_curve)

    metrics.total_return = equity_curve.iloc[-1] - equity_curve.iloc[0]
    metrics.total_return_percent = total_return * 100
    metrics.annualized_return = calculate_annualized_return(total_return, len(equity_curve)) * 100

    # MDD 계산
    mdd, mdd_pct, mdd_duration = calculate_max_drawdown(equity_curve)
    metrics.max_drawdown = mdd
    metrics.max_drawdown_percent = mdd_pct * 100
    metrics.max_drawdown_duration = mdd_duration

    # 리스크 지표
    metrics.sharpe_ratio = calculate_sharpe_ratio(returns)
    metrics.sortino_ratio = calculate_sortino_ratio(returns)
    metrics.calmar_ratio = calculate_calmar_ratio(
        metrics.annualized_return / 100,
        mdd_pct
    )
    metrics.std_returns = returns.std() * 100 if len(returns) > 0 else 0.0

    # 거래 통계
    if trades:
        metrics.total_trades = len(trades)
        metrics.winning_trades = sum(1 for t in trades if t.pnl > 0)
        metrics.losing_trades = sum(1 for t in trades if t.pnl < 0)
        metrics.win_rate = calculate_win_rate(trades) * 100
        metrics.profit_factor = calculate_profit_factor(trades)

        trade_stats = calculate_trade_stats(trades)
        metrics.avg_profit = trade_stats['avg_profit']
        metrics.avg_loss = trade_stats['avg_loss']
        metrics.avg_profit_percent = trade_stats['avg_profit_pct']
        metrics.avg_loss_percent = trade_stats['avg_loss_pct']
        metrics.best_trade = trade_stats['best_trade']
        metrics.worst_trade = trade_stats['worst_trade']
        metrics.avg_trade = trade_stats['avg_trade']
        metrics.avg_holding_days = trade_stats['avg_holding_days']

    return metrics


def format_metrics_report(metrics: PerformanceMetrics) -> str:
    """성과 지표 보고서 포맷팅"""
    lines = []
    lines.append("=" * 60)
    lines.append("백테스트 성과 보고서")
    lines.append("=" * 60)
    lines.append("")

    # 수익률
    lines.append("[수익률]")
    lines.append(f"  총 수익금: {metrics.total_return:,.0f}원")
    lines.append(f"  총 수익률: {metrics.total_return_percent:.2f}%")
    lines.append(f"  연환산 수익률: {metrics.annualized_return:.2f}%")
    lines.append("")

    # 리스크
    lines.append("[리스크 지표]")
    lines.append(f"  최대 낙폭(MDD): {metrics.max_drawdown:,.0f}원 ({metrics.max_drawdown_percent:.2f}%)")
    lines.append(f"  MDD 기간: {metrics.max_drawdown_duration}일")
    lines.append(f"  샤프 비율: {metrics.sharpe_ratio:.2f}")
    lines.append(f"  소르티노 비율: {metrics.sortino_ratio:.2f}")
    lines.append(f"  칼마 비율: {metrics.calmar_ratio:.2f}")
    lines.append(f"  수익률 표준편차: {metrics.std_returns:.2f}%")
    lines.append("")

    # 거래 통계
    lines.append("[거래 통계]")
    lines.append(f"  총 거래 수: {metrics.total_trades}회")
    lines.append(f"  승리/패배: {metrics.winning_trades}회 / {metrics.losing_trades}회")
    lines.append(f"  승률: {metrics.win_rate:.1f}%")
    lines.append(f"  수익 팩터: {metrics.profit_factor:.2f}")
    lines.append(f"  평균 보유일: {metrics.avg_holding_days:.1f}일")
    lines.append("")

    # 손익 통계
    lines.append("[손익 통계]")
    lines.append(f"  평균 수익 거래: {metrics.avg_profit:,.0f}원 ({metrics.avg_profit_percent:.2f}%)")
    lines.append(f"  평균 손실 거래: {metrics.avg_loss:,.0f}원 ({metrics.avg_loss_percent:.2f}%)")
    lines.append(f"  최고 수익 거래: {metrics.best_trade:,.0f}원")
    lines.append(f"  최대 손실 거래: {metrics.worst_trade:,.0f}원")
    lines.append(f"  평균 거래 손익: {metrics.avg_trade:,.0f}원")
    lines.append("")

    # 기간
    if metrics.start_date and metrics.end_date:
        lines.append("[기간]")
        lines.append(f"  시작일: {metrics.start_date}")
        lines.append(f"  종료일: {metrics.end_date}")
        lines.append(f"  거래일: {metrics.trading_days}일")
        lines.append("")

    lines.append("=" * 60)

    return "\n".join(lines)
