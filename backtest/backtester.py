"""
백테스터 모듈
전략 백테스팅 및 성과 평가
"""

import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional, Union
from dataclasses import dataclass, field
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SignalType, TRADING
from strategies import BaseStrategy, Signal, get_strategy
from backtest.metrics import (
    TradeRecord,
    PerformanceMetrics,
    calculate_all_metrics,
    format_metrics_report,
)
from utils import log_info, log_error, log_trade, measure_time


@dataclass
class Position:
    """보유 포지션"""
    code: str
    name: str
    strategy: str
    entry_date: datetime
    entry_price: float
    quantity: int
    side: str = 'long'
    stop_loss: Optional[float] = None
    take_profit: Optional[float] = None
    current_price: float = 0.0
    unrealized_pnl: float = 0.0


@dataclass
class BacktestConfig:
    """백테스트 설정"""
    initial_capital: float = 10000000  # 1000만원
    commission_rate: float = 0.00015   # 수수료율 0.015%
    slippage_rate: float = 0.001       # 슬리피지 0.1%
    max_position_size: float = 0.1     # 1회 최대 투자 비율
    max_positions: int = 10            # 최대 동시 보유 종목 수
    use_stop_loss: bool = True         # 손절 사용
    use_take_profit: bool = True       # 익절 사용
    allow_short: bool = False          # 공매도 허용


class Backtester:
    """
    전략 백테스터

    과거 데이터로 전략 성과 검증
    """

    def __init__(self, strategy: Union[str, BaseStrategy],
                 config: BacktestConfig = None):
        """
        Args:
            strategy: 전략 이름 또는 BaseStrategy 인스턴스
            config: 백테스트 설정
        """
        if isinstance(strategy, str):
            self.strategy = get_strategy(strategy)
            if not self.strategy:
                raise ValueError(f"전략을 찾을 수 없음: {strategy}")
        else:
            self.strategy = strategy

        self.config = config or BacktestConfig()
        self.reset()

    def reset(self):
        """백테스트 상태 초기화"""
        self.capital = self.config.initial_capital
        self.positions: Dict[str, Position] = {}
        self.trades: List[TradeRecord] = []
        self.equity_curve = []
        self.daily_returns = []
        self.current_date = None

    def _calculate_position_size(self, price: float) -> int:
        """포지션 크기 계산"""
        max_amount = self.capital * self.config.max_position_size
        return int(max_amount / price)

    def _apply_slippage(self, price: float, side: str) -> float:
        """슬리피지 적용"""
        if side == 'buy':
            return price * (1 + self.config.slippage_rate)
        else:
            return price * (1 - self.config.slippage_rate)

    def _calculate_commission(self, amount: float) -> float:
        """수수료 계산"""
        return amount * self.config.commission_rate

    def _open_position(self, code: str, name: str, price: float,
                       signal: Signal, date: datetime) -> bool:
        """
        포지션 진입

        Returns:
            성공 여부
        """
        # 최대 포지션 수 확인
        if len(self.positions) >= self.config.max_positions:
            return False

        # 이미 보유 중인 종목 확인
        if code in self.positions:
            return False

        # 포지션 크기 계산
        entry_price = self._apply_slippage(price, 'buy')
        quantity = self._calculate_position_size(entry_price)

        if quantity <= 0:
            return False

        # 필요 금액 계산
        amount = entry_price * quantity
        commission = self._calculate_commission(amount)
        total_cost = amount + commission

        # 자본 확인
        if total_cost > self.capital:
            quantity = int((self.capital - commission) / entry_price)
            if quantity <= 0:
                return False
            amount = entry_price * quantity
            commission = self._calculate_commission(amount)
            total_cost = amount + commission

        # 포지션 생성
        position = Position(
            code=code,
            name=name,
            strategy=self.strategy.name,
            entry_date=date,
            entry_price=entry_price,
            quantity=quantity,
            side='long',
            stop_loss=signal.stop_loss,
            take_profit=signal.take_profit,
            current_price=price,
        )

        self.positions[code] = position
        self.capital -= total_cost

        log_trade(
            code=code,
            trade_type='BUY',
            price=entry_price,
            quantity=quantity
        )

        return True

    def _close_position(self, code: str, price: float, date: datetime,
                        reason: str = "") -> Optional[TradeRecord]:
        """
        포지션 청산

        Returns:
            거래 기록 또는 None
        """
        if code not in self.positions:
            return None

        position = self.positions[code]
        exit_price = self._apply_slippage(price, 'sell')

        # 손익 계산
        amount = exit_price * position.quantity
        commission = self._calculate_commission(amount)
        net_amount = amount - commission

        entry_amount = position.entry_price * position.quantity
        pnl = net_amount - entry_amount
        pnl_percent = (pnl / entry_amount) * 100 if entry_amount > 0 else 0

        # 보유 기간 계산
        holding_days = (date - position.entry_date).days if hasattr(date, 'days') else 1

        # 거래 기록 생성
        trade = TradeRecord(
            code=code,
            name=position.name,
            strategy=position.strategy,
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            exit_date=date,
            exit_price=exit_price,
            quantity=position.quantity,
            side=position.side,
            stop_loss=position.stop_loss,
            take_profit=position.take_profit,
            exit_reason=reason,
            pnl=pnl,
            pnl_percent=pnl_percent,
            holding_days=max(1, holding_days),
        )

        # 포지션 제거 및 자본 업데이트
        del self.positions[code]
        self.capital += net_amount

        self.trades.append(trade)

        log_trade(
            code=code,
            trade_type='SELL',
            price=exit_price,
            quantity=trade.quantity,
            pnl=pnl
        )

        return trade

    def _check_stop_loss(self, position: Position, current_price: float) -> bool:
        """손절 확인"""
        if not self.config.use_stop_loss or not position.stop_loss:
            return False

        return current_price <= position.stop_loss

    def _check_take_profit(self, position: Position, current_price: float) -> bool:
        """익절 확인"""
        if not self.config.use_take_profit or not position.take_profit:
            return False

        return current_price >= position.take_profit

    def _update_equity(self, date: datetime):
        """자산 가치 업데이트"""
        # 보유 포지션 평가액
        position_value = sum(
            p.current_price * p.quantity for p in self.positions.values()
        )

        total_equity = self.capital + position_value

        self.equity_curve.append({
            'date': date,
            'equity': total_equity,
            'capital': self.capital,
            'position_value': position_value,
            'positions': len(self.positions),
        })

    def _process_day(self, date: datetime, data: Dict[str, pd.DataFrame]):
        """
        일별 처리

        Args:
            date: 거래일
            data: {code: DataFrame} 당일 데이터
        """
        self.current_date = date

        # 1. 기존 포지션 가격 업데이트 및 손익절 확인
        codes_to_close = []

        for code, position in self.positions.items():
            if code not in data:
                continue

            df = data[code]
            if df.empty:
                continue

            # 컬럼명 매핑
            col_lower = {c.lower(): c for c in df.columns}
            close_col = col_lower.get('close', 'Close')
            low_col = col_lower.get('low', 'Low')
            high_col = col_lower.get('high', 'High')

            current_price = df[close_col].iloc[-1]
            low_price = df[low_col].iloc[-1]
            high_price = df[high_col].iloc[-1]

            position.current_price = current_price

            # 손절 확인 (장중 저가 기준)
            if self._check_stop_loss(position, low_price):
                codes_to_close.append((code, position.stop_loss, '손절'))
            # 익절 확인 (장중 고가 기준)
            elif self._check_take_profit(position, high_price):
                codes_to_close.append((code, position.take_profit, '익절'))

        # 손익절 실행
        for code, price, reason in codes_to_close:
            self._close_position(code, price, date, reason)

        # 2. 새로운 신호 확인 및 진입
        for code, df in data.items():
            if code in self.positions:
                continue

            if df.empty or len(df) < 10:
                continue

            # 전략 신호 확인
            try:
                signal = self.strategy.generate_signal(df, code)

                if signal and signal.signal_type == SignalType.BUY:
                    col_lower = {c.lower(): c for c in df.columns}
                    close_col = col_lower.get('close', 'Close')
                    price = df[close_col].iloc[-1]

                    self._open_position(code, signal.name or code, price, signal, date)

            except Exception as e:
                log_error(f"신호 생성 오류 [{code}]: {e}")

        # 3. 자산 업데이트
        self._update_equity(date)

    @measure_time
    def run(self, data: Dict[str, pd.DataFrame],
            start_date: datetime = None,
            end_date: datetime = None) -> PerformanceMetrics:
        """
        백테스트 실행

        Args:
            data: {code: DataFrame} OHLCV 데이터
            start_date: 시작일
            end_date: 종료일

        Returns:
            성과 지표
        """
        self.reset()

        if not data:
            log_error("백테스트 데이터가 없습니다")
            return PerformanceMetrics()

        log_info(f"백테스트 시작: {self.strategy.name} 전략, {len(data)}개 종목")

        # 모든 날짜 수집
        all_dates = set()
        for code, df in data.items():
            if df.empty:
                continue
            all_dates.update(df.index.tolist())

        # 날짜 정렬
        dates = sorted(all_dates)

        # 기간 필터링
        if start_date:
            dates = [d for d in dates if d >= start_date]
        if end_date:
            dates = [d for d in dates if d <= end_date]

        if not dates:
            log_error("유효한 거래일이 없습니다")
            return PerformanceMetrics()

        log_info(f"백테스트 기간: {dates[0]} ~ {dates[-1]}")

        # 일별 처리
        for date in dates:
            # 해당 날짜까지의 데이터 추출
            day_data = {}
            for code, df in data.items():
                if df.empty:
                    continue

                # 해당 날짜까지의 데이터
                mask = df.index <= date
                if mask.any():
                    day_data[code] = df[mask]

            self._process_day(date, day_data)

        # 남은 포지션 청산
        for code in list(self.positions.keys()):
            if code in data and not data[code].empty:
                col_lower = {c.lower(): c for c in data[code].columns}
                close_col = col_lower.get('close', 'Close')
                price = data[code][close_col].iloc[-1]
                self._close_position(code, price, dates[-1], '백테스트 종료')

        # 성과 계산
        equity_df = pd.DataFrame(self.equity_curve)
        if not equity_df.empty:
            equity_df.set_index('date', inplace=True)
            equity_series = equity_df['equity']
        else:
            equity_series = pd.Series([self.config.initial_capital])

        metrics = calculate_all_metrics(
            equity_series,
            self.trades,
            self.config.initial_capital
        )

        log_info(f"백테스트 완료: 총 {len(self.trades)}건 거래")

        return metrics

    def get_trades(self) -> List[TradeRecord]:
        """거래 기록 반환"""
        return self.trades

    def get_equity_curve(self) -> pd.DataFrame:
        """자산 곡선 반환"""
        return pd.DataFrame(self.equity_curve)

    def generate_report(self) -> str:
        """백테스트 보고서 생성"""
        equity_df = pd.DataFrame(self.equity_curve)
        if not equity_df.empty:
            equity_df.set_index('date', inplace=True)
            equity_series = equity_df['equity']
        else:
            equity_series = pd.Series([self.config.initial_capital])

        metrics = calculate_all_metrics(
            equity_series,
            self.trades,
            self.config.initial_capital
        )

        return format_metrics_report(metrics)


class MultiStrategyBacktester:
    """
    다중 전략 백테스터

    여러 전략을 동시에 테스트하고 비교
    """

    def __init__(self, strategies: List[Union[str, BaseStrategy]],
                 config: BacktestConfig = None):
        """
        Args:
            strategies: 전략 이름 또는 인스턴스 리스트
            config: 백테스트 설정
        """
        self.backtesters = []
        for strategy in strategies:
            try:
                bt = Backtester(strategy, config)
                self.backtesters.append(bt)
            except ValueError as e:
                log_error(str(e))

        self.results: Dict[str, PerformanceMetrics] = {}

    @measure_time
    def run(self, data: Dict[str, pd.DataFrame],
            start_date: datetime = None,
            end_date: datetime = None) -> Dict[str, PerformanceMetrics]:
        """
        모든 전략 백테스트 실행

        Returns:
            {전략명: 성과지표} 딕셔너리
        """
        self.results = {}

        for bt in self.backtesters:
            strategy_name = bt.strategy.name
            log_info(f"전략 백테스트: {strategy_name}")

            metrics = bt.run(data, start_date, end_date)
            self.results[strategy_name] = metrics

        return self.results

    def compare_strategies(self) -> pd.DataFrame:
        """전략 비교 테이블 생성"""
        if not self.results:
            return pd.DataFrame()

        records = []
        for name, metrics in self.results.items():
            records.append({
                '전략': name,
                '총수익률(%)': metrics.total_return_percent,
                '연환산수익률(%)': metrics.annualized_return,
                'MDD(%)': metrics.max_drawdown_percent,
                '샤프비율': metrics.sharpe_ratio,
                '승률(%)': metrics.win_rate,
                '수익팩터': metrics.profit_factor,
                '총거래수': metrics.total_trades,
            })

        df = pd.DataFrame(records)
        df = df.sort_values('총수익률(%)', ascending=False)
        return df

    def generate_comparison_report(self) -> str:
        """전략 비교 보고서"""
        lines = []
        lines.append("=" * 80)
        lines.append("다중 전략 백테스트 비교 보고서")
        lines.append("=" * 80)
        lines.append("")

        df = self.compare_strategies()
        if df.empty:
            lines.append("결과가 없습니다.")
        else:
            lines.append(df.to_string(index=False))

        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)


def run_backtest(strategy: Union[str, BaseStrategy],
                 data: Dict[str, pd.DataFrame],
                 initial_capital: float = 10000000,
                 start_date: datetime = None,
                 end_date: datetime = None) -> tuple:
    """
    백테스트 실행 헬퍼 함수

    Returns:
        (PerformanceMetrics, 보고서 문자열)
    """
    config = BacktestConfig(initial_capital=initial_capital)
    bt = Backtester(strategy, config)

    metrics = bt.run(data, start_date, end_date)
    report = bt.generate_report()

    return metrics, report
