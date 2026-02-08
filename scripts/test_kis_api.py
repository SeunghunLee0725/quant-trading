#!/usr/bin/env python3
"""
한국투자증권 API 테스트 스크립트

사용 전 설정:
1. .env 파일에 KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO 설정
2. python scripts/test_kis_api.py 실행
"""

import sys
from pathlib import Path

# 프로젝트 루트 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from data import get_kis_api


def test_connection():
    """API 연결 테스트"""
    print("=" * 60)
    print("한국투자증권 API 연결 테스트")
    print("=" * 60)

    api = get_kis_api()

    if not api.is_configured:
        print("\n❌ API가 설정되지 않았습니다.")
        print("   .env 파일에 다음 항목을 설정하세요:")
        print("   - KIS_APP_KEY")
        print("   - KIS_APP_SECRET")
        print("   - KIS_ACCOUNT_NO")
        return False

    print("\n✓ API 설정 확인됨")

    # 토큰 발급 테스트
    print("\n[1] 액세스 토큰 발급...")
    token = api.get_access_token()

    if token:
        print(f"   ✓ 토큰 발급 성공: {token[:20]}...")
        return True
    else:
        print("   ❌ 토큰 발급 실패")
        return False


def test_current_price():
    """현재가 조회 테스트"""
    print("\n[2] 현재가 조회 테스트...")

    api = get_kis_api()

    # 삼성전자 현재가 조회
    code = "005930"
    result = api.get_current_price(code)

    if result:
        print(f"   ✓ {result['name']} ({code})")
        print(f"     현재가: {result['price']:,}원")
        print(f"     전일비: {result['change']:+,}원 ({result['change_rate']:+.2f}%)")
        print(f"     거래량: {result['volume']:,}")
        return True
    else:
        print("   ❌ 현재가 조회 실패")
        return False


def test_daily_ohlcv():
    """일봉 데이터 조회 테스트"""
    print("\n[3] 일봉 데이터 조회 테스트...")

    api = get_kis_api()

    # 삼성전자 일봉
    code = "005930"
    df = api.get_daily_ohlcv(code)

    if df is not None and not df.empty:
        print(f"   ✓ {len(df)}일 데이터 조회됨")
        print(f"     기간: {df.index[0].strftime('%Y-%m-%d')} ~ {df.index[-1].strftime('%Y-%m-%d')}")
        print("\n   최근 5일:")
        print(df.tail())
        return True
    else:
        print("   ❌ 일봉 데이터 조회 실패")
        return False


def test_minute_ohlcv():
    """분봉 데이터 조회 테스트"""
    print("\n[4] 분봉 데이터 조회 테스트...")

    api = get_kis_api()

    # 삼성전자 15분봉
    code = "005930"
    df = api.get_minute_ohlcv(code, timeframe=15)

    if df is not None and not df.empty:
        print(f"   ✓ {len(df)}개 분봉 데이터 조회됨")
        print("\n   최근 5개:")
        print(df.tail())
        return True
    else:
        print("   ⚠ 분봉 데이터 없음 (장 마감 시 정상)")
        return True


def test_volume_rank():
    """거래량 상위 조회 테스트"""
    print("\n[5] 거래량 상위 종목 테스트...")

    api = get_kis_api()
    results = api.get_volume_rank('J')  # 전체 시장

    if results:
        print(f"   ✓ {len(results)}개 종목 조회됨")
        print("\n   거래량 TOP 10:")
        for item in results[:10]:
            print(f"     {item['rank']:2}. [{item['code']}] {item['name']}: "
                  f"{item['volume']:,}주 ({item['change_rate']:+.2f}%)")
        return True
    else:
        print("   ❌ 거래량 순위 조회 실패")
        return False


def test_limit_up():
    """상한가 종목 조회 테스트"""
    print("\n[6] 상한가 종목 테스트...")

    api = get_kis_api()
    results = api.get_limit_price_stocks('upper')

    if results is not None:
        if results:
            print(f"   ✓ {len(results)}개 상한가 종목")
            for item in results[:5]:
                print(f"     [{item['code']}] {item['name']}: "
                      f"{item['price']:,}원 ({item['change_rate']:+.2f}%)")
        else:
            print("   ⚠ 상한가 종목 없음 (정상)")
        return True
    else:
        print("   ❌ 상한가 조회 실패")
        return False


def main():
    """메인 테스트"""
    print("\n" + "=" * 60)
    print(" 한국투자증권 Open API 테스트")
    print("=" * 60)

    # 연결 테스트
    if not test_connection():
        return 1

    # 각 기능 테스트
    results = {
        '현재가 조회': test_current_price(),
        '일봉 데이터': test_daily_ohlcv(),
        '분봉 데이터': test_minute_ohlcv(),
        '거래량 순위': test_volume_rank(),
        '상한가 종목': test_limit_up(),
    }

    # 결과 요약
    print("\n" + "=" * 60)
    print(" 테스트 결과 요약")
    print("=" * 60)

    for name, success in results.items():
        status = "✓ 성공" if success else "❌ 실패"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    print("\n" + "=" * 60)

    if all_passed:
        print(" 모든 테스트 통과! 한투 API 사용 준비 완료")
    else:
        print(" 일부 테스트 실패. 설정을 확인하세요.")

    print("=" * 60 + "\n")

    return 0 if all_passed else 1


if __name__ == '__main__':
    sys.exit(main())
