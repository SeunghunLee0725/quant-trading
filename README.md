# Quant Trading System

한국 주식 퀀트 트레이딩 시스템 - 종목 스크리닝, 백테스트, 자동 매매

## 주요 기능

- **종목 스크리닝**: 다양한 필터와 전략으로 매수 후보 종목 탐색
- **백테스트**: 전략 성과 검증 (수익률, MDD, 승률 등)
- **실시간 대시보드**: Streamlit 기반 웹 UI
- **데이터 수집**: KOSPI/KOSDAQ 전 종목 일봉 데이터

## 전략

| 전략 | 설명 | 데이터 |
|-----|-----|-------|
| limit_up | 상한가 따라잡기 | 일봉 |
| breakout | 돌파 매매 | 일봉 |
| minute15 | 15분봉 단타 | 분봉 (실시간만) |
| minute30 | 30분봉 단타 | 분봉 (실시간만) |

## 설치

```bash
# 저장소 클론
git clone https://github.com/YOUR_USERNAME/quant-trading.git
cd quant-trading

# 가상환경 생성 및 활성화
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 의존성 설치
pip install -r requirements.txt

# 환경변수 설정
cp .env.example .env
# .env 파일을 편집하여 API 키 설정
```

## 실행

```bash
# 대시보드 실행
streamlit run dashboard.py

# 데이터 수집
python main.py --mode collect

# 스크리닝
python main.py --mode screen
```

## 환경변수

| 변수 | 설명 |
|-----|-----|
| KIS_APP_KEY | 한국투자증권 API App Key |
| KIS_APP_SECRET | 한국투자증권 API Secret |
| KIS_ACCOUNT_NO | 계좌번호 |
| TELEGRAM_BOT_TOKEN | 텔레그램 알림용 (선택) |
| TELEGRAM_CHAT_ID | 텔레그램 채팅 ID (선택) |

## Streamlit Cloud 배포

1. GitHub에 저장소 생성 및 코드 푸시
2. [Streamlit Cloud](https://streamlit.io/cloud) 접속
3. "New app" 클릭
4. GitHub 저장소 연결
5. Main file path: `dashboard.py` 설정
6. Secrets에 환경변수 추가 (선택)
7. Deploy 클릭

## 기술 스택

- **언어**: Python 3.10+
- **UI**: Streamlit
- **데이터**: pandas, numpy
- **데이터 수집**: pykrx, FinanceDataReader, 한국투자증권 API
- **DB**: SQLite (aiosqlite)

## 라이선스

MIT License
