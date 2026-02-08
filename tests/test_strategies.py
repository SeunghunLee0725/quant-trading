"""
전략 모듈 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SignalType
from strategies import (
    Signal,
    get_strategy,
    get_all_strategies,
    Minute15Strategy,
    Minute30Strategy,
    LimitUpStrategy,
    BreakoutStrategy,
)


@pytest.fixture
def sample_daily_data():
    """일봉 테스트 데이터"""
    dates = pd.date_range(start="2024-01-01", periods=60, freq="D")

    np.random.seed(42)
    base_price = 10000

    opens = []
    highs = []
    lows = []
    closes = []
    volumes = []

    price = base_price

    for i in range(60):
        open_price = price
        change = np.random.uniform(-0.03, 0.04)
        close_price = open_price * (1 + change)
        high_price = max(open_price, close_price) * (1 + np.random.uniform(0, 0.02))
        low_price = min(open_price, close_price) * (1 - np.random.uniform(0, 0.02))
        volume = int(np.random.uniform(100000, 500000))

        opens.append(open_price)
        highs.append(high_price)
        lows.append(low_price)
        closes.append(close_price)
        volumes.append(volume)

        price = close_price

    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )


@pytest.fixture
def limit_up_data():
    """상한가 테스트 데이터"""
    dates = pd.date_range(start="2024-01-01", periods=20, freq="D")

    # 10일차에 상한가 (29% 상승)
    opens = [10000] * 20
    closes = [10000] * 20
    highs = [10200] * 20
    lows = [9800] * 20
    volumes = [100000] * 20

    # 상한가 날
    limit_up_idx = 10
    opens[limit_up_idx] = 10000
    closes[limit_up_idx] = 12900  # 29% 상승
    highs[limit_up_idx] = 12900
    lows[limit_up_idx] = 10000
    volumes[limit_up_idx] = 1000000  # 거래량 급증

    # 상한가 이후 박스권
    for i in range(limit_up_idx + 1, 20):
        opens[i] = 12800
        closes[i] = 12700 + np.random.randint(-200, 200)
        highs[i] = max(opens[i], closes[i]) + 100
        lows[i] = min(opens[i], closes[i]) - 100
        volumes[i] = 200000 + np.random.randint(-50000, 50000)

    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )


@pytest.fixture
def breakout_data():
    """기준봉 돌파 테스트 데이터"""
    dates = pd.date_range(start="2024-01-01", periods=30, freq="D")

    opens = [10000] * 30
    closes = [10000] * 30
    highs = [10200] * 30
    lows = [9800] * 30
    volumes = [100000] * 30

    # 기준봉 (거래량 급증 + 큰 상승)
    ref_idx = 15
    opens[ref_idx] = 10000
    closes[ref_idx] = 10600  # 6% 상승
    highs[ref_idx] = 10700
    lows[ref_idx] = 9900
    volumes[ref_idx] = 500000  # 거래량 5배

    # 조정 기간 (거래량 감소)
    for i in range(ref_idx + 1, 28):
        opens[i] = 10500
        closes[i] = 10400 + np.random.randint(-100, 100)
        highs[i] = 10600  # 기준봉 고가 미돌파
        lows[i] = 10300
        volumes[i] = 80000  # 거래량 감소

    # 돌파 (기준봉 고가 돌파)
    opens[28] = 10500
    closes[28] = 10800  # 기준봉 고가 돌파
    highs[28] = 10900
    lows[28] = 10400
    volumes[28] = 300000

    opens[29] = 10800
    closes[29] = 10900
    highs[29] = 11000
    lows[29] = 10700
    volumes[29] = 250000

    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )


class TestSignal:
    """Signal 클래스 테스트"""

    def test_signal_creation(self):
        """Signal 생성 테스트"""
        signal = Signal(
            code="005930",
            name="삼성전자",
            datetime=datetime.now(),
            signal_type=SignalType.BUY,
            strategy="test",
            price=70000,
            stop_loss=67000,
            take_profit=77000,
        )

        assert signal.code == "005930"
        assert signal.signal_type == SignalType.BUY
        assert signal.price == 70000

    def test_signal_to_dict(self):
        """Signal to_dict 테스트"""
        signal = Signal(
            code="005930",
            name="삼성전자",
            datetime=datetime.now(),
            signal_type=SignalType.BUY,
            strategy="test",
            price=70000,
        )

        d = signal.to_dict()

        assert isinstance(d, dict)
        assert d["code"] == "005930"
        assert d["signal_type"] == "BUY"


class TestStrategyRegistry:
    """전략 레지스트리 테스트"""

    def test_get_strategy(self):
        """전략 조회 테스트"""
        strategy = get_strategy("limit_up")
        assert strategy is not None
        assert strategy.name == "limit_up"

    def test_get_all_strategies(self):
        """전체 전략 조회 테스트"""
        strategies = get_all_strategies()
        assert len(strategies) >= 4


class TestMinute15Strategy:
    """15분봉 전략 테스트"""

    def test_strategy_creation(self):
        """전략 생성 테스트"""
        strategy = Minute15Strategy()
        assert strategy.name == "minute15"

    def test_generate_signal(self, sample_daily_data):
        """신호 생성 테스트"""
        strategy = Minute15Strategy()
        signal = strategy.generate_signal(sample_daily_data, "005930", "삼성전자")

        # 신호가 있거나 없거나 (조건에 따라)
        if signal:
            assert signal.strategy == "minute15"
            assert signal.signal_type == SignalType.BUY


class TestMinute30Strategy:
    """30분봉 전략 테스트"""

    def test_strategy_creation(self):
        """전략 생성 테스트"""
        strategy = Minute30Strategy()
        assert strategy.name == "minute30"

    def test_generate_signal(self, sample_daily_data):
        """신호 생성 테스트"""
        strategy = Minute30Strategy()
        signal = strategy.generate_signal(sample_daily_data, "005930", "삼성전자")

        if signal:
            assert signal.strategy == "minute30"


class TestLimitUpStrategy:
    """상한가 전략 테스트"""

    def test_strategy_creation(self):
        """전략 생성 테스트"""
        strategy = LimitUpStrategy()
        assert strategy.name == "limit_up"

    def test_check_buy_conditions(self, limit_up_data):
        """매수 조건 확인 테스트"""
        strategy = LimitUpStrategy()
        conditions = strategy.check_buy_conditions(limit_up_data)

        assert "recent_limit_up" in conditions
        assert "price_support" in conditions
        assert "consolidation" in conditions

    def test_generate_signal_with_limit_up(self, limit_up_data):
        """상한가 데이터로 신호 생성 테스트"""
        strategy = LimitUpStrategy()
        signal = strategy.generate_signal(limit_up_data, "005930", "삼성전자")

        # 상한가 조건에 맞는 데이터이므로 신호가 있을 수 있음
        if signal:
            assert signal.strategy == "limit_up"
            assert signal.stop_loss < signal.price
            assert signal.take_profit > signal.price


class TestBreakoutStrategy:
    """돌파 전략 테스트"""

    def test_strategy_creation(self):
        """전략 생성 테스트"""
        strategy = BreakoutStrategy()
        assert strategy.name == "breakout"

    def test_check_buy_conditions(self, breakout_data):
        """매수 조건 확인 테스트"""
        strategy = BreakoutStrategy()
        conditions = strategy.check_buy_conditions(breakout_data)

        assert "reference_candle" in conditions
        assert "consolidation" in conditions
        assert "breakout" in conditions

    def test_generate_signal_with_breakout(self, breakout_data):
        """돌파 데이터로 신호 생성 테스트"""
        strategy = BreakoutStrategy()
        signal = strategy.generate_signal(breakout_data, "005930", "삼성전자")

        if signal:
            assert signal.strategy == "breakout"
            assert signal.stop_loss < signal.price


class TestBaseStrategy:
    """BaseStrategy 테스트"""

    def test_get_signal_reason(self, sample_daily_data):
        """신호 사유 생성 테스트"""
        strategy = LimitUpStrategy()

        conditions = {
            "recent_limit_up": True,
            "price_support": True,
            "consolidation": False,
        }

        reason = strategy.get_signal_reason(conditions)
        assert isinstance(reason, str)
        assert len(reason) > 0
        # get_signal_reason returns Korean names for met conditions
        assert "최근 상한가 기록" in reason
        assert "상한가 종가 지지" in reason


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
