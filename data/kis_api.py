"""
한국투자증권 Open API 모듈
실시간 및 과거 주식 데이터 수집
"""

import requests
import json
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Tuple
from pathlib import Path
import time
import os
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils import log_info, log_error, log_warning


class KISApi:
    """
    한국투자증권 Open API 클라이언트

    사용법:
    1. 한국투자증권 계좌 개설
    2. https://apiportal.koreainvestment.com 에서 앱 등록
    3. APP_KEY, APP_SECRET 발급
    4. .env 파일에 설정
    """

    # API 엔드포인트
    BASE_URL_REAL = "https://openapi.koreainvestment.com:9443"  # 실전
    BASE_URL_MOCK = "https://openapivts.koreainvestment.com:29443"  # 모의

    def __init__(self,
                 app_key: str = None,
                 app_secret: str = None,
                 account_no: str = None,
                 is_mock: bool = False):
        """
        Args:
            app_key: 한투 API 앱 키
            app_secret: 한투 API 앱 시크릿
            account_no: 계좌번호 (XXXXXXXX-XX 형식)
            is_mock: 모의투자 여부
        """
        self.app_key = app_key or os.getenv('KIS_APP_KEY', '')
        self.app_secret = app_secret or os.getenv('KIS_APP_SECRET', '')
        self.account_no = account_no or os.getenv('KIS_ACCOUNT_NO', '')
        self.is_mock = is_mock

        self.base_url = self.BASE_URL_MOCK if is_mock else self.BASE_URL_REAL
        self.access_token = None
        self.token_expired = None

        # 계좌번호 파싱
        if self.account_no and '-' in self.account_no:
            parts = self.account_no.split('-')
            self.cano = parts[0]  # 계좌번호 앞 8자리
            self.acnt_prdt_cd = parts[1]  # 계좌번호 뒤 2자리
        else:
            self.cano = ""
            self.acnt_prdt_cd = ""

    @property
    def is_configured(self) -> bool:
        """API 설정 완료 여부"""
        return bool(self.app_key and self.app_secret)

    def _get_headers(self, tr_id: str = None,
                     content_type: str = "application/json") -> Dict[str, str]:
        """API 요청 헤더 생성"""
        headers = {
            "content-type": content_type,
            "appkey": self.app_key,
            "appsecret": self.app_secret,
        }

        if self.access_token:
            headers["authorization"] = f"Bearer {self.access_token}"

        if tr_id:
            headers["tr_id"] = tr_id

        return headers

    def get_access_token(self) -> Optional[str]:
        """
        OAuth 액세스 토큰 발급

        Returns:
            액세스 토큰 또는 None
        """
        if not self.is_configured:
            log_error("한투 API가 설정되지 않았습니다. .env 파일을 확인하세요.")
            return None

        # 토큰이 유효하면 재사용
        if self.access_token and self.token_expired:
            if datetime.now() < self.token_expired:
                return self.access_token

        url = f"{self.base_url}/oauth2/tokenP"

        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            response = requests.post(url, json=body)
            response.raise_for_status()

            data = response.json()

            if 'access_token' in data:
                self.access_token = data['access_token']
                # 토큰 만료 시간 설정 (보통 24시간, 여유있게 23시간)
                self.token_expired = datetime.now() + timedelta(hours=23)
                log_info("한투 API 토큰 발급 성공")
                return self.access_token
            else:
                log_error(f"토큰 발급 실패: {data}")
                return None

        except Exception as e:
            log_error(f"토큰 발급 오류: {e}")
            return None

    def _request(self, method: str, endpoint: str,
                 tr_id: str = None,
                 params: Dict = None,
                 body: Dict = None) -> Optional[Dict]:
        """
        API 요청 실행

        Args:
            method: HTTP 메소드 (GET, POST)
            endpoint: API 엔드포인트
            tr_id: 거래 ID
            params: URL 파라미터
            body: 요청 본문

        Returns:
            응답 데이터 또는 None
        """
        # 토큰 확인
        if not self.access_token:
            if not self.get_access_token():
                return None

        url = f"{self.base_url}{endpoint}"
        headers = self._get_headers(tr_id)

        try:
            if method.upper() == 'GET':
                response = requests.get(url, headers=headers, params=params)
            else:
                response = requests.post(url, headers=headers, json=body)

            response.raise_for_status()
            data = response.json()

            # 응답 코드 확인
            if data.get('rt_cd') == '0':
                return data
            else:
                log_error(f"API 오류: {data.get('msg1', 'Unknown error')}")
                return None

        except requests.exceptions.RequestException as e:
            log_error(f"API 요청 실패: {e}")
            return None

    # ============ 시세 조회 ============

    def get_current_price(self, code: str) -> Optional[Dict]:
        """
        현재가 조회

        Args:
            code: 종목코드 (6자리)

        Returns:
            현재가 정보 딕셔너리
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-price"
        tr_id = "FHKST01010100"

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",  # J: 주식
            "FID_INPUT_ISCD": code
        }

        data = self._request('GET', endpoint, tr_id, params=params)

        if data and 'output' in data:
            output = data['output']
            return {
                'code': code,
                'name': output.get('hts_kor_isnm', ''),
                'price': int(output.get('stck_prpr', 0)),
                'change': int(output.get('prdy_vrss', 0)),
                'change_rate': float(output.get('prdy_ctrt', 0)),
                'volume': int(output.get('acml_vol', 0)),
                'high': int(output.get('stck_hgpr', 0)),
                'low': int(output.get('stck_lwpr', 0)),
                'open': int(output.get('stck_oprc', 0)),
                'prev_close': int(output.get('stck_sdpr', 0)),
            }
        return None

    def get_daily_ohlcv(self, code: str,
                        start_date: str = None,
                        end_date: str = None,
                        period: str = 'D') -> Optional[pd.DataFrame]:
        """
        일/주/월봉 OHLCV 조회

        Args:
            code: 종목코드
            start_date: 시작일 (YYYYMMDD)
            end_date: 종료일 (YYYYMMDD)
            period: D(일), W(주), M(월)

        Returns:
            OHLCV DataFrame
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice"
        tr_id = "FHKST03010100"

        if end_date is None:
            end_date = datetime.now().strftime('%Y%m%d')
        if start_date is None:
            start_date = (datetime.now() - timedelta(days=365)).strftime('%Y%m%d')

        # 날짜 형식 정리
        start_date = start_date.replace('-', '')
        end_date = end_date.replace('-', '')

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_DATE_1": start_date,
            "FID_INPUT_DATE_2": end_date,
            "FID_PERIOD_DIV_CODE": period,
            "FID_ORG_ADJ_PRC": "0",  # 0: 수정주가, 1: 원주가
        }

        data = self._request('GET', endpoint, tr_id, params=params)

        if data and 'output2' in data:
            records = []
            for item in data['output2']:
                if not item.get('stck_bsop_date'):
                    continue

                records.append({
                    'Date': pd.to_datetime(item['stck_bsop_date']),
                    'Open': int(item.get('stck_oprc', 0)),
                    'High': int(item.get('stck_hgpr', 0)),
                    'Low': int(item.get('stck_lwpr', 0)),
                    'Close': int(item.get('stck_clpr', 0)),
                    'Volume': int(item.get('acml_vol', 0)),
                })

            if records:
                df = pd.DataFrame(records)
                df.set_index('Date', inplace=True)
                df.sort_index(inplace=True)
                return df

        return None

    def get_minute_ohlcv(self, code: str,
                         timeframe: int = 1) -> Optional[pd.DataFrame]:
        """
        분봉 OHLCV 조회 (당일)

        Args:
            code: 종목코드
            timeframe: 분봉 단위 (1, 3, 5, 10, 15, 30, 60)

        Returns:
            분봉 OHLCV DataFrame
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/inquire-time-itemchartprice"
        tr_id = "FHKST03010200"

        # 현재 시간
        now = datetime.now()
        time_str = now.strftime('%H%M%S')

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code,
            "FID_INPUT_HOUR_1": time_str,
            "FID_PW_DATA_INCU_YN": "Y",  # 과거 데이터 포함
        }

        data = self._request('GET', endpoint, tr_id, params=params)

        if data and 'output2' in data:
            records = []
            for item in data['output2']:
                if not item.get('stck_cntg_hour'):
                    continue

                # 시간 파싱
                hour = item['stck_cntg_hour']
                dt = datetime.strptime(f"{now.strftime('%Y%m%d')}{hour}", '%Y%m%d%H%M%S')

                records.append({
                    'DateTime': dt,
                    'Open': int(item.get('stck_oprc', 0)),
                    'High': int(item.get('stck_hgpr', 0)),
                    'Low': int(item.get('stck_lwpr', 0)),
                    'Close': int(item.get('stck_prpr', 0)),
                    'Volume': int(item.get('cntg_vol', 0)),
                })

            if records:
                df = pd.DataFrame(records)
                df.set_index('DateTime', inplace=True)
                df.sort_index(inplace=True)

                # 분봉 리샘플링
                if timeframe > 1:
                    df = df.resample(f'{timeframe}min').agg({
                        'Open': 'first',
                        'High': 'max',
                        'Low': 'min',
                        'Close': 'last',
                        'Volume': 'sum'
                    }).dropna()

                return df

        return None

    # ============ 종목 정보 ============

    def get_stock_info(self, code: str) -> Optional[Dict]:
        """
        종목 기본 정보 조회

        Args:
            code: 종목코드

        Returns:
            종목 정보 딕셔너리
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/search-stock-info"
        tr_id = "CTPF1002R"

        params = {
            "PRDT_TYPE_CD": "300",  # 300: 주식
            "PDNO": code
        }

        data = self._request('GET', endpoint, tr_id, params=params)

        if data and 'output' in data:
            output = data['output']
            return {
                'code': code,
                'name': output.get('prdt_abrv_name', ''),
                'market': output.get('mket_id_cd', ''),
                'sector': output.get('idx_bztp_scls_cd_name', ''),
                'listed_shares': int(output.get('lstg_stqt', 0)),
            }
        return None

    def get_market_stocks(self, market: str = 'KOSPI') -> Optional[pd.DataFrame]:
        """
        시장별 종목 리스트 조회

        Args:
            market: 'KOSPI' 또는 'KOSDAQ'

        Returns:
            종목 리스트 DataFrame
        """
        # 한투 API는 종목 리스트 조회가 제한적
        # 대신 KRX에서 가져오거나 FinanceDataReader 사용 권장
        log_warning("한투 API는 종목 리스트 조회가 제한적입니다. FinanceDataReader 사용을 권장합니다.")

        try:
            import FinanceDataReader as fdr
            return fdr.StockListing(market)
        except Exception as e:
            log_error(f"종목 리스트 조회 실패: {e}")
            return None

    # ============ 거래량 상위 ============

    def get_volume_rank(self, market: str = 'J') -> Optional[List[Dict]]:
        """
        거래량 상위 종목 조회

        Args:
            market: J(전체), K(코스피), Q(코스닥)

        Returns:
            거래량 상위 종목 리스트
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/volume-rank"
        tr_id = "FHPST01710000"

        params = {
            "FID_COND_MRKT_DIV_CODE": market,
            "FID_COND_SCR_DIV_CODE": "20101",
            "FID_INPUT_ISCD": "0000",
            "FID_DIV_CLS_CODE": "0",
            "FID_BLNG_CLS_CODE": "0",
            "FID_TRGT_CLS_CODE": "111111111",
            "FID_TRGT_EXLS_CLS_CODE": "000000",
            "FID_INPUT_PRICE_1": "0",
            "FID_INPUT_PRICE_2": "0",
            "FID_VOL_CNT": "0",
            "FID_INPUT_DATE_1": ""
        }

        data = self._request('GET', endpoint, tr_id, params=params)

        if data and 'output' in data:
            results = []
            for item in data['output']:
                results.append({
                    'rank': int(item.get('data_rank', 0)),
                    'code': item.get('stck_shrn_iscd', ''),
                    'name': item.get('hts_kor_isnm', ''),
                    'price': int(item.get('stck_prpr', 0)),
                    'change_rate': float(item.get('prdy_ctrt', 0)),
                    'volume': int(item.get('acml_vol', 0)),
                    'amount': int(item.get('acml_tr_pbmn', 0)),
                })
            return results
        return None

    # ============ 상한가/하한가 ============

    def get_limit_price_stocks(self, limit_type: str = 'upper') -> Optional[List[Dict]]:
        """
        상한가/하한가 종목 조회

        Args:
            limit_type: 'upper' (상한가) 또는 'lower' (하한가)

        Returns:
            상한가/하한가 종목 리스트
        """
        endpoint = "/uapi/domestic-stock/v1/quotations/capture-uplowprice"
        tr_id = "FHPST01740000"

        # 상한가: 상승률 상위 / 하한가: 상승률 하위
        div_code = "0" if limit_type == 'upper' else "1"

        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_COND_SCR_DIV_CODE": "10101",
            "FID_INPUT_ISCD": "0000",
            "FID_DIV_CLS_CODE": div_code,
            "FID_BLNG_CLS_CODE": "0",
            "FID_TRGT_CLS_CODE": "111111111",
            "FID_TRGT_EXLS_CLS_CODE": "000000",
            "FID_INPUT_PRICE_1": "0",
            "FID_INPUT_PRICE_2": "0",
            "FID_VOL_CNT": "0",
        }

        data = self._request('GET', endpoint, tr_id, params=params)

        if data and 'output' in data:
            results = []
            for item in data['output']:
                change_rate = float(item.get('prdy_ctrt', 0))

                # 상한가는 29% 이상, 하한가는 -29% 이하만 필터
                if limit_type == 'upper' and change_rate < 29:
                    continue
                if limit_type == 'lower' and change_rate > -29:
                    continue

                results.append({
                    'code': item.get('stck_shrn_iscd', ''),
                    'name': item.get('hts_kor_isnm', ''),
                    'price': int(item.get('stck_prpr', 0)),
                    'change_rate': change_rate,
                    'volume': int(item.get('acml_vol', 0)),
                })
            return results
        return None


# 싱글톤 인스턴스
_kis_api: Optional[KISApi] = None


def get_kis_api(is_mock: bool = False) -> KISApi:
    """한투 API 인스턴스 반환"""
    global _kis_api
    if _kis_api is None:
        _kis_api = KISApi(is_mock=is_mock)
    return _kis_api


# 편의 함수들
def fetch_current_price(code: str) -> Optional[Dict]:
    """현재가 조회"""
    api = get_kis_api()
    return api.get_current_price(code)


def fetch_daily_ohlcv(code: str, days: int = 365) -> Optional[pd.DataFrame]:
    """일봉 데이터 조회"""
    api = get_kis_api()
    start_date = (datetime.now() - timedelta(days=days)).strftime('%Y%m%d')
    return api.get_daily_ohlcv(code, start_date=start_date)


def fetch_minute_ohlcv(code: str, timeframe: int = 15) -> Optional[pd.DataFrame]:
    """분봉 데이터 조회"""
    api = get_kis_api()
    return api.get_minute_ohlcv(code, timeframe=timeframe)


def fetch_volume_rank(market: str = 'J') -> Optional[List[Dict]]:
    """거래량 상위 종목"""
    api = get_kis_api()
    return api.get_volume_rank(market)


def fetch_limit_up_stocks() -> Optional[List[Dict]]:
    """상한가 종목"""
    api = get_kis_api()
    return api.get_limit_price_stocks('upper')
