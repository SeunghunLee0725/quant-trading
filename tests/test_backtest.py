"""
백테스트 모듈 테스트
"""

import pytest
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from backtest import (
    TradeRecord,
    PerformanceMetrics,
    Position,
    BacktestConfig,
    Backtester,
    calculate_returns,
    calculate_total_return,
    calculate_annualized_return,
    calculate_max_drawdown,
    calculate_sharpe_ratio,
    calculate_sortino_ratio,
    calculate_profit_factor,
    calculate_win_rate,
    calculate_all_metrics,
    format_metrics_report,
)
from strategies import LimitUpStrategy


@pytest.fixture
def equity_curve():
    """테스트용 자산 곡선"""
    dates = pd.date_range(start='2024-01-01', periods=252, freq='D')

    # 연 10% 수익률 시뮬레이션
    np.random.seed(42)
    daily_returns = np.random.normal(0.0004, 0.01, 252)  # 평균 0.04%, 표준편차 1%

    equity = [10000000]  # 1000만원 시작
    for r in daily_returns:
        equity.append(equity[-1] * (1 + r))

    return pd.Series(equity[1:], index=dates)


@pytest.fixture
def sample_trades():
    """테스트용 거래 기록"""
    trades = [
        TradeRecord(
            code='005930', name='삼성전자', strategy='test',
            entry_date=datetime(2024, 1, 5),
            entry_price=70000, exit_date=datetime(2024, 1, 15),
            exit_price=77000, quantity=100, side='long',
            pnl=700000, pnl_percent=10.0, holding_days=10
        ),
        TradeRecord(
            code='000660', name='SK하이닉스', strategy='test',
            entry_date=datetime(2024, 1, 20),
            entry_price=130000, exit_date=datetime(2024, 1, 25),
            exit_price=125000, quantity=50, side='long',
            pnl=-250000, pnl_percent=-3.85, holding_days=5
        ),
        TradeRecord(
            code='035420', name='NAVER', strategy='test',
            entry_date=datetime(2024, 2, 1),
            entry_price=200000, exit_date=datetime(2024, 2, 20),
            exit_price=230000, quantity=30, side='long',
            pnl=900000, pnl_percent=15.0, holding_days=19
        ),
    ]
    return trades


@pytest.fixture
def sample_stock_data():
    """테스트용 종목 데이터"""
    dates = pd.date_range(start='2024-01-01', periods=100, freq='D')

    data = {}
    for code in ['005930', '000660', '035420']:
        np.random.seed(hash(code) % 100)
        base_price = 50000 + hash(code) % 50000

        prices = [base_price]
        for _ in range(99):
            change = np.random.normal(0.001, 0.02)
            prices.append(prices[-1] * (1 + change))

        prices = np.array(prices)

        data[code] = pd.DataFrame({
            'Open': prices * 0.99,
            'High': prices * 1.02,
            'Low': prices * 0.97,
            'Close': prices,
            'Volume': np.random.randint(100000, 1000000, 100),
        }, index=dates)

    return data


class TestMetricsCalculation:
    """성과 지표 계산 테스트"""

    def test_calculate_returns(self, equity_curve):
        """수익률 계산 테스트"""
        returns = calculate_returns(equity_curve)

        assert len(returns) == len(equity_curve) - 1
        assert not returns.isna().all()

    def test_calculate_total_return(self, equity_curve):
        """총 수익률 계산 테스트"""
        total_return = calculate_total_return(equity_curve)

        assert isinstance(total_return, float)
        # 10000000에서 시작해서 양수/음수 수익률

    def test_calculate_annualized_return(self):
        """연환산 수익률 계산 테스트"""
        # 1년간 10% 수익
        annual = calculate_annualized_return(0.10, 252)
        assert abs(annual - 0.10) < 0.01

        # 2년간 21% 수익 (연 10%)
        annual_2y = calculate_annualized_return(0.21, 504)
        assert abs(annual_2y - 0.10) < 0.02

    def test_calculate_max_drawdown(self, equity_curve):
        """MDD 계산 테스트"""
        mdd, mdd_pct, duration = calculate_max_drawdown(equity_curve)

        assert mdd >= 0
        assert 0 <= abs(mdd_pct) <= 1

    def test_calculate_sharpe_ratio(self, equity_curve):
        """샤프 비율 계산 테스트"""
        returns = calculate_returns(equity_curve)
        sharpe = calculate_sharpe_ratio(returns)

        assert isinstance(sharpe, float)

    def test_calculate_sortino_ratio(self, equity_curve):
        """소르티노 비율 계산 테스트"""
        returns = calculate_returns(equity_curve)
        sortino = calculate_sortino_ratio(returns)

        assert isinstance(sortino, float)

    def test_calculate_profit_factor(self, sample_trades):
        """수익 팩터 계산 테스트"""
        pf = calculate_profit_factor(sample_trades)

        # 수익 > 손실이면 > 1
        assert pf > 0

    def test_calculate_win_rate(self, sample_trades):
        """승률 계산 테스트"""
        win_rate = calculate_win_rate(sample_trades)

        # 3개 중 2개 수익 = 66.67%
        assert abs(win_rate - 0.6667) < 0.01

    def test_calculate_all_metrics(self, equity_curve, sample_trades):
        """전체 지표 계산 테스트"""
        metrics = calculate_all_metrics(equity_curve, sample_trades)

        assert isinstance(metrics, PerformanceMetrics)
        assert metrics.total_trades == 3
        assert metrics.winning_trades == 2
        assert metrics.losing_trades == 1


class TestTradeRecord:
    """TradeRecord 테스트"""

    def test_trade_record_creation(self):
        """거래 기록 생성 테스트"""
        trade = TradeRecord(
            code='005930',
            name='삼성전자',
            strategy='test',
            entry_date=datetime.now(),
            entry_price=70000,
        )

        assert trade.code == '005930'
        assert trade.entry_price == 70000


class TestBacktestConfig:
    """BacktestConfig 테스트"""

    def test_default_config(self):
        """기본 설정 테스트"""
        config = BacktestConfig()

        assert config.initial_capital == 10000000
        assert config.commission_rate > 0
        assert config.max_positions > 0

    def test_custom_config(self):
        """커스텀 설정 테스트"""
        config = BacktestConfig(
            initial_capital=50000000,
            max_positions=5,
        )

        assert config.initial_capital == 50000000
        assert config.max_positions == 5


class TestBacktester:
    """Backtester 테스트"""

    def test_backtester_creation(self):
        """백테스터 생성 테스트"""
        bt = Backtester('limit_up')

        assert bt.strategy is not None
        assert bt.config is not None

    def test_backtester_reset(self):
        """백테스터 초기화 테스트"""
        bt = Backtester('limit_up')
        bt.capital = 5000000
        bt.reset()

        assert bt.capital == bt.config.initial_capital
        assert len(bt.positions) == 0
        assert len(bt.trades) == 0

    def test_backtester_run(self, sample_stock_data):
        """백테스트 실행 테스트"""
        bt = Backtester('limit_up')
        metrics = bt.run(sample_stock_data)

        assert isinstance(metrics, PerformanceMetrics)

    def test_backtester_get_equity_curve(self, sample_stock_data):
        """자산 곡선 조회 테스트"""
        bt = Backtester('limit_up')
        bt.run(sample_stock_data)

        equity = bt.get_equity_curve()

        assert isinstance(equity, pd.DataFrame)

    def test_backtester_generate_report(self, sample_stock_data):
        """보고서 생성 테스트"""
        bt = Backtester('limit_up')
        bt.run(sample_stock_data)

        report = bt.generate_report()

        assert isinstance(report, str)
        assert '백테스트' in report


class TestFormatReport:
    """보고서 포맷팅 테스트"""

    def test_format_metrics_report(self, equity_curve, sample_trades):
        """지표 보고서 포맷팅 테스트"""
        metrics = calculate_all_metrics(equity_curve, sample_trades)
        report = format_metrics_report(metrics)

        assert isinstance(report, str)
        assert '수익률' in report
        assert '리스크' in report
        assert '거래 통계' in report


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
