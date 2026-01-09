"""
30분봉 60선 매매 전략
PDF 기준: 30분봉 60선(=일봉 5일선) 지지 매매
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SignalType, Minute30StrategyParams
from strategies.base_strategy import BaseStrategy, Signal, register_strategy
from indicators import (
    calculate_all_ma,
    calculate_ma_divergence,
    is_bullish,
    detect_volume_spike,
)


class Minute30Strategy(BaseStrategy):
    """
    30분봉 60선 매매 전략

    PDF 핵심 내용:
    "간단히 한 줄로 설명하면 60선에 가까우면 매수하고, 60선과 멀어지면 매도한다"

    매수 조건:
    1. 30분봉 종가 >= 60선
    2. 이전 캔들이 60선 터치 후 반등 (지지 확인)
    3. 거래량 증가 동반
    4. 양봉 마감

    손절 조건:
    - 30분봉 종가 < 60선
    - 돌파 캔들 저가 이탈

    익절 조건:
    - 60선 대비 이격률 10% 이상
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = Minute30StrategyParams()
        strategy_params = {
            'ma_divergence_threshold': default_params.ma_divergence_threshold,
            'ma_period': 60,  # 30분봉 60선 = 일봉 5일선
            'near_ma_threshold': 0.02,  # MA 근접 판단 기준 (2%)
        }
        if params:
            strategy_params.update(params)

        super().__init__(name='minute30', params=strategy_params)

    def _get_columns(self, df: pd.DataFrame) -> Dict[str, str]:
        """컬럼명 매핑"""
        col_lower = {c.lower(): c for c in df.columns}
        return {
            'open': col_lower.get('open', 'Open'),
            'high': col_lower.get('high', 'High'),
            'low': col_lower.get('low', 'Low'),
            'close': col_lower.get('close', 'Close'),
            'volume': col_lower.get('volume', 'Volume'),
        }

    def _ensure_ma(self, df: pd.DataFrame) -> pd.DataFrame:
        """MA60 계산 확인"""
        ma_col = f"ma{self.params['ma_period']}"
        if ma_col not in df.columns:
            df = calculate_all_ma(df, [self.params['ma_period']])
        return df

    def _check_price_above_ma60(self, df: pd.DataFrame) -> bool:
        """현재가가 60선 위에 있는지 확인"""
        cols = self._get_columns(df)
        df = self._ensure_ma(df)

        ma_col = f"ma{self.params['ma_period']}"
        current_price = df[cols['close']].iloc[-1]
        ma60 = df[ma_col].iloc[-1]

        return current_price >= ma60

    def _check_ma60_support(self, df: pd.DataFrame, lookback: int = 3) -> bool:
        """
        60선 지지 확인 (최근 N캔들 내에서 60선 터치 후 반등)

        지지 패턴:
        - 저가가 60선 근처까지 내려왔다가
        - 종가가 60선 위에서 마감
        """
        cols = self._get_columns(df)
        df = self._ensure_ma(df)

        ma_col = f"ma{self.params['ma_period']}"
        near_threshold = self.params['near_ma_threshold']

        # 최근 lookback 캔들 확인
        for i in range(-lookback, 0):
            try:
                low = df[cols['low']].iloc[i]
                close = df[cols['close']].iloc[i]
                ma60 = df[ma_col].iloc[i]

                # 저가가 60선 근처 (아래 또는 약간 위)
                low_near_ma = low <= ma60 * (1 + near_threshold)

                # 종가가 60선 위
                close_above_ma = close > ma60

                if low_near_ma and close_above_ma:
                    return True
            except IndexError:
                continue

        return False

    def _check_volume_increase(self, df: pd.DataFrame) -> bool:
        """거래량 증가 확인"""
        cols = self._get_columns(df)

        # 현재 거래량 vs 이전 5캔들 평균
        current_volume = df[cols['volume']].iloc[-1]
        avg_volume = df[cols['volume']].iloc[-6:-1].mean()

        return current_volume > avg_volume

    def _check_bullish_candle(self, df: pd.DataFrame) -> bool:
        """양봉 확인"""
        cols = self._get_columns(df)
        return df[cols['close']].iloc[-1] > df[cols['open']].iloc[-1]

    def _get_breakout_candle_low(self, df: pd.DataFrame, lookback: int = 5) -> float:
        """
        돌파 캔들(60선 지지 확인된 캔들)의 저가 찾기
        """
        cols = self._get_columns(df)
        df = self._ensure_ma(df)

        ma_col = f"ma{self.params['ma_period']}"
        near_threshold = self.params['near_ma_threshold']

        # 최근 캔들 중 60선 지지 캔들 찾기
        for i in range(-lookback, 0):
            try:
                low = df[cols['low']].iloc[i]
                close = df[cols['close']].iloc[i]
                ma60 = df[ma_col].iloc[i]

                if low <= ma60 * (1 + near_threshold) and close > ma60:
                    return low
            except IndexError:
                continue

        # 찾지 못하면 현재 저가 반환
        return df[cols['low']].iloc[-1]

    def check_buy_conditions(self, df: pd.DataFrame) -> Dict[str, bool]:
        """매수 조건 확인"""
        df = self._ensure_ma(df)

        conditions = {
            'price_above_ma60': self._check_price_above_ma60(df),
            'ma60_support': self._check_ma60_support(df),
            'volume_increase': self._check_volume_increase(df),
            'bullish_candle': self._check_bullish_candle(df),
        }

        return conditions

    def generate_signal(self, df: pd.DataFrame, code: str = "",
                        name: str = "") -> Optional[Signal]:
        """
        매매 신호 생성

        Args:
            df: OHLCV DataFrame (30분봉)
            code: 종목 코드
            name: 종목명

        Returns:
            Signal 또는 None
        """
        if len(df) < 60:  # 최소 데이터 필요
            return None

        df = self._ensure_ma(df)

        # 매수 조건 확인
        conditions = self.check_buy_conditions(df)

        # 모든 조건 충족 시 매수 신호
        if all(conditions.values()):
            cols = self._get_columns(df)
            ma_col = f"ma{self.params['ma_period']}"

            entry_price = df[cols['close']].iloc[-1]
            ma60 = df[ma_col].iloc[-1]

            # 손절가: 돌파 캔들 저가 또는 60선 -2%
            breakout_low = self._get_breakout_candle_low(df)
            stop_loss = min(breakout_low * 0.99, ma60 * 0.98)

            # 익절가: 진입가 대비 목표 수익률 또는 60선 이격 중 높은 값
            ma_based_target = ma60 * (1 + self.params['ma_divergence_threshold'])
            price_based_target = entry_price * 1.05  # 최소 5% 수익 목표
            take_profit = max(ma_based_target, price_based_target)

            # 현재 이격도
            current_divergence = (entry_price - ma60) / ma60

            return Signal(
                code=code,
                name=name,
                datetime=datetime.now(),
                signal_type=SignalType.BUY,
                strategy=self.name,
                price=entry_price,
                stop_loss=stop_loss,
                take_profit=take_profit,
                reason=self.get_signal_reason(conditions),
                strength=1.0 - min(current_divergence, 0.1),  # 이격도 낮을수록 강한 신호
                metadata={
                    'ma60': ma60,
                    'breakout_candle_low': breakout_low,
                    'current_divergence': current_divergence,
                    'conditions': conditions,
                }
            )

        return None

    def check_sell_conditions(self, df: pd.DataFrame,
                              entry_price: float = None,
                              breakout_low: float = None) -> Dict[str, bool]:
        """
        매도/손절 조건 확인

        Args:
            df: OHLCV DataFrame
            entry_price: 진입 가격
            breakout_low: 돌파 캔들 저가

        Returns:
            각 조건별 충족 여부
        """
        cols = self._get_columns(df)
        df = self._ensure_ma(df)

        current_price = df[cols['close']].iloc[-1]
        ma_col = f"ma{self.params['ma_period']}"
        ma60 = df[ma_col].iloc[-1]

        conditions = {}

        # 손절 조건 1: 60선 이탈 (종가 기준)
        conditions['ma60_break'] = current_price < ma60

        # 손절 조건 2: 돌파 캔들 저가 이탈
        if breakout_low:
            conditions['breakout_low_break'] = current_price < breakout_low

        # 익절 조건: 60선 대비 이격 10% 이상
        ma_divergence = (current_price - ma60) / ma60
        conditions['take_profit_reached'] = ma_divergence >= self.params['ma_divergence_threshold']

        return conditions

    def calculate_stop_loss(self, df: pd.DataFrame, entry_price: float) -> float:
        """손절가 계산"""
        df = self._ensure_ma(df)
        ma_col = f"ma{self.params['ma_period']}"
        ma60 = df[ma_col].iloc[-1]

        breakout_low = self._get_breakout_candle_low(df)
        return min(breakout_low * 0.99, ma60 * 0.98)

    def calculate_take_profit(self, df: pd.DataFrame, entry_price: float) -> float:
        """익절가 계산"""
        df = self._ensure_ma(df)
        ma_col = f"ma{self.params['ma_period']}"
        ma60 = df[ma_col].iloc[-1]

        return ma60 * (1 + self.params['ma_divergence_threshold'])


# 전략 등록
register_strategy(Minute30Strategy())
