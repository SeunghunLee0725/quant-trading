"""
퀀트 트레이딩 시스템 설정 파일
환경변수 및 전역 설정 관리
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

# 프로젝트 정보
PROJECT_NAME = "PDF 기반 퀀트 트레이딩 시스템"
PROJECT_VERSION = "1.0.0"

# 프로젝트 루트 디렉토리
BASE_DIR = Path(__file__).resolve().parent.parent

# 시장 목록
MARKETS = ['KOSPI', 'KOSDAQ']

# 데이터베이스 설정
DATABASE = {
    'path': BASE_DIR / 'db' / 'quant.db',
    'backup_path': BASE_DIR / 'db' / 'backup',
}

# 로그 설정
LOGGING = {
    'path': BASE_DIR / 'logs',
    'level': os.getenv('LOG_LEVEL', 'INFO'),
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'max_bytes': 10 * 1024 * 1024,  # 10MB
    'backup_count': 5,
}

# 텔레그램 봇 설정
TELEGRAM = {
    'token': os.getenv('TELEGRAM_BOT_TOKEN', ''),
    'chat_id': os.getenv('TELEGRAM_CHAT_ID', ''),
    'enabled': os.getenv('TELEGRAM_ENABLED', 'false').lower() == 'true',
}

# 데이터 수집 설정
DATA_COLLECTION = {
    # 수집할 시장
    'markets': ['KOSPI', 'KOSDAQ'],

    # 데이터 보관 기간 (일)
    'daily_retention_days': 730,  # 2년
    'minute_retention_days': 90,  # 3개월

    # 분봉 타임프레임
    'minute_timeframes': [1, 3, 5, 15, 30],

    # API 요청 간격 (초)
    'request_interval': 0.5,

    # 재시도 설정
    'max_retries': 3,
    'retry_delay': 5,
}

# 매매 설정
TRADING = {
    # 리스크 관리
    'max_position_ratio': 0.1,      # 1회 매매 최대 투자 비율 (10%)
    'max_daily_loss_ratio': 0.03,   # 일일 최대 손실 비율 (3%)
    'max_positions': 5,              # 동시 보유 최대 종목 수

    # 손절/익절
    'default_stop_loss': 0.03,       # 기본 손절 비율 (3%)
    'default_take_profit': 0.10,     # 기본 익절 비율 (10%)

    # 수수료
    'commission_rate': 0.00015,      # 매매 수수료 (0.015%)
    'tax_rate': 0.0023,              # 거래세 (0.23%, 매도 시)
}

# 스케줄 설정
SCHEDULE = {
    'morning_screening': '08:30',    # 장전 스크리닝
    'realtime_interval': 15,         # 실시간 체크 간격 (분)
    'closing_routine': '15:40',      # 장후 정리
    'daily_update': '18:00',         # 일봉 데이터 업데이트
}

# 백테스트 설정
BACKTEST = {
    'initial_capital': 10_000_000,   # 초기 자본금 (1천만원)
    'commission_rate': 0.00015,
    'slippage': 0.001,               # 슬리피지 (0.1%)
}


def get_db_path() -> Path:
    """데이터베이스 경로 반환"""
    return DATABASE['path']


def get_log_path() -> Path:
    """로그 디렉토리 경로 반환"""
    return LOGGING['path']


def is_telegram_enabled() -> bool:
    """텔레그램 알림 활성화 여부"""
    return TELEGRAM['enabled'] and TELEGRAM['token'] and TELEGRAM['chat_id']


def validate_settings() -> list:
    """설정 유효성 검사"""
    errors = []

    # 디렉토리 존재 확인
    if not DATABASE['path'].parent.exists():
        errors.append(f"Database directory not found: {DATABASE['path'].parent}")

    if not LOGGING['path'].exists():
        errors.append(f"Log directory not found: {LOGGING['path']}")

    # 텔레그램 설정 확인
    if TELEGRAM['enabled']:
        if not TELEGRAM['token']:
            errors.append("Telegram token is not set")
        if not TELEGRAM['chat_id']:
            errors.append("Telegram chat_id is not set")

    return errors
