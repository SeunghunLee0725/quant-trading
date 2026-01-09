"""
종목 필터 모듈
PDF 기준: 거래량, 시가총액, 이동평균 등 기본 필터
"""

import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass, field
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@dataclass
class FilterResult:
    """필터 결과"""
    code: str
    name: str
    passed: bool
    filter_name: str
    value: Any = None
    threshold: Any = None
    reason: str = ""


@dataclass
class StockFilter:
    """기본 필터 클래스"""
    name: str
    description: str
    filter_func: Callable
    params: Dict[str, Any] = field(default_factory=dict)

    def apply(self, df: pd.DataFrame, code: str = "", name: str = "") -> FilterResult:
        """필터 적용"""
        try:
            passed, value, threshold = self.filter_func(df, **self.params)
            return FilterResult(
                code=code,
                name=name,
                passed=passed,
                filter_name=self.name,
                value=value,
                threshold=threshold,
                reason=f"{self.name}: {value} vs {threshold}"
            )
        except Exception as e:
            return FilterResult(
                code=code,
                name=name,
                passed=False,
                filter_name=self.name,
                reason=f"Error: {str(e)}"
            )


def _get_columns(df: pd.DataFrame) -> Dict[str, str]:
    """컬럼명 매핑"""
    col_lower = {c.lower(): c for c in df.columns}
    return {
        'open': col_lower.get('open', 'Open'),
        'high': col_lower.get('high', 'High'),
        'low': col_lower.get('low', 'Low'),
        'close': col_lower.get('close', 'Close'),
        'volume': col_lower.get('volume', 'Volume'),
    }


# ============ 거래량 필터 ============

def filter_min_volume(df: pd.DataFrame, min_volume: int = 100000,
                      days: int = 5) -> tuple:
    """
    최소 거래량 필터

    Args:
        df: OHLCV DataFrame
        min_volume: 최소 거래량
        days: 평균 계산 기간

    Returns:
        (통과 여부, 평균 거래량, 기준)
    """
    cols = _get_columns(df)
    avg_volume = df[cols['volume']].iloc[-days:].mean()
    return avg_volume >= min_volume, int(avg_volume), min_volume


def filter_volume_spike(df: pd.DataFrame, spike_ratio: float = 2.0,
                        lookback: int = 20) -> tuple:
    """
    거래량 급증 필터

    Args:
        df: OHLCV DataFrame
        spike_ratio: 거래량 배수 기준
        lookback: 평균 계산 기간

    Returns:
        (통과 여부, 거래량 비율, 기준)
    """
    cols = _get_columns(df)
    current_vol = df[cols['volume']].iloc[-1]
    avg_vol = df[cols['volume']].iloc[-lookback:-1].mean()

    if avg_vol == 0:
        return False, 0, spike_ratio

    ratio = current_vol / avg_vol
    return ratio >= spike_ratio, round(ratio, 2), spike_ratio


def filter_volume_increase(df: pd.DataFrame, increase_days: int = 3) -> tuple:
    """
    거래량 증가 추세 필터

    Args:
        df: OHLCV DataFrame
        increase_days: 연속 증가 일수

    Returns:
        (통과 여부, 연속 증가 일수, 기준)
    """
    cols = _get_columns(df)
    volumes = df[cols['volume']].iloc[-increase_days - 1:].values

    if len(volumes) < increase_days + 1:
        return False, 0, increase_days

    # 연속 증가 확인
    consecutive = 0
    for i in range(1, len(volumes)):
        if volumes[i] > volumes[i - 1]:
            consecutive += 1
        else:
            consecutive = 0

    return consecutive >= increase_days, consecutive, increase_days


# ============ 가격 필터 ============

def filter_price_range(df: pd.DataFrame, min_price: int = 1000,
                       max_price: int = 500000) -> tuple:
    """
    가격 범위 필터

    Args:
        df: OHLCV DataFrame
        min_price: 최소 가격
        max_price: 최대 가격

    Returns:
        (통과 여부, 현재가, 범위)
    """
    cols = _get_columns(df)
    current_price = df[cols['close']].iloc[-1]
    passed = min_price <= current_price <= max_price
    return passed, int(current_price), f"{min_price}~{max_price}"


def filter_price_above_ma(df: pd.DataFrame, period: int = 20) -> tuple:
    """
    이동평균선 위 필터

    Args:
        df: OHLCV DataFrame
        period: 이동평균 기간

    Returns:
        (통과 여부, 현재가, MA)
    """
    cols = _get_columns(df)
    ma = df[cols['close']].rolling(window=period).mean()

    if pd.isna(ma.iloc[-1]):
        return False, 0, 0

    current_price = df[cols['close']].iloc[-1]
    ma_value = ma.iloc[-1]
    return current_price > ma_value, round(current_price, 0), round(ma_value, 0)


def filter_price_change(df: pd.DataFrame, min_change: float = -0.05,
                        max_change: float = 0.05) -> tuple:
    """
    가격 변동률 필터

    Args:
        df: OHLCV DataFrame
        min_change: 최소 변동률
        max_change: 최대 변동률

    Returns:
        (통과 여부, 변동률, 범위)
    """
    cols = _get_columns(df)

    if len(df) < 2:
        return False, 0, f"{min_change}~{max_change}"

    current_close = df[cols['close']].iloc[-1]
    prev_close = df[cols['close']].iloc[-2]

    change_rate = (current_close - prev_close) / prev_close
    passed = min_change <= change_rate <= max_change

    return passed, round(change_rate * 100, 2), f"{min_change * 100}%~{max_change * 100}%"


def filter_positive_change(df: pd.DataFrame, days: int = 1) -> tuple:
    """
    양봉(상승) 필터

    Args:
        df: OHLCV DataFrame
        days: 연속 양봉 일수

    Returns:
        (통과 여부, 연속 양봉 수, 기준)
    """
    cols = _get_columns(df)

    if len(df) < days:
        return False, 0, days

    consecutive = 0
    for i in range(-days, 0):
        close = df[cols['close']].iloc[i]
        open_price = df[cols['open']].iloc[i]
        if close > open_price:
            consecutive += 1
        else:
            break

    return consecutive >= days, consecutive, days


# ============ 이동평균 정배열 필터 ============

def filter_ma_alignment(df: pd.DataFrame, periods: List[int] = None,
                        ascending: bool = True) -> tuple:
    """
    이동평균선 정배열/역배열 필터

    Args:
        df: OHLCV DataFrame
        periods: 이동평균 기간 리스트
        ascending: True=정배열, False=역배열

    Returns:
        (통과 여부, MA 값들, 상태)
    """
    if periods is None:
        periods = [5, 20, 60]

    cols = _get_columns(df)
    ma_values = []

    for period in periods:
        ma = df[cols['close']].rolling(window=period).mean()
        if pd.isna(ma.iloc[-1]):
            return False, [], "정배열" if ascending else "역배열"
        ma_values.append(round(ma.iloc[-1], 0))

    if ascending:
        # 정배열: 단기 > 장기
        passed = all(ma_values[i] > ma_values[i + 1] for i in range(len(ma_values) - 1))
        status = "정배열"
    else:
        # 역배열: 단기 < 장기
        passed = all(ma_values[i] < ma_values[i + 1] for i in range(len(ma_values) - 1))
        status = "역배열"

    return passed, ma_values, status


# ============ 박스권 필터 ============

def filter_box_range(df: pd.DataFrame, lookback: int = 10,
                     variance: float = 0.05) -> tuple:
    """
    박스권 횡보 필터

    Args:
        df: OHLCV DataFrame
        lookback: 확인 기간
        variance: 허용 변동폭

    Returns:
        (통과 여부, 변동폭, 기준)
    """
    cols = _get_columns(df)

    if len(df) < lookback:
        return False, 0, variance

    recent = df.iloc[-lookback:]
    high = recent[cols['high']].max()
    low = recent[cols['low']].min()

    if low == 0:
        return False, 0, variance

    actual_variance = (high - low) / low
    passed = actual_variance <= variance

    return passed, round(actual_variance * 100, 2), f"{variance * 100}%"


def filter_near_52week_high(df: pd.DataFrame, threshold: float = 0.05) -> tuple:
    """
    52주 신고가 근접 필터

    Args:
        df: OHLCV DataFrame (최소 252일)
        threshold: 신고가 대비 임계값

    Returns:
        (통과 여부, 현재가/신고가 비율, 기준)
    """
    cols = _get_columns(df)
    lookback = min(252, len(df))

    high_52w = df[cols['high']].iloc[-lookback:].max()
    current_price = df[cols['close']].iloc[-1]

    if high_52w == 0:
        return False, 0, threshold

    ratio = current_price / high_52w
    passed = ratio >= (1 - threshold)

    return passed, round(ratio * 100, 2), f"{(1 - threshold) * 100}%"


def filter_near_52week_low(df: pd.DataFrame, threshold: float = 0.10) -> tuple:
    """
    52주 신저가 근접 필터

    Args:
        df: OHLCV DataFrame
        threshold: 신저가 대비 임계값

    Returns:
        (통과 여부, 현재가/신저가 비율, 기준)
    """
    cols = _get_columns(df)
    lookback = min(252, len(df))

    low_52w = df[cols['low']].iloc[-lookback:].min()
    current_price = df[cols['close']].iloc[-1]

    if low_52w == 0:
        return False, 0, threshold

    ratio = current_price / low_52w
    passed = ratio <= (1 + threshold)

    return passed, round(ratio * 100, 2), f"{(1 + threshold) * 100}%"


# ============ 캔들 패턴 필터 ============

def filter_long_candle(df: pd.DataFrame, threshold: float = 0.05) -> tuple:
    """
    장대양봉/장대음봉 필터

    Args:
        df: OHLCV DataFrame
        threshold: 몸통 크기 임계값

    Returns:
        (통과 여부, 몸통 크기, 기준)
    """
    cols = _get_columns(df)

    open_price = df[cols['open']].iloc[-1]
    close_price = df[cols['close']].iloc[-1]

    if open_price == 0:
        return False, 0, threshold

    body_ratio = abs(close_price - open_price) / open_price
    passed = body_ratio >= threshold

    return passed, round(body_ratio * 100, 2), f"{threshold * 100}%"


def filter_bullish_candle(df: pd.DataFrame) -> tuple:
    """
    양봉 필터

    Returns:
        (통과 여부, 종가-시가, "양봉")
    """
    cols = _get_columns(df)
    open_price = df[cols['open']].iloc[-1]
    close_price = df[cols['close']].iloc[-1]

    passed = close_price > open_price
    diff = close_price - open_price

    return passed, int(diff), "양봉"


# ============ 필터 팩토리 ============

class FilterFactory:
    """필터 생성 팩토리"""

    AVAILABLE_FILTERS = {
        'min_volume': (filter_min_volume, "최소 거래량 필터"),
        'volume_spike': (filter_volume_spike, "거래량 급증 필터"),
        'volume_increase': (filter_volume_increase, "거래량 증가 추세 필터"),
        'price_range': (filter_price_range, "가격 범위 필터"),
        'price_above_ma': (filter_price_above_ma, "이동평균 위 필터"),
        'price_change': (filter_price_change, "가격 변동률 필터"),
        'positive_change': (filter_positive_change, "양봉 필터"),
        'ma_alignment': (filter_ma_alignment, "이동평균 정배열 필터"),
        'box_range': (filter_box_range, "박스권 필터"),
        'near_52week_high': (filter_near_52week_high, "52주 신고가 근접 필터"),
        'near_52week_low': (filter_near_52week_low, "52주 신저가 근접 필터"),
        'long_candle': (filter_long_candle, "장대 캔들 필터"),
        'bullish_candle': (filter_bullish_candle, "양봉 필터"),
    }

    @classmethod
    def create(cls, filter_name: str, **params) -> Optional[StockFilter]:
        """필터 생성"""
        if filter_name not in cls.AVAILABLE_FILTERS:
            return None

        filter_func, description = cls.AVAILABLE_FILTERS[filter_name]
        return StockFilter(
            name=filter_name,
            description=description,
            filter_func=filter_func,
            params=params
        )

    @classmethod
    def create_preset(cls, preset_name: str) -> List[StockFilter]:
        """
        프리셋 필터 세트 생성

        Args:
            preset_name: 'default', 'aggressive', 'conservative', 'volume_focus'

        Returns:
            필터 리스트
        """
        presets = {
            'default': [
                ('min_volume', {'min_volume': 100000}),
                ('price_range', {'min_price': 1000, 'max_price': 500000}),
                ('price_above_ma', {'period': 20}),
            ],
            'aggressive': [
                ('min_volume', {'min_volume': 500000}),
                ('volume_spike', {'spike_ratio': 2.0}),
                ('price_range', {'min_price': 3000, 'max_price': 100000}),
                ('ma_alignment', {'periods': [5, 20, 60], 'ascending': True}),
            ],
            'conservative': [
                ('min_volume', {'min_volume': 50000}),
                ('price_range', {'min_price': 5000, 'max_price': 200000}),
                ('price_above_ma', {'period': 60}),
                ('box_range', {'lookback': 20, 'variance': 0.10}),
            ],
            'volume_focus': [
                ('min_volume', {'min_volume': 1000000}),
                ('volume_spike', {'spike_ratio': 3.0}),
                ('volume_increase', {'increase_days': 2}),
            ],
            'breakout': [
                ('min_volume', {'min_volume': 200000}),
                ('volume_spike', {'spike_ratio': 2.5}),
                ('near_52week_high', {'threshold': 0.10}),
                ('ma_alignment', {'periods': [5, 20], 'ascending': True}),
            ],
        }

        if preset_name not in presets:
            preset_name = 'default'

        filters = []
        for filter_name, params in presets[preset_name]:
            f = cls.create(filter_name, **params)
            if f:
                filters.append(f)

        return filters

    @classmethod
    def list_filters(cls) -> Dict[str, str]:
        """사용 가능한 필터 목록"""
        return {name: desc for name, (_, desc) in cls.AVAILABLE_FILTERS.items()}
