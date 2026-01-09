"""
캔들 패턴 인식 모듈
PDF 기준: 망치형, 역망치형, 장대양봉/음봉, 도지, 잉컬핑 등
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List, Tuple, Union
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import CandleThreshold


def get_ohlc_columns(df: pd.DataFrame) -> Dict[str, str]:
    """DataFrame에서 OHLC 컬럼명 찾기"""
    col_lower = {c.lower(): c for c in df.columns}
    return {
        'open': col_lower.get('open', 'Open'),
        'high': col_lower.get('high', 'High'),
        'low': col_lower.get('low', 'Low'),
        'close': col_lower.get('close', 'Close'),
    }


# =========================================================
# 기본 캔들 계산 함수
# =========================================================

def calculate_candle_body(open_price: Union[pd.Series, float],
                          close_price: Union[pd.Series, float]) -> Union[pd.Series, float]:
    """
    캔들 몸통 크기 계산 (절대값)

    Args:
        open_price: 시가
        close_price: 종가

    Returns:
        몸통 크기
    """
    return abs(close_price - open_price)


def calculate_candle_body_ratio(df: pd.DataFrame) -> pd.Series:
    """
    캔들 몸통 비율 계산 (몸통 / 전체 범위)

    Args:
        df: OHLCV DataFrame

    Returns:
        몸통 비율 Series
    """
    cols = get_ohlc_columns(df)
    body = calculate_candle_body(df[cols['open']], df[cols['close']])
    candle_range = df[cols['high']] - df[cols['low']]
    return body / candle_range.replace(0, np.nan)


def calculate_upper_shadow(df: pd.DataFrame) -> pd.Series:
    """
    윗꼬리 크기 계산

    Args:
        df: OHLCV DataFrame

    Returns:
        윗꼬리 크기 Series
    """
    cols = get_ohlc_columns(df)
    body_high = df[[cols['open'], cols['close']]].max(axis=1)
    return df[cols['high']] - body_high


def calculate_lower_shadow(df: pd.DataFrame) -> pd.Series:
    """
    아랫꼬리 크기 계산

    Args:
        df: OHLCV DataFrame

    Returns:
        아랫꼬리 크기 Series
    """
    cols = get_ohlc_columns(df)
    body_low = df[[cols['open'], cols['close']]].min(axis=1)
    return body_low - df[cols['low']]


def calculate_candle_range(df: pd.DataFrame) -> pd.Series:
    """
    캔들 전체 범위 (고가 - 저가)

    Args:
        df: OHLCV DataFrame

    Returns:
        캔들 범위 Series
    """
    cols = get_ohlc_columns(df)
    return df[cols['high']] - df[cols['low']]


def calculate_change_rate(df: pd.DataFrame) -> pd.Series:
    """
    캔들 변화율 계산 ((종가-시가)/시가)

    Args:
        df: OHLCV DataFrame

    Returns:
        변화율 Series
    """
    cols = get_ohlc_columns(df)
    return (df[cols['close']] - df[cols['open']]) / df[cols['open']]


def is_bullish(df: pd.DataFrame) -> pd.Series:
    """
    양봉 여부 (종가 > 시가)

    Args:
        df: OHLCV DataFrame

    Returns:
        양봉 여부 Boolean Series
    """
    cols = get_ohlc_columns(df)
    return df[cols['close']] > df[cols['open']]


def is_bearish(df: pd.DataFrame) -> pd.Series:
    """
    음봉 여부 (종가 < 시가)

    Args:
        df: OHLCV DataFrame

    Returns:
        음봉 여부 Boolean Series
    """
    cols = get_ohlc_columns(df)
    return df[cols['close']] < df[cols['open']]


# =========================================================
# 단일 캔들 패턴
# =========================================================

def detect_long_bullish_candle(df: pd.DataFrame, threshold: float = None) -> pd.Series:
    """
    장대양봉 감지 (PDF: 5% 이상 상승)

    Args:
        df: OHLCV DataFrame
        threshold: 상승률 임계값 (기본값: 5%)

    Returns:
        장대양봉 여부 Boolean Series
    """
    if threshold is None:
        threshold = CandleThreshold.LONG_CANDLE_RATIO

    change = calculate_change_rate(df)
    return change >= threshold


def detect_long_bearish_candle(df: pd.DataFrame, threshold: float = None) -> pd.Series:
    """
    장대음봉 감지 (PDF: 5% 이상 하락)

    Args:
        df: OHLCV DataFrame
        threshold: 하락률 임계값 (기본값: 5%)

    Returns:
        장대음봉 여부 Boolean Series
    """
    if threshold is None:
        threshold = CandleThreshold.LONG_CANDLE_RATIO

    change = calculate_change_rate(df)
    return change <= -threshold


def detect_doji(df: pd.DataFrame, threshold: float = None) -> pd.Series:
    """
    도지 캔들 감지 (시가와 종가가 거의 같음)

    Args:
        df: OHLCV DataFrame
        threshold: 몸통 비율 임계값 (기본값: 1%)

    Returns:
        도지 여부 Boolean Series
    """
    if threshold is None:
        threshold = CandleThreshold.DOJI_BODY_RATIO

    body_ratio = calculate_candle_body_ratio(df)
    return body_ratio <= threshold


def detect_hammer(df: pd.DataFrame, body_ratio: float = 0.3,
                  shadow_ratio: float = None) -> pd.Series:
    """
    망치형 캔들 감지 (PDF: 아랫꼬리가 몸통의 2~3배)

    Args:
        df: OHLCV DataFrame
        body_ratio: 몸통이 전체의 몇 % 이하
        shadow_ratio: 아랫꼬리/몸통 비율 임계값

    Returns:
        망치형 여부 Boolean Series
    """
    if shadow_ratio is None:
        shadow_ratio = CandleThreshold.HAMMER_SHADOW_RATIO

    cols = get_ohlc_columns(df)
    body = calculate_candle_body(df[cols['open']], df[cols['close']])
    lower_shadow = calculate_lower_shadow(df)
    upper_shadow = calculate_upper_shadow(df)
    candle_range = calculate_candle_range(df)

    # 조건: 아랫꼬리가 몸통의 N배 이상, 윗꼬리가 작음, 몸통이 작음
    is_hammer = (
        (lower_shadow >= body * shadow_ratio) &
        (upper_shadow <= body * 0.5) &
        (body <= candle_range * body_ratio) &
        (candle_range > 0)
    )

    return is_hammer


def detect_inverted_hammer(df: pd.DataFrame, body_ratio: float = 0.3,
                           shadow_ratio: float = None) -> pd.Series:
    """
    역망치형 캔들 감지 (PDF: 윗꼬리가 몸통의 2~3배)

    Args:
        df: OHLCV DataFrame
        body_ratio: 몸통이 전체의 몇 % 이하
        shadow_ratio: 윗꼬리/몸통 비율 임계값

    Returns:
        역망치형 여부 Boolean Series
    """
    if shadow_ratio is None:
        shadow_ratio = CandleThreshold.HAMMER_SHADOW_RATIO

    cols = get_ohlc_columns(df)
    body = calculate_candle_body(df[cols['open']], df[cols['close']])
    lower_shadow = calculate_lower_shadow(df)
    upper_shadow = calculate_upper_shadow(df)
    candle_range = calculate_candle_range(df)

    # 조건: 윗꼬리가 몸통의 N배 이상, 아랫꼬리가 작음
    is_inverted = (
        (upper_shadow >= body * shadow_ratio) &
        (lower_shadow <= body * 0.5) &
        (body <= candle_range * body_ratio) &
        (candle_range > 0)
    )

    return is_inverted


def detect_spinning_top(df: pd.DataFrame, body_ratio: float = 0.3) -> pd.Series:
    """
    팽이형 캔들 감지 (몸통이 작고 양쪽 꼬리가 비슷)

    Args:
        df: OHLCV DataFrame
        body_ratio: 몸통이 전체의 몇 % 이하

    Returns:
        팽이형 여부 Boolean Series
    """
    body_pct = calculate_candle_body_ratio(df)
    lower_shadow = calculate_lower_shadow(df)
    upper_shadow = calculate_upper_shadow(df)

    # 양쪽 꼬리 비율이 비슷한지 확인
    shadow_ratio = np.minimum(lower_shadow, upper_shadow) / np.maximum(lower_shadow, upper_shadow).replace(0, np.nan)

    return (body_pct <= body_ratio) & (shadow_ratio >= 0.5)


# =========================================================
# 복합 캔들 패턴
# =========================================================

def detect_engulfing_bullish(df: pd.DataFrame) -> pd.Series:
    """
    상승 잉컬핑 감지 (PDF: 이전 음봉을 감싸는 양봉)

    Args:
        df: OHLCV DataFrame

    Returns:
        상승 잉컬핑 여부 Boolean Series
    """
    cols = get_ohlc_columns(df)

    # 현재 캔들
    curr_open = df[cols['open']]
    curr_close = df[cols['close']]
    curr_bullish = is_bullish(df)

    # 이전 캔들
    prev_open = df[cols['open']].shift(1)
    prev_close = df[cols['close']].shift(1)
    prev_bearish = is_bearish(df).shift(1)

    # 조건: 이전이 음봉, 현재가 양봉이고 이전 몸통을 완전히 감쌈
    engulfing = (
        prev_bearish &
        curr_bullish &
        (curr_open <= prev_close) &
        (curr_close >= prev_open)
    )

    return engulfing.fillna(False)


def detect_engulfing_bearish(df: pd.DataFrame) -> pd.Series:
    """
    하락 잉컬핑 감지 (PDF: 이전 양봉을 감싸는 음봉)

    Args:
        df: OHLCV DataFrame

    Returns:
        하락 잉컬핑 여부 Boolean Series
    """
    cols = get_ohlc_columns(df)

    # 현재 캔들
    curr_open = df[cols['open']]
    curr_close = df[cols['close']]
    curr_bearish = is_bearish(df)

    # 이전 캔들
    prev_open = df[cols['open']].shift(1)
    prev_close = df[cols['close']].shift(1)
    prev_bullish = is_bullish(df).shift(1)

    # 조건: 이전이 양봉, 현재가 음봉이고 이전 몸통을 완전히 감쌈
    engulfing = (
        prev_bullish &
        curr_bearish &
        (curr_open >= prev_close) &
        (curr_close <= prev_open)
    )

    return engulfing.fillna(False)


def detect_morning_star(df: pd.DataFrame) -> pd.Series:
    """
    모닝스타 패턴 감지 (3캔들 상승 반전 패턴)

    Args:
        df: OHLCV DataFrame

    Returns:
        모닝스타 여부 Boolean Series
    """
    cols = get_ohlc_columns(df)

    # 3일 전: 장대음봉
    day1_bearish = detect_long_bearish_candle(df).shift(2)

    # 2일 전: 작은 몸통 (도지 또는 팽이)
    day2_small = (calculate_candle_body_ratio(df) <= 0.3).shift(1)

    # 현재: 장대양봉
    day3_bullish = detect_long_bullish_candle(df)

    # 추가 조건: 2일차가 1일차 몸통 아래에서 시작
    day2_gap_down = (df[cols['open']].shift(1) < df[cols['close']].shift(2))

    return (day1_bearish & day2_small & day3_bullish & day2_gap_down).fillna(False)


def detect_evening_star(df: pd.DataFrame) -> pd.Series:
    """
    이브닝스타 패턴 감지 (3캔들 하락 반전 패턴)

    Args:
        df: OHLCV DataFrame

    Returns:
        이브닝스타 여부 Boolean Series
    """
    cols = get_ohlc_columns(df)

    # 3일 전: 장대양봉
    day1_bullish = detect_long_bullish_candle(df).shift(2)

    # 2일 전: 작은 몸통
    day2_small = (calculate_candle_body_ratio(df) <= 0.3).shift(1)

    # 현재: 장대음봉
    day3_bearish = detect_long_bearish_candle(df)

    # 추가 조건: 2일차가 1일차 몸통 위에서 시작
    day2_gap_up = (df[cols['open']].shift(1) > df[cols['close']].shift(2))

    return (day1_bullish & day2_small & day3_bearish & day2_gap_up).fillna(False)


# =========================================================
# 캔들 지지/저항 레벨
# =========================================================

def get_candle_support_level(df: pd.DataFrame, index: int = -1) -> float:
    """
    특정 캔들의 지지 레벨 반환 (캔들 저가 또는 몸통 하단)

    Args:
        df: OHLCV DataFrame
        index: 캔들 인덱스 (기본값: -1, 마지막 캔들)

    Returns:
        지지 레벨 가격
    """
    cols = get_ohlc_columns(df)
    return df[cols['low']].iloc[index]


def get_candle_resistance_level(df: pd.DataFrame, index: int = -1) -> float:
    """
    특정 캔들의 저항 레벨 반환 (캔들 고가)

    Args:
        df: OHLCV DataFrame
        index: 캔들 인덱스

    Returns:
        저항 레벨 가격
    """
    cols = get_ohlc_columns(df)
    return df[cols['high']].iloc[index]


def get_candle_50_percent_level(df: pd.DataFrame, index: int = -1) -> float:
    """
    캔들 몸통 50% 지점 반환 (PDF 15분봉 전략 기준)

    Args:
        df: OHLCV DataFrame
        index: 캔들 인덱스

    Returns:
        50% 레벨 가격
    """
    cols = get_ohlc_columns(df)
    open_price = df[cols['open']].iloc[index]
    close_price = df[cols['close']].iloc[index]
    return (open_price + close_price) / 2


# =========================================================
# 통합 패턴 분석
# =========================================================

def analyze_candle_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    모든 캔들 패턴 분석

    Args:
        df: OHLCV DataFrame

    Returns:
        패턴 분석 결과가 추가된 DataFrame
    """
    df = df.copy()

    # 기본 정보
    df['is_bullish'] = is_bullish(df)
    df['is_bearish'] = is_bearish(df)
    df['change_rate'] = calculate_change_rate(df)
    df['body_ratio'] = calculate_candle_body_ratio(df)

    # 단일 패턴
    df['long_bullish'] = detect_long_bullish_candle(df)
    df['long_bearish'] = detect_long_bearish_candle(df)
    df['doji'] = detect_doji(df)
    df['hammer'] = detect_hammer(df)
    df['inverted_hammer'] = detect_inverted_hammer(df)
    df['spinning_top'] = detect_spinning_top(df)

    # 복합 패턴
    df['engulfing_bullish'] = detect_engulfing_bullish(df)
    df['engulfing_bearish'] = detect_engulfing_bearish(df)
    df['morning_star'] = detect_morning_star(df)
    df['evening_star'] = detect_evening_star(df)

    return df


def get_pattern_signal(df: pd.DataFrame) -> str:
    """
    현재(마지막) 캔들의 패턴 신호 반환

    Args:
        df: 패턴 분석된 DataFrame

    Returns:
        'BULLISH', 'BEARISH', 'NEUTRAL'
    """
    df = analyze_candle_patterns(df)
    last = df.iloc[-1]

    # 상승 신호 패턴
    bullish_patterns = ['long_bullish', 'hammer', 'engulfing_bullish', 'morning_star']
    if any(last.get(p, False) for p in bullish_patterns):
        return 'BULLISH'

    # 하락 신호 패턴
    bearish_patterns = ['long_bearish', 'inverted_hammer', 'engulfing_bearish', 'evening_star']
    if any(last.get(p, False) for p in bearish_patterns):
        return 'BEARISH'

    return 'NEUTRAL'
