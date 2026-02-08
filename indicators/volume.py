"""
거래량 지표 모듈
PDF 기준: 거래량 급등, 매집 구간, 기준봉 판단
"""

import pandas as pd
import numpy as np
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import VolumeThreshold


def get_volume_column(df: pd.DataFrame) -> str:
    """DataFrame에서 거래량 컬럼명 찾기"""
    col_lower = {c.lower(): c for c in df.columns}
    return col_lower.get('volume', 'Volume')


def calculate_volume_ma(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    거래량 이동평균 계산

    Args:
        df: OHLCV DataFrame
        period: 이동평균 기간 (기본값: 20일)

    Returns:
        거래량 MA Series
    """
    vol_col = get_volume_column(df)
    return df[vol_col].rolling(window=period, min_periods=1).mean()


def calculate_volume_ratio(df: pd.DataFrame, period: int = 20) -> pd.Series:
    """
    거래량 비율 계산 (현재 거래량 / 평균 거래량)

    Args:
        df: OHLCV DataFrame
        period: 이동평균 기간

    Returns:
        거래량 비율 Series (배수)
    """
    vol_col = get_volume_column(df)
    vol_ma = calculate_volume_ma(df, period)
    return df[vol_col] / vol_ma


def calculate_volume_change(df: pd.DataFrame, periods: int = 1) -> pd.Series:
    """
    거래량 변화율 계산

    Args:
        df: OHLCV DataFrame
        periods: 비교 기간 (1 = 전일 대비)

    Returns:
        거래량 변화율 Series
    """
    vol_col = get_volume_column(df)
    return df[vol_col].pct_change(periods=periods)


def detect_volume_spike(df: pd.DataFrame, threshold: float = None,
                        period: int = 20) -> pd.Series:
    """
    거래량 급등 감지

    Args:
        df: OHLCV DataFrame
        threshold: 급등 판단 임계값 (평균 대비 배수, 기본값: 2.0)
        period: 평균 계산 기간

    Returns:
        거래량 급등 여부 Boolean Series
    """
    if threshold is None:
        threshold = VolumeThreshold.SPIKE_RATIO

    vol_ratio = calculate_volume_ratio(df, period)
    return vol_ratio >= threshold


def detect_volume_decline(df: pd.DataFrame, threshold: float = None,
                          period: int = 20) -> pd.Series:
    """
    거래량 감소 감지

    Args:
        df: OHLCV DataFrame
        threshold: 감소 판단 임계값 (평균 대비 배수, 기본값: 0.5)
        period: 평균 계산 기간

    Returns:
        거래량 감소 여부 Boolean Series
    """
    if threshold is None:
        threshold = VolumeThreshold.DECLINE_RATIO

    vol_ratio = calculate_volume_ratio(df, period)
    return vol_ratio <= threshold


def is_accumulation_phase(df: pd.DataFrame, lookback: int = 10,
                          price_variance: float = None,
                          volume_variance: float = None) -> bool:
    """
    매집 구간 판단 (PDF 기준: 가격 횡보 + 거래량 감소/안정)

    Args:
        df: OHLCV DataFrame
        lookback: 확인 기간
        price_variance: 가격 변동 허용 범위 (기본값: 5%)
        volume_variance: 거래량 변동 허용 범위 (기본값: 30%)

    Returns:
        매집 구간 여부
    """
    if price_variance is None:
        price_variance = 0.05
    if volume_variance is None:
        volume_variance = VolumeThreshold.ACCUMULATION_VARIANCE

    if len(df) < lookback:
        return False

    recent = df.tail(lookback)
    col_lower = {c.lower(): c for c in df.columns}
    close_col = col_lower.get('close', 'Close')
    vol_col = get_volume_column(df)

    # 가격 횡보 확인 (변동 범위가 작음)
    price_range = (recent[close_col].max() - recent[close_col].min()) / recent[close_col].mean()
    is_price_stable = price_range <= price_variance

    # 거래량 안정/감소 확인
    vol_std = recent[vol_col].std() / recent[vol_col].mean()
    is_volume_stable = vol_std <= volume_variance

    return is_price_stable and is_volume_stable


def detect_breakout_volume(df: pd.DataFrame, lookback: int = 10,
                           threshold: float = None) -> pd.Series:
    """
    기준봉 거래량 감지 (매집 구간 평균 대비 급등)

    Args:
        df: OHLCV DataFrame
        lookback: 매집 구간 기간
        threshold: 돌파 거래량 배수 (기본값: 3.0)

    Returns:
        돌파 거래량 여부 Boolean Series
    """
    if threshold is None:
        threshold = VolumeThreshold.BREAKOUT_RATIO

    vol_col = get_volume_column(df)

    # lookback 기간 평균 거래량
    rolling_mean = df[vol_col].rolling(window=lookback, min_periods=1).mean().shift(1)

    return df[vol_col] >= (rolling_mean * threshold)


def detect_climax_volume(df: pd.DataFrame, percentile: float = 95,
                         lookback: int = 60) -> pd.Series:
    """
    클라이맥스(극대) 거래량 감지

    Args:
        df: OHLCV DataFrame
        percentile: 상위 퍼센타일 (기본값: 95%)
        lookback: 기준 기간

    Returns:
        클라이맥스 거래량 여부 Boolean Series
    """
    vol_col = get_volume_column(df)

    def check_climax(window):
        if len(window) < lookback:
            return False
        threshold = np.percentile(window[:-1], percentile)
        return window.iloc[-1] >= threshold

    result = df[vol_col].rolling(window=lookback, min_periods=lookback).apply(
        lambda x: check_climax(x), raw=False
    )

    return result.fillna(False).astype(bool)


def calculate_obv(df: pd.DataFrame) -> pd.Series:
    """
    On-Balance Volume (OBV) 계산

    Args:
        df: OHLCV DataFrame

    Returns:
        OBV Series
    """
    col_lower = {c.lower(): c for c in df.columns}
    close_col = col_lower.get('close', 'Close')
    vol_col = get_volume_column(df)

    close = df[close_col]
    volume = df[vol_col]

    # 가격 방향에 따라 거래량 부호 결정
    direction = np.sign(close.diff())
    direction.iloc[0] = 0

    obv = (direction * volume).cumsum()
    return obv


def calculate_vwap(df: pd.DataFrame) -> pd.Series:
    """
    Volume Weighted Average Price (VWAP) 계산

    Args:
        df: OHLCV DataFrame

    Returns:
        VWAP Series
    """
    col_lower = {c.lower(): c for c in df.columns}
    high_col = col_lower.get('high', 'High')
    low_col = col_lower.get('low', 'Low')
    close_col = col_lower.get('close', 'Close')
    vol_col = get_volume_column(df)

    typical_price = (df[high_col] + df[low_col] + df[close_col]) / 3
    cumulative_tpv = (typical_price * df[vol_col]).cumsum()
    cumulative_volume = df[vol_col].cumsum()

    return cumulative_tpv / cumulative_volume


def get_volume_profile(df: pd.DataFrame, bins: int = 20) -> pd.DataFrame:
    """
    거래량 프로파일 (가격대별 거래량 분포)

    Args:
        df: OHLCV DataFrame
        bins: 가격 구간 수

    Returns:
        가격대별 거래량 DataFrame
    """
    col_lower = {c.lower(): c for c in df.columns}
    close_col = col_lower.get('close', 'Close')
    vol_col = get_volume_column(df)

    # 가격 구간 생성
    price_bins = pd.cut(df[close_col], bins=bins)

    # 구간별 거래량 합계
    profile = df.groupby(price_bins)[vol_col].sum()
    profile = profile.reset_index()
    profile.columns = ['price_range', 'volume']

    return profile


def analyze_volume_trend(df: pd.DataFrame, short_period: int = 5,
                         long_period: int = 20) -> str:
    """
    거래량 추세 분석

    Args:
        df: OHLCV DataFrame
        short_period: 단기 이평 기간
        long_period: 장기 이평 기간

    Returns:
        'INCREASING', 'DECREASING', 'STABLE'
    """
    vol_col = get_volume_column(df)

    short_ma = df[vol_col].rolling(window=short_period).mean().iloc[-1]
    long_ma = df[vol_col].rolling(window=long_period).mean().iloc[-1]

    ratio = short_ma / long_ma

    if ratio > 1.2:
        return 'INCREASING'
    elif ratio < 0.8:
        return 'DECREASING'
    else:
        return 'STABLE'


def calculate_volume_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """
    모든 거래량 지표 계산

    Args:
        df: OHLCV DataFrame

    Returns:
        거래량 지표가 추가된 DataFrame
    """
    df = df.copy()
    vol_col = get_volume_column(df)

    # 거래량 이동평균
    df['volume_ma5'] = calculate_volume_ma(df, 5)
    df['volume_ma20'] = calculate_volume_ma(df, 20)

    # 거래량 비율
    df['volume_ratio'] = calculate_volume_ratio(df, 20)

    # 거래량 급등/감소
    df['volume_spike'] = detect_volume_spike(df)
    df['volume_decline'] = detect_volume_decline(df)

    # OBV
    df['obv'] = calculate_obv(df)

    return df
