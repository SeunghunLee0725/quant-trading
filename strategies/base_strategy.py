"""
매매 전략 베이스 클래스
모든 전략의 기본 인터페이스 정의
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, Any, List
from enum import Enum
import pandas as pd
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import SignalType, TRADING


@dataclass
class Signal:
    """매매 신호 데이터 클래스"""
    code: str                           # 종목 코드
    name: str                           # 종목명
    datetime: datetime                  # 신호 발생 시간
    signal_type: SignalType             # 신호 유형 (BUY/SELL)
    strategy: str                       # 전략명
    price: float                        # 현재/진입 가격
    stop_loss: Optional[float] = None   # 손절가
    take_profit: Optional[float] = None # 익절가
    reason: str = ""                    # 신호 발생 사유
    strength: float = 1.0               # 신호 강도 (0~1)
    metadata: Dict[str, Any] = field(default_factory=dict)  # 추가 정보

    def to_dict(self) -> Dict[str, Any]:
        """딕셔너리로 변환"""
        return {
            'code': self.code,
            'name': self.name,
            'datetime': self.datetime.isoformat(),
            'signal_type': self.signal_type.value,
            'strategy': self.strategy,
            'price': self.price,
            'stop_loss': self.stop_loss,
            'take_profit': self.take_profit,
            'reason': self.reason,
            'strength': self.strength,
            'metadata': self.metadata,
        }

    @property
    def risk_reward_ratio(self) -> Optional[float]:
        """손익비 계산"""
        if self.stop_loss is None or self.take_profit is None:
            return None

        risk = abs(self.price - self.stop_loss)
        reward = abs(self.take_profit - self.price)

        if risk == 0:
            return None

        return reward / risk

    @property
    def stop_loss_percent(self) -> Optional[float]:
        """손절률 (%)"""
        if self.stop_loss is None:
            return None
        return (self.stop_loss - self.price) / self.price * 100

    @property
    def take_profit_percent(self) -> Optional[float]:
        """익절률 (%)"""
        if self.take_profit is None:
            return None
        return (self.take_profit - self.price) / self.price * 100


class BaseStrategy(ABC):
    """매매 전략 추상 베이스 클래스"""

    def __init__(self, name: str, params: Dict[str, Any] = None):
        """
        Args:
            name: 전략 이름
            params: 전략 파라미터
        """
        self.name = name
        self.params = params or {}

        # 기본 리스크 관리 설정
        self.default_stop_loss_pct = TRADING['default_stop_loss']
        self.default_take_profit_pct = TRADING['default_take_profit']

    @abstractmethod
    def generate_signal(self, df: pd.DataFrame, code: str = "",
                        name: str = "") -> Optional[Signal]:
        """
        매매 신호 생성 (구현 필수)

        Args:
            df: OHLCV DataFrame (이동평균 등 지표 포함)
            code: 종목 코드
            name: 종목명

        Returns:
            Signal 객체 또는 None (신호 없음)
        """
        pass

    def check_buy_conditions(self, df: pd.DataFrame) -> bool:
        """
        매수 조건 확인 (서브클래스에서 구현)

        Args:
            df: OHLCV DataFrame

        Returns:
            매수 조건 충족 여부
        """
        return False

    def check_sell_conditions(self, df: pd.DataFrame,
                              entry_price: float = None) -> bool:
        """
        매도 조건 확인 (서브클래스에서 구현)

        Args:
            df: OHLCV DataFrame
            entry_price: 진입 가격 (손절/익절 판단용)

        Returns:
            매도 조건 충족 여부
        """
        return False

    def calculate_entry_price(self, df: pd.DataFrame) -> float:
        """
        진입 가격 계산

        Args:
            df: OHLCV DataFrame

        Returns:
            진입 가격 (기본값: 현재 종가)
        """
        col_lower = {c.lower(): c for c in df.columns}
        close_col = col_lower.get('close', 'Close')
        return float(df[close_col].iloc[-1])

    def calculate_stop_loss(self, df: pd.DataFrame,
                            entry_price: float) -> float:
        """
        손절가 계산

        Args:
            df: OHLCV DataFrame
            entry_price: 진입 가격

        Returns:
            손절가 (기본값: 진입가의 -3%)
        """
        return entry_price * (1 - self.default_stop_loss_pct)

    def calculate_take_profit(self, df: pd.DataFrame,
                              entry_price: float) -> float:
        """
        익절가 계산

        Args:
            df: OHLCV DataFrame
            entry_price: 진입 가격

        Returns:
            익절가 (기본값: 진입가의 +10%)
        """
        return entry_price * (1 + self.default_take_profit_pct)

    def validate_signal(self, signal: Signal) -> bool:
        """
        신호 유효성 검증

        Args:
            signal: 검증할 신호

        Returns:
            유효 여부
        """
        if signal is None:
            return False

        # 가격 유효성
        if signal.price <= 0:
            return False

        # 손절가 유효성 (매수 신호의 경우)
        if signal.signal_type == SignalType.BUY:
            if signal.stop_loss and signal.stop_loss >= signal.price:
                return False
            if signal.take_profit and signal.take_profit <= signal.price:
                return False

        return True

    def get_position_size(self, capital: float, risk_percent: float = 0.02,
                          entry_price: float = None,
                          stop_loss: float = None) -> int:
        """
        포지션 크기 계산 (리스크 기반)

        Args:
            capital: 총 자본금
            risk_percent: 리스크 비율 (기본값: 2%)
            entry_price: 진입 가격
            stop_loss: 손절가

        Returns:
            매수 수량
        """
        if entry_price is None or entry_price <= 0:
            return 0

        # 최대 투자 금액 (자본의 10%)
        max_investment = capital * TRADING['max_position_ratio']

        if stop_loss and entry_price > stop_loss:
            # 리스크 기반 계산
            risk_amount = capital * risk_percent
            risk_per_share = entry_price - stop_loss
            shares_by_risk = int(risk_amount / risk_per_share)
            shares_by_max = int(max_investment / entry_price)
            return min(shares_by_risk, shares_by_max)
        else:
            # 단순 최대 투자금 기반
            return int(max_investment / entry_price)

    # 조건명 한글 매핑
    CONDITION_NAMES_KR = {
        # 상한가 전략 (limit_up)
        'recent_limit_up': '최근 상한가 기록',
        'price_support': '상한가 종가 지지',
        'consolidation': '박스권 횡보 형성',
        'volume_pattern': '거래량 감소 후 재증가',
        'box_breakout': '박스권 상단 돌파',

        # 돌파 전략 (breakout)
        'reference_candle': '기준봉 출현',
        'breakout': '기준봉 고가 돌파',
        'ma_alignment': '이동평균선 정배열',
        'volume_increase': '거래량 증가 동반',

        # 15분봉 전략 (minute15)
        'bullish': '양봉 마감',
        'long_candle_7pct': '7% 이상 장대양봉',
        'volume_spike_2x': '거래량 2배 이상 급등',
        'above_ma60': '60선 위 위치',
        'price_support_50pct': '장대양봉 50% 지지',

        # 30분봉 전략 (minute30)
        'price_above_ma60': '현재가 60선 위',
        'ma60_support': '60선 지지 확인',
        'bullish_candle': '양봉 마감',
    }

    def get_signal_reason(self, conditions: Dict[str, bool]) -> str:
        """
        신호 발생 사유 생성 (한글)

        Args:
            conditions: {조건명: 충족여부} 딕셔너리

        Returns:
            한글 사유 문자열
        """
        met_conditions = []
        for k, v in conditions.items():
            if v:
                # 한글 이름이 있으면 사용, 없으면 원본 사용
                kr_name = self.CONDITION_NAMES_KR.get(k, k)
                met_conditions.append(kr_name)
        return ", ".join(met_conditions)

    def get_params(self) -> Dict[str, Any]:
        """전략 파라미터 반환"""
        return self.params.copy()

    def set_params(self, params: Dict[str, Any]) -> None:
        """전략 파라미터 설정"""
        self.params.update(params)

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}(name='{self.name}')"


class StrategyManager:
    """전략 관리자 클래스"""

    def __init__(self):
        self.strategies: Dict[str, BaseStrategy] = {}

    def register(self, strategy: BaseStrategy) -> None:
        """전략 등록"""
        self.strategies[strategy.name] = strategy

    def get(self, name: str) -> Optional[BaseStrategy]:
        """전략 조회"""
        return self.strategies.get(name)

    def get_all(self) -> List[BaseStrategy]:
        """모든 전략 조회"""
        return list(self.strategies.values())

    def generate_all_signals(self, df: pd.DataFrame, code: str = "",
                             name: str = "") -> List[Signal]:
        """
        모든 전략으로 신호 생성

        Args:
            df: OHLCV DataFrame
            code: 종목 코드
            name: 종목명

        Returns:
            생성된 신호 리스트
        """
        signals = []
        for strategy in self.strategies.values():
            try:
                signal = strategy.generate_signal(df, code, name)
                if signal and strategy.validate_signal(signal):
                    signals.append(signal)
            except Exception as e:
                print(f"Error in strategy {strategy.name}: {e}")
        return signals


# 전역 전략 관리자
strategy_manager = StrategyManager()


def register_strategy(strategy: BaseStrategy) -> None:
    """전략 등록 헬퍼 함수"""
    strategy_manager.register(strategy)


def get_strategy(name: str) -> Optional[BaseStrategy]:
    """전략 조회 헬퍼 함수"""
    return strategy_manager.get(name)


def get_all_strategies() -> List[BaseStrategy]:
    """모든 등록된 전략 반환"""
    return strategy_manager.get_all()


# 전략 레지스트리 (하위 호환성)
STRATEGY_REGISTRY = strategy_manager.strategies
