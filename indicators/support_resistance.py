"""
지지/저항선 계산 모듈
PDF 기준: 지지선, 저항선, 박스권, 추세선
"""

import pandas as pd
import numpy as np
from typing import Optional, Dict, List
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SupportResistance


def get_price_columns(df: pd.DataFrame) -> Dict[str, str]:
    """DataFrame에서 가격 컬럼명 찾기"""
    col_lower = {c.lower(): c for c in df.columns}
    return {
        'open': col_lower.get('open', 'Open'),
        'high': col_lower.get('high', 'High'),
        'low': col_lower.get('low', 'Low'),
        'close': col_lower.get('close', 'Close'),
    }


# =========================================================
# 피봇 포인트
# =========================================================

def calculate_pivot_points(df: pd.DataFrame) -> Dict[str, float]:
    """
    피봇 포인트 계산 (P, S1, S2, S3, R1, R2, R3)

    Args:
        df: OHLCV DataFrame

    Returns:
        피봇 포인트 딕셔너리
    """
    cols = get_price_columns(df)
    last = df.iloc[-1]

    high = last[cols['high']]
    low = last[cols['low']]
    close = last[cols['close']]

    # 피봇 포인트
    pivot = (high + low + close) / 3

    # 지지선
    s1 = 2 * pivot - high
    s2 = pivot - (high - low)
    s3 = low - 2 * (high - pivot)

    # 저항선
    r1 = 2 * pivot - low
    r2 = pivot + (high - low)
    r3 = high + 2 * (pivot - low)

    return {
        'pivot': pivot,
        'r1': r1, 'r2': r2, 'r3': r3,
        's1': s1, 's2': s2, 's3': s3,
    }


# =========================================================
# 지역 최고/최저점
# =========================================================

def find_local_minima(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """
    지역 최저점 탐색

    Args:
        df: OHLCV DataFrame
        window: 좌우 비교 기간

    Returns:
        지역 최저점 여부 Boolean Series
    """
    cols = get_price_columns(df)
    low = df[cols['low']]

    # 좌우 window 기간 동안 현재가 최저인지 확인
    rolling_min = low.rolling(window=2*window+1, center=True, min_periods=1).min()
    return low == rolling_min


def find_local_maxima(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """
    지역 최고점 탐색

    Args:
        df: OHLCV DataFrame
        window: 좌우 비교 기간

    Returns:
        지역 최고점 여부 Boolean Series
    """
    cols = get_price_columns(df)
    high = df[cols['high']]

    rolling_max = high.rolling(window=2*window+1, center=True, min_periods=1).max()
    return high == rolling_max


def get_local_minima_values(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """지역 최저점 값들만 반환"""
    cols = get_price_columns(df)
    minima = find_local_minima(df, window)
    result = df[cols['low']].copy()
    result[~minima] = np.nan
    return result


def get_local_maxima_values(df: pd.DataFrame, window: int = 5) -> pd.Series:
    """지역 최고점 값들만 반환"""
    cols = get_price_columns(df)
    maxima = find_local_maxima(df, window)
    result = df[cols['high']].copy()
    result[~maxima] = np.nan
    return result


# =========================================================
# 지지/저항 레벨
# =========================================================

def find_support_levels(df: pd.DataFrame, lookback: int = None,
                        num_levels: int = 3) -> List[float]:
    """
    지지선 레벨 탐색

    Args:
        df: OHLCV DataFrame
        lookback: 탐색 기간 (기본값: 20일)
        num_levels: 반환할 레벨 수

    Returns:
        지지선 가격 리스트 (높은 순)
    """
    if lookback is None:
        lookback = SupportResistance.BOX_LOOKBACK_DAYS

    cols = get_price_columns(df)
    recent = df.tail(lookback)

    # 지역 최저점들 찾기
    minima = get_local_minima_values(recent)
    support_values = minima.dropna().tolist()

    if not support_values:
        # 최저점이 없으면 최근 저가들 사용
        support_values = recent[cols['low']].nsmallest(num_levels).tolist()

    # 중복 제거 및 클러스터링
    clustered = cluster_price_levels(support_values)

    return sorted(clustered, reverse=True)[:num_levels]


def find_resistance_levels(df: pd.DataFrame, lookback: int = None,
                           num_levels: int = 3) -> List[float]:
    """
    저항선 레벨 탐색

    Args:
        df: OHLCV DataFrame
        lookback: 탐색 기간
        num_levels: 반환할 레벨 수

    Returns:
        저항선 가격 리스트 (낮은 순)
    """
    if lookback is None:
        lookback = SupportResistance.BOX_LOOKBACK_DAYS

    cols = get_price_columns(df)
    recent = df.tail(lookback)

    # 지역 최고점들 찾기
    maxima = get_local_maxima_values(recent)
    resistance_values = maxima.dropna().tolist()

    if not resistance_values:
        resistance_values = recent[cols['high']].nlargest(num_levels).tolist()

    clustered = cluster_price_levels(resistance_values)

    return sorted(clustered)[:num_levels]


def cluster_price_levels(prices: List[float], tolerance: float = 0.02) -> List[float]:
    """
    가격 레벨 클러스터링 (근접한 가격을 그룹화)

    Args:
        prices: 가격 리스트
        tolerance: 클러스터링 허용 오차 (%)

    Returns:
        클러스터링된 가격 리스트
    """
    if not prices:
        return []

    prices = sorted(prices)
    clusters = []
    current_cluster = [prices[0]]

    for price in prices[1:]:
        if price <= current_cluster[-1] * (1 + tolerance):
            current_cluster.append(price)
        else:
            clusters.append(np.mean(current_cluster))
            current_cluster = [price]

    clusters.append(np.mean(current_cluster))
    return clusters


# =========================================================
# 근접 여부 판단
# =========================================================

def is_near_support(price: float, support: float, threshold: float = None) -> bool:
    """
    지지선 근접 여부 확인

    Args:
        price: 현재 가격
        support: 지지선 가격
        threshold: 근접 판단 임계값 (%)

    Returns:
        근접 여부
    """
    if threshold is None:
        threshold = SupportResistance.NEAR_THRESHOLD

    return abs(price - support) / support <= threshold


def is_near_resistance(price: float, resistance: float, threshold: float = None) -> bool:
    """
    저항선 근접 여부 확인

    Args:
        price: 현재 가격
        resistance: 저항선 가격
        threshold: 근접 판단 임계값 (%)

    Returns:
        근접 여부
    """
    if threshold is None:
        threshold = SupportResistance.NEAR_THRESHOLD

    return abs(price - resistance) / resistance <= threshold


def get_nearest_support(price: float, supports: List[float]) -> Optional[float]:
    """현재 가격 아래의 가장 가까운 지지선 반환"""
    below_supports = [s for s in supports if s < price]
    return max(below_supports) if below_supports else None


def get_nearest_resistance(price: float, resistances: List[float]) -> Optional[float]:
    """현재 가격 위의 가장 가까운 저항선 반환"""
    above_resistances = [r for r in resistances if r > price]
    return min(above_resistances) if above_resistances else None


# =========================================================
# 지지/저항 돌파 감지
# =========================================================

def detect_support_break(df: pd.DataFrame, support: float,
                         threshold: float = None) -> pd.Series:
    """
    지지선 이탈 감지

    Args:
        df: OHLCV DataFrame
        support: 지지선 가격
        threshold: 이탈 판단 임계값 (%)

    Returns:
        이탈 여부 Boolean Series
    """
    if threshold is None:
        threshold = SupportResistance.BREAK_THRESHOLD

    cols = get_price_columns(df)
    break_level = support * (1 - threshold)

    return df[cols['close']] < break_level


def detect_resistance_break(df: pd.DataFrame, resistance: float,
                            threshold: float = None) -> pd.Series:
    """
    저항선 돌파 감지

    Args:
        df: OHLCV DataFrame
        resistance: 저항선 가격
        threshold: 돌파 판단 임계값 (%)

    Returns:
        돌파 여부 Boolean Series
    """
    if threshold is None:
        threshold = SupportResistance.BREAK_THRESHOLD

    cols = get_price_columns(df)
    break_level = resistance * (1 + threshold)

    return df[cols['close']] > break_level


# =========================================================
# 박스권 탐색
# =========================================================

def find_box_range(df: pd.DataFrame, lookback: int = None,
                   variance: float = None) -> Optional[Dict[str, float]]:
    """
    박스권 범위 탐색 (PDF: 매집 구간)

    Args:
        df: OHLCV DataFrame
        lookback: 탐색 기간
        variance: 허용 변동 범위

    Returns:
        {'high': 상단, 'low': 하단, 'mid': 중앙} 또는 None
    """
    if lookback is None:
        lookback = SupportResistance.BOX_LOOKBACK_DAYS
    if variance is None:
        variance = SupportResistance.BOX_VARIANCE

    if len(df) < lookback:
        return None

    cols = get_price_columns(df)
    recent = df.tail(lookback)

    high = recent[cols['high']].max()
    low = recent[cols['low']].min()
    mid = (high + low) / 2

    # 박스권 판단: 변동 범위가 허용치 이내
    range_ratio = (high - low) / mid
    if range_ratio > variance * 2:
        return None

    return {
        'high': high,
        'low': low,
        'mid': mid,
        'range': high - low,
        'range_ratio': range_ratio
    }


def is_in_box_range(df: pd.DataFrame, lookback: int = None,
                    variance: float = None) -> bool:
    """
    현재 박스권 내에 있는지 확인

    Args:
        df: OHLCV DataFrame
        lookback: 탐색 기간
        variance: 허용 변동 범위

    Returns:
        박스권 내 여부
    """
    box = find_box_range(df, lookback, variance)
    return box is not None


def detect_box_breakout(df: pd.DataFrame, lookback: int = None,
                        threshold: float = None) -> pd.Series:
    """
    박스권 상단 돌파 감지

    Args:
        df: OHLCV DataFrame
        lookback: 박스권 기간
        threshold: 돌파 판단 임계값 (%)

    Returns:
        돌파 여부 Boolean Series
    """
    if lookback is None:
        lookback = SupportResistance.BOX_LOOKBACK_DAYS
    if threshold is None:
        threshold = SupportResistance.BREAK_THRESHOLD

    cols = get_price_columns(df)

    # 롤링으로 박스권 상단 계산 (현재 제외)
    rolling_high = df[cols['high']].shift(1).rolling(window=lookback, min_periods=lookback).max()
    break_level = rolling_high * (1 + threshold)

    return df[cols['close']] > break_level


def detect_box_breakdown(df: pd.DataFrame, lookback: int = None,
                         threshold: float = None) -> pd.Series:
    """
    박스권 하단 이탈 감지

    Args:
        df: OHLCV DataFrame
        lookback: 박스권 기간
        threshold: 이탈 판단 임계값 (%)

    Returns:
        이탈 여부 Boolean Series
    """
    if lookback is None:
        lookback = SupportResistance.BOX_LOOKBACK_DAYS
    if threshold is None:
        threshold = SupportResistance.BREAK_THRESHOLD

    cols = get_price_columns(df)

    rolling_low = df[cols['low']].shift(1).rolling(window=lookback, min_periods=lookback).min()
    break_level = rolling_low * (1 - threshold)

    return df[cols['close']] < break_level


# =========================================================
# 52주 고가/저가
# =========================================================

def get_52week_high(df: pd.DataFrame) -> float:
    """52주(약 250 거래일) 최고가 반환"""
    cols = get_price_columns(df)
    lookback = min(250, len(df))
    return df[cols['high']].tail(lookback).max()


def get_52week_low(df: pd.DataFrame) -> float:
    """52주 최저가 반환"""
    cols = get_price_columns(df)
    lookback = min(250, len(df))
    return df[cols['low']].tail(lookback).min()


def is_near_52week_high(df: pd.DataFrame, threshold: float = 0.05) -> bool:
    """
    52주 신고가 근접 여부 확인

    Args:
        df: OHLCV DataFrame
        threshold: 근접 판단 임계값 (기본값: 5%)

    Returns:
        근접 여부
    """
    cols = get_price_columns(df)
    current_price = df[cols['close']].iloc[-1]
    high_52w = get_52week_high(df)

    return current_price >= high_52w * (1 - threshold)


def is_52week_high_breakout(df: pd.DataFrame) -> bool:
    """52주 신고가 돌파 여부 확인"""
    cols = get_price_columns(df)
    current_high = df[cols['high']].iloc[-1]

    # 오늘 제외한 52주 최고가
    lookback = min(250, len(df) - 1)
    prev_high_52w = df[cols['high']].iloc[:-1].tail(lookback).max()

    return current_high > prev_high_52w


# =========================================================
# 분석 함수
# =========================================================

def analyze_support_resistance(df: pd.DataFrame, lookback: int = None) -> Dict:
    """
    지지/저항 종합 분석

    Args:
        df: OHLCV DataFrame
        lookback: 분석 기간

    Returns:
        분석 결과 딕셔너리
    """
    cols = get_price_columns(df)
    current_price = df[cols['close']].iloc[-1]

    # 지지/저항 레벨
    supports = find_support_levels(df, lookback)
    resistances = find_resistance_levels(df, lookback)

    # 피봇 포인트
    pivots = calculate_pivot_points(df)

    # 박스권
    box = find_box_range(df, lookback)

    # 52주 고/저
    high_52w = get_52week_high(df)
    low_52w = get_52week_low(df)

    return {
        'current_price': current_price,
        'supports': supports,
        'resistances': resistances,
        'nearest_support': get_nearest_support(current_price, supports),
        'nearest_resistance': get_nearest_resistance(current_price, resistances),
        'pivots': pivots,
        'box_range': box,
        'high_52w': high_52w,
        'low_52w': low_52w,
        'near_52w_high': is_near_52week_high(df),
    }
