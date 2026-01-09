"""
퀀트 트레이딩 시스템 상수 정의
PDF "주식공부" 기반 매매 전략 파라미터
"""

from enum import Enum
from dataclasses import dataclass
from typing import Tuple

# ============================================================
# 이동평균선 기간 (PDF 기준)
# ============================================================

class MAPeriod:
    """이동평균선 기간 상수"""
    MA5 = 5       # 단타 매매선, 투자자 평균단가
    MA10 = 10     # 단기 추세
    MA20 = 20     # 중기 추세, 세력선
    MA60 = 60     # 수급선 (3개월)
    MA120 = 120   # 경기선 (6개월)
    MA240 = 240   # 생명선 (1년)
    MA400 = 400   # 장기 추세선

    # 분봉에서의 이동평균선 (30분봉 기준)
    # 30분봉 60선 = 일봉 5일선
    # 30분봉 120선 = 일봉 10일선
    MINUTE30_MA60 = 60
    MINUTE30_MA120 = 120

    # 모든 기간 리스트
    ALL_PERIODS = [MA5, MA10, MA20, MA60, MA120, MA240]


# ============================================================
# 거래량 관련 상수 (PDF 기준)
# ============================================================

class VolumeThreshold:
    """거래량 임계값"""
    # 거래량 급등 기준 (전일 대비 배수)
    SPIKE_RATIO = 2.0

    # 기준봉 거래량 (매집구간 평균 대비)
    BREAKOUT_RATIO = 3.0

    # 거래량 감소 기준
    DECLINE_RATIO = 0.5

    # 매집 구간 거래량 변동 허용 범위
    ACCUMULATION_VARIANCE = 0.3


# ============================================================
# 캔들 패턴 관련 상수 (PDF 기준)
# ============================================================

class CandleThreshold:
    """캔들 패턴 임계값"""
    # 장대양봉/장대음봉 기준 (5% 이상)
    LONG_CANDLE_RATIO = 0.05

    # 15분봉 단타 장대양봉 기준 (7% 이상)
    MINUTE15_LONG_CANDLE_RATIO = 0.07

    # 도지 캔들 몸통 비율 (1% 이하)
    DOJI_BODY_RATIO = 0.01

    # 망치형/역망치형 꼬리 비율 (몸통의 2배 이상)
    HAMMER_SHADOW_RATIO = 2.0

    # 잉컬핑 패턴 최소 비율
    ENGULFING_MIN_RATIO = 1.5


# ============================================================
# 지지/저항선 관련 상수
# ============================================================

class SupportResistance:
    """지지/저항선 관련 상수"""
    # 지지/저항선 근접 판단 기준
    NEAR_THRESHOLD = 0.02  # 2%

    # 지지선 이탈 기준
    BREAK_THRESHOLD = 0.01  # 1%

    # 박스권 판단 기간
    BOX_LOOKBACK_DAYS = 20

    # 박스권 허용 변동 범위
    BOX_VARIANCE = 0.05  # 5%


# ============================================================
# 15분봉 단타 전략 파라미터 (PDF 기준)
# ============================================================

@dataclass(frozen=True)
class Minute15StrategyParams:
    """15분봉 단타 전략 파라미터"""
    # 매수 조건
    long_candle_threshold: float = 0.07      # 7% 이상 장대양봉
    volume_spike_ratio: float = 2.0          # 거래량 2배 이상
    support_level: float = 0.50              # 캔들 50% 지지

    # 손절 조건
    candle_low_break: bool = True            # 장대양봉 저가 이탈
    ma60_break: bool = True                  # 60선 이탈

    # 익절 조건
    ma_divergence_threshold: float = 0.10    # 60선 이격 10%


# ============================================================
# 30분봉 60선 전략 파라미터 (PDF 기준)
# ============================================================

@dataclass(frozen=True)
class Minute30StrategyParams:
    """30분봉 60선 전략 파라미터"""
    # 매수 조건: 60선 지지 + 거래량 + 양봉

    # 손절 조건
    ma60_break: bool = True                  # 60선 이탈
    breakout_candle_low_break: bool = True   # 돌파 캔들 저가 이탈

    # 익절 조건
    ma_divergence_threshold: float = 0.10    # 60선 이격 10%


# ============================================================
# 상한가 종가 지지 전략 파라미터 (PDF 기준)
# ============================================================

@dataclass(frozen=True)
class LimitUpStrategyParams:
    """상한가 종가 지지 전략 파라미터"""
    # 상한가 기준 (코스피: 30%, 코스닥: 30%)
    limit_up_threshold: float = 0.29         # 29% 이상

    # 매수 조건
    lookback_days: int = 5                   # 최근 5일 내 상한가
    support_threshold: float = 0.03          # 상한가 종가 ±3% 지지
    consolidation_days: Tuple[int, int] = (3, 5)  # 3~5일 박스권 조정

    # 손절 조건
    support_break_threshold: float = 0.05    # 상한가 종가선 -5%


# ============================================================
# 기준봉 돌파 전략 파라미터 (PDF 기준)
# ============================================================

@dataclass(frozen=True)
class BreakoutStrategyParams:
    """기준봉 돌파 전략 파라미터"""
    # 매집 구간 조건
    min_accumulation_days: int = 10          # 최소 10일 횡보
    box_variance: float = 0.05               # 박스권 변동 5% 이내

    # 기준봉 조건
    reference_candle_threshold: float = 0.05  # 5% 이상 장대양봉 (기준봉)
    long_candle_threshold: float = 0.05      # 5% 이상 장대양봉 (별칭)
    volume_spike_ratio: float = 3.0          # 거래량 3배 이상
    ma20_breakout: bool = True               # 20일선 돌파

    # 탐색 기간
    lookback_days: int = 15                  # 기준봉 탐색 기간
    consolidation_days: tuple = (3, 10)      # 조정 기간 범위

    # 돌파 조건
    breakout_threshold: float = 0.01         # 돌파 판정 임계값 (1%)

    # 손절 조건
    ma5_break: bool = True                   # 5일선 이탈
    breakout_candle_low_break: bool = True   # 기준봉 저가 이탈


# ============================================================
# 골든크로스/데드크로스 설정
# ============================================================

class CrossSignal:
    """크로스 신호 설정"""
    # 기본 크로스 조합 (5일선 vs 20일선)
    DEFAULT_SHORT_MA = MAPeriod.MA5
    DEFAULT_LONG_MA = MAPeriod.MA20

    # 추가 크로스 조합
    CROSS_PAIRS = [
        (MAPeriod.MA5, MAPeriod.MA20),
        (MAPeriod.MA20, MAPeriod.MA60),
        (MAPeriod.MA60, MAPeriod.MA120),
    ]


# ============================================================
# 시장 관련 상수
# ============================================================

class Market(Enum):
    """시장 구분"""
    KOSPI = 'KOSPI'
    KOSDAQ = 'KOSDAQ'


class SignalType(Enum):
    """신호 유형"""
    BUY = 'BUY'
    SELL = 'SELL'
    HOLD = 'HOLD'


class StrategyName(Enum):
    """전략 이름"""
    MINUTE15 = 'minute15'          # 15분봉 단타
    MINUTE30 = 'minute30'          # 30분봉 60선
    LIMIT_UP = 'limit_up'          # 상한가 종가 지지
    BREAKOUT = 'breakout'          # 기준봉 돌파
    GOLDEN_CROSS = 'golden_cross'  # 골든크로스


# ============================================================
# 키움증권 코드 (PDF 기준 - 참고용)
# ============================================================

class KiwoomCode:
    """키움증권 HTS 코드 (참고용)"""
    SECTOR_THEME = '0171'          # 섹터/테마 종목 조회
    LIMIT_UP_RANKING = '0162'      # 상한가 및 상승 상위
    VOLUME_RANKING = '0184'        # 거래대금(거래량) 순위
    REALTIME_RANKING = '0198'      # 실시간 종목 조회 순위
    AFTER_HOURS = '1304'           # 시간외 단일가 순위
    PRE_MARKET = '0183'            # 장전 예상체결등락률 상위


# ============================================================
# 시간 관련 상수
# ============================================================

class TradingTime:
    """거래 시간 상수"""
    MARKET_OPEN = '09:00'
    MARKET_CLOSE = '15:30'
    PRE_MARKET_START = '08:30'
    AFTER_HOURS_END = '18:00'

    # 동시호가
    OPENING_AUCTION_START = '08:30'
    OPENING_AUCTION_END = '09:00'
    CLOSING_AUCTION_START = '15:20'
    CLOSING_AUCTION_END = '15:30'
