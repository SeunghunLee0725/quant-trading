"""
텔레그램 봇 알림 모듈
매매 신호 및 보고서 전송
"""

import asyncio
import aiohttp
from datetime import datetime
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import TELEGRAM
from strategies import Signal
from screener import ScreeningResult
from backtest import PerformanceMetrics
from utils import log_error, log_warning


@dataclass
class TelegramConfig:
    """텔레그램 설정"""
    bot_token: str
    chat_id: str
    enabled: bool = True
    parse_mode: str = "HTML"
    disable_notification: bool = False


class TelegramNotifier:
    """
    텔레그램 알림 봇

    매매 신호, 스크리닝 결과, 백테스트 보고서 등 전송
    """

    BASE_URL = "https://api.telegram.org/bot{token}/{method}"

    def __init__(self, config: TelegramConfig = None):
        """
        Args:
            config: 텔레그램 설정 (None이면 환경변수에서 로드)
        """
        if config:
            self.config = config
        else:
            self.config = TelegramConfig(
                bot_token=TELEGRAM.get('bot_token', ''),
                chat_id=TELEGRAM.get('chat_id', ''),
                enabled=TELEGRAM.get('enabled', False),
            )

        self._session: Optional[aiohttp.ClientSession] = None

    @property
    def is_configured(self) -> bool:
        """설정 완료 여부"""
        return bool(self.config.bot_token and self.config.chat_id)

    async def _get_session(self) -> aiohttp.ClientSession:
        """HTTP 세션 반환"""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def close(self):
        """세션 종료"""
        if self._session and not self._session.closed:
            await self._session.close()

    async def _send_request(self, method: str, **params) -> Dict[str, Any]:
        """
        텔레그램 API 요청

        Args:
            method: API 메소드
            **params: 요청 파라미터

        Returns:
            API 응답
        """
        if not self.is_configured:
            log_warning("텔레그램이 설정되지 않았습니다")
            return {'ok': False, 'error': 'Not configured'}

        url = self.BASE_URL.format(token=self.config.bot_token, method=method)

        try:
            session = await self._get_session()
            async with session.post(url, json=params) as response:
                result = await response.json()

                if not result.get('ok'):
                    log_error(f"텔레그램 API 오류: {result.get('description')}")

                return result

        except Exception as e:
            log_error(f"텔레그램 요청 실패: {e}")
            return {'ok': False, 'error': str(e)}

    async def send_message(self, text: str, parse_mode: str = None,
                           disable_notification: bool = None) -> bool:
        """
        메시지 전송

        Args:
            text: 메시지 내용
            parse_mode: 파싱 모드 (HTML, Markdown)
            disable_notification: 알림 끄기

        Returns:
            성공 여부
        """
        if not self.config.enabled:
            return False

        params = {
            'chat_id': self.config.chat_id,
            'text': text,
            'parse_mode': parse_mode or self.config.parse_mode,
            'disable_notification': disable_notification or self.config.disable_notification,
        }

        result = await self._send_request('sendMessage', **params)
        return result.get('ok', False)

    def send_message_sync(self, text: str, **kwargs) -> bool:
        """동기 메시지 전송"""
        return asyncio.run(self.send_message(text, **kwargs))

    # ============ 신호 알림 ============

    async def send_signal(self, signal: Signal) -> bool:
        """
        매매 신호 전송

        Args:
            signal: Signal 객체
        """
        emoji = "🔵" if signal.signal_type.value == 'BUY' else "🔴"
        signal_type = "매수" if signal.signal_type.value == 'BUY' else "매도"

        message = f"""
{emoji} <b>{signal_type} 신호</b>

📌 <b>종목:</b> [{signal.code}] {signal.name}
📊 <b>전략:</b> {signal.strategy}
💰 <b>진입가:</b> {signal.price:,.0f}원
🛑 <b>손절가:</b> {signal.stop_loss:,.0f}원 ({(signal.stop_loss - signal.price) / signal.price * 100:.1f}%)
🎯 <b>목표가:</b> {signal.take_profit:,.0f}원 ({(signal.take_profit - signal.price) / signal.price * 100:.1f}%)
📝 <b>사유:</b> {signal.reason}
⏰ <b>시간:</b> {signal.datetime.strftime('%Y-%m-%d %H:%M')}
💪 <b>강도:</b> {signal.strength:.2f}
"""
        return await self.send_message(message.strip())

    async def send_signals(self, signals: List[Signal]) -> int:
        """
        여러 신호 전송

        Returns:
            성공 전송 수
        """
        success_count = 0
        for signal in signals:
            if await self.send_signal(signal):
                success_count += 1
                await asyncio.sleep(0.5)  # 속도 제한
        return success_count

    # ============ 스크리닝 알림 ============

    async def send_screening_result(self, result: ScreeningResult) -> bool:
        """스크리닝 결과 전송"""
        if not result.signal:
            return False

        return await self.send_signal(result.signal)

    async def send_screening_summary(self, results: List[ScreeningResult],
                                     max_items: int = 10) -> bool:
        """
        스크리닝 요약 전송

        Args:
            results: 스크리닝 결과 리스트
            max_items: 최대 표시 항목 수
        """
        if not results:
            return await self.send_message("📊 스크리닝 결과: 조건 충족 종목 없음")

        # 전략별 분류
        by_strategy = {}
        for r in results:
            if r.strategy not in by_strategy:
                by_strategy[r.strategy] = []
            by_strategy[r.strategy].append(r)

        message_lines = [
            "📊 <b>스크리닝 결과</b>",
            f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            f"총 {len(results)}개 종목 발견",
            "",
        ]

        for strategy, items in by_strategy.items():
            message_lines.append(f"<b>▶ {strategy}</b>")

            for r in items[:max_items]:
                if r.signal:
                    price = r.signal.price
                    message_lines.append(
                        f"  • [{r.code}] {r.name}: {price:,.0f}원"
                    )

            if len(items) > max_items:
                message_lines.append(f"  ... 외 {len(items) - max_items}개")

            message_lines.append("")

        return await self.send_message("\n".join(message_lines))

    # ============ 백테스트 알림 ============

    async def send_backtest_result(self, metrics: PerformanceMetrics,
                                   strategy_name: str = "") -> bool:
        """백테스트 결과 전송"""
        profit_emoji = "📈" if metrics.total_return_percent > 0 else "📉"

        message = f"""
{profit_emoji} <b>백테스트 결과</b> - {strategy_name}

📊 <b>수익률</b>
  • 총 수익률: {metrics.total_return_percent:.2f}%
  • 연환산 수익률: {metrics.annualized_return:.2f}%
  • 총 수익금: {metrics.total_return:,.0f}원

⚠️ <b>리스크</b>
  • 최대 낙폭: {metrics.max_drawdown_percent:.2f}%
  • 샤프 비율: {metrics.sharpe_ratio:.2f}

📈 <b>거래 통계</b>
  • 총 거래: {metrics.total_trades}회
  • 승률: {metrics.win_rate:.1f}%
  • 수익 팩터: {metrics.profit_factor:.2f}
  • 평균 보유일: {metrics.avg_holding_days:.1f}일
"""
        return await self.send_message(message.strip())

    # ============ 일반 알림 ============

    async def send_daily_report(self, report: str) -> bool:
        """일일 보고서 전송"""
        header = f"📋 <b>일일 보고서</b>\n⏰ {datetime.now().strftime('%Y-%m-%d')}\n\n"
        return await self.send_message(header + report)

    async def send_error_alert(self, error_message: str) -> bool:
        """오류 알림 전송"""
        message = f"""
🚨 <b>오류 발생</b>

⏰ {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
📝 {error_message}
"""
        return await self.send_message(message.strip())

    async def send_position_update(self, code: str, name: str,
                                   action: str, price: float,
                                   quantity: int, pnl: float = None,
                                   reason: str = "") -> bool:
        """포지션 변경 알림"""
        emoji = "🟢" if action == 'BUY' else "🔴"
        action_text = "매수" if action == 'BUY' else "매도"

        message_lines = [
            f"{emoji} <b>{action_text} 체결</b>",
            "",
            f"📌 <b>종목:</b> [{code}] {name}",
            f"💰 <b>가격:</b> {price:,.0f}원",
            f"📦 <b>수량:</b> {quantity:,}주",
            f"💵 <b>금액:</b> {price * quantity:,.0f}원",
        ]

        if pnl is not None:
            pnl_emoji = "💰" if pnl >= 0 else "💸"
            message_lines.append(f"{pnl_emoji} <b>손익:</b> {pnl:+,.0f}원")

        if reason:
            message_lines.append(f"📝 <b>사유:</b> {reason}")

        message_lines.append(f"⏰ {datetime.now().strftime('%Y-%m-%d %H:%M')}")

        return await self.send_message("\n".join(message_lines))


# 싱글톤 인스턴스
_notifier: Optional[TelegramNotifier] = None


def get_notifier() -> TelegramNotifier:
    """텔레그램 알림 인스턴스 반환"""
    global _notifier
    if _notifier is None:
        _notifier = TelegramNotifier()
    return _notifier


# 편의 함수들
def notify_signal(signal: Signal) -> bool:
    """신호 알림 (동기)"""
    notifier = get_notifier()
    return asyncio.run(notifier.send_signal(signal))


def notify_signals(signals: List[Signal]) -> int:
    """여러 신호 알림 (동기)"""
    notifier = get_notifier()
    return asyncio.run(notifier.send_signals(signals))


def notify_screening(results: List[ScreeningResult]) -> bool:
    """스크리닝 결과 알림 (동기)"""
    notifier = get_notifier()
    return asyncio.run(notifier.send_screening_summary(results))


def notify_backtest(metrics: PerformanceMetrics,
                    strategy_name: str = "") -> bool:
    """백테스트 결과 알림 (동기)"""
    notifier = get_notifier()
    return asyncio.run(notifier.send_backtest_result(metrics, strategy_name))


def notify_error(error_message: str) -> bool:
    """오류 알림 (동기)"""
    notifier = get_notifier()
    return asyncio.run(notifier.send_error_alert(error_message))


def notify_message(text: str) -> bool:
    """일반 메시지 알림 (동기)"""
    notifier = get_notifier()
    return notifier.send_message_sync(text)
