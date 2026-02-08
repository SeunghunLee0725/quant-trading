"""
상한가 종가 지지 전략
PDF 기준: 상한가 후 3~5일 박스권 조정 → 돌파 매수
"""

import pandas as pd
import numpy as np
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SignalType, LimitUpStrategyParams
from strategies.base_strategy import BaseStrategy, Signal, register_strategy
from indicators import (
    find_box_range,
)


class LimitUpStrategy(BaseStrategy):
    """
    상한가 종가 지지 전략

    PDF 핵심 내용:
    "상한가 이후에 3~5거래일 동안 박스권의 모습으로 깃발 모양을 할 때"
    "상한가 종가를 지지하면서 자리를 만들어가는 추종해서 매수"

    매수 조건:
    1. 최근 5일 내 상한가 기록 (29% 이상 상승)
    2. 상한가 종가 부근 ±3% 지지 확인
    3. 3~5일간 박스권 횡보
    4. 거래량 감소 후 재증가 신호
    5. 박스권 상단 돌파

    손절 조건:
    - 상한가 종가선 -5% 이탈
    - 박스권 하단 이탈

    익절 조건:
    - 신고가 갱신 후 음봉 출현
    - 거래량 급감
    """

    def __init__(self, params: Dict[str, Any] = None):
        default_params = LimitUpStrategyParams()
        strategy_params = {
            'limit_up_threshold': default_params.limit_up_threshold,
            'lookback_days': default_params.lookback_days,
            'support_threshold': default_params.support_threshold,
            'consolidation_days_min': default_params.consolidation_days[0],
            'consolidation_days_max': default_params.consolidation_days[1],
            'support_break_threshold': default_params.support_break_threshold,
        }
        if params:
            strategy_params.update(params)

        super().__init__(name='limit_up', params=strategy_params)

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

    def _find_limit_up_day(self, df: pd.DataFrame) -> Optional[Tuple[int, float]]:
        """
        최근 상한가 기록 날짜 찾기

        Returns:
            (인덱스 위치, 상한가 종가) 또는 None
        """
        cols = self._get_columns(df)
        lookback = self.params['lookback_days']
        threshold = self.params['limit_up_threshold']

        # 최근 lookback일 확인
        for i in range(-lookback, 0):
            try:
                open_price = df[cols['open']].iloc[i]
                close_price = df[cols['close']].iloc[i]

                # 상승률 계산 (전일 종가 대비)
                if i > -len(df):
                    prev_close = df[cols['close']].iloc[i - 1]
                    change_rate = (close_price - prev_close) / prev_close
                else:
                    change_rate = (close_price - open_price) / open_price

                if change_rate >= threshold:
                    return (len(df) + i, close_price)  # 양수 인덱스와 종가 반환
            except IndexError:
                continue

        return None

    def _check_recent_limit_up(self, df: pd.DataFrame) -> Tuple[bool, Optional[float]]:
        """
        최근 상한가 기록 여부 확인

        Returns:
            (상한가 여부, 상한가 종가)
        """
        result = self._find_limit_up_day(df)
        if result:
            return True, result[1]
        return False, None

    def _check_price_support(self, df: pd.DataFrame, limit_up_close: float) -> bool:
        """
        상한가 종가 부근 지지 확인 (±3%)
        """
        cols = self._get_columns(df)
        threshold = self.params['support_threshold']

        # 최근 5일의 종가가 상한가 종가 ±3% 범위 내인지 확인
        for i in range(-5, 0):
            try:
                close = df[cols['close']].iloc[i]
                diff_ratio = abs(close - limit_up_close) / limit_up_close

                if diff_ratio > threshold:
                    return False
            except IndexError:
                continue

        return True

    def _check_consolidation(self, df: pd.DataFrame) -> Tuple[bool, Optional[Dict]]:
        """
        박스권 횡보 확인 (3~5일)

        Returns:
            (박스권 여부, 박스권 정보)
        """
        min_days = self.params['consolidation_days_min']
        max_days = self.params['consolidation_days_max']

        # 다양한 기간으로 박스권 확인
        for lookback in range(min_days, max_days + 1):
            box = find_box_range(df, lookback=lookback, variance=0.05)
            if box:
                return True, box

        return False, None

    def _check_volume_pattern(self, df: pd.DataFrame) -> bool:
        """
        거래량 패턴 확인 (감소 후 재증가)
        """
        cols = self._get_columns(df)

        # 최근 5일 거래량 추이
        recent_volumes = df[cols['volume']].iloc[-5:].values

        if len(recent_volumes) < 5:
            return False

        # 중간에 감소했다가 마지막에 증가하는 패턴
        mid_avg = np.mean(recent_volumes[1:4])
        first_vol = recent_volumes[0]
        last_vol = recent_volumes[-1]

        # 중간이 처음보다 낮고, 마지막이 중간보다 높으면 OK
        volume_decline = mid_avg < first_vol
        volume_increase = last_vol > mid_avg

        return volume_decline and volume_increase

    def _check_box_breakout(self, df: pd.DataFrame, box_high: float) -> bool:
        """
        박스권 상단 돌파 확인
        """
        cols = self._get_columns(df)
        current_close = df[cols['close']].iloc[-1]

        return current_close > box_high * 1.01  # 1% 여유

    def check_buy_conditions(self, df: pd.DataFrame) -> Dict[str, Any]:
        """매수 조건 확인"""
        conditions = {
            'recent_limit_up': False,
            'price_support': False,
            'consolidation': False,
            'volume_pattern': False,
            'box_breakout': False,
        }
        metadata = {}

        # 1. 최근 상한가 확인
        has_limit_up, limit_up_close = self._check_recent_limit_up(df)
        conditions['recent_limit_up'] = has_limit_up

        if not has_limit_up:
            return conditions

        metadata['limit_up_close'] = limit_up_close

        # 2. 상한가 종가 지지 확인
        conditions['price_support'] = self._check_price_support(df, limit_up_close)

        # 3. 박스권 횡보 확인
        is_consolidating, box_info = self._check_consolidation(df)
        conditions['consolidation'] = is_consolidating

        if box_info:
            metadata['box'] = box_info

        # 4. 거래량 패턴 확인
        conditions['volume_pattern'] = self._check_volume_pattern(df)

        # 5. 박스권 돌파 확인
        if box_info:
            conditions['box_breakout'] = self._check_box_breakout(df, box_info['high'])

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
        if len(df) < 10:  # 최소 데이터 필요
            return None

        # 매수 조건 확인
        result = self.check_buy_conditions(df)
        metadata = result.pop('metadata', {})

        # 핵심 조건 충족 확인
        core_conditions = ['recent_limit_up', 'price_support', 'consolidation']
        if not all(result[c] for c in core_conditions):
            return None

        # 박스권 돌파 또는 거래량 신호
        if not (result['box_breakout'] or result['volume_pattern']):
            return None

        cols = self._get_columns(df)
        entry_price = df[cols['close']].iloc[-1]

        # 손절가: 상한가 종가 -5% 또는 박스권 하단
        limit_up_close = metadata.get('limit_up_close', entry_price)
        box_info = metadata.get('box', {})
        box_low = box_info.get('low', limit_up_close * 0.95)

        stop_loss = max(
            limit_up_close * (1 - self.params['support_break_threshold']),
            box_low * 0.99
        )

        # 익절가: 상한가 종가 + 박스권 높이 (또는 15%)
        box_height = box_info.get('range', entry_price * 0.10)
        take_profit = entry_price + box_height

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
            strength=sum(result.values()) / len(result),
            metadata={
                'limit_up_close': limit_up_close,
                'box': box_info,
                'conditions': result,
            }
        )

    def check_sell_conditions(self, df: pd.DataFrame,
                              entry_price: float = None,
                              limit_up_close: float = None,
                              box_low: float = None) -> Dict[str, bool]:
        """
        매도/손절 조건 확인
        """
        cols = self._get_columns(df)
        current_price = df[cols['close']].iloc[-1]

        conditions = {}

        # 손절 1: 상한가 종가선 이탈
        if limit_up_close:
            support_break = limit_up_close * (1 - self.params['support_break_threshold'])
            conditions['limit_up_support_break'] = current_price < support_break

        # 손절 2: 박스권 하단 이탈
        if box_low:
            conditions['box_low_break'] = current_price < box_low * 0.99

        # 익절: 신고가 후 음봉
        conditions['new_high_reversal'] = self._check_new_high_reversal(df)

        return conditions

    def _check_new_high_reversal(self, df: pd.DataFrame) -> bool:
        """신고가 후 음봉 확인"""
        cols = self._get_columns(df)

        if len(df) < 2:
            return False

        # 전일이 신고가였고 오늘이 음봉
        prev_high = df[cols['high']].iloc[-2]
        max_high = df[cols['high']].iloc[:-2].max() if len(df) > 2 else prev_high

        is_prev_new_high = prev_high >= max_high
        is_today_bearish = df[cols['close']].iloc[-1] < df[cols['open']].iloc[-1]

        return is_prev_new_high and is_today_bearish


# 전략 등록
register_strategy(LimitUpStrategy())
