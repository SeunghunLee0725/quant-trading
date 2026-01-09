"""
로깅 시스템 모듈
파일 및 콘솔 로깅 관리
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from typing import Optional

# config 임포트를 위한 경로 설정
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import LOGGING, get_log_path


class LoggerManager:
    """로거 관리 클래스"""

    _loggers: dict = {}

    @classmethod
    def get_logger(cls, name: str = 'quant', level: str = None) -> logging.Logger:
        """
        로거 인스턴스 반환

        Args:
            name: 로거 이름
            level: 로그 레벨 (DEBUG, INFO, WARNING, ERROR)

        Returns:
            Logger 인스턴스
        """
        if name in cls._loggers:
            return cls._loggers[name]

        logger = logging.getLogger(name)
        level = level or LOGGING['level']
        logger.setLevel(getattr(logging, level.upper(), logging.INFO))

        # 기존 핸들러 제거 (중복 방지)
        logger.handlers.clear()

        # 콘솔 핸들러
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.DEBUG)
        console_format = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_format)
        logger.addHandler(console_handler)

        # 파일 핸들러
        log_path = get_log_path()
        log_path.mkdir(parents=True, exist_ok=True)

        file_handler = RotatingFileHandler(
            log_path / f'{name}.log',
            maxBytes=LOGGING['max_bytes'],
            backupCount=LOGGING['backup_count'],
            encoding='utf-8'
        )
        file_handler.setLevel(logging.DEBUG)
        file_format = logging.Formatter(LOGGING['format'])
        file_handler.setFormatter(file_format)
        logger.addHandler(file_handler)

        # 에러 전용 파일 핸들러
        error_handler = RotatingFileHandler(
            log_path / f'{name}_error.log',
            maxBytes=LOGGING['max_bytes'],
            backupCount=LOGGING['backup_count'],
            encoding='utf-8'
        )
        error_handler.setLevel(logging.ERROR)
        error_handler.setFormatter(file_format)
        logger.addHandler(error_handler)

        cls._loggers[name] = logger
        return logger

    @classmethod
    def get_strategy_logger(cls, strategy_name: str) -> logging.Logger:
        """전략별 로거 반환"""
        return cls.get_logger(f'strategy.{strategy_name}')

    @classmethod
    def get_data_logger(cls) -> logging.Logger:
        """데이터 수집 로거 반환"""
        return cls.get_logger('data')

    @classmethod
    def get_signal_logger(cls) -> logging.Logger:
        """신호 로거 반환"""
        return cls.get_logger('signal')


# 편의 함수들
def get_logger(name: str = 'quant') -> logging.Logger:
    """기본 로거 반환"""
    return LoggerManager.get_logger(name)


def log_info(message: str, logger_name: str = 'quant') -> None:
    """INFO 레벨 로깅"""
    LoggerManager.get_logger(logger_name).info(message)


def log_warning(message: str, logger_name: str = 'quant') -> None:
    """WARNING 레벨 로깅"""
    LoggerManager.get_logger(logger_name).warning(message)


def log_error(message: str, logger_name: str = 'quant', exc_info: bool = False) -> None:
    """ERROR 레벨 로깅"""
    LoggerManager.get_logger(logger_name).error(message, exc_info=exc_info)


def log_debug(message: str, logger_name: str = 'quant') -> None:
    """DEBUG 레벨 로깅"""
    LoggerManager.get_logger(logger_name).debug(message)


def log_signal(code: str, strategy: str, signal_type: str,
               price: float, reason: str = None) -> None:
    """매매 신호 로깅"""
    logger = LoggerManager.get_signal_logger()
    msg = f"[{signal_type}] {code} | Strategy: {strategy} | Price: {price:,.0f}"
    if reason:
        msg += f" | Reason: {reason}"
    logger.info(msg)


def log_trade(code: str, trade_type: str, price: float,
              quantity: int, pnl: float = None) -> None:
    """매매 체결 로깅"""
    logger = LoggerManager.get_signal_logger()
    msg = f"[TRADE] {code} | {trade_type} | Price: {price:,.0f} | Qty: {quantity}"
    if pnl is not None:
        msg += f" | PnL: {pnl:+,.0f}"
    logger.info(msg)


def log_screening(screening_type: str = None, count: int = None, stocks: list = None,
                  *, strategy: str = None, total: int = None, passed: int = None,
                  results: list = None) -> None:
    """스크리닝 결과 로깅"""
    logger = LoggerManager.get_logger('screener')

    # 새로운 호출 방식 (strategy, total, passed, results)
    if strategy is not None:
        msg = f"[SCREENING] {strategy} | Total: {total} | Passed: {passed}"
        if results:
            msg += f" | Top: {results[:5]}"
    # 기존 호출 방식 (screening_type, count, stocks)
    else:
        msg = f"[SCREENING] {screening_type} | Found: {count} stocks"
        if stocks:
            msg += f" | Top: {stocks[:5]}"

    logger.info(msg)


class PerformanceLogger:
    """성능 측정 로거"""

    def __init__(self, name: str, logger: logging.Logger = None):
        self.name = name
        self.logger = logger or get_logger()
        self.start_time: Optional[datetime] = None

    def __enter__(self):
        self.start_time = datetime.now()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (datetime.now() - self.start_time).total_seconds()
        self.logger.debug(f"[PERF] {self.name} completed in {elapsed:.3f}s")
        return False


def measure_time(func_or_name=None):
    """
    함수 실행 시간 측정 데코레이터

    사용법:
        @measure_time  # 함수명을 이름으로 사용
        @measure_time("custom_name")  # 커스텀 이름 사용
    """
    def decorator(func, name=None):
        actual_name = name or func.__name__

        def wrapper(*args, **kwargs):
            with PerformanceLogger(actual_name):
                return func(*args, **kwargs)
        return wrapper

    # @measure_time 처럼 인자 없이 사용된 경우
    if callable(func_or_name):
        return decorator(func_or_name)

    # @measure_time("name") 처럼 이름과 함께 사용된 경우
    def wrapper(func):
        return decorator(func, func_or_name)
    return wrapper
