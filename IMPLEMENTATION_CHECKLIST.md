# 퀀트 프로그램 구현 체크리스트

## 구현 순서 및 의존성 맵

```
[Phase 1] 환경설정
    │
    ▼
[Phase 2] 데이터 수집 ◄── 모든 후속 작업의 기반
    │
    ▼
[Phase 3] 지표 계산 ◄── 전략의 기반
    │
    ├──────────────────┐
    ▼                  ▼
[Phase 4] 전략      [Phase 5] 스크리닝  (병렬 가능)
    │                  │
    └────────┬─────────┘
             ▼
[Phase 6] 백테스팅 ◄── 전략 검증
    │
    ├──────────────────┐
    ▼                  ▼
[Phase 7] 알림      [Phase 8] 메인     (병렬 가능)
    │                  │
    └────────┬─────────┘
             ▼
[Phase 9] 테스트 ◄── 최종 검증
```

---

## Phase 1: 프로젝트 환경 설정

### 1.1 디렉토리 구조 생성
- [ ] config/ 폴더 생성
- [ ] data/ 폴더 생성
- [ ] indicators/ 폴더 생성
- [ ] strategies/ 폴더 생성
- [ ] screener/ 폴더 생성
- [ ] backtest/ 폴더 생성
- [ ] notification/ 폴더 생성
- [ ] utils/ 폴더 생성
- [ ] tests/ 폴더 생성
- [ ] db/ 폴더 생성
- [ ] logs/ 폴더 생성
- [ ] 각 폴더에 __init__.py 생성

### 1.2 requirements.txt 작성 및 설치
- [ ] requirements.txt 파일 작성
- [ ] 패키지 설치 테스트
- [ ] 버전 호환성 확인

### 1.3 설정 파일 작성
- [ ] config/settings.py
  - [ ] DB 경로 설정
  - [ ] API 키 설정 (환경변수)
  - [ ] 로그 설정
  - [ ] 텔레그램 설정
- [ ] config/constants.py
  - [ ] 이동평균 기간 상수
  - [ ] 거래량 임계값 상수
  - [ ] 캔들 패턴 임계값
  - [ ] 리스크 관리 상수

---

## Phase 2: 데이터 수집 모듈

### 2.1 데이터베이스 모듈 (data/database.py)
- [ ] DatabaseManager 클래스 생성
- [ ] 테이블 생성 함수
  - [ ] stocks 테이블
  - [ ] daily_ohlcv 테이블
  - [ ] minute_ohlcv 테이블
  - [ ] limit_up_history 테이블
  - [ ] signals 테이블
- [ ] CRUD 함수 구현
  - [ ] insert_stock()
  - [ ] insert_daily_ohlcv()
  - [ ] insert_minute_ohlcv()
  - [ ] get_daily_ohlcv()
  - [ ] get_minute_ohlcv()
  - [ ] get_stocks_by_market()
- [ ] 인덱스 생성
- [ ] 연결 풀링 (선택사항)

### 2.2 데이터 수집 모듈 (data/collector.py)
- [ ] DataCollector 클래스 생성
- [ ] 종목 리스트 수집
  - [ ] get_kospi_stocks()
  - [ ] get_kosdaq_stocks()
  - [ ] update_stock_master()
- [ ] 일봉 데이터 수집
  - [ ] fetch_daily_ohlcv(code, start_date, end_date)
  - [ ] update_all_daily_ohlcv()
- [ ] 분봉 데이터 수집 (가능한 경우)
  - [ ] fetch_minute_ohlcv(code, timeframe)
- [ ] 상한가 종목 수집
  - [ ] fetch_limit_up_stocks(date)
- [ ] 거래대금 상위 수집
  - [ ] fetch_top_volume_stocks(date, top_n)
- [ ] 에러 핸들링 및 재시도 로직

### 2.3 로깅 시스템 (utils/logger.py)
- [ ] Logger 클래스 생성
- [ ] 파일 로깅 설정
- [ ] 콘솔 로깅 설정
- [ ] 로그 레벨 설정 (DEBUG, INFO, WARNING, ERROR)
- [ ] 로그 포맷 설정
- [ ] 로그 로테이션 설정

### 2.4 유틸리티 함수 (utils/helpers.py)
- [ ] 날짜 관련 함수
  - [ ] get_trading_days()
  - [ ] is_trading_day()
  - [ ] get_last_trading_day()
- [ ] 데이터 변환 함수
  - [ ] df_to_dict()
  - [ ] dict_to_df()

### 2.5 데이터 검증 (utils/validators.py)
- [ ] validate_ohlcv_data()
- [ ] validate_stock_code()
- [ ] validate_date_range()
- [ ] check_data_completeness()

---

## Phase 3: 기술적 지표 계산 모듈

### 3.1 이동평균선 (indicators/moving_average.py)
- [ ] calculate_sma(data, period)
  - [ ] 입력: Series/DataFrame, 기간
  - [ ] 출력: Series
  - [ ] 엣지케이스: 데이터 부족 시 NaN
- [ ] calculate_ema(data, period)
  - [ ] 지수이동평균 계산
- [ ] calculate_all_ma(df)
  - [ ] 5, 10, 20, 60, 120, 240일선 일괄 계산
- [ ] get_ma_status(price, ma_dict)
  - [ ] 정배열/역배열/혼조 판단
  - [ ] 반환: 'BULLISH', 'BEARISH', 'MIXED'
- [ ] detect_golden_cross(ma_short, ma_long)
  - [ ] 골든크로스 발생 여부
  - [ ] 반환: bool
- [ ] detect_dead_cross(ma_short, ma_long)
  - [ ] 데드크로스 발생 여부
- [ ] calculate_ma_divergence(price, ma)
  - [ ] 이격도 계산 ((price - ma) / ma * 100)

### 3.2 거래량 지표 (indicators/volume.py)
- [ ] calculate_volume_ma(volume, period)
  - [ ] 거래량 이동평균
- [ ] calculate_volume_ratio(current_vol, ma_vol)
  - [ ] 거래량 비율 (배수)
- [ ] detect_volume_spike(df, threshold=2.0)
  - [ ] 거래량 급등 감지
  - [ ] threshold: 평균 대비 배수
- [ ] is_accumulation_phase(df, lookback=10)
  - [ ] 매집 구간 판단
  - [ ] 조건: 가격 횡보 + 거래량 감소
- [ ] detect_climax_volume(df)
  - [ ] 클라이맥스(극대) 거래량 감지
- [ ] calculate_obv(df)
  - [ ] On-Balance Volume (선택)

### 3.3 캔들 패턴 (indicators/candle_pattern.py)
- [ ] 기본 계산 함수
  - [ ] calculate_candle_body(open, close)
  - [ ] calculate_upper_shadow(high, open, close)
  - [ ] calculate_lower_shadow(low, open, close)
  - [ ] calculate_candle_range(high, low)
  - [ ] is_bullish(open, close)
  - [ ] is_bearish(open, close)
- [ ] 단일 캔들 패턴
  - [ ] detect_hammer(row, body_ratio=0.3)
  - [ ] detect_inverted_hammer(row, body_ratio=0.3)
  - [ ] detect_doji(row, threshold=0.1)
  - [ ] detect_long_bullish_candle(row, threshold=0.05)
  - [ ] detect_long_bearish_candle(row, threshold=0.05)
  - [ ] detect_spinning_top(row)
- [ ] 복합 캔들 패턴
  - [ ] detect_engulfing_bullish(prev, curr)
  - [ ] detect_engulfing_bearish(prev, curr)
  - [ ] detect_morning_star(candles)
  - [ ] detect_evening_star(candles)
- [ ] 통합 패턴 분석
  - [ ] analyze_candle_pattern(df)
    - [ ] 모든 패턴 검사 후 결과 반환

### 3.4 지지/저항선 (indicators/support_resistance.py)
- [ ] find_pivot_points(df)
  - [ ] 피봇 포인트 계산 (P, R1, R2, S1, S2)
- [ ] find_local_minima(df, window=5)
  - [ ] 지역 최저점 탐색
- [ ] find_local_maxima(df, window=5)
  - [ ] 지역 최고점 탐색
- [ ] find_support_levels(df, lookback=20)
  - [ ] 지지선 레벨 탐색 (클러스터링)
- [ ] find_resistance_levels(df, lookback=20)
  - [ ] 저항선 레벨 탐색
- [ ] is_near_support(price, support, threshold=0.02)
  - [ ] 지지선 근접 여부
- [ ] is_near_resistance(price, resistance, threshold=0.02)
  - [ ] 저항선 근접 여부
- [ ] detect_support_break(df, support)
  - [ ] 지지선 이탈 감지
- [ ] detect_resistance_break(df, resistance)
  - [ ] 저항선 돌파 감지
- [ ] find_box_range(df, lookback=20)
  - [ ] 박스권 범위 탐색

---

## Phase 4: 매매 전략 구현

### 4.1 베이스 전략 (strategies/base_strategy.py)
- [ ] Signal 데이터클래스
  - [ ] code: str
  - [ ] datetime: datetime
  - [ ] signal_type: str (BUY/SELL)
  - [ ] strategy: str
  - [ ] price: float
  - [ ] stop_loss: float
  - [ ] take_profit: float
  - [ ] reason: str
- [ ] BaseStrategy 추상 클래스
  - [ ] __init__(self, name, params)
  - [ ] generate_signal(self, df) -> Optional[Signal]
  - [ ] calculate_entry_price(self, df) -> float
  - [ ] calculate_stop_loss(self, df, entry_price) -> float
  - [ ] calculate_take_profit(self, df, entry_price) -> float
  - [ ] validate_signal(self, signal) -> bool
  - [ ] get_position_size(self, capital, risk_percent) -> int

### 4.2 15분봉 단타 전략 (strategies/minute15_strategy.py)
- [ ] Minute15Strategy 클래스
- [ ] 매수 조건 구현
  - [ ] check_long_candle(df, threshold=0.07)
  - [ ] check_volume_spike(df, threshold=2.0)
  - [ ] check_price_support(df, candle_50_percent)
  - [ ] check_above_ma60(df)
- [ ] 손절 조건 구현
  - [ ] check_candle_low_break(price, candle_low)
  - [ ] check_ma60_break(price, ma60)
- [ ] 익절 조건 구현
  - [ ] check_ma_divergence(price, ma60, threshold=0.10)
  - [ ] check_bearish_candle(df)
- [ ] generate_signal() 메서드 구현
- [ ] 파라미터 최적화 지원

### 4.3 30분봉 60선 전략 (strategies/minute30_strategy.py)
- [ ] Minute30Strategy 클래스
- [ ] 매수 조건 구현
  - [ ] check_price_above_ma60(close, ma60)
  - [ ] check_ma60_support(df)
  - [ ] check_volume_increase(df)
  - [ ] check_bullish_close(open, close)
- [ ] 손절 조건 구현
  - [ ] check_close_below_ma60(close, ma60)
  - [ ] check_breakout_candle_low_break(price, candle_low)
- [ ] 익절 조건 구현
  - [ ] check_ma_divergence_10_percent(price, ma60)
  - [ ] check_long_bearish_candle(df)
- [ ] generate_signal() 메서드 구현

### 4.4 상한가 종가 지지 전략 (strategies/limit_up_strategy.py)
- [ ] LimitUpStrategy 클래스
- [ ] 상한가 감지
  - [ ] detect_limit_up(df, threshold=0.29)
- [ ] 매수 조건 구현
  - [ ] check_recent_limit_up(df, days=5)
  - [ ] check_price_support(df, limit_up_close, threshold=0.03)
  - [ ] check_consolidation(df, days_range=(3,5))
  - [ ] check_volume_pattern(df)
  - [ ] check_box_breakout(df)
- [ ] 손절 조건 구현
  - [ ] check_support_break(price, limit_up_close, threshold=0.05)
  - [ ] check_box_low_break(price, box_low)
- [ ] 익절 조건 구현
  - [ ] check_new_high(df)
  - [ ] check_volume_decline(df)
- [ ] generate_signal() 메서드 구현

### 4.5 기준봉 돌파 전략 (strategies/breakout_strategy.py)
- [ ] BreakoutStrategy 클래스
- [ ] 매집 구간 감지
  - [ ] detect_accumulation(df, min_days=10)
  - [ ] calculate_box_range(df)
- [ ] 매수 조건 구현
  - [ ] check_long_bullish_candle(df, threshold=0.05)
  - [ ] check_volume_spike(df, threshold=3.0)
  - [ ] check_ma20_breakout(close, ma20)
  - [ ] check_close_above_box_high(close, box_high)
- [ ] 손절 조건 구현
  - [ ] check_ma5_break(close, ma5)
  - [ ] check_breakout_candle_low_break(price, candle_low)
- [ ] 익절 조건 구현
  - [ ] check_target_price(price, entry, box_height)
  - [ ] check_long_bearish_candle(df)
- [ ] generate_signal() 메서드 구현

---

## Phase 5: 종목 스크리닝 모듈

### 5.1 필터 함수 (screener/filters.py)
- [ ] 거래량 필터
  - [ ] filter_volume_spike(df, threshold=2.0)
  - [ ] filter_volume_above_ma(df, ma_period=20)
  - [ ] filter_volume_increase(df, days=3)
- [ ] 가격 필터
  - [ ] filter_price_above_ma(df, ma_period)
  - [ ] filter_price_range(df, min_price, max_price)
  - [ ] filter_golden_cross(df)
  - [ ] filter_near_52week_high(df, threshold=0.95)
  - [ ] filter_breakout_box(df, lookback=20)
- [ ] 상승률 필터
  - [ ] filter_daily_change(df, min_change=0.05)
  - [ ] filter_weekly_change(df, min_change)
  - [ ] filter_limit_up(df)
- [ ] 복합 필터
  - [ ] filter_accumulation_breakout(df)
  - [ ] filter_limit_up_consolidation(df)
  - [ ] filter_ma_alignment(df)

### 5.2 종목 스크리너 (screener/stock_screener.py)
- [ ] StockScreener 클래스
- [ ] 장전 스크리닝
  - [ ] run_morning_screening()
    - [ ] 전일 상한가 종목
    - [ ] 52주 신고가 근접 종목
    - [ ] 골든크로스 발생 종목
- [ ] 장중 스크리닝
  - [ ] run_realtime_screening()
    - [ ] 거래량 급등 + 상승 종목
    - [ ] 박스권 돌파 종목
- [ ] 장후 스크리닝
  - [ ] run_closing_screening()
    - [ ] 당일 상한가 종목 기록
    - [ ] 거래대금 상위 분석
- [ ] 결과 저장 및 알림
  - [ ] save_screening_result()
  - [ ] notify_screening_result()

---

## Phase 6: 백테스팅 모듈

### 6.1 성과 지표 (backtest/performance.py)
- [ ] 수익률 지표
  - [ ] calculate_total_return(trades)
  - [ ] calculate_cagr(total_return, years)
  - [ ] calculate_monthly_returns(equity_curve)
- [ ] 리스크 지표
  - [ ] calculate_volatility(returns)
  - [ ] calculate_max_drawdown(equity_curve)
  - [ ] calculate_calmar_ratio(cagr, max_dd)
- [ ] 리스크 조정 수익률
  - [ ] calculate_sharpe_ratio(returns, rf_rate=0.03)
  - [ ] calculate_sortino_ratio(returns, rf_rate=0.03)
- [ ] 매매 지표
  - [ ] calculate_win_rate(trades)
  - [ ] calculate_profit_factor(trades)
  - [ ] calculate_avg_win_loss_ratio(trades)
  - [ ] calculate_avg_holding_period(trades)
  - [ ] calculate_trade_frequency(trades)

### 6.2 백테스터 (backtest/backtester.py)
- [ ] Trade 데이터클래스
  - [ ] entry_date, exit_date
  - [ ] entry_price, exit_price
  - [ ] position_size, pnl
  - [ ] strategy, code
- [ ] Backtester 클래스
  - [ ] __init__(strategy, initial_capital, commission)
  - [ ] run(df, start_date, end_date) -> BacktestResult
  - [ ] _execute_entry(signal, capital)
  - [ ] _execute_exit(position, price, reason)
  - [ ] _update_equity(trades)
- [ ] BacktestResult 데이터클래스
  - [ ] trades: List[Trade]
  - [ ] equity_curve: pd.Series
  - [ ] metrics: dict
- [ ] 리포트 생성
  - [ ] generate_report() -> dict
  - [ ] plot_equity_curve()
  - [ ] plot_drawdown()

---

## Phase 7: 알림 시스템

### 7.1 텔레그램 봇 (notification/telegram_bot.py)
- [ ] TelegramNotifier 클래스
  - [ ] __init__(token, chat_id)
  - [ ] _validate_config()
- [ ] 메시지 전송
  - [ ] send_message(text)
  - [ ] send_signal(signal: Signal)
  - [ ] send_daily_report(report: dict)
  - [ ] send_error(error: Exception)
- [ ] 메시지 포맷팅
  - [ ] _format_signal_message(signal)
  - [ ] _format_report_message(report)
  - [ ] _format_error_message(error)
- [ ] 에러 핸들링
  - [ ] 재시도 로직
  - [ ] 연결 실패 처리

---

## Phase 8: 메인 실행

### 8.1 메인 파일 (main.py)
- [ ] 초기화
  - [ ] load_config()
  - [ ] setup_logging()
  - [ ] connect_database()
  - [ ] initialize_notifier()
- [ ] 일일 루틴
  - [ ] morning_routine()
    - [ ] 데이터 업데이트
    - [ ] 장전 스크리닝
    - [ ] 관심종목 알림
  - [ ] realtime_routine()
    - [ ] 실시간 모니터링
    - [ ] 신호 생성 및 알림
  - [ ] closing_routine()
    - [ ] 장후 데이터 정리
    - [ ] 일일 리포트 생성
- [ ] 스케줄링
  - [ ] schedule_jobs()
  - [ ] run_scheduler()
- [ ] CLI 인터페이스 (선택)
  - [ ] argparse 설정
  - [ ] 명령어 처리

---

## Phase 9: 테스트

### 9.1 지표 테스트 (tests/test_indicators.py)
- [ ] 이동평균선 테스트
  - [ ] test_sma_calculation()
  - [ ] test_ema_calculation()
  - [ ] test_golden_cross_detection()
  - [ ] test_dead_cross_detection()
- [ ] 거래량 테스트
  - [ ] test_volume_ma()
  - [ ] test_volume_spike_detection()
  - [ ] test_accumulation_detection()
- [ ] 캔들 패턴 테스트
  - [ ] test_hammer_detection()
  - [ ] test_engulfing_detection()
  - [ ] test_doji_detection()
- [ ] 지지/저항 테스트
  - [ ] test_support_detection()
  - [ ] test_resistance_detection()
  - [ ] test_box_range_detection()

### 9.2 전략 테스트 (tests/test_strategies.py)
- [ ] 15분봉 전략 테스트
  - [ ] test_minute15_buy_signal()
  - [ ] test_minute15_stop_loss()
  - [ ] test_minute15_take_profit()
- [ ] 30분봉 전략 테스트
  - [ ] test_minute30_buy_signal()
  - [ ] test_minute30_stop_loss()
- [ ] 상한가 전략 테스트
  - [ ] test_limit_up_detection()
  - [ ] test_limit_up_consolidation()
- [ ] 돌파 전략 테스트
  - [ ] test_breakout_signal()
  - [ ] test_box_breakout()

### 9.3 통합 테스트
- [ ] 데이터 파이프라인 테스트
  - [ ] test_data_collection_to_storage()
  - [ ] test_indicator_calculation_pipeline()
- [ ] 신호 생성 테스트
  - [ ] test_signal_generation_pipeline()
- [ ] 백테스트 검증
  - [ ] test_backtest_execution()
  - [ ] test_performance_calculation()

### 9.4 백테스트 검증 기준
- [ ] 각 전략별 최소 1년 데이터 백테스트
- [ ] 승률 50% 이상 확인
- [ ] 최대 낙폭(MDD) 20% 이하 확인
- [ ] 손익비 1.5:1 이상 확인
- [ ] 거래 횟수 통계적 유의성 확인 (최소 30회)

---

## 추가 고려사항

### 에러 핸들링
- [ ] 네트워크 에러 처리
- [ ] 데이터 누락 처리
- [ ] API 제한 처리
- [ ] 잘못된 입력 처리

### 성능 최적화
- [ ] 데이터 캐싱
- [ ] 쿼리 최적화
- [ ] 메모리 관리

### 문서화
- [ ] 코드 주석
- [ ] API 문서
- [ ] 사용자 가이드

---

## 예상 구현 파일 목록 (총 25개)

| 순서 | 파일 | 의존성 |
|------|------|--------|
| 1 | config/settings.py | - |
| 2 | config/constants.py | - |
| 3 | utils/logger.py | config |
| 4 | utils/helpers.py | - |
| 5 | utils/validators.py | - |
| 6 | data/database.py | config, utils |
| 7 | data/collector.py | database, utils |
| 8 | indicators/moving_average.py | - |
| 9 | indicators/volume.py | - |
| 10 | indicators/candle_pattern.py | - |
| 11 | indicators/support_resistance.py | - |
| 12 | strategies/base_strategy.py | indicators |
| 13 | strategies/minute15_strategy.py | base_strategy |
| 14 | strategies/minute30_strategy.py | base_strategy |
| 15 | strategies/limit_up_strategy.py | base_strategy |
| 16 | strategies/breakout_strategy.py | base_strategy |
| 17 | screener/filters.py | indicators |
| 18 | screener/stock_screener.py | filters, data |
| 19 | backtest/performance.py | - |
| 20 | backtest/backtester.py | performance, strategies |
| 21 | notification/telegram_bot.py | config |
| 22 | main.py | all modules |
| 23 | tests/test_indicators.py | indicators |
| 24 | tests/test_strategies.py | strategies |
| 25 | requirements.txt | - |

---

## 구현 시작 명령어

```bash
# 1. 디렉토리 구조 생성
cd /Users/lee_ai_labtop/dev/Quant
mkdir -p config data indicators strategies screener backtest notification utils tests db logs

# 2. __init__.py 파일 생성
touch config/__init__.py data/__init__.py indicators/__init__.py strategies/__init__.py screener/__init__.py backtest/__init__.py notification/__init__.py utils/__init__.py tests/__init__.py

# 3. 패키지 설치
pip install -r requirements.txt

# 4. 데이터베이스 초기화
python -c "from data.database import DatabaseManager; db = DatabaseManager(); db.create_tables()"

# 5. 테스트 실행
pytest tests/ -v
```
