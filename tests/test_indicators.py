"""
지표 모듈 테스트
"""

import pytest
import pandas as pd
import numpy as np
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from indicators import (
    # 이동평균
    calculate_sma,
    calculate_ema,
    calculate_all_ma,
    get_ma_values,
    get_ma_status,
    detect_golden_cross,
    detect_dead_cross,
    # 거래량
    calculate_volume_ma,
    calculate_volume_ratio,
    detect_volume_spike,
    is_accumulation_phase,
    # 캔들 패턴
    detect_hammer,
    detect_doji,
    detect_long_bullish_candle,
    is_bullish,
    # 지지/저항
    find_support_levels,
    find_resistance_levels,
    find_box_range,
    detect_box_breakout,
    is_near_52week_high,
)


# 테스트용 더미 데이터 생성
@pytest.fixture
def sample_ohlcv():
    """테스트용 OHLCV 데이터"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    # 상승 추세 데이터 생성
    np.random.seed(42)
    base_price = 10000
    prices = [base_price]

    for i in range(99):
        change = np.random.normal(0.001, 0.02)  # 약간의 상승 추세
        prices.append(prices[-1] * (1 + change))

    prices = np.array(prices)

    df = pd.DataFrame({
        'Open': prices * (1 - np.random.uniform(0, 0.02, 100)),
        'High': prices * (1 + np.random.uniform(0, 0.03, 100)),
        'Low': prices * (1 - np.random.uniform(0, 0.03, 100)),
        'Close': prices,
        'Volume': np.random.randint(100000, 1000000, 100),
    }, index=dates)

    return df


@pytest.fixture
def volume_spike_data():
    """거래량 급증 데이터"""
    dates = pd.date_range(start='2024-01-01', periods=30, freq='D')

    # 마지막 날 거래량 급증
    volumes = [100000] * 29 + [500000]

    df = pd.DataFrame({
        'Open': [10000] * 30,
        'High': [10500] * 30,
        'Low': [9500] * 30,
        'Close': [10200] * 30,
        'Volume': volumes,
    }, index=dates)

    return df


class TestMovingAverage:
    """이동평균 테스트"""

    def test_calculate_sma(self, sample_ohlcv):
        """SMA 계산 테스트"""
        sma = calculate_sma(sample_ohlcv, period=5)

        assert len(sma) == len(sample_ohlcv)
        assert not sma.isna().all()
        # 첫 5개 이후부터는 NaN이 아님
        assert not sma.iloc[4:].isna().any()

    def test_calculate_ema(self, sample_ohlcv):
        """EMA 계산 테스트"""
        ema = calculate_ema(sample_ohlcv, period=5)

        assert len(ema) == len(sample_ohlcv)
        assert not ema.isna().all()

    def test_calculate_all_ma(self, sample_ohlcv):
        """전체 MA 계산 테스트"""
        df = calculate_all_ma(sample_ohlcv, periods=[5, 20])

        assert 'ma5' in df.columns
        assert 'ma20' in df.columns

    def test_get_ma_values(self, sample_ohlcv):
        """MA 값 조회 테스트"""
        df = calculate_all_ma(sample_ohlcv, periods=[5, 20])
        ma_values = get_ma_values(df, periods=[5, 20])

        assert 5 in ma_values
        assert 20 in ma_values
        assert ma_values[5] > 0

    def test_get_ma_status(self, sample_ohlcv):
        """MA 상태 판단 테스트"""
        df = calculate_all_ma(sample_ohlcv, periods=[5, 20, 60])
        ma_values = get_ma_values(df, periods=[5, 20, 60])
        current_price = sample_ohlcv['Close'].iloc[-1]

        status = get_ma_status(current_price, ma_values)

        assert status in ['BULLISH', 'BEARISH', 'MIXED', 'UNKNOWN']

    def test_detect_golden_cross(self, sample_ohlcv):
        """골든크로스 감지 테스트"""
        df = calculate_all_ma(sample_ohlcv, periods=[5, 20])

        golden = detect_golden_cross(df['ma5'], df['ma20'])

        assert len(golden) == len(sample_ohlcv)
        assert golden.dtype == bool

    def test_detect_dead_cross(self, sample_ohlcv):
        """데드크로스 감지 테스트"""
        df = calculate_all_ma(sample_ohlcv, periods=[5, 20])

        dead = detect_dead_cross(df['ma5'], df['ma20'])

        assert len(dead) == len(sample_ohlcv)
        assert dead.dtype == bool


class TestVolume:
    """거래량 테스트"""

    def test_calculate_volume_ma(self, sample_ohlcv):
        """거래량 MA 계산 테스트"""
        vol_ma = calculate_volume_ma(sample_ohlcv, period=20)

        assert len(vol_ma) == len(sample_ohlcv)
        assert not vol_ma.isna().all()

    def test_calculate_volume_ratio(self, sample_ohlcv):
        """거래량 비율 계산 테스트"""
        vol_ratio = calculate_volume_ratio(sample_ohlcv, period=20)

        assert len(vol_ratio) == len(sample_ohlcv)

    def test_detect_volume_spike(self, volume_spike_data):
        """거래량 급증 감지 테스트"""
        spike = detect_volume_spike(volume_spike_data, threshold=2.0, lookback=20)

        assert isinstance(spike, pd.Series)
        # 마지막 날은 거래량 급증
        assert spike.iloc[-1] == True

    def test_is_accumulation_phase(self, sample_ohlcv):
        """세력 매집 구간 판단 테스트"""
        result = is_accumulation_phase(sample_ohlcv)

        assert isinstance(result, bool)


class TestCandlePattern:
    """캔들 패턴 테스트"""

    def test_detect_hammer(self, sample_ohlcv):
        """해머 패턴 감지 테스트"""
        hammer = detect_hammer(sample_ohlcv)

        assert isinstance(hammer, pd.Series)
        assert hammer.dtype == bool

    def test_detect_doji(self, sample_ohlcv):
        """도지 패턴 감지 테스트"""
        doji = detect_doji(sample_ohlcv, threshold=0.01)

        assert isinstance(doji, pd.Series)
        assert doji.dtype == bool

    def test_detect_long_bullish_candle(self, sample_ohlcv):
        """장대양봉 감지 테스트"""
        long_bull = detect_long_bullish_candle(sample_ohlcv, threshold=0.03)

        assert isinstance(long_bull, pd.Series)
        assert long_bull.dtype == bool

    def test_is_bullish(self, sample_ohlcv):
        """양봉 판단 테스트"""
        bullish = is_bullish(sample_ohlcv)

        assert isinstance(bullish, pd.Series)
        assert bullish.dtype == bool


class TestSupportResistance:
    """지지/저항 테스트"""

    def test_find_support_levels(self, sample_ohlcv):
        """지지선 찾기 테스트"""
        supports = find_support_levels(sample_ohlcv, lookback=20)

        assert isinstance(supports, list)
        for level in supports:
            assert level > 0

    def test_find_resistance_levels(self, sample_ohlcv):
        """저항선 찾기 테스트"""
        resistances = find_resistance_levels(sample_ohlcv, lookback=20)

        assert isinstance(resistances, list)
        for level in resistances:
            assert level > 0

    def test_find_box_range(self, sample_ohlcv):
        """박스권 찾기 테스트"""
        box = find_box_range(sample_ohlcv, lookback=10, variance=0.10)

        # 박스권이 있거나 없거나
        if box:
            assert 'high' in box
            assert 'low' in box
            assert box['high'] > box['low']

    def test_detect_box_breakout(self, sample_ohlcv):
        """박스권 돌파 테스트"""
        breakout = detect_box_breakout(sample_ohlcv, lookback=20, variance=0.10)

        assert isinstance(breakout, dict)
        assert 'breakout_up' in breakout
        assert 'breakout_down' in breakout

    def test_is_near_52week_high(self, sample_ohlcv):
        """52주 신고가 근접 테스트"""
        result = is_near_52week_high(sample_ohlcv, threshold=0.10)

        assert isinstance(result, bool)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
