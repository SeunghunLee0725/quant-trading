"""
이동평균선 지표 모듈
PDF 기준: 5, 10, 20, 60, 120, 240일 이동평균선
"""

import pandas as pd
import numpy as np
from typing import Optional, List, Dict, Tuple, Union
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import MAPeriod, CrossSignal


def calculate_sma(data: Union[pd.Series, pd.DataFrame], period: int,
                  column: str = 'close') -> pd.Series:
    """
    단순이동평균(SMA) 계산

    Args:
        data: 가격 데이터 (Series 또는 DataFrame)
        period: 이동평균 기간
        column: DataFrame인 경우 사용할 컬럼명

    Returns:
        SMA Series
    """
    if isinstance(data, pd.DataFrame):
        # 컬럼명 대소문자 구분 없이 찾기
        col_lower = {c.lower(): c for c in data.columns}
        actual_col = col_lower.get(column.lower(), column)
        series = data[actual_col]
    else:
        series = data

    return series.rolling(window=period, min_periods=1).mean()


def calculate_ema(data: Union[pd.Series, pd.DataFrame], period: int,
                  column: str = 'close') -> pd.Series:
    """
    지수이동평균(EMA) 계산

    Args:
        data: 가격 데이터
        period: 이동평균 기간
        column: DataFrame인 경우 사용할 컬럼명

    Returns:
        EMA Series
    """
    if isinstance(data, pd.DataFrame):
        col_lower = {c.lower(): c for c in data.columns}
        actual_col = col_lower.get(column.lower(), column)
        series = data[actual_col]
    else:
        series = data

    return series.ewm(span=period, adjust=False).mean()


def calculate_wma(data: Union[pd.Series, pd.DataFrame], period: int,
                  column: str = 'close') -> pd.Series:
    """
    가중이동평균(WMA) 계산

    Args:
        data: 가격 데이터
        period: 이동평균 기간
        column: DataFrame인 경우 사용할 컬럼명

    Returns:
        WMA Series
    """
    if isinstance(data, pd.DataFrame):
        col_lower = {c.lower(): c for c in data.columns}
        actual_col = col_lower.get(column.lower(), column)
        series = data[actual_col]
    else:
        series = data

    weights = np.arange(1, period + 1)
    return series.rolling(window=period).apply(
        lambda x: np.dot(x, weights) / weights.sum(),
        raw=True
    )


def calculate_all_ma(df: pd.DataFrame, periods: List[int] = None,
                     ma_type: str = 'sma') -> pd.DataFrame:
    """
    모든 이동평균선 계산

    Args:
        df: OHLCV DataFrame
        periods: 이동평균 기간 리스트 (기본값: 5, 10, 20, 60, 120, 240)
        ma_type: 이동평균 타입 ('sma', 'ema')

    Returns:
        이동평균선이 추가된 DataFrame
    """
    if periods is None:
        periods = MAPeriod.ALL_PERIODS

    df = df.copy()
    ma_func = calculate_ema if ma_type.lower() == 'ema' else calculate_sma

    for period in periods:
        col_name = f'ma{period}'
        df[col_name] = ma_func(df, period)

    return df


def get_ma_values(df: pd.DataFrame, periods: List[int] = None) -> Dict[int, float]:
    """
    현재(마지막) 이동평균 값들 반환

    Args:
        df: 이동평균이 계산된 DataFrame
        periods: 조회할 기간 리스트

    Returns:
        {기간: 이동평균값} 딕셔너리
    """
    if periods is None:
        periods = MAPeriod.ALL_PERIODS

    result = {}
    for period in periods:
        col_name = f'ma{period}'
        if col_name in df.columns:
            result[period] = df[col_name].iloc[-1]

    return result


def get_ma_status(price: float, ma_values: Dict[int, float]) -> str:
    """
    이동평균선 정배열/역배열 상태 판단

    Args:
        price: 현재 가격
        ma_values: {기간: 이동평균값} 딕셔너리

    Returns:
        'BULLISH' (정배열), 'BEARISH' (역배열), 'MIXED' (혼조)
    """
    if not ma_values:
        return 'UNKNOWN'

    # 기간 순으로 정렬
    sorted_periods = sorted(ma_values.keys())
    values = [ma_values[p] for p in sorted_periods]

    # 정배열: 가격 > 단기MA > 장기MA
    is_bullish = (price >= values[0]) and all(
        values[i] >= values[i + 1] for i in range(len(values) - 1)
    )

    # 역배열: 가격 < 단기MA < 장기MA
    is_bearish = (price <= values[0]) and all(
        values[i] <= values[i + 1] for i in range(len(values) - 1)
    )

    if is_bullish:
        return 'BULLISH'
    elif is_bearish:
        return 'BEARISH'
    else:
        return 'MIXED'


def detect_golden_cross(ma_short: pd.Series, ma_long: pd.Series,
                        lookback: int = 1) -> pd.Series:
    """
    골든크로스 감지 (단기MA가 장기MA를 상향 돌파)

    Args:
        ma_short: 단기 이동평균 Series
        ma_long: 장기 이동평균 Series
        lookback: 확인할 과거 기간

    Returns:
        골든크로스 발생 여부 Boolean Series
    """
    # 현재: 단기 > 장기, 이전: 단기 <= 장기
    current_above = ma_short > ma_long
    previous_below = ma_short.shift(lookback) <= ma_long.shift(lookback)

    return current_above & previous_below


def detect_dead_cross(ma_short: pd.Series, ma_long: pd.Series,
                      lookback: int = 1) -> pd.Series:
    """
    데드크로스 감지 (단기MA가 장기MA를 하향 돌파)

    Args:
        ma_short: 단기 이동평균 Series
        ma_long: 장기 이동평균 Series
        lookback: 확인할 과거 기간

    Returns:
        데드크로스 발생 여부 Boolean Series
    """
    # 현재: 단기 < 장기, 이전: 단기 >= 장기
    current_below = ma_short < ma_long
    previous_above = ma_short.shift(lookback) >= ma_long.shift(lookback)

    return current_below & previous_above


def detect_all_crosses(df: pd.DataFrame,
                       pairs: List[Tuple[int, int]] = None) -> pd.DataFrame:
    """
    모든 크로스 신호 감지

    Args:
        df: 이동평균이 계산된 DataFrame
        pairs: (단기MA 기간, 장기MA 기간) 튜플 리스트

    Returns:
        크로스 신호가 추가된 DataFrame
    """
    if pairs is None:
        pairs = CrossSignal.CROSS_PAIRS

    df = df.copy()

    for short_period, long_period in pairs:
        short_col = f'ma{short_period}'
        long_col = f'ma{long_period}'

        if short_col not in df.columns or long_col not in df.columns:
            continue

        golden_col = f'golden_cross_{short_period}_{long_period}'
        dead_col = f'dead_cross_{short_period}_{long_period}'

        df[golden_col] = detect_golden_cross(df[short_col], df[long_col])
        df[dead_col] = detect_dead_cross(df[short_col], df[long_col])

    return df


def calculate_ma_divergence(price: Union[pd.Series, float],
                            ma: Union[pd.Series, float]) -> Union[pd.Series, float]:
    """
    이격도 계산 ((가격 - MA) / MA * 100)

    Args:
        price: 현재 가격 또는 가격 Series
        ma: 이동평균 값 또는 Series

    Returns:
        이격도 (%) - 양수면 MA 위, 음수면 MA 아래
    """
    return (price - ma) / ma * 100


def is_price_above_ma(df: pd.DataFrame, period: int) -> pd.Series:
    """가격이 특정 이동평균 위에 있는지 확인"""
    col_lower = {c.lower(): c for c in df.columns}
    close_col = col_lower.get('close', 'Close')
    ma_col = f'ma{period}'

    if ma_col not in df.columns:
        df = calculate_all_ma(df, [period])

    return df[close_col] > df[ma_col]


def is_price_below_ma(df: pd.DataFrame, period: int) -> pd.Series:
    """가격이 특정 이동평균 아래에 있는지 확인"""
    return ~is_price_above_ma(df, period)


def get_ma_support_resistance(df: pd.DataFrame, periods: List[int] = None,
                              threshold: float = 0.02) -> Dict[str, List[float]]:
    """
    현재가 기준 지지/저항 역할을 하는 이동평균선 찾기

    Args:
        df: 이동평균이 계산된 DataFrame
        periods: 확인할 기간 리스트
        threshold: 근접 판단 임계값 (%)

    Returns:
        {'support': [지지 MA값들], 'resistance': [저항 MA값들]}
    """
    if periods is None:
        periods = MAPeriod.ALL_PERIODS

    col_lower = {c.lower(): c for c in df.columns}
    close_col = col_lower.get('close', 'Close')
    current_price = df[close_col].iloc[-1]

    result = {'support': [], 'resistance': []}

    for period in periods:
        ma_col = f'ma{period}'
        if ma_col not in df.columns:
            continue

        ma_value = df[ma_col].iloc[-1]
        diff_ratio = (current_price - ma_value) / ma_value

        if abs(diff_ratio) <= threshold:
            # 근접한 경우
            if diff_ratio > 0:
                result['support'].append(ma_value)
            else:
                result['resistance'].append(ma_value)
        elif diff_ratio > threshold:
            # 가격이 MA 위에 있음 → MA는 지지선
            result['support'].append(ma_value)
        else:
            # 가격이 MA 아래에 있음 → MA는 저항선
            result['resistance'].append(ma_value)

    return result


def check_ma_alignment(df: pd.DataFrame, periods: List[int] = None,
                       ascending: bool = True) -> bool:
    """
    이동평균선 정렬 상태 확인

    Args:
        df: 이동평균이 계산된 DataFrame
        periods: 확인할 기간 리스트 (짧은 순)
        ascending: True면 정배열(단기>장기), False면 역배열

    Returns:
        정렬 여부
    """
    if periods is None:
        periods = [5, 20, 60]

    values = []
    for period in periods:
        ma_col = f'ma{period}'
        if ma_col not in df.columns:
            return False
        values.append(df[ma_col].iloc[-1])

    if ascending:
        # 정배열: 단기 > 장기 순
        return all(values[i] > values[i + 1] for i in range(len(values) - 1))
    else:
        # 역배열: 단기 < 장기 순
        return all(values[i] < values[i + 1] for i in range(len(values) - 1))
