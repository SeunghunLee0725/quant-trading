#!/usr/bin/env python3
"""
주식 퀀트 트레이딩 시스템
PDF '주식공부.pdf' 기반 매매 전략 구현

사용법:
    python main.py --mode screen          # 종목 스크리닝
    python main.py --mode backtest        # 백테스트 실행
    python main.py --mode collect         # 데이터 수집
    python main.py --mode analyze CODE    # 단일 종목 분석
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import List

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import (
    PROJECT_NAME,
)
from data import get_db, get_collector
from strategies import (
    get_strategy,
)
from screener import (
    StockScreener,
)
from backtest import (
    Backtester,
    MultiStrategyBacktester,
    BacktestConfig,
)
from notification import (
    notify_screening,
    notify_backtest,
    notify_error,
)
from utils import (
    log_info,
    log_error,
    log_warning,
    get_today,
    date_to_str,
    measure_time,
)


def collect_data(markets: List[str] = None, days: int = 365):
    """
    데이터 수집

    Args:
        markets: 시장 리스트 ('KOSPI', 'KOSDAQ')
        days: 수집 기간 (일)
    """
    log_info("=" * 60)
    log_info("데이터 수집 시작")
    log_info("=" * 60)

    if markets is None:
        markets = ['KOSPI', 'KOSDAQ']

    collector = get_collector()
    db = get_db()

    end_date = get_today()
    start_date = end_date - timedelta(days=days)

    total_stocks = 0
    success_count = 0

    for market in markets:
        log_info(f"\n[{market}] 종목 목록 수집 중...")

        # 종목 목록 가져오기
        if market == 'KOSPI':
            stocks = collector.get_kospi_stocks()
        else:
            stocks = collector.get_kosdaq_stocks()

        if stocks.empty:
            log_warning(f"{market} 종목 목록을 가져올 수 없습니다")
            continue

        log_info(f"[{market}] {len(stocks)}개 종목 발견")

        # 종목별 데이터 수집
        for _, row in stocks.iterrows():
            code = row.get('Code') or row.get('code')
            name = row.get('Name') or row.get('name')

            if not code:
                continue

            total_stocks += 1

            try:
                # 일봉 데이터 수집
                df = collector.fetch_daily_ohlcv(
                    code,
                    start_date=date_to_str(start_date),
                    end_date=date_to_str(end_date)
                )

                if df is not None and not df.empty:
                    # DB에 저장
                    db.insert_stock(code, name, market)
                    db.insert_daily_ohlcv_df(code, df)
                    success_count += 1

                    if success_count % 100 == 0:
                        log_info(f"진행: {success_count}/{total_stocks}")

            except Exception as e:
                log_error(f"[{code}] 데이터 수집 실패: {e}")

    log_info("")
    log_info("=" * 60)
    log_info(f"데이터 수집 완료: {success_count}/{total_stocks} 성공")
    log_info("=" * 60)


@measure_time
def run_screen(strategy_names: List[str] = None, preset: str = 'default',
               notify: bool = True):
    """
    종목 스크리닝 실행

    Args:
        strategy_names: 사용할 전략 이름 리스트
        preset: 필터 프리셋
        notify: 텔레그램 알림 여부
    """
    log_info("=" * 60)
    log_info("종목 스크리닝 시작")
    log_info("=" * 60)

    db = get_db()
    collector = get_collector()

    # 종목 목록 조회
    stocks = db.get_all_active_stocks()
    if not stocks:
        log_error("등록된 종목이 없습니다. 먼저 데이터를 수집하세요.")
        return

    log_info(f"총 {len(stocks)}개 종목 대상")

    # 종목별 데이터 로드
    stock_data = {}
    for stock in stocks:
        code = stock['code']
        name = stock['name']

        df = db.get_daily_ohlcv(code, limit=252)  # 최근 1년

        if df is not None and len(df) >= 20:
            stock_data[code] = {
                'df': df,
                'name': name,
            }

    log_info(f"유효 데이터: {len(stock_data)}개 종목")

    # 스크리너 생성
    screener = StockScreener(strategies=strategy_names)
    screener.set_filter_preset(preset)

    # 스크리닝 실행
    results = screener.screen_stocks(stock_data)

    # 결과 출력
    print("\n" + screener.generate_report())

    # DB에 결과 저장
    for result in results:
        if result.signal:
            db.save_signal(result.signal)

    # 텔레그램 알림
    if notify and results:
        notify_screening(results)

    log_info(f"\n스크리닝 완료: {len(results)}개 종목 발견")

    return results


@measure_time
def run_backtesting(strategy_name: str = None, days: int = 365,
                    initial_capital: float = 10000000,
                    notify: bool = True):
    """
    백테스트 실행

    Args:
        strategy_name: 전략 이름 (None이면 전체)
        days: 백테스트 기간
        initial_capital: 초기 자본
        notify: 텔레그램 알림 여부
    """
    log_info("=" * 60)
    log_info("백테스트 시작")
    log_info("=" * 60)

    db = get_db()

    # 종목 데이터 로드
    stocks = db.get_all_active_stocks()
    if not stocks:
        log_error("등록된 종목이 없습니다")
        return

    # 백테스트 데이터 준비
    end_date = get_today()
    start_date = end_date - timedelta(days=days)

    stock_data = {}
    for stock in stocks[:100]:  # 상위 100개만 (속도)
        code = stock['code']
        df = db.get_daily_ohlcv(code, limit=days + 60)

        if df is not None and len(df) >= 60:
            stock_data[code] = df

    log_info(f"백테스트 대상: {len(stock_data)}개 종목")

    # 백테스트 설정
    config = BacktestConfig(initial_capital=initial_capital)

    if strategy_name:
        # 단일 전략 백테스트
        strategy = get_strategy(strategy_name)
        if not strategy:
            log_error(f"전략을 찾을 수 없음: {strategy_name}")
            return

        bt = Backtester(strategy, config)
        metrics = bt.run(stock_data, start_date, end_date)

        print("\n" + bt.generate_report())

        if notify:
            notify_backtest(metrics, strategy_name)

    else:
        # 다중 전략 백테스트
        strategies = ['limit_up', 'breakout', 'minute15', 'minute30']
        multi_bt = MultiStrategyBacktester(strategies, config)

        results = multi_bt.run(stock_data, start_date, end_date)

        print("\n" + multi_bt.generate_comparison_report())

        if notify:
            for name, metrics in results.items():
                notify_backtest(metrics, name)


def analyze_stock(code: str, strategies: List[str] = None):
    """
    단일 종목 분석

    Args:
        code: 종목 코드
        strategies: 적용할 전략 리스트
    """
    log_info("=" * 60)
    log_info(f"종목 분석: {code}")
    log_info("=" * 60)

    db = get_db()
    collector = get_collector()

    # 종목 정보
    stock = db.get_stock(code)
    if stock:
        name = stock['name']
        log_info(f"종목명: {name}")
    else:
        name = code

    # 데이터 로드
    df = db.get_daily_ohlcv(code, limit=252)

    if df is None or df.empty:
        # DB에 없으면 실시간 수집
        log_info("데이터 실시간 수집 중...")
        df = collector.fetch_daily_ohlcv(code)

        if df is None or df.empty:
            log_error(f"종목 데이터를 가져올 수 없습니다: {code}")
            return

    log_info(f"데이터: {len(df)}일")

    # 전략 적용
    if strategies is None:
        strategies = ['limit_up', 'breakout', 'minute15', 'minute30']

    print("\n[전략별 분석 결과]")
    print("-" * 40)

    for strategy_name in strategies:
        strategy = get_strategy(strategy_name)
        if not strategy:
            continue

        signal = strategy.generate_signal(df, code, name)

        if signal:
            print(f"\n▶ {strategy_name}: 매수 신호!")
            print(f"  진입가: {signal.price:,.0f}원")
            print(f"  손절가: {signal.stop_loss:,.0f}원 ({(signal.stop_loss - signal.price) / signal.price * 100:.1f}%)")
            print(f"  목표가: {signal.take_profit:,.0f}원 ({(signal.take_profit - signal.price) / signal.price * 100:.1f}%)")
            print(f"  사유: {signal.reason}")
            print(f"  강도: {signal.strength:.2f}")
        else:
            print(f"\n▶ {strategy_name}: 신호 없음")

    # 추가 지표 정보
    print("\n[기술적 지표]")
    print("-" * 40)

    from indicators import (
        calculate_all_ma,
        get_ma_status,
        get_ma_values,
        calculate_volume_ratio,
    )

    # 이동평균
    df_ma = calculate_all_ma(df)
    ma_values = get_ma_values(df_ma, [5, 20, 60])

    col_lower = {c.lower(): c for c in df.columns}
    close_col = col_lower.get('close', 'Close')
    current_price = df[close_col].iloc[-1]

    ma_status = get_ma_status(current_price, ma_values)
    print(f"이동평균 상태: {ma_status}")

    for period, value in ma_values.items():
        diff = (current_price - value) / value * 100
        print(f"  MA{period}: {value:,.0f}원 (이격도: {diff:+.1f}%)")

    # 거래량
    vol_ratio = calculate_volume_ratio(df)
    print(f"\n거래량 비율: {vol_ratio.iloc[-1]:.2f}x (20일 평균 대비)")


def main():
    """메인 함수"""
    parser = argparse.ArgumentParser(
        description=f'{PROJECT_NAME} - PDF 기반 퀀트 트레이딩 시스템',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
예시:
  python main.py --mode screen                    # 종목 스크리닝
  python main.py --mode screen --strategy limit_up  # 특정 전략만
  python main.py --mode backtest                  # 전체 전략 백테스트
  python main.py --mode backtest --strategy breakout  # 특정 전략
  python main.py --mode collect                   # 데이터 수집
  python main.py --mode analyze --code 005930     # 삼성전자 분석
        """
    )

    parser.add_argument(
        '--mode', '-m',
        choices=['screen', 'backtest', 'collect', 'analyze'],
        default='screen',
        help='실행 모드'
    )

    parser.add_argument(
        '--strategy', '-s',
        type=str,
        default=None,
        help='사용할 전략 (limit_up, breakout, minute15, minute30)'
    )

    parser.add_argument(
        '--code', '-c',
        type=str,
        default=None,
        help='종목 코드 (analyze 모드용)'
    )

    parser.add_argument(
        '--days', '-d',
        type=int,
        default=365,
        help='기간 (일)'
    )

    parser.add_argument(
        '--capital',
        type=float,
        default=10000000,
        help='초기 자본 (백테스트용)'
    )

    parser.add_argument(
        '--preset',
        type=str,
        default='default',
        choices=['default', 'aggressive', 'conservative', 'volume_focus', 'breakout'],
        help='필터 프리셋'
    )

    parser.add_argument(
        '--market',
        type=str,
        default=None,
        choices=['KOSPI', 'KOSDAQ'],
        help='시장 (collect 모드용)'
    )

    parser.add_argument(
        '--no-notify',
        action='store_true',
        help='텔레그램 알림 비활성화'
    )

    args = parser.parse_args()

    # 시작 메시지
    log_info("")
    log_info(f"{'=' * 60}")
    log_info(f" {PROJECT_NAME}")
    log_info(" PDF 기반 퀀트 트레이딩 시스템")
    log_info(f"{'=' * 60}")
    log_info(f" 실행 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    log_info(f" 모드: {args.mode}")
    log_info(f"{'=' * 60}")
    log_info("")

    try:
        if args.mode == 'collect':
            markets = [args.market] if args.market else None
            collect_data(markets=markets, days=args.days)

        elif args.mode == 'screen':
            strategies = [args.strategy] if args.strategy else None
            run_screen(
                strategy_names=strategies,
                preset=args.preset,
                notify=not args.no_notify
            )

        elif args.mode == 'backtest':
            run_backtesting(
                strategy_name=args.strategy,
                days=args.days,
                initial_capital=args.capital,
                notify=not args.no_notify
            )

        elif args.mode == 'analyze':
            if not args.code:
                log_error("종목 코드를 입력하세요 (--code)")
                return 1

            strategies = [args.strategy] if args.strategy else None
            analyze_stock(args.code, strategies)

    except KeyboardInterrupt:
        log_warning("\n사용자에 의해 중단됨")
        return 1

    except Exception as e:
        log_error(f"오류 발생: {e}")
        if not args.no_notify:
            notify_error(str(e))
        raise

    log_info("")
    log_info("완료!")
    return 0


if __name__ == '__main__':
    sys.exit(main())
