"""
데이터 수집 모듈
FinanceDataReader, pykrx를 활용한 한국 주식 데이터 수집
"""

import time
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, Tuple
from pathlib import Path
import pandas as pd

# 데이터 소스 라이브러리
import FinanceDataReader as fdr
from pykrx import stock as pykrx_stock

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import DATA_COLLECTION
from data.database import DatabaseManager, get_db


class DataCollector:
    """주식 데이터 수집 클래스"""

    def __init__(self, db: Optional[DatabaseManager] = None):
        """
        Args:
            db: 데이터베이스 매니저 인스턴스
        """
        self.db = db or get_db()
        self.request_interval = DATA_COLLECTION['request_interval']
        self.max_retries = DATA_COLLECTION['max_retries']
        self.retry_delay = DATA_COLLECTION['retry_delay']

    def _sleep(self) -> None:
        """API 요청 간격 대기"""
        time.sleep(self.request_interval)

    def _retry_on_error(self, func, *args, **kwargs) -> Any:
        """에러 발생 시 재시도"""
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    time.sleep(self.retry_delay)
        raise last_error

    # =========================================================
    # 종목 리스트 수집
    # =========================================================

    def get_kospi_stocks(self) -> pd.DataFrame:
        """코스피 종목 리스트 조회"""
        try:
            df = fdr.StockListing('KOSPI')
            df = df.rename(columns={
                'Code': 'code',
                'Name': 'name',
                'Market': 'market',
                'Sector': 'sector',
                'ListingDate': 'listing_date',
                'MarketCap': 'market_cap'
            })
            df['market'] = 'KOSPI'
            return df
        except Exception as e:
            print(f"Error fetching KOSPI stocks: {e}")
            return pd.DataFrame()

    def get_kosdaq_stocks(self) -> pd.DataFrame:
        """코스닥 종목 리스트 조회"""
        try:
            df = fdr.StockListing('KOSDAQ')
            df = df.rename(columns={
                'Code': 'code',
                'Name': 'name',
                'Market': 'market',
                'Sector': 'sector',
                'ListingDate': 'listing_date',
                'MarketCap': 'market_cap'
            })
            df['market'] = 'KOSDAQ'
            return df
        except Exception as e:
            print(f"Error fetching KOSDAQ stocks: {e}")
            return pd.DataFrame()

    def update_stock_master(self) -> Tuple[int, int]:
        """
        종목 마스터 데이터 업데이트

        Returns:
            (코스피 업데이트 수, 코스닥 업데이트 수)
        """
        kospi_count = 0
        kosdaq_count = 0

        # 코스피 종목
        kospi_df = self.get_kospi_stocks()
        if not kospi_df.empty:
            stocks = kospi_df.to_dict('records')
            for stock in stocks:
                # 필수 필드만 추출
                self.db.insert_stock(
                    code=stock.get('code', ''),
                    name=stock.get('name', ''),
                    market='KOSPI',
                    sector=stock.get('sector'),
                    listing_date=stock.get('listing_date'),
                    market_cap=stock.get('market_cap')
                )
            kospi_count = len(stocks)

        self._sleep()

        # 코스닥 종목
        kosdaq_df = self.get_kosdaq_stocks()
        if not kosdaq_df.empty:
            stocks = kosdaq_df.to_dict('records')
            for stock in stocks:
                self.db.insert_stock(
                    code=stock.get('code', ''),
                    name=stock.get('name', ''),
                    market='KOSDAQ',
                    sector=stock.get('sector'),
                    listing_date=stock.get('listing_date'),
                    market_cap=stock.get('market_cap')
                )
            kosdaq_count = len(stocks)

        return kospi_count, kosdaq_count

    # =========================================================
    # 일봉 데이터 수집
    # =========================================================

    def fetch_daily_ohlcv(self, code: str, start_date=None,
                          end_date=None) -> pd.DataFrame:
        """
        개별 종목 일봉 데이터 조회

        Args:
            code: 종목 코드
            start_date: 시작일 (기본값: 2년 전) - str 또는 date
            end_date: 종료일 (기본값: 오늘) - str 또는 date

        Returns:
            OHLCV DataFrame
        """
        # 날짜 형식 정리
        if end_date is None:
            end_date = date.today()
        elif isinstance(end_date, str):
            end_date = datetime.strptime(end_date.replace('-', ''), '%Y%m%d').date()

        if start_date is None:
            start_date = end_date - timedelta(days=DATA_COLLECTION['daily_retention_days'])
        elif isinstance(start_date, str):
            start_date = datetime.strptime(start_date.replace('-', ''), '%Y%m%d').date()

        try:
            df = fdr.DataReader(
                code,
                start_date.strftime('%Y-%m-%d'),
                end_date.strftime('%Y-%m-%d')
            )
            return df
        except Exception as e:
            print(f"Error fetching daily OHLCV for {code}: {e}")
            return pd.DataFrame()

    def fetch_and_save_daily_ohlcv(self, code: str, start_date: date = None,
                                   end_date: date = None) -> int:
        """
        일봉 데이터 수집 및 DB 저장

        Args:
            code: 종목 코드
            start_date: 시작일
            end_date: 종료일

        Returns:
            저장된 레코드 수
        """
        df = self.fetch_daily_ohlcv(code, start_date, end_date)
        if df.empty:
            return 0

        return self.db.insert_daily_ohlcv_df(code, df)

    def update_daily_ohlcv(self, code: str) -> int:
        """
        개별 종목 일봉 데이터 업데이트 (마지막 날짜 이후만)

        Args:
            code: 종목 코드

        Returns:
            업데이트된 레코드 수
        """
        latest_date = self.db.get_latest_daily_date(code)

        if latest_date:
            start_date = latest_date + timedelta(days=1)
        else:
            start_date = date.today() - timedelta(days=DATA_COLLECTION['daily_retention_days'])

        end_date = date.today()

        if start_date > end_date:
            return 0

        return self.fetch_and_save_daily_ohlcv(code, start_date, end_date)

    def update_all_daily_ohlcv(self, market: str = None,
                               progress_callback=None) -> Dict[str, int]:
        """
        모든 종목 일봉 데이터 업데이트

        Args:
            market: 시장 필터 ('KOSPI', 'KOSDAQ', None=전체)
            progress_callback: 진행상황 콜백 함수

        Returns:
            {'updated': 업데이트 종목 수, 'failed': 실패 종목 수, 'records': 총 레코드 수}
        """
        if market:
            stocks = self.db.get_stocks_by_market(market)
        else:
            stocks = self.db.get_all_active_stocks()

        result = {'updated': 0, 'failed': 0, 'records': 0}
        total = len(stocks)

        for i, stock in enumerate(stocks):
            code = stock['code']
            try:
                count = self.update_daily_ohlcv(code)
                if count > 0:
                    result['updated'] += 1
                    result['records'] += count
            except Exception as e:
                result['failed'] += 1
                print(f"Failed to update {code}: {e}")

            if progress_callback:
                progress_callback(i + 1, total, code)

            self._sleep()

        return result

    # =========================================================
    # 거래량/거래대금 상위 종목 조회
    # =========================================================

    def get_top_volume_stocks(self, market: str = 'KOSPI', top_n: int = 50) -> pd.DataFrame:
        """
        거래량 상위 종목 조회 (FinanceDataReader 기반)

        Args:
            market: 'KOSPI' 또는 'KOSDAQ'
            top_n: 상위 N개

        Returns:
            거래량 상위 종목 DataFrame
        """
        try:
            # FinanceDataReader로 종목 리스트 조회 (거래량 포함)
            if market.upper() == 'KOSPI':
                df = fdr.StockListing('KOSPI')
            else:
                df = fdr.StockListing('KOSDAQ')

            if df.empty:
                return pd.DataFrame()

            # 거래량 컬럼 확인 및 정렬
            vol_col = None
            for col in ['Volume', 'volume', 'Stocks', '거래량']:
                if col in df.columns:
                    vol_col = col
                    break

            if vol_col is None:
                # 거래량 컬럼이 없으면 시가총액으로 정렬
                cap_col = 'Marcap' if 'Marcap' in df.columns else None
                if cap_col:
                    df = df.sort_values(cap_col, ascending=False).head(top_n)
            else:
                df = df.sort_values(vol_col, ascending=False).head(top_n)

            df = df.reset_index(drop=True)
            return df

        except Exception as e:
            print(f"Error fetching top volume stocks: {e}")
            return pd.DataFrame()

    def get_top_value_stocks(self, date_str: str = None, top_n: int = 50) -> pd.DataFrame:
        """
        거래대금 상위 종목 조회

        Args:
            date_str: 날짜 (YYYYMMDD 형식)
            top_n: 상위 N개

        Returns:
            거래대금 상위 종목 DataFrame
        """
        if date_str is None:
            date_str = date.today().strftime('%Y%m%d')

        try:
            df = pykrx_stock.get_market_ohlcv_by_ticker(date_str)
            if df.empty:
                return pd.DataFrame()

            # 거래대금 기준 정렬
            df = df.sort_values('거래대금', ascending=False).head(top_n)
            df = df.reset_index()
            df.columns = ['code', 'open', 'high', 'low', 'close', 'volume', 'value', 'change_rate']

            return df
        except Exception as e:
            print(f"Error fetching top value stocks: {e}")
            return pd.DataFrame()

    # =========================================================
    # 상한가/상승 상위 종목 조회
    # =========================================================

    def get_top_gainers(self, date_str: str = None, top_n: int = 30) -> pd.DataFrame:
        """
        상승률 상위 종목 조회

        Args:
            date_str: 날짜 (YYYYMMDD 형식)
            top_n: 상위 N개

        Returns:
            상승률 상위 종목 DataFrame
        """
        if date_str is None:
            date_str = date.today().strftime('%Y%m%d')

        try:
            df = pykrx_stock.get_market_ohlcv_by_ticker(date_str)
            if df.empty:
                return pd.DataFrame()

            # 등락률 기준 정렬
            df = df.sort_values('등락률', ascending=False).head(top_n)
            df = df.reset_index()
            df.columns = ['code', 'open', 'high', 'low', 'close', 'volume', 'value', 'change_rate']

            return df
        except Exception as e:
            print(f"Error fetching top gainers: {e}")
            return pd.DataFrame()

    def get_limit_up_stocks(self, date_str: str = None) -> pd.DataFrame:
        """
        상한가 종목 조회 (등락률 29% 이상)

        Args:
            date_str: 날짜 (YYYYMMDD 형식)

        Returns:
            상한가 종목 DataFrame
        """
        if date_str is None:
            date_str = date.today().strftime('%Y%m%d')

        try:
            df = pykrx_stock.get_market_ohlcv_by_ticker(date_str)
            if df.empty:
                return pd.DataFrame()

            # 상한가 필터 (29% 이상)
            df = df[df['등락률'] >= 29.0]
            df = df.sort_values('등락률', ascending=False)
            df = df.reset_index()
            df.columns = ['code', 'open', 'high', 'low', 'close', 'volume', 'value', 'change_rate']

            return df
        except Exception as e:
            print(f"Error fetching limit up stocks: {e}")
            return pd.DataFrame()

    def fetch_and_save_limit_up_stocks(self, date_str: str = None) -> int:
        """
        상한가 종목 조회 및 DB 저장

        Args:
            date_str: 날짜 (YYYYMMDD 형식)

        Returns:
            저장된 레코드 수
        """
        if date_str is None:
            date_str = date.today().strftime('%Y%m%d')

        df = self.get_limit_up_stocks(date_str)
        if df.empty:
            return 0

        date_val = datetime.strptime(date_str, '%Y%m%d').date()
        count = 0

        for _, row in df.iterrows():
            self.db.insert_limit_up(
                code=row['code'],
                date_val=date_val,
                close_price=row['close'],
                change_rate=row['change_rate'],
                volume=int(row['volume']),
                value=row.get('value')
            )
            count += 1

        return count

    # =========================================================
    # 52주 신고가 종목 조회
    # =========================================================

    def get_52week_high_stocks(self, date_str: str = None) -> pd.DataFrame:
        """
        52주 신고가 종목 조회

        Args:
            date_str: 날짜 (YYYYMMDD 형식)

        Returns:
            52주 신고가 종목 DataFrame
        """
        if date_str is None:
            date_str = date.today().strftime('%Y%m%d')

        try:
            # 전 종목 당일 OHLCV 조회
            df = pykrx_stock.get_market_ohlcv_by_ticker(date_str)
            if df.empty:
                return pd.DataFrame()

            result_list = []
            codes = df.index.tolist()

            # 각 종목의 52주 고가 확인 (샘플링)
            for code in codes[:100]:  # 상위 100개만 확인 (시간 절약)
                try:
                    end_date = datetime.strptime(date_str, '%Y%m%d')
                    start_date = end_date - timedelta(days=365)

                    hist = fdr.DataReader(code, start_date, end_date)
                    if hist.empty:
                        continue

                    high_52w = hist['High'].max()
                    current_high = df.loc[code, '고가']

                    if current_high >= high_52w * 0.98:  # 52주 고가의 98% 이상
                        result_list.append({
                            'code': code,
                            'current_high': current_high,
                            'high_52w': high_52w,
                            'close': df.loc[code, '종가'],
                            'volume': df.loc[code, '거래량'],
                            'change_rate': df.loc[code, '등락률']
                        })
                except Exception:
                    continue

                self._sleep()

            return pd.DataFrame(result_list)
        except Exception as e:
            print(f"Error fetching 52-week high stocks: {e}")
            return pd.DataFrame()

    # =========================================================
    # 시장 전체 데이터 조회
    # =========================================================

    def get_market_ohlcv(self, date_str: str = None, market: str = 'KOSPI') -> pd.DataFrame:
        """
        시장 전체 종목 OHLCV 조회

        Args:
            date_str: 날짜 (YYYYMMDD 형식)
            market: 시장 ('KOSPI', 'KOSDAQ')

        Returns:
            시장 전체 OHLCV DataFrame
        """
        if date_str is None:
            date_str = date.today().strftime('%Y%m%d')

        try:
            df = pykrx_stock.get_market_ohlcv_by_ticker(date_str, market=market)
            if df.empty:
                return pd.DataFrame()

            df = df.reset_index()
            df.columns = ['code', 'open', 'high', 'low', 'close', 'volume', 'value', 'change_rate']
            df['market'] = market
            df['date'] = datetime.strptime(date_str, '%Y%m%d').date()

            return df
        except Exception as e:
            print(f"Error fetching market OHLCV: {e}")
            return pd.DataFrame()

    # =========================================================
    # 유틸리티 메서드
    # =========================================================

    def get_stock_name(self, code: str) -> Optional[str]:
        """종목명 조회"""
        stock = self.db.get_stock(code)
        return stock['name'] if stock else None

    def is_trading_day(self, date_val: date = None) -> bool:
        """거래일 여부 확인"""
        if date_val is None:
            date_val = date.today()

        # 주말 체크
        if date_val.weekday() >= 5:
            return False

        # 공휴일 체크는 pykrx 활용
        date_str = date_val.strftime('%Y%m%d')
        try:
            df = pykrx_stock.get_market_ohlcv_by_ticker(date_str)
            return not df.empty
        except Exception:
            return False

    def get_latest_trading_day(self) -> date:
        """가장 최근 거래일 조회"""
        today = date.today()
        for i in range(7):
            check_date = today - timedelta(days=i)
            if self.is_trading_day(check_date):
                return check_date
        return today


# 싱글톤 인스턴스
_collector_instance: Optional[DataCollector] = None


def get_collector() -> DataCollector:
    """데이터 수집기 인스턴스 반환 (싱글톤)"""
    global _collector_instance
    if _collector_instance is None:
        _collector_instance = DataCollector()
    return _collector_instance
