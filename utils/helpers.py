"""
유틸리티 헬퍼 함수 모듈
"""

from datetime import datetime, date, timedelta
from typing import List, Union
import pandas as pd


# =========================================================
# 날짜 관련 함수
# =========================================================

def get_today() -> date:
    """오늘 날짜 반환"""
    return date.today()


def get_now() -> datetime:
    """현재 시간 반환"""
    return datetime.now()


def date_to_str(d: Union[date, datetime], fmt: str = '%Y-%m-%d') -> str:
    """날짜를 문자열로 변환"""
    return d.strftime(fmt)


def str_to_date(s: str, fmt: str = '%Y-%m-%d') -> date:
    """문자열을 날짜로 변환"""
    return datetime.strptime(s, fmt).date()


def get_date_range(start: date, end: date) -> List[date]:
    """날짜 범위 리스트 반환"""
    delta = end - start
    return [start + timedelta(days=i) for i in range(delta.days + 1)]


def get_weekdays(start: date, end: date) -> List[date]:
    """주중 날짜만 반환 (주말 제외)"""
    return [d for d in get_date_range(start, end) if d.weekday() < 5]


def is_weekend(d: date) -> bool:
    """주말 여부 확인"""
    return d.weekday() >= 5


def get_previous_trading_day(d: date = None, skip_days: int = 1) -> date:
    """이전 거래일 반환 (주말 제외)"""
    if d is None:
        d = date.today()

    result = d
    count = 0
    while count < skip_days:
        result = result - timedelta(days=1)
        if not is_weekend(result):
            count += 1

    return result


def get_next_trading_day(d: date = None, skip_days: int = 1) -> date:
    """다음 거래일 반환 (주말 제외)"""
    if d is None:
        d = date.today()

    result = d
    count = 0
    while count < skip_days:
        result = result + timedelta(days=1)
        if not is_weekend(result):
            count += 1

    return result


# =========================================================
# 숫자/금액 관련 함수
# =========================================================

def format_number(n: Union[int, float], decimal: int = 0) -> str:
    """숫자를 천 단위 구분 문자열로 변환"""
    if pd.isna(n):
        return '-'
    if decimal > 0:
        return f'{n:,.{decimal}f}'
    return f'{int(n):,}'


def format_percent(n: float, decimal: int = 2) -> str:
    """비율을 퍼센트 문자열로 변환"""
    if pd.isna(n):
        return '-'
    return f'{n * 100:.{decimal}f}%'


def format_change(n: float, decimal: int = 2) -> str:
    """변화율을 부호 포함 문자열로 변환"""
    if pd.isna(n):
        return '-'
    sign = '+' if n > 0 else ''
    return f'{sign}{n * 100:.{decimal}f}%'


def round_price(price: float, tick_size: int = 1) -> int:
    """호가 단위로 반올림"""
    return int(round(price / tick_size) * tick_size)


def calculate_change_rate(current: float, previous: float) -> float:
    """변화율 계산"""
    if previous == 0:
        return 0.0
    return (current - previous) / previous


# =========================================================
# DataFrame 관련 함수
# =========================================================

def ensure_datetime_index(df: pd.DataFrame, column: str = None) -> pd.DataFrame:
    """DataFrame 인덱스를 datetime으로 변환"""
    df = df.copy()

    if column and column in df.columns:
        df[column] = pd.to_datetime(df[column])
        df.set_index(column, inplace=True)
    elif not isinstance(df.index, pd.DatetimeIndex):
        df.index = pd.to_datetime(df.index)

    return df


def resample_ohlcv(df: pd.DataFrame, rule: str) -> pd.DataFrame:
    """
    OHLCV 데이터 리샘플링

    Args:
        df: OHLCV DataFrame
        rule: 리샘플링 규칙 (예: '1H', '4H', '1D')

    Returns:
        리샘플링된 DataFrame
    """
    df = ensure_datetime_index(df)

    # 컬럼명 소문자 변환
    df.columns = df.columns.str.lower()

    agg_dict = {
        'open': 'first',
        'high': 'max',
        'low': 'min',
        'close': 'last',
        'volume': 'sum'
    }

    # 존재하는 컬럼만 사용
    agg_dict = {k: v for k, v in agg_dict.items() if k in df.columns}

    return df.resample(rule).agg(agg_dict).dropna()


def normalize_column_names(df: pd.DataFrame) -> pd.DataFrame:
    """컬럼명 정규화 (소문자, 공백 제거)"""
    df = df.copy()
    df.columns = df.columns.str.lower().str.strip().str.replace(' ', '_')
    return df


# =========================================================
# 종목 코드 관련 함수
# =========================================================

def normalize_stock_code(code: str) -> str:
    """종목 코드 정규화 (6자리 패딩)"""
    code = str(code).strip()
    if len(code) < 6:
        code = code.zfill(6)
    return code


def is_valid_stock_code(code: str) -> bool:
    """유효한 종목 코드 여부 확인"""
    code = str(code).strip()
    return len(code) == 6 and code.isdigit()


def is_kospi_code(code: str) -> bool:
    """코스피 종목 코드 여부 (대략적 판단)"""
    code = normalize_stock_code(code)
    return code[0] in ['0', '1', '2', '3', '4', '5']


def is_kosdaq_code(code: str) -> bool:
    """코스닥 종목 코드 여부 (대략적 판단)"""
    code = normalize_stock_code(code)
    return code[0] in ['6', '7', '8', '9']


# =========================================================
# 리스트/딕셔너리 관련 함수
# =========================================================

def chunk_list(lst: list, chunk_size: int) -> List[list]:
    """리스트를 지정된 크기로 분할"""
    return [lst[i:i + chunk_size] for i in range(0, len(lst), chunk_size)]


def flatten_list(nested_list: List[list]) -> list:
    """중첩 리스트를 평탄화"""
    return [item for sublist in nested_list for item in sublist]


def safe_get(d: dict, *keys, default=None):
    """딕셔너리에서 안전하게 값 가져오기"""
    result = d
    for key in keys:
        try:
            result = result[key]
        except (KeyError, TypeError, IndexError):
            return default
    return result
