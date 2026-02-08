"""
종목 스크리너 모듈
PDF 기준: 전략별 매수 조건 충족 종목 탐색
"""

import pandas as pd
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from screener.filters import StockFilter, FilterResult, FilterFactory
from strategies import (
    BaseStrategy,
    Signal,
    get_strategy,
    Minute15Strategy,
    Minute30Strategy,
    LimitUpStrategy,
    BreakoutStrategy,
)
from utils import log_info, log_error, log_screening, measure_time


@dataclass
class ScreeningResult:
    """스크리닝 결과"""
    code: str
    name: str
    datetime: datetime
    strategy: str
    signal: Optional[Signal]
    filter_results: List[FilterResult] = field(default_factory=list)
    score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)


class StockScreener:
    """
    종목 스크리너

    PDF 기반 전략들을 적용하여 매수 조건 충족 종목 탐색
    """

    def __init__(self, strategies: List[str] = None, filters: List[StockFilter] = None):
        """
        Args:
            strategies: 사용할 전략 이름 리스트 (None이면 전체)
            filters: 사전 필터 리스트 (None이면 기본 필터)
        """
        self.strategies = self._load_strategies(strategies)
        self.filters = filters or FilterFactory.create_preset('default')
        self.results: List[ScreeningResult] = []

    def _load_strategies(self, strategy_names: List[str] = None) -> List[BaseStrategy]:
        """전략 로드"""
        if strategy_names is None:
            return [
                Minute15Strategy(),
                Minute30Strategy(),
                LimitUpStrategy(),
                BreakoutStrategy(),
            ]

        strategies = []
        for name in strategy_names:
            strategy = get_strategy(name)
            if strategy:
                strategies.append(strategy)
            else:
                log_error(f"전략을 찾을 수 없음: {name}")

        return strategies

    def add_filter(self, filter_name: str, **params) -> 'StockScreener':
        """필터 추가"""
        f = FilterFactory.create(filter_name, **params)
        if f:
            self.filters.append(f)
        return self

    def set_filter_preset(self, preset_name: str) -> 'StockScreener':
        """필터 프리셋 설정"""
        self.filters = FilterFactory.create_preset(preset_name)
        return self

    def clear_filters(self) -> 'StockScreener':
        """필터 초기화"""
        self.filters = []
        return self

    def _apply_filters(self, df: pd.DataFrame, code: str,
                       name: str) -> tuple:
        """
        필터 적용

        Returns:
            (통과 여부, 필터 결과 리스트)
        """
        results = []

        for f in self.filters:
            result = f.apply(df, code, name)
            results.append(result)

            if not result.passed:
                return False, results

        return True, results

    def screen_stock(self, df: pd.DataFrame, code: str = "",
                     name: str = "") -> List[ScreeningResult]:
        """
        단일 종목 스크리닝

        Args:
            df: OHLCV DataFrame
            code: 종목 코드
            name: 종목명

        Returns:
            스크리닝 결과 리스트
        """
        results = []

        # 1. 필터 적용
        passed, filter_results = self._apply_filters(df, code, name)

        if not passed:
            return results

        # 2. 각 전략 적용
        for strategy in self.strategies:
            try:
                signal = strategy.generate_signal(df, code, name)

                if signal:
                    result = ScreeningResult(
                        code=code,
                        name=name,
                        datetime=datetime.now(),
                        strategy=strategy.name,
                        signal=signal,
                        filter_results=filter_results,
                        score=signal.strength,
                        metadata={
                            'strategy_name': strategy.name,
                            'signal_type': signal.signal_type.value,
                            'entry_price': signal.price,
                            'stop_loss': signal.stop_loss,
                            'take_profit': signal.take_profit,
                        }
                    )
                    results.append(result)

            except Exception as e:
                log_error(f"전략 적용 오류 [{strategy.name}][{code}]: {e}")

        return results

    @measure_time
    def screen_stocks(self, stock_data: Dict[str, Dict[str, Any]],
                      max_workers: int = 4) -> List[ScreeningResult]:
        """
        복수 종목 스크리닝 (병렬 처리)

        Args:
            stock_data: {code: {'df': DataFrame, 'name': str}} 형태
            max_workers: 병렬 처리 워커 수

        Returns:
            스크리닝 결과 리스트
        """
        self.results = []

        total = len(stock_data)
        processed = 0
        passed = 0

        log_info(f"스크리닝 시작: {total}개 종목, {len(self.strategies)}개 전략")

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {}

            for code, data in stock_data.items():
                df = data.get('df')
                name = data.get('name', code)

                if df is None or df.empty:
                    continue

                future = executor.submit(self.screen_stock, df, code, name)
                futures[future] = code

            for future in as_completed(futures):
                code = futures[future]
                processed += 1

                try:
                    results = future.result()
                    if results:
                        self.results.extend(results)
                        passed += len(results)

                    # 진행률 로깅 (10% 단위)
                    if processed % max(1, total // 10) == 0:
                        log_info(f"진행: {processed}/{total} ({processed / total * 100:.1f}%)")

                except Exception as e:
                    log_error(f"스크리닝 오류 [{code}]: {e}")

        # 결과 정렬 (score 기준 내림차순)
        self.results.sort(key=lambda x: x.score, reverse=True)

        log_screening(
            strategy="ALL",
            total=total,
            passed=passed,
            results=[r.code for r in self.results[:10]]
        )

        return self.results

    def get_top_results(self, n: int = 10,
                        strategy: str = None) -> List[ScreeningResult]:
        """
        상위 N개 결과 반환

        Args:
            n: 반환할 개수
            strategy: 특정 전략으로 필터링 (None이면 전체)

        Returns:
            상위 스크리닝 결과
        """
        if strategy:
            filtered = [r for r in self.results if r.strategy == strategy]
        else:
            filtered = self.results

        return filtered[:n]

    def get_results_by_strategy(self) -> Dict[str, List[ScreeningResult]]:
        """전략별 결과 분류"""
        by_strategy = {}

        for result in self.results:
            if result.strategy not in by_strategy:
                by_strategy[result.strategy] = []
            by_strategy[result.strategy].append(result)

        return by_strategy

    def to_dataframe(self) -> pd.DataFrame:
        """결과를 DataFrame으로 변환"""
        if not self.results:
            return pd.DataFrame()

        records = []
        for r in self.results:
            record = {
                'code': r.code,
                'name': r.name,
                'datetime': r.datetime,
                'strategy': r.strategy,
                'score': r.score,
                'signal_type': r.signal.signal_type.value if r.signal else None,
                'entry_price': r.signal.price if r.signal else None,
                'stop_loss': r.signal.stop_loss if r.signal else None,
                'take_profit': r.signal.take_profit if r.signal else None,
                'reason': r.signal.reason if r.signal else None,
            }
            records.append(record)

        return pd.DataFrame(records)

    def generate_report(self) -> str:
        """스크리닝 보고서 생성"""
        if not self.results:
            return "스크리닝 결과가 없습니다."

        lines = []
        lines.append("=" * 60)
        lines.append("종목 스크리닝 보고서")
        lines.append(f"생성 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append("=" * 60)
        lines.append("")

        # 전략별 통계
        by_strategy = self.get_results_by_strategy()
        lines.append("[전략별 결과]")
        for strategy, results in by_strategy.items():
            lines.append(f"  - {strategy}: {len(results)}개 종목")
        lines.append("")

        # 상위 종목
        lines.append("[상위 종목 (점수순)]")
        for i, r in enumerate(self.results[:20], 1):
            signal_info = ""
            if r.signal:
                signal_info = f" | 진입: {r.signal.price:,.0f} | 손절: {r.signal.stop_loss:,.0f}"

            lines.append(
                f"  {i:2}. [{r.code}] {r.name} - {r.strategy} "
                f"(점수: {r.score:.2f}){signal_info}"
            )
        lines.append("")

        # 전략별 상세
        lines.append("[전략별 상세]")
        for strategy, results in by_strategy.items():
            lines.append(f"\n▶ {strategy}")
            for r in results[:5]:
                if r.signal:
                    lines.append(
                        f"   - [{r.code}] {r.name}: "
                        f"진입 {r.signal.price:,.0f}원, "
                        f"손절 {r.signal.stop_loss:,.0f}원, "
                        f"목표 {r.signal.take_profit:,.0f}원"
                    )
                    lines.append(f"     사유: {r.signal.reason}")
        lines.append("")

        lines.append("=" * 60)

        return "\n".join(lines)


class DailyScreener(StockScreener):
    """
    일봉 기반 스크리너

    장 마감 후 또는 장전 스크리닝용
    """

    def __init__(self, strategies: List[str] = None):
        # 일봉 전략만 사용
        daily_strategies = strategies or ['limit_up', 'breakout']
        filters = FilterFactory.create_preset('default')

        super().__init__(strategies=daily_strategies, filters=filters)


class IntradayScreener(StockScreener):
    """
    분봉 기반 스크리너

    장중 실시간 스크리닝용
    """

    def __init__(self, strategies: List[str] = None):
        # 분봉 전략 사용
        intraday_strategies = strategies or ['minute15', 'minute30']
        filters = FilterFactory.create_preset('volume_focus')

        super().__init__(strategies=intraday_strategies, filters=filters)


def run_screening(stock_data: Dict[str, Dict[str, Any]],
                  screener_type: str = 'daily',
                  strategies: List[str] = None) -> List[ScreeningResult]:
    """
    스크리닝 실행 헬퍼 함수

    Args:
        stock_data: {code: {'df': DataFrame, 'name': str}}
        screener_type: 'daily' 또는 'intraday'
        strategies: 사용할 전략 리스트

    Returns:
        스크리닝 결과
    """
    if screener_type == 'intraday':
        screener = IntradayScreener(strategies)
    else:
        screener = DailyScreener(strategies)

    return screener.screen_stocks(stock_data)
