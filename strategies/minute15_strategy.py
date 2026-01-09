"""
15분봉 단타 전략
PDF 기준: 15분봉에서 7~10% 장대양봉 + 50% 지지 + 60선 위
"""

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SignalType, Minute15StrategyParams, CandleThreshold
from strategies.base_strategy import BaseStrategy, Signal, register_strategy
from indicators import (
    calculate_all_ma,
    calculate_change_rate,
    detect_volume_spike,
    get_candle_50_percent_level,
    get_candle_support_level,
    is_bullish,
)


class Minute15Strategy(BaseStrategy):
    """
    15분봉 단타 전략

    매수 조건 (PDF 기준):
    1. 15분봉에서 7% 이상 장대양봉 출현
    2. 거래량 >= 전일 동시간대 2배
    3. 현재가 >= 장대양봉 몸통 50% 지지
    4. 60선(=일봉 10일선) 위에 위치

    손절 조건:
    - 장대양봉 저가 이탈
    - 60선 이탈

    익절 조건:
    - 60선 대비 이격 10% 이상
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = Minute15StrategyParams()
        strategy_params = {
            'long_candle_threshold': default_params.long_candle_threshold,
            'volume_spike_ratio': default_params.volume_spike_ratio,
            'support_level': default_params.support_level,
            'ma_divergence_threshold': default_params.ma_divergence_threshold,
        }
        if params:
            strategy_params.update(params)

        super().__init__(name='minute15', params=strategy_params)

        # 신호 발생한 캔들 정보 저장 (손절가 계산용)
        self._signal_candle_low: Optional[float] = None
        self._signal_candle_50pct: Optional[float] = None

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

    def _check_long_candle(self, df: pd.DataFrame) -> bool:
        """장대양봉 확인 (7% 이상)"""
        cols = self._get_columns(df)
        change = (df[cols['close']].iloc[-1] - df[cols['open']].iloc[-1]) / df[cols['open']].iloc[-1]
        return change >= self.params['long_candle_threshold']

    def _check_bullish(self, df: pd.DataFrame) -> bool:
        """양봉 여부 확인"""
        cols = self._get_columns(df)
        return df[cols['close']].iloc[-1] > df[cols['open']].iloc[-1]

    def _check_volume_spike(self, df: pd.DataFrame) -> bool:
        """거래량 급등 확인"""
        spike = detect_volume_spike(df, threshold=self.params['volume_spike_ratio'])
        return spike.iloc[-1]

    def _check_price_support(self, df: pd.DataFrame, candle_50pct: float) -> bool:
        """50% 지지 확인 (현재가가 장대양봉 50% 위)"""
        cols = self._get_columns(df)
        current_price = df[cols['close']].iloc[-1]
        return current_price >= candle_50pct

    def _check_above_ma60(self, df: pd.DataFrame) -> bool:
        """60선 위에 있는지 확인"""
        cols = self._get_columns(df)

        # MA60 계산 (없으면 계산)
        if 'ma60' not in df.columns:
            df = calculate_all_ma(df, [60])

        current_price = df[cols['close']].iloc[-1]
        ma60 = df['ma60'].iloc[-1]

        return current_price > ma60

    def _get_candle_50_percent(self, df: pd.DataFrame) -> float:
        """장대양봉 50% 레벨 계산"""
        cols = self._get_columns(df)
        open_price = df[cols['open']].iloc[-1]
        close_price = df[cols['close']].iloc[-1]
        return (open_price + close_price) / 2

    def _get_candle_low(self, df: pd.DataFrame) -> float:
        """장대양봉 저가"""
        cols = self._get_columns(df)
        return df[cols['low']].iloc[-1]

    def check_buy_conditions(self, df: pd.DataFrame) -> Dict[str, bool]:
        """
        매수 조건 확인

        Returns:
            각 조건별 충족 여부 딕셔너리
        """
        conditions = {
            'bullish': self._check_bullish(df),
            'long_candle_7pct': self._check_long_candle(df),
            'volume_spike_2x': self._check_volume_spike(df),
            'above_ma60': self._check_above_ma60(df),
        }

        # 장대양봉이 확인된 경우에만 50% 지지 체크
        if conditions['long_candle_7pct']:
            candle_50pct = self._get_candle_50_percent(df)
            conditions['price_support_50pct'] = self._check_price_support(df, candle_50pct)
        else:
            conditions['price_support_50pct'] = False

        return conditions

    def generate_signal(self, df: pd.DataFrame, code: str = "",
                        name: str = "") -> Optional[Signal]:
        """
        매매 신호 생성

        Args:
            df: OHLCV DataFrame (15분봉)
            code: 종목 코드
            name: 종목명

        Returns:
            Signal 또는 None
        """
        if len(df) < 60:  # 최소 데이터 필요
            return None

        # MA 계산
        if 'ma60' not in df.columns:
            df = calculate_all_ma(df, [60])

        # 매수 조건 확인
        conditions = self.check_buy_conditions(df)

        # 모든 조건 충족 시 매수 신호
        if all(conditions.values()):
            cols = self._get_columns(df)
            entry_price = df[cols['close']].iloc[-1]

            # 손절가: 장대양봉 저가
            candle_low = self._get_candle_low(df)
            stop_loss = candle_low * 0.99  # 저가 -1%

            # 익절가: 진입가 대비 목표 수익률 또는 60선 이격 중 높은 값
            ma60 = df['ma60'].iloc[-1]
            ma_based_target = ma60 * (1 + self.params['ma_divergence_threshold'])
            price_based_target = entry_price * 1.05  # 최소 5% 수익 목표
            take_profit = max(ma_based_target, price_based_target)

            # 신호 강도 계산 (조건 충족 개수 기반)
            strength = sum(conditions.values()) / len(conditions)

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
                strength=strength,
                metadata={
                    'candle_low': candle_low,
                    'candle_50pct': self._get_candle_50_percent(df),
                    'ma60': ma60,
                    'conditions': conditions,
                }
            )

        return None

    def check_sell_conditions(self, df: pd.DataFrame,
                              entry_price: float = None,
                              candle_low: float = None) -> Dict[str, bool]:
        """
        매도/손절 조건 확인

        Args:
            df: OHLCV DataFrame
            entry_price: 진입 가격
            candle_low: 진입 시 장대양봉 저가

        Returns:
            각 조건별 충족 여부
        """
        cols = self._get_columns(df)
        current_price = df[cols['close']].iloc[-1]

        conditions = {}

        # MA60 확인
        if 'ma60' not in df.columns:
            df = calculate_all_ma(df, [60])

        ma60 = df['ma60'].iloc[-1]

        # 손절 조건 1: 장대양봉 저가 이탈
        if candle_low:
            conditions['candle_low_break'] = current_price < candle_low

        # 손절 조건 2: 60선 이탈
        conditions['ma60_break'] = current_price < ma60

        # 익절 조건: 60선 대비 이격 10% 이상
        ma_divergence = (current_price - ma60) / ma60
        conditions['take_profit_reached'] = ma_divergence >= self.params['ma_divergence_threshold']

        return conditions

    def calculate_stop_loss(self, df: pd.DataFrame, entry_price: float) -> float:
        """손절가 계산 (장대양봉 저가)"""
        candle_low = self._get_candle_low(df)
        return candle_low * 0.99  # 저가 -1% 여유

    def calculate_take_profit(self, df: pd.DataFrame, entry_price: float) -> float:
        """익절가 계산 (60선 대비 10% 이격)"""
        if 'ma60' not in df.columns:
            df = calculate_all_ma(df, [60])

        ma60 = df['ma60'].iloc[-1]
        return ma60 * (1 + self.params['ma_divergence_threshold'])


# 전략 등록
register_strategy(Minute15Strategy())
