"""
데이터 검증 모듈
"""

from datetime import date, datetime
from typing import Optional, List, Tuple
import pandas as pd


class ValidationError(Exception):
    """검증 오류 예외"""
    pass


# =========================================================
# OHLCV 데이터 검증
# =========================================================

def validate_ohlcv_data(df: pd.DataFrame) -> Tuple[bool, List[str]]:
    """
    OHLCV 데이터 유효성 검증

    Args:
        df: OHLCV DataFrame

    Returns:
        (유효 여부, 에러 메시지 리스트)
    """
    errors = []

    if df.empty:
        return False, ['DataFrame is empty']

    # 컬럼명 정규화
    columns = [c.lower() for c in df.columns]

    # 필수 컬럼 확인
    required_columns = ['open', 'high', 'low', 'close']
    missing = [col for col in required_columns if col not in columns]
    if missing:
        errors.append(f"Missing required columns: {missing}")

    if errors:
        return False, errors

    # 컬럼명 소문자로 변환
    df_check = df.copy()
    df_check.columns = [c.lower() for c in df_check.columns]

    # 가격 데이터 유효성 검사
    for col in ['open', 'high', 'low', 'close']:
        if col not in df_check.columns:
            continue

        # NaN 체크
        nan_count = df_check[col].isna().sum()
        if nan_count > 0:
            errors.append(f"Column '{col}' has {nan_count} NaN values")

        # 음수 체크
        negative_count = (df_check[col] < 0).sum()
        if negative_count > 0:
            errors.append(f"Column '{col}' has {negative_count} negative values")

    # High >= Low 검사
    if 'high' in df_check.columns and 'low' in df_check.columns:
        invalid_count = (df_check['high'] < df_check['low']).sum()
        if invalid_count > 0:
            errors.append(f"{invalid_count} rows have high < low")

    # High >= Open, Close 검사
    if all(col in df_check.columns for col in ['high', 'open', 'close']):
        invalid_high_open = (df_check['high'] < df_check['open']).sum()
        invalid_high_close = (df_check['high'] < df_check['close']).sum()
        if invalid_high_open > 0:
            errors.append(f"{invalid_high_open} rows have high < open")
        if invalid_high_close > 0:
            errors.append(f"{invalid_high_close} rows have high < close")

    # Low <= Open, Close 검사
    if all(col in df_check.columns for col in ['low', 'open', 'close']):
        invalid_low_open = (df_check['low'] > df_check['open']).sum()
        invalid_low_close = (df_check['low'] > df_check['close']).sum()
        if invalid_low_open > 0:
            errors.append(f"{invalid_low_open} rows have low > open")
        if invalid_low_close > 0:
            errors.append(f"{invalid_low_close} rows have low > close")

    return len(errors) == 0, errors


def validate_ohlcv_strict(df: pd.DataFrame) -> bool:
    """엄격한 OHLCV 데이터 검증 (에러 시 예외 발생)"""
    is_valid, errors = validate_ohlcv_data(df)
    if not is_valid:
        raise ValidationError('\n'.join(errors))
    return True


# =========================================================
# 종목 코드 검증
# =========================================================

def validate_stock_code(code: str) -> Tuple[bool, Optional[str]]:
    """
    종목 코드 유효성 검증

    Args:
        code: 종목 코드

    Returns:
        (유효 여부, 에러 메시지)
    """
    if not code:
        return False, "Stock code is empty"

    code = str(code).strip()

    if len(code) != 6:
        return False, f"Stock code must be 6 digits, got {len(code)}"

    if not code.isdigit():
        return False, "Stock code must contain only digits"

    return True, None


def validate_stock_codes(codes: List[str]) -> Tuple[List[str], List[str]]:
    """
    여러 종목 코드 검증

    Args:
        codes: 종목 코드 리스트

    Returns:
        (유효한 코드 리스트, 유효하지 않은 코드 리스트)
    """
    valid = []
    invalid = []

    for code in codes:
        is_valid, _ = validate_stock_code(code)
        if is_valid:
            valid.append(code.zfill(6))
        else:
            invalid.append(code)

    return valid, invalid


# =========================================================
# 날짜 검증
# =========================================================

def validate_date_range(start_date: date, end_date: date) -> Tuple[bool, Optional[str]]:
    """
    날짜 범위 유효성 검증

    Args:
        start_date: 시작 날짜
        end_date: 종료 날짜

    Returns:
        (유효 여부, 에러 메시지)
    """
    if start_date > end_date:
        return False, f"Start date ({start_date}) is after end date ({end_date})"

    if end_date > date.today():
        return False, f"End date ({end_date}) is in the future"

    # 너무 오래된 데이터 체크 (10년 이상)
    if (date.today() - start_date).days > 3650:
        return False, f"Start date ({start_date}) is more than 10 years ago"

    return True, None


def validate_trading_time(dt: datetime) -> Tuple[bool, Optional[str]]:
    """
    거래 시간 유효성 검증

    Args:
        dt: 시간

    Returns:
        (유효 여부, 에러 메시지)
    """
    # 주말 체크
    if dt.weekday() >= 5:
        return False, "Weekend is not a trading day"

    # 시간 체크 (09:00 ~ 15:30)
    market_open = dt.replace(hour=9, minute=0, second=0)
    market_close = dt.replace(hour=15, minute=30, second=0)

    if dt < market_open or dt > market_close:
        return False, f"Time {dt.time()} is outside trading hours (09:00~15:30)"

    return True, None


# =========================================================
# 신호 데이터 검증
# =========================================================

def validate_signal(code: str, signal_type: str, price: float,
                   stop_loss: float = None, take_profit: float = None) -> Tuple[bool, List[str]]:
    """
    매매 신호 유효성 검증

    Args:
        code: 종목 코드
        signal_type: 신호 유형 (BUY, SELL)
        price: 가격
        stop_loss: 손절가
        take_profit: 익절가

    Returns:
        (유효 여부, 에러 메시지 리스트)
    """
    errors = []

    # 종목 코드 검증
    is_valid, error = validate_stock_code(code)
    if not is_valid:
        errors.append(error)

    # 신호 유형 검증
    if signal_type not in ['BUY', 'SELL']:
        errors.append(f"Invalid signal type: {signal_type}")

    # 가격 검증
    if price <= 0:
        errors.append(f"Invalid price: {price}")

    # BUY 신호일 때 손절/익절 검증
    if signal_type == 'BUY':
        if stop_loss is not None and stop_loss >= price:
            errors.append(f"Stop loss ({stop_loss}) should be lower than price ({price})")

        if take_profit is not None and take_profit <= price:
            errors.append(f"Take profit ({take_profit}) should be higher than price ({price})")

    # SELL 신호일 때 (숏 포지션이 있다면)
    if signal_type == 'SELL':
        if stop_loss is not None and stop_loss <= price:
            errors.append(f"Stop loss ({stop_loss}) should be higher than price ({price}) for sell")

        if take_profit is not None and take_profit >= price:
            errors.append(f"Take profit ({take_profit}) should be lower than price ({price}) for sell")

    return len(errors) == 0, errors


# =========================================================
# 데이터 완전성 검사
# =========================================================

def check_data_completeness(df: pd.DataFrame, expected_dates: List[date]) -> Tuple[bool, List[date]]:
    """
    데이터 완전성 검사

    Args:
        df: 날짜 인덱스를 가진 DataFrame
        expected_dates: 기대하는 날짜 리스트

    Returns:
        (완전 여부, 누락된 날짜 리스트)
    """
    if df.empty:
        return False, expected_dates

    # 인덱스를 날짜로 변환
    if isinstance(df.index, pd.DatetimeIndex):
        actual_dates = set(df.index.date)
    else:
        actual_dates = set(pd.to_datetime(df.index).date)

    expected_set = set(expected_dates)
    missing = expected_set - actual_dates

    return len(missing) == 0, sorted(list(missing))


def check_data_freshness(df: pd.DataFrame, max_age_days: int = 1) -> Tuple[bool, Optional[date]]:
    """
    데이터 최신성 검사

    Args:
        df: 날짜 인덱스를 가진 DataFrame
        max_age_days: 최대 허용 경과 일수

    Returns:
        (최신 여부, 마지막 데이터 날짜)
    """
    if df.empty:
        return False, None

    # 마지막 날짜 확인
    if isinstance(df.index, pd.DatetimeIndex):
        last_date = df.index[-1].date()
    else:
        last_date = pd.to_datetime(df.index[-1]).date()

    age = (date.today() - last_date).days

    return age <= max_age_days, last_date
