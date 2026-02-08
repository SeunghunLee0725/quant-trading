"""
기준봉 돌파 전략
PDF 기준: 거래량 터진 기준봉 → 눌림 후 돌파 매수
"""

import pandas as pd
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SignalType, BreakoutStrategyParams
from strategies.base_strategy import BaseStrategy, Signal, register_strategy
from indicators import (
    calculate_sma,
)


class BreakoutStrategy(BaseStrategy):
    """
    기준봉 돌파 전략

    PDF 핵심 내용:
    "거래량이 터지면서 시세를 분출하는 기준봉이 나오고,
     그 후에 거래량이 줄면서 조정을 받다가
     기준봉의 고가를 돌파하는 시점에 매수"

    매수 조건:
    1. 최근 N일 내 기준봉 출현 (거래량 3배 이상 + 5% 이상 상승)
    2. 기준봉 이후 거래량 감소 조정
    3. 기준봉 고가 돌파 시 매수
    4. 이동평균선 정배열 확인

    손절 조건:
    - 기준봉 저가 이탈
    - 기준봉 종가 -3% 이탈

    익절 조건:
    - 목표가 도달 (기준봉 몸통의 1~2배)
    - 거래량 급증 후 음봉 출현
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = BreakoutStrategyParams()
        strategy_params = {
            'reference_candle_threshold': default_params.reference_candle_threshold,
            'volume_spike_ratio': default_params.volume_spike_ratio,
            'lookback_days': default_params.lookback_days,
            'consolidation_days_min': default_params.consolidation_days[0],
            'consolidation_days_max': default_params.consolidation_days[1],
            'breakout_threshold': default_params.breakout_threshold,
        }
        if params:
            strategy_params.update(params)

        super().__init__(name='breakout', params=strategy_params)

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

    def _find_reference_candle(self, df: pd.DataFrame) -> Optional[Tuple[int, Dict]]:
        """
        기준봉 찾기 (거래량 급증 + 큰 상승)

        Returns:
            (인덱스 위치, 기준봉 정보) 또는 None
        """
        cols = self._get_columns(df)
        lookback = self.params['lookback_days']
        candle_threshold = self.params['reference_candle_threshold']
        volume_ratio = self.params['volume_spike_ratio']

        # 거래량 이동평균 계산 (20일)
        volume_ma = df[cols['volume']].rolling(window=20, min_periods=5).mean()

        # 최근 lookback일 내에서 기준봉 찾기
        for i in range(-lookback, -2):  # 최근 2일은 제외 (조정 기간 필요)
            try:
                idx = len(df) + i
                open_price = df[cols['open']].iloc[i]
                close_price = df[cols['close']].iloc[i]
                high_price = df[cols['high']].iloc[i]
                low_price = df[cols['low']].iloc[i]
                volume = df[cols['volume']].iloc[i]

                # 상승률 계산
                change_rate = (close_price - open_price) / open_price

                # 거래량 비율 계산
                vol_ma = volume_ma.iloc[i]
                vol_ratio = volume / vol_ma if vol_ma > 0 else 0

                # 기준봉 조건: 상승률 5% 이상 + 거래량 3배 이상
                if change_rate >= candle_threshold and vol_ratio >= volume_ratio:
                    return (idx, {
                        'index': idx,
                        'open': open_price,
                        'high': high_price,
                        'low': low_price,
                        'close': close_price,
                        'volume': volume,
                        'change_rate': change_rate,
                        'volume_ratio': vol_ratio,
                        'body': close_price - open_price,
                    })
            except IndexError:
                continue

        return None

    def _check_consolidation(self, df: pd.DataFrame, ref_candle: Dict) -> bool:
        """
        기준봉 이후 조정(눌림) 확인

        조건:
        - 거래량 감소
        - 가격이 기준봉 고가를 넘지 않음
        - 가격이 기준봉 저가를 이탈하지 않음
        """
        cols = self._get_columns(df)
        ref_idx = ref_candle['index']
        ref_high = ref_candle['high']
        ref_low = ref_candle['low']

        # 기준봉 이후 데이터
        after_ref = df.iloc[ref_idx + 1:]

        if len(after_ref) < 2:
            return False

        # 거래량 감소 확인 (기준봉 대비 50% 이하)
        avg_vol_after = after_ref[cols['volume']].mean()
        vol_decreased = avg_vol_after < ref_candle['volume'] * 0.7

        # 가격이 기준봉 범위 내에서 조정
        highs_after = after_ref[cols['high']]
        lows_after = after_ref[cols['low']]

        price_in_range = (highs_after <= ref_high * 1.02).all() and \
                         (lows_after >= ref_low * 0.98).all()

        return vol_decreased and price_in_range

    def _check_breakout(self, df: pd.DataFrame, ref_candle: Dict) -> bool:
        """
        기준봉 고가 돌파 확인
        """
        cols = self._get_columns(df)
        current_close = df[cols['close']].iloc[-1]
        ref_high = ref_candle['high']
        threshold = self.params['breakout_threshold']

        # 현재 종가가 기준봉 고가 + 1% 이상
        return current_close > ref_high * (1 + threshold)

    def _check_ma_alignment(self, df: pd.DataFrame) -> bool:
        """
        이동평균선 정배열 확인 (5일 > 20일 > 60일)
        """
        cols = self._get_columns(df)

        if len(df) < 60:
            return True  # 데이터 부족시 조건 통과

        ma5 = calculate_sma(df, 5, cols['close'])
        ma20 = calculate_sma(df, 20, cols['close'])
        ma60 = calculate_sma(df, 60, cols['close'])

        # 현재 정배열 확인
        return ma5.iloc[-1] > ma20.iloc[-1] > ma60.iloc[-1]

    def _check_volume_increase(self, df: pd.DataFrame) -> bool:
        """
        돌파 시 거래량 증가 확인
        """
        cols = self._get_columns(df)

        if len(df) < 6:
            return False

        # 최근 5일 평균 거래량
        recent_avg = df[cols['volume']].iloc[-6:-1].mean()
        current_vol = df[cols['volume']].iloc[-1]

        # 오늘 거래량이 최근 평균의 1.5배 이상
        return current_vol > recent_avg * 1.5

    def check_buy_conditions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """매수 조건 확인"""
        conditions = {
            'reference_candle': False,
            'consolidation': False,
            'breakout': False,
            'ma_alignment': False,
            'volume_increase': False,
        }
        metadata = {}

        # 1. 기준봉 찾기
        result = self._find_reference_candle(df)
        if not result:
            return conditions

        ref_idx, ref_candle = result
        conditions['reference_candle'] = True
        metadata['reference_candle'] = ref_candle

        # 2. 조정 기간 확인
        conditions['consolidation'] = self._check_consolidation(df, ref_candle)

        # 3. 돌파 확인
        conditions['breakout'] = self._check_breakout(df, ref_candle)

        # 4. 이동평균선 정배열 확인
        conditions['ma_alignment'] = self._check_ma_alignment(df)

        # 5. 돌파 시 거래량 증가 확인
        conditions['volume_increase'] = self._check_volume_increase(df)

        return {**conditions, 'metadata': metadata}

    def generate_signal(self, df: pd.DataFrame, code: str = "",
                        name: str = "") -> Optional[Signal]:
        """
        매매 신호 생성

        Args:
            df: OHLCV DataFrame (일봉)
            code: 종목 코드
            name: 종목명

        Returns:
            Signal 또는 None
        """
        if len(df) < 20:  # 최소 데이터 필요
            return None

        # 매수 조건 확인
        result = self.check_buy_conditions(df)
        metadata = result.pop('metadata', {})

        # 핵심 조건 충족 확인
        core_conditions = ['reference_candle', 'consolidation', 'breakout']
        if not all(result[c] for c in core_conditions):
            return None

        # 보조 조건 중 하나 이상 충족
        aux_conditions = ['ma_alignment', 'volume_increase']
        if not any(result[c] for c in aux_conditions):
            return None

        cols = self._get_columns(df)
        entry_price = df[cols['close']].iloc[-1]

        # 기준봉 정보
        ref_candle = metadata.get('reference_candle', {})
        ref_low = ref_candle.get('low', entry_price * 0.95)
        ref_close = ref_candle.get('close', entry_price)
        ref_body = ref_candle.get('body', entry_price * 0.05)

        # 손절가: 기준봉 저가 또는 종가 -3%
        stop_loss = max(ref_low * 0.99, ref_close * 0.97)

        # 익절가: 기준봉 몸통의 1~2배 상승
        take_profit = entry_price + ref_body * 1.5

        # 신호 강도 계산
        strength = sum(result.values()) / len(result)

        return Signal(
            code=code,
            name=name,
            datetime=datetime.now(),
            signal_type=SignalType.BUY,
            strategy=self.name,
            price=entry_price,
            stop_loss=stop_loss,
            take_profit=take_profit,
            reason=self.get_signal_reason(result),
            strength=strength,
            metadata={
                'reference_candle': ref_candle,
                'conditions': result,
            }
        )

    def check_sell_conditions(self, df: pd.DataFrame,
                              entry_price: float = None,
                              ref_low: float = None,
                              ref_close: float = None) -> Dict[str, bool]:
        """
        매도/손절 조건 확인
        """
        cols = self._get_columns(df)
        current_price = df[cols['close']].iloc[-1]

        conditions = {}

        # 손절 1: 기준봉 저가 이탈
        if ref_low:
            conditions['ref_low_break'] = current_price < ref_low * 0.99

        # 손절 2: 기준봉 종가 -3% 이탈
        if ref_close:
            conditions['ref_close_break'] = current_price < ref_close * 0.97

        # 익절: 거래량 급증 후 음봉
        conditions['volume_spike_reversal'] = self._check_volume_spike_reversal(df)

        return conditions

    def _check_volume_spike_reversal(self, df: pd.DataFrame) -> bool:
        """거래량 급증 후 음봉 출현 확인"""
        cols = self._get_columns(df)

        if len(df) < 3:
            return False

        # 전일 거래량 급증 + 오늘 음봉
        volume_ma = df[cols['volume']].iloc[-20:-1].mean() if len(df) > 20 else \
                    df[cols['volume']].iloc[:-1].mean()

        prev_volume = df[cols['volume']].iloc[-2]
        vol_spike = prev_volume > volume_ma * 2

        today_open = df[cols['open']].iloc[-1]
        today_close = df[cols['close']].iloc[-1]
        is_bearish = today_close < today_open

        return vol_spike and is_bearish


# 전략 등록
register_strategy(BreakoutStrategy())
