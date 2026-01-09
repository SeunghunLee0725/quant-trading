"""
데이터베이스 관리 모듈
SQLite 기반 주식 데이터 저장 및 관리
"""

import sqlite3
from pathlib import Path
from datetime import datetime, date
from typing import Optional, List, Dict, Any, Tuple
from contextlib import contextmanager
import pandas as pd

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import get_db_path, DATABASE


class DatabaseManager:
    """SQLite 데이터베이스 관리 클래스"""

    def __init__(self, db_path: Optional[Path] = None):
        """
        Args:
            db_path: 데이터베이스 파일 경로 (기본값: config에서 설정한 경로)
        """
        self.db_path = db_path or get_db_path()
        self._ensure_db_directory()
        self._init_db()

    def _ensure_db_directory(self) -> None:
        """데이터베이스 디렉토리 생성"""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def get_connection(self):
        """데이터베이스 연결 컨텍스트 매니저"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def _init_db(self) -> None:
        """데이터베이스 초기화 및 테이블 생성"""
        self.create_tables()

    def create_tables(self) -> None:
        """모든 테이블 생성"""
        with self.get_connection() as conn:
            cursor = conn.cursor()

            # 종목 마스터 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS stocks (
                    code TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    market TEXT,
                    sector TEXT,
                    listing_date DATE,
                    market_cap REAL,
                    is_active INTEGER DEFAULT 1,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 일봉 OHLCV 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS daily_ohlcv (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    date DATE NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    value REAL,
                    change_rate REAL,
                    UNIQUE(code, date),
                    FOREIGN KEY (code) REFERENCES stocks(code)
                )
            ''')

            # 분봉 OHLCV 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS minute_ohlcv (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    datetime TIMESTAMP NOT NULL,
                    timeframe INTEGER NOT NULL,
                    open REAL,
                    high REAL,
                    low REAL,
                    close REAL,
                    volume INTEGER,
                    UNIQUE(code, datetime, timeframe),
                    FOREIGN KEY (code) REFERENCES stocks(code)
                )
            ''')

            # 상한가 기록 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS limit_up_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    date DATE NOT NULL,
                    close_price REAL,
                    change_rate REAL,
                    volume INTEGER,
                    value REAL,
                    consecutive_days INTEGER DEFAULT 1,
                    UNIQUE(code, date),
                    FOREIGN KEY (code) REFERENCES stocks(code)
                )
            ''')

            # 매매 신호 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS signals (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    code TEXT NOT NULL,
                    datetime TIMESTAMP NOT NULL,
                    strategy TEXT NOT NULL,
                    signal_type TEXT NOT NULL,
                    price REAL,
                    stop_loss REAL,
                    take_profit REAL,
                    reason TEXT,
                    executed INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (code) REFERENCES stocks(code)
                )
            ''')

            # 스크리닝 결과 테이블
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS screening_results (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE NOT NULL,
                    screening_type TEXT NOT NULL,
                    code TEXT NOT NULL,
                    name TEXT,
                    reason TEXT,
                    score REAL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 인덱스 생성
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_code_date ON daily_ohlcv(code, date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_daily_date ON daily_ohlcv(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_minute_code_datetime ON minute_ohlcv(code, datetime)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_minute_timeframe ON minute_ohlcv(timeframe)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_datetime ON signals(datetime)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_signals_strategy ON signals(strategy)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_limit_up_date ON limit_up_history(date)')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_screening_date ON screening_results(date)')

    # =========================================================
    # 종목 마스터 관련 메서드
    # =========================================================

    def insert_stock(self, code: str, name: str, market: str = None,
                     sector: str = None, listing_date: date = None,
                     market_cap: float = None) -> None:
        """종목 정보 삽입 또는 업데이트"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO stocks (code, name, market, sector, listing_date, market_cap, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    market = COALESCE(excluded.market, market),
                    sector = COALESCE(excluded.sector, sector),
                    listing_date = COALESCE(excluded.listing_date, listing_date),
                    market_cap = COALESCE(excluded.market_cap, market_cap),
                    updated_at = excluded.updated_at
            ''', (code, name, market, sector, listing_date, market_cap, datetime.now()))

    def insert_stocks_bulk(self, stocks: List[Dict[str, Any]]) -> int:
        """종목 정보 벌크 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO stocks (code, name, market, sector, listing_date, market_cap, updated_at)
                VALUES (:code, :name, :market, :sector, :listing_date, :market_cap, :updated_at)
                ON CONFLICT(code) DO UPDATE SET
                    name = excluded.name,
                    market = COALESCE(excluded.market, market),
                    sector = COALESCE(excluded.sector, sector),
                    updated_at = excluded.updated_at
            ''', [{**s, 'updated_at': datetime.now()} for s in stocks])
            return cursor.rowcount

    def get_stock(self, code: str) -> Optional[Dict[str, Any]]:
        """종목 정보 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM stocks WHERE code = ?', (code,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_stocks_by_market(self, market: str) -> List[Dict[str, Any]]:
        """시장별 종목 목록 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT * FROM stocks WHERE market = ? AND is_active = 1 ORDER BY code',
                (market,)
            )
            return [dict(row) for row in cursor.fetchall()]

    def get_all_active_stocks(self) -> List[Dict[str, Any]]:
        """모든 활성 종목 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM stocks WHERE is_active = 1 ORDER BY market, code')
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================
    # 일봉 데이터 관련 메서드
    # =========================================================

    def insert_daily_ohlcv(self, code: str, date_val: date, open_price: float,
                          high: float, low: float, close: float,
                          volume: int, value: float = None,
                          change_rate: float = None) -> None:
        """일봉 데이터 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO daily_ohlcv (code, date, open, high, low, close, volume, value, change_rate)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    value = COALESCE(excluded.value, value),
                    change_rate = COALESCE(excluded.change_rate, change_rate)
            ''', (code, date_val, open_price, high, low, close, volume, value, change_rate))

    def insert_daily_ohlcv_bulk(self, data: List[Dict[str, Any]]) -> int:
        """일봉 데이터 벌크 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO daily_ohlcv (code, date, open, high, low, close, volume, value, change_rate)
                VALUES (:code, :date, :open, :high, :low, :close, :volume, :value, :change_rate)
                ON CONFLICT(code, date) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume,
                    value = COALESCE(excluded.value, value),
                    change_rate = COALESCE(excluded.change_rate, change_rate)
            ''', data)
            return cursor.rowcount

    def insert_daily_ohlcv_df(self, code: str, df: pd.DataFrame) -> int:
        """DataFrame으로부터 일봉 데이터 삽입"""
        if df.empty:
            return 0

        records = []
        for idx, row in df.iterrows():
            record = {
                'code': code,
                'date': idx.date() if isinstance(idx, datetime) else idx,
                'open': row.get('Open', row.get('open')),
                'high': row.get('High', row.get('high')),
                'low': row.get('Low', row.get('low')),
                'close': row.get('Close', row.get('close')),
                'volume': int(row.get('Volume', row.get('volume', 0))),
                'value': row.get('Value', row.get('value')),
                'change_rate': row.get('Change', row.get('change_rate')),
            }
            records.append(record)

        return self.insert_daily_ohlcv_bulk(records)

    def get_daily_ohlcv(self, code: str, start_date: date = None,
                        end_date: date = None, limit: int = None) -> pd.DataFrame:
        """일봉 데이터 조회"""
        with self.get_connection() as conn:
            query = 'SELECT * FROM daily_ohlcv WHERE code = ?'
            params = [code]

            if start_date:
                query += ' AND date >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND date <= ?'
                params.append(end_date)

            query += ' ORDER BY date'

            if limit:
                query += ' LIMIT ?'
                params.append(limit)

            df = pd.read_sql_query(query, conn, params=params, parse_dates=['date'])

            if not df.empty:
                df.set_index('date', inplace=True)

            return df

    def get_latest_daily_date(self, code: str) -> Optional[date]:
        """종목의 가장 최근 일봉 날짜 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'SELECT MAX(date) as max_date FROM daily_ohlcv WHERE code = ?',
                (code,)
            )
            row = cursor.fetchone()
            if row and row['max_date']:
                return datetime.strptime(row['max_date'], '%Y-%m-%d').date()
            return None

    # =========================================================
    # 분봉 데이터 관련 메서드
    # =========================================================

    def insert_minute_ohlcv(self, code: str, dt: datetime, timeframe: int,
                           open_price: float, high: float, low: float,
                           close: float, volume: int) -> None:
        """분봉 데이터 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO minute_ohlcv (code, datetime, timeframe, open, high, low, close, volume)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, datetime, timeframe) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
            ''', (code, dt, timeframe, open_price, high, low, close, volume))

    def insert_minute_ohlcv_bulk(self, data: List[Dict[str, Any]]) -> int:
        """분봉 데이터 벌크 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.executemany('''
                INSERT INTO minute_ohlcv (code, datetime, timeframe, open, high, low, close, volume)
                VALUES (:code, :datetime, :timeframe, :open, :high, :low, :close, :volume)
                ON CONFLICT(code, datetime, timeframe) DO UPDATE SET
                    open = excluded.open,
                    high = excluded.high,
                    low = excluded.low,
                    close = excluded.close,
                    volume = excluded.volume
            ''', data)
            return cursor.rowcount

    def get_minute_ohlcv(self, code: str, timeframe: int,
                         start_dt: datetime = None, end_dt: datetime = None,
                         limit: int = None) -> pd.DataFrame:
        """분봉 데이터 조회"""
        with self.get_connection() as conn:
            query = 'SELECT * FROM minute_ohlcv WHERE code = ? AND timeframe = ?'
            params = [code, timeframe]

            if start_dt:
                query += ' AND datetime >= ?'
                params.append(start_dt)
            if end_dt:
                query += ' AND datetime <= ?'
                params.append(end_dt)

            query += ' ORDER BY datetime'

            if limit:
                query += ' LIMIT ?'
                params.append(limit)

            df = pd.read_sql_query(query, conn, params=params, parse_dates=['datetime'])

            if not df.empty:
                df.set_index('datetime', inplace=True)

            return df

    # =========================================================
    # 상한가 기록 관련 메서드
    # =========================================================

    def insert_limit_up(self, code: str, date_val: date, close_price: float,
                        change_rate: float, volume: int, value: float = None,
                        consecutive_days: int = 1) -> None:
        """상한가 기록 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO limit_up_history (code, date, close_price, change_rate, volume, value, consecutive_days)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(code, date) DO UPDATE SET
                    close_price = excluded.close_price,
                    change_rate = excluded.change_rate,
                    volume = excluded.volume,
                    value = COALESCE(excluded.value, value),
                    consecutive_days = excluded.consecutive_days
            ''', (code, date_val, close_price, change_rate, volume, value, consecutive_days))

    def get_limit_up_history(self, start_date: date = None,
                             end_date: date = None) -> pd.DataFrame:
        """상한가 기록 조회"""
        with self.get_connection() as conn:
            query = 'SELECT * FROM limit_up_history WHERE 1=1'
            params = []

            if start_date:
                query += ' AND date >= ?'
                params.append(start_date)
            if end_date:
                query += ' AND date <= ?'
                params.append(end_date)

            query += ' ORDER BY date DESC, change_rate DESC'

            return pd.read_sql_query(query, conn, params=params, parse_dates=['date'])

    def get_recent_limit_up_stocks(self, days: int = 5) -> List[str]:
        """최근 N일 내 상한가 기록 종목 코드 조회"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT code FROM limit_up_history
                WHERE date >= date('now', ? || ' days')
                ORDER BY date DESC
            ''', (f'-{days}',))
            return [row['code'] for row in cursor.fetchall()]

    # =========================================================
    # 매매 신호 관련 메서드
    # =========================================================

    def insert_signal(self, code: str, dt: datetime, strategy: str,
                      signal_type: str, price: float, stop_loss: float = None,
                      take_profit: float = None, reason: str = None) -> int:
        """매매 신호 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO signals (code, datetime, strategy, signal_type, price, stop_loss, take_profit, reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (code, dt, strategy, signal_type, price, stop_loss, take_profit, reason))
            return cursor.lastrowid

    def get_signals(self, strategy: str = None, signal_type: str = None,
                    start_dt: datetime = None, end_dt: datetime = None,
                    executed: bool = None) -> pd.DataFrame:
        """매매 신호 조회"""
        with self.get_connection() as conn:
            query = 'SELECT * FROM signals WHERE 1=1'
            params = []

            if strategy:
                query += ' AND strategy = ?'
                params.append(strategy)
            if signal_type:
                query += ' AND signal_type = ?'
                params.append(signal_type)
            if start_dt:
                query += ' AND datetime >= ?'
                params.append(start_dt)
            if end_dt:
                query += ' AND datetime <= ?'
                params.append(end_dt)
            if executed is not None:
                query += ' AND executed = ?'
                params.append(1 if executed else 0)

            query += ' ORDER BY datetime DESC'

            return pd.read_sql_query(query, conn, params=params, parse_dates=['datetime', 'created_at'])

    def mark_signal_executed(self, signal_id: int) -> None:
        """신호 실행 완료 표시"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE signals SET executed = 1 WHERE id = ?', (signal_id,))

    # =========================================================
    # 스크리닝 결과 관련 메서드
    # =========================================================

    def insert_screening_result(self, date_val: date, screening_type: str,
                                code: str, name: str = None,
                                reason: str = None, score: float = None) -> None:
        """스크리닝 결과 삽입"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO screening_results (date, screening_type, code, name, reason, score)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (date_val, screening_type, code, name, reason, score))

    def get_screening_results(self, date_val: date = None,
                              screening_type: str = None) -> pd.DataFrame:
        """스크리닝 결과 조회"""
        with self.get_connection() as conn:
            query = 'SELECT * FROM screening_results WHERE 1=1'
            params = []

            if date_val:
                query += ' AND date = ?'
                params.append(date_val)
            if screening_type:
                query += ' AND screening_type = ?'
                params.append(screening_type)

            query += ' ORDER BY date DESC, score DESC'

            return pd.read_sql_query(query, conn, params=params, parse_dates=['date', 'created_at'])

    # =========================================================
    # 유틸리티 메서드
    # =========================================================

    def execute_query(self, query: str, params: tuple = None) -> List[Dict[str, Any]]:
        """임의의 쿼리 실행"""
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params or ())
            return [dict(row) for row in cursor.fetchall()]

    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """테이블 정보 조회"""
        return self.execute_query(f'PRAGMA table_info({table_name})')

    def get_row_count(self, table_name: str) -> int:
        """테이블 행 수 조회"""
        result = self.execute_query(f'SELECT COUNT(*) as count FROM {table_name}')
        return result[0]['count'] if result else 0

    def vacuum(self) -> None:
        """데이터베이스 최적화"""
        with self.get_connection() as conn:
            conn.execute('VACUUM')

    def backup(self, backup_path: Path = None) -> Path:
        """데이터베이스 백업"""
        import shutil
        backup_path = backup_path or DATABASE['backup_path']
        backup_path.mkdir(parents=True, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = backup_path / f'quant_backup_{timestamp}.db'

        shutil.copy2(self.db_path, backup_file)
        return backup_file


# 싱글톤 인스턴스
_db_instance: Optional[DatabaseManager] = None


def get_db() -> DatabaseManager:
    """데이터베이스 인스턴스 반환 (싱글톤)"""
    global _db_instance
    if _db_instance is None:
        _db_instance = DatabaseManager()
    return _db_instance
