# 퀀트 트레이딩 시스템 구현 계획서

## 프로젝트 개요
- **목표**: "주식공부.pdf" 기반 퀀트 트레이딩 시스템 구현
- **환경**: macOS (Apple Silicon M시리즈), Python 3.13.5
- **핵심 전략**: 15분봉 단타, 30분봉 60선 매매, 상한가 종가 지지 매매

---

## Phase 1: 프로젝트 환경 설정

### 1.1 디렉토리 구조 생성
```
Quant/
├── config/
│   ├── settings.py          # 전역 설정 (API 키, DB 경로 등)
│   └── constants.py         # 상수 정의 (이동평균 기간 등)
├── data/
│   ├── collector.py         # 데이터 수집 모듈
│   ├── database.py          # SQLite DB 관리
│   └── cache.py             # 데이터 캐싱
├── indicators/
│   ├── moving_average.py    # 이동평균선
│   ├── volume.py            # 거래량 지표
│   ├── candle_pattern.py    # 캔들 패턴 인식
│   └── support_resistance.py # 지지/저항선
├── strategies/
│   ├── base_strategy.py     # 전략 베이스 클래스
│   ├── minute15_strategy.py # 15분봉 단타 전략
│   ├── minute30_strategy.py # 30분봉 60선 전략
│   ├── limit_up_strategy.py # 상한가 종가 지지 전략
│   └── breakout_strategy.py # 기준봉 돌파 전략
├── screener/
│   ├── stock_screener.py    # 종목 스크리닝
│   └── filters.py           # 필터 조건들
├── backtest/
│   ├── backtester.py        # 백테스팅 엔진
│   └── performance.py       # 성과 분석
├── notification/
│   └── telegram_bot.py      # 텔레그램 알림
├── utils/
│   ├── logger.py            # 로깅
│   ├── validators.py        # 데이터 검증
│   └── helpers.py           # 유틸리티 함수
├── tests/
│   ├── test_indicators.py
│   ├── test_strategies.py
│   └── test_screener.py
├── db/
│   └── quant.db             # SQLite 데이터베이스
├── logs/
│   └── app.log              # 로그 파일
├── main.py                  # 메인 실행 파일
├── requirements.txt         # 의존성 패키지
└── README.md                # 프로젝트 설명
```

### 1.2 필수 패키지 설치
```
pandas>=2.0.0
numpy>=1.24.0
requests>=2.28.0
yfinance>=0.2.0
FinanceDataReader>=0.9.0
pykrx>=1.0.0
sqlite3 (내장)
schedule>=1.2.0
python-telegram-bot>=20.0
mplfinance>=0.12.0
ta>=0.10.0
python-dotenv>=1.0.0
aiohttp>=3.8.0
pytest>=7.0.0
```

---

## Phase 2: 데이터 수집 모듈 구현

### 2.1 데이터 소스 선정 (키움증권 API 대안)
- **1순위**: FinanceDataReader (무료, 일봉/분봉 지원)
- **2순위**: pykrx (한국거래소 데이터)
- **3순위**: yfinance (해외주식, 백업용)

### 2.2 수집 데이터 종류
| 데이터 | 주기 | 보관기간 | 용도 |
|--------|------|----------|------|
| 일봉 OHLCV | 일 1회 | 2년 | 이동평균, 추세 분석 |
| 15분봉 | 실시간 | 3개월 | 15분봉 단타 전략 |
| 30분봉 | 실시간 | 3개월 | 30분봉 60선 전략 |
| 거래대금 순위 | 일 1회 | 1년 | 종목 스크리닝 |
| 상한가 종목 | 일 1회 | 1년 | 상한가 전략 |
| 52주 신고가 | 일 1회 | 1년 | 돌파 전략 |

### 2.3 데이터베이스 스키마
```sql
-- 종목 마스터
CREATE TABLE stocks (
    code TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    market TEXT,  -- KOSPI, KOSDAQ
    sector TEXT,
    listing_date DATE,
    updated_at TIMESTAMP
);

-- 일봉 데이터
CREATE TABLE daily_ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    date DATE NOT NULL,
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    value REAL,  -- 거래대금
    UNIQUE(code, date)
);

-- 분봉 데이터
CREATE TABLE minute_ohlcv (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    datetime TIMESTAMP NOT NULL,
    timeframe INTEGER,  -- 1, 3, 5, 15, 30
    open REAL,
    high REAL,
    low REAL,
    close REAL,
    volume INTEGER,
    UNIQUE(code, datetime, timeframe)
);

-- 상한가 기록
CREATE TABLE limit_up_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    date DATE NOT NULL,
    close_price REAL,
    volume INTEGER,
    consecutive_days INTEGER DEFAULT 1,
    UNIQUE(code, date)
);

-- 매매 신호
CREATE TABLE signals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT NOT NULL,
    datetime TIMESTAMP NOT NULL,
    strategy TEXT NOT NULL,
    signal_type TEXT,  -- BUY, SELL
    price REAL,
    reason TEXT,
    executed INTEGER DEFAULT 0
);

-- 인덱스 생성
CREATE INDEX idx_daily_code_date ON daily_ohlcv(code, date);
CREATE INDEX idx_minute_code_datetime ON minute_ohlcv(code, datetime);
CREATE INDEX idx_signals_datetime ON signals(datetime);
```

---

## Phase 3: 기술적 지표 계산 모듈

### 3.1 이동평균선 (moving_average.py)
```python
# 구현할 함수들
def calculate_sma(data, period)          # 단순이동평균
def calculate_ema(data, period)          # 지수이동평균
def get_ma_status(price, ma5, ma20, ma60, ma120, ma240)  # 정배열/역배열 판단
def detect_golden_cross(ma_short, ma_long)   # 골든크로스 감지
def detect_dead_cross(ma_short, ma_long)     # 데드크로스 감지
def calculate_ma_divergence(price, ma)       # 이격도 계산
```

### 3.2 거래량 지표 (volume.py)
```python
def calculate_volume_ma(volume, period)      # 거래량 이동평균
def calculate_volume_ratio(volume, ma_volume) # 거래량 비율
def detect_volume_spike(volume, threshold=2.0) # 거래량 급등 감지
def is_accumulation_phase(df, lookback=10)   # 매집 구간 판단
def detect_climax_volume(df)                 # 클라이맥스 거래량 감지
```

### 3.3 캔들 패턴 (candle_pattern.py)
```python
def calculate_candle_body(open, close)       # 몸통 크기
def calculate_upper_shadow(high, open, close) # 윗꼬리
def calculate_lower_shadow(low, open, close)  # 아랫꼬리
def is_bullish(open, close)                  # 양봉 여부
def is_bearish(open, close)                  # 음봉 여부

# 패턴 인식
def detect_hammer(row)                       # 망치형
def detect_inverted_hammer(row)              # 역망치형
def detect_doji(row, threshold=0.1)          # 도지
def detect_engulfing_bullish(prev, curr)     # 상승 잉컬핑
def detect_engulfing_bearish(prev, curr)     # 하락 잉컬핑
def detect_long_bullish_candle(row, threshold=0.05)  # 장대양봉
def detect_long_bearish_candle(row, threshold=0.05)  # 장대음봉
```

### 3.4 지지/저항선 (support_resistance.py)
```python
def find_pivot_points(df)                    # 피봇 포인트
def find_support_levels(df, lookback=20)     # 지지선 탐색
def find_resistance_levels(df, lookback=20)  # 저항선 탐색
def is_near_support(price, support, threshold=0.02)   # 지지선 근접 여부
def is_near_resistance(price, resistance, threshold=0.02) # 저항선 근접 여부
def detect_support_break(price, support)     # 지지선 이탈 감지
def detect_resistance_break(price, resistance) # 저항선 돌파 감지
```

---

## Phase 4: 매매 전략 구현

### 4.1 베이스 전략 클래스 (base_strategy.py)
```python
class BaseStrategy:
    def __init__(self, name, params)
    def generate_signal(self, df) -> Signal
    def calculate_entry_price(self, df) -> float
    def calculate_stop_loss(self, df, entry_price) -> float
    def calculate_take_profit(self, df, entry_price) -> float
    def validate_signal(self, signal) -> bool
    def get_position_size(self, capital, risk_percent) -> int
```

### 4.2 15분봉 단타 전략 (minute15_strategy.py)
```python
# PDF 기준: 15분봉 7~10% 장대양봉 + 50% 지지

class Minute15Strategy(BaseStrategy):
    매수 조건:
    1. 15분봉에서 7% 이상 장대양봉 출현
    2. 거래량 >= 전일 동시간대 2배
    3. 현재가 >= 장대양봉 몸통 50% 지지
    4. 60선(=일봉 10일선) 위에 위치

    손절 조건:
    - 장대양봉 저가 이탈
    - 60선 이탈

    익절 조건:
    - 60선 대비 이격 10% 이상
    - 윗꼬리 긴 음봉 출현
```

### 4.3 30분봉 60선 전략 (minute30_strategy.py)
```python
# PDF 기준: 30분봉 60선 지지 매매 (60선 = 일봉 5일선)

class Minute30Strategy(BaseStrategy):
    매수 조건:
    1. 30분봉 종가 >= 60선
    2. 이전 캔들이 60선 터치 후 반등 (지지 확인)
    3. 거래량 증가 동반
    4. 양봉 마감

    손절 조건:
    - 30분봉 종가 < 60선
    - 돌파 캔들 저가 이탈

    익절 조건:
    - 60선 대비 이격률 10% 이상
    - 장대음봉 출현
```

### 4.4 상한가 종가 지지 전략 (limit_up_strategy.py)
```python
# PDF 기준: 상한가 후 3~5일 박스권 조정 → 돌파 매수

class LimitUpStrategy(BaseStrategy):
    매수 조건:
    1. 최근 5일 내 상한가 기록
    2. 상한가 종가 부근 ±3% 지지 확인
    3. 3~5일간 박스권 횡보
    4. 거래량 감소 후 재증가 신호
    5. 박스권 상단 돌파

    손절 조건:
    - 상한가 종가선 -5% 이탈
    - 박스권 하단 이탈

    익절 조건:
    - 신고가 갱신 후 음봉 출현
    - 거래량 급감
```

### 4.5 기준봉 돌파 전략 (breakout_strategy.py)
```python
# PDF 기준: 매집 구간 → 기준봉 출현 → 매수

class BreakoutStrategy(BaseStrategy):
    매수 조건:
    1. 매집 구간 확인 (10일 이상 박스권 횡보)
    2. 당일 장대양봉 5% 이상
    3. 거래량 >= 매집구간 평균의 3배
    4. 20일선 돌파
    5. 종가 > 박스권 상단

    손절 조건:
    - 5일선 이탈
    - 기준봉 저가 이탈

    익절 조건:
    - 목표가 도달 (박스권 높이만큼)
    - 장대음봉 출현
```

---

## Phase 5: 종목 스크리닝 모듈

### 5.1 필터 조건 (filters.py)
```python
# 거래량 필터
def filter_volume_spike(df, threshold=2.0)       # 거래량 급등
def filter_volume_above_ma(df, ma_period=20)     # 거래량 이평 이상

# 가격 필터
def filter_price_above_ma(df, ma_period)         # 이동평균선 이상
def filter_golden_cross(df)                      # 골든크로스 발생
def filter_near_52week_high(df, threshold=0.95)  # 52주 신고가 근접
def filter_breakout_box(df, lookback=20)         # 박스권 돌파

# 상승률 필터
def filter_daily_change(df, min_change=0.05)     # 일간 상승률
def filter_limit_up(df)                          # 상한가 종목

# 복합 필터
def filter_accumulation_breakout(df)             # 매집 후 돌파
def filter_limit_up_consolidation(df)            # 상한가 후 조정
```

### 5.2 일일 스크리닝 루틴 (stock_screener.py)
```python
class StockScreener:
    def run_morning_screening(self)    # 08:30 - 장 시작 전
        - 전일 상한가 종목
        - 시간외 급등 종목
        - 52주 신고가 근접 종목

    def run_realtime_screening(self)   # 09:00~15:30 - 장중
        - 거래량 급등 + 5% 이상 상승
        - 15분봉/30분봉 신호 발생 종목
        - 박스권 돌파 종목

    def run_closing_screening(self)    # 15:30 - 장 마감 후
        - 당일 상한가 종목 기록
        - 거래대금 상위 분석
        - 익일 관심종목 선정
```

---

## Phase 6: 백테스팅 모듈

### 6.1 백테스터 (backtester.py)
```python
class Backtester:
    def __init__(self, strategy, initial_capital, commission)
    def run(self, df, start_date, end_date) -> BacktestResult
    def calculate_returns(self) -> float
    def calculate_max_drawdown(self) -> float
    def calculate_sharpe_ratio(self) -> float
    def calculate_win_rate(self) -> float
    def generate_report(self) -> dict
```

### 6.2 성과 지표 (performance.py)
```python
def calculate_total_return(trades)
def calculate_cagr(total_return, years)
def calculate_volatility(returns)
def calculate_sharpe_ratio(returns, risk_free_rate=0.03)
def calculate_sortino_ratio(returns, risk_free_rate=0.03)
def calculate_max_drawdown(equity_curve)
def calculate_win_rate(trades)
def calculate_profit_factor(trades)
def calculate_average_win_loss_ratio(trades)
```

---

## Phase 7: 알림 시스템

### 7.1 텔레그램 봇 (telegram_bot.py)
```python
class TelegramNotifier:
    def __init__(self, token, chat_id)
    def send_signal(self, signal)          # 매매 신호 알림
    def send_daily_report(self, report)    # 일일 리포트
    def send_error(self, error)            # 에러 알림

# 메시지 포맷
"""
🔔 [매수 신호]
종목: 삼성전자 (005930)
전략: 30분봉 60선 지지
현재가: 72,500원
진입가: 72,000원
손절가: 70,800원 (-1.7%)
목표가: 79,200원 (+10%)
발생시간: 2024-01-15 10:30:00
"""
```

---

## Phase 8: 메인 실행 및 스케줄링

### 8.1 메인 실행 파일 (main.py)
```python
def main():
    1. 설정 로드
    2. DB 연결
    3. 데이터 업데이트
    4. 스크리닝 실행
    5. 전략별 신호 생성
    6. 알림 발송
    7. 로그 기록

# 스케줄링
schedule.every().day.at("08:30").do(morning_routine)    # 장전 스크리닝
schedule.every(15).minutes.do(realtime_check)          # 장중 모니터링
schedule.every().day.at("15:40").do(closing_routine)   # 장후 정리
schedule.every().day.at("18:00").do(daily_data_update) # 일봉 업데이트
```

---

## Phase 9: 테스트 및 검증

### 9.1 단위 테스트
```python
# test_indicators.py
- test_sma_calculation()
- test_golden_cross_detection()
- test_candle_pattern_recognition()
- test_volume_spike_detection()

# test_strategies.py
- test_minute15_signal_generation()
- test_minute30_signal_generation()
- test_limit_up_signal_generation()
- test_stop_loss_calculation()

# test_screener.py
- test_volume_filter()
- test_price_filter()
- test_combined_screening()
```

### 9.2 통합 테스트
- 데이터 수집 → 지표 계산 → 신호 생성 파이프라인
- 백테스트 전체 프로세스
- 알림 발송 테스트

### 9.3 백테스트 검증
- 각 전략별 최소 1년 데이터로 백테스트
- 승률 50% 이상, MDD 20% 이하 목표
- 손익비 1.5:1 이상 목표

---

## 구현 우선순위 및 의존성

```
Phase 1 (환경설정)
    ↓
Phase 2 (데이터수집) ← 모든 후속 작업의 기반
    ↓
Phase 3 (지표계산) ← 전략 구현의 기반
    ↓
Phase 4 (전략구현) + Phase 5 (스크리닝) ← 병렬 진행 가능
    ↓
Phase 6 (백테스팅) ← 전략 검증
    ↓
Phase 7 (알림) + Phase 8 (메인) ← 병렬 진행 가능
    ↓
Phase 9 (테스트) ← 전체 검증
```

---

## 리스크 관리 규칙

### 자금 관리
- 1회 매매 최대 투자금: 총 자본의 10%
- 일일 최대 손실: 총 자본의 3%
- 동시 보유 종목: 최대 5종목

### 손절 규칙
- 진입가 대비 -3% 무조건 손절
- 전략별 손절 조건 충족 시 즉시 손절
- 장 마감 10분 전 미익절 종목 정리

### 익절 규칙
- 목표가 도달 시 50% 익절
- 추가 상승 시 트레일링 스탑 적용
- 음봉 출현 시 나머지 익절

---

## 예상 파일 목록 (총 25개 파일)

1. config/settings.py
2. config/constants.py
3. data/collector.py
4. data/database.py
5. data/cache.py
6. indicators/moving_average.py
7. indicators/volume.py
8. indicators/candle_pattern.py
9. indicators/support_resistance.py
10. strategies/base_strategy.py
11. strategies/minute15_strategy.py
12. strategies/minute30_strategy.py
13. strategies/limit_up_strategy.py
14. strategies/breakout_strategy.py
15. screener/stock_screener.py
16. screener/filters.py
17. backtest/backtester.py
18. backtest/performance.py
19. notification/telegram_bot.py
20. utils/logger.py
21. utils/validators.py
22. utils/helpers.py
23. tests/test_indicators.py
24. tests/test_strategies.py
25. main.py
