# AGENTS.md — Quant

한국 주식 퀀트 트레이딩 시스템 (종목 스크리닝, 백테스트, 자동매매)

## 기술 스택

```yaml
Language: Python 3.10+
Dashboard: Streamlit
Data: pandas, KOSPI/KOSDAQ 전종목
Notification: Telegram Bot
Database: SQLite (로컬)
```

## 핵심 규칙

### MUST
1. 백테스트 검증 완료 후 전략 적용
2. 리스크 관리 포함 (MDD 제한, 손절가)
3. API 키는 .env로만 관리
4. 모든 전략에 수수료/슬리피지 반영

### MUST NOT
1. .env 파일 커밋 금지 (API 키 포함)
2. 실매매 로직 무단 변경 금지
3. API 호출 횟수 제한 초과 금지 (한투 API rate limit 주의)

## 디렉토리 구조

```
Quant/
├── main.py              # 메인 엔트리포인트
├── dashboard.py         # Streamlit 대시보드
├── strategies/          # 전략 모듈
│   ├── base_strategy.py
│   ├── limit_up_strategy.py    # 상한가 따라잡기
│   ├── breakout_strategy.py    # 돌파 매매
│   ├── minute15_strategy.py    # 15분봉
│   └── minute30_strategy.py    # 30분봉
├── screener/            # 종목 스크리닝
├── indicators/          # 기술지표 (MA, 거래량, 캔들패턴)
├── backtest/            # 백테스트 엔진
├── notification/        # Telegram 알림
├── config/              # 설정
├── tests/               # 테스트 (59 tests)
└── requirements.txt
```

## 개발 명령어

```bash
pip install -r requirements.txt
streamlit run dashboard.py
python main.py --mode collect   # 데이터 수집
python main.py --mode screen    # 스크리닝
python main.py --mode backtest  # 백테스트
pytest tests/ -v
```

## 고도화 로드맵

### 단기
- [ ] 기존 59개 테스트 실행 검증
- [ ] 일봉 전략 백테스트 결과 분석

### 중기
- [ ] 분봉 전략(15분/30분) 완성
- [ ] 리스크 관리 고도화 (포지션 사이징, 포트폴리오 분산)
- [ ] 실시간 데이터 파이프라인

### 장기
- [ ] 자동매매 파이프라인 (한투 API 연동)
- [ ] 머신러닝 기반 시그널 생성

## 도메인 지식

- KOSPI/KOSDAQ: 한국 주식시장
- 상한가: 일일 가격 제한 +30%
- 돌파매매: 전고점/저항선 돌파 시 매수
- 분봉 전략: 15분/30분 단위 단타 매매
- MDD: Maximum Drawdown (최대 낙폭)
- 이동평균(MA), 거래량, 지지/저항선, 캔들패턴
