#!/usr/bin/env python3
"""
주식 퀀트 트레이딩 시스템 - Streamlit 대시보드
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

# 프로젝트 루트 경로 추가
sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import get_db
from screener import StockScreener
from strategies import get_strategy, get_all_strategies
from backtest import Backtester, BacktestConfig, MultiStrategyBacktester

# 페이지 설정
st.set_page_config(
    page_title="Quant Trading Dashboard",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 스타일 - 다크모드 호환
st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: bold;
        color: #4FC3F7;
        margin-bottom: 1rem;
    }
    .metric-card {
        background-color: rgba(255, 255, 255, 0.1);
        padding: 1rem;
        border-radius: 0.5rem;
    }
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        color: #FFFFFF !important;
    }
    [data-testid="stMetricLabel"] {
        color: #B0BEC5 !important;
    }
    [data-testid="stMetricDelta"] {
        color: #81C784 !important;
    }
    .stMarkdown p, .stMarkdown li {
        color: #E0E0E0;
    }
    h1, h2, h3 {
        color: #FFFFFF !important;
    }
</style>
""", unsafe_allow_html=True)


# DB 데이터 로드 함수
@st.cache_data(ttl=60)
def load_stocks():
    """종목 데이터 로드"""
    db = get_db()
    return db.get_all_active_stocks()


@st.cache_data(ttl=60)
def load_stock_count():
    """종목 수 로드"""
    db = get_db()
    return {
        'total': db.get_row_count('stocks'),
        'kospi': len(db.get_stocks_by_market('KOSPI')),
        'kosdaq': len(db.get_stocks_by_market('KOSDAQ')),
        'daily_data': db.get_row_count('daily_ohlcv'),
    }


@st.cache_data(ttl=60)
def load_stock_data(code: str, limit: int = 100):
    """종목 일봉 데이터 로드"""
    db = get_db()
    return db.get_daily_ohlcv(code, limit=limit)


# 사이드바
st.sidebar.title("📊 Quant Trading")
st.sidebar.markdown("---")

menu = st.sidebar.radio(
    "메뉴 선택",
    ["🏠 대시보드", "🔍 종목 스크리닝", "📈 백테스트", "📊 종목 분석", "⚙️ 설정"]
)

# 메인 컨텐츠
if menu == "🏠 대시보드":
    st.markdown(
        '<h1 class="main-header">주식 퀀트 트레이딩 시스템</h1>',
        unsafe_allow_html=True
    )
    st.markdown("PDF '주식공부.pdf' 기반 매매 전략 구현 시스템")

    st.markdown("---")

    # DB에서 실제 데이터 로드
    counts = load_stock_count()

    # 주요 지표
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="📈 전략 수",
            value="4개",
            delta="활성"
        )

    with col2:
        st.metric(
            label="📊 등록 종목",
            value=f"{counts['total']:,}개",
            delta=f"KOSPI {counts['kospi']:,} / KOSDAQ {counts['kosdaq']:,}"
        )

    with col3:
        st.metric(
            label="📅 일봉 데이터",
            value=f"{counts['daily_data']:,}건",
            delta="수집 완료"
        )

    with col4:
        st.metric(
            label="🎯 시스템 상태",
            value="정상",
            delta="운영중"
        )

    st.markdown("---")

    # 시장별 종목 수
    st.subheader("📊 시장별 종목 현황")

    market_col1, market_col2 = st.columns(2)

    with market_col1:
        st.info(f"**KOSPI**: {counts['kospi']:,}개 종목")

    with market_col2:
        st.info(f"**KOSDAQ**: {counts['kosdaq']:,}개 종목")

    st.markdown("---")

    # 전략 소개
    st.subheader("📋 구현된 전략")

    strategies = {
        "상한가 따라잡기 (limit_up)": {
            "설명": "상한가 종목의 눌림목 진입",
            "타임프레임": "일봉",
            "위험도": "높음"
        },
        "돌파 매매 (breakout)": {
            "설명": "박스권 상단 돌파 시 매수",
            "타임프레임": "일봉/분봉",
            "위험도": "중간"
        },
        "15분봉 전략 (minute15)": {
            "설명": "15분봉 기반 단기 매매",
            "타임프레임": "15분봉",
            "위험도": "중간"
        },
        "30분봉 전략 (minute30)": {
            "설명": "30분봉 기반 스윙 매매",
            "타임프레임": "30분봉",
            "위험도": "낮음"
        }
    }

    cols = st.columns(2)
    for i, (name, info) in enumerate(strategies.items()):
        with cols[i % 2]:
            with st.container():
                st.markdown(f"**{name}**")
                st.write(f"- 설명: {info['설명']}")
                st.write(f"- 타임프레임: {info['타임프레임']}")
                st.write(f"- 위험도: {info['위험도']}")
                st.markdown("")

elif menu == "🔍 종목 스크리닝":
    st.header("🔍 종목 스크리닝")
    st.markdown("---")

    col1, col2 = st.columns([1, 2])

    # 필터 프리셋 설명
    PRESET_INFO = {
        "default": {
            "name": "기본 설정",
            "desc": "최소 거래량 10만주, 가격 1천~50만원, 20일선 위",
            "filters": [
                ("최소 거래량", "5일 평균 10만주 이상"),
                ("가격 범위", "1,000원 ~ 500,000원"),
                ("이동평균", "현재가 > 20일선"),
            ]
        },
        "aggressive": {
            "name": "공격적 (단기 급등)",
            "desc": "거래량 50만+, 급증 2배↑, 가격 3천~10만원, 정배열",
            "filters": [
                ("최소 거래량", "5일 평균 50만주 이상"),
                ("거래량 급증", "20일 평균 대비 2배 이상"),
                ("가격 범위", "3,000원 ~ 100,000원"),
                ("이동평균 정배열", "MA5 > MA20 > MA60"),
            ]
        },
        "conservative": {
            "name": "보수적 (안정적)",
            "desc": "거래량 5만+, 가격 5천~20만원, 60일선 위, 박스권 10%",
            "filters": [
                ("최소 거래량", "5일 평균 5만주 이상"),
                ("가격 범위", "5,000원 ~ 200,000원"),
                ("이동평균", "현재가 > 60일선"),
                ("박스권 횡보", "20일간 변동폭 10% 이내"),
            ]
        },
        "volume_focus": {
            "name": "거래량 중심",
            "desc": "거래량 100만+, 급증 3배↑, 2일 연속 증가",
            "filters": [
                ("최소 거래량", "5일 평균 100만주 이상"),
                ("거래량 급증", "20일 평균 대비 3배 이상"),
                ("거래량 증가", "2일 연속 거래량 증가"),
            ]
        },
        "breakout": {
            "name": "돌파 매매용",
            "desc": "거래량 20만+, 급증 2.5배↑, 52주 신고가 근접, 정배열",
            "filters": [
                ("최소 거래량", "5일 평균 20만주 이상"),
                ("거래량 급증", "20일 평균 대비 2.5배 이상"),
                ("52주 신고가", "현재가가 52주 최고가의 90% 이상"),
                ("이동평균 정배열", "MA5 > MA20"),
            ]
        },
    }

    with col1:
        st.subheader("스크리닝 설정")

        strategy = st.selectbox(
            "전략 선택",
            ["전체", "limit_up", "breakout", "minute15", "minute30"]
        )

        preset = st.selectbox(
            "필터 프리셋",
            list(PRESET_INFO.keys()),
            format_func=lambda x: f"{x} - {PRESET_INFO[x]['name']}"
        )

        # 선택된 프리셋 적용 필터 표시
        st.markdown("**📋 적용 필터:**")
        for filter_name, filter_desc in PRESET_INFO[preset]['filters']:
            st.caption(f"• {filter_name}: {filter_desc}")

        st.markdown("")
        market = st.multiselect(
            "시장",
            ["KOSPI", "KOSDAQ"],
            default=["KOSPI", "KOSDAQ"]
        )

        # 전체 종목 수 확인
        total_stocks = len(load_stocks()) if load_stocks() else 3000
        max_stocks = st.slider(
            "분석 종목 수",
            100, total_stocks, min(500, total_stocks), step=100,
            help=f"전체 종목: {total_stocks:,}개"
        )
        use_all = st.checkbox("전체 종목 분석", value=False)
        if use_all:
            max_stocks = total_stocks

        run_screening = st.button("🔍 스크리닝 실행", type="primary")

        # 프리셋 설명 펼침
        with st.expander("📖 전체 프리셋 비교"):
            for key, info in PRESET_INFO.items():
                st.markdown(f"**{key}** - {info['name']}")
                for fn, fd in info['filters']:
                    st.caption(f"  • {fn}: {fd}")
                st.markdown("")

    with col2:
        st.subheader("스크리닝 결과")

        if run_screening:
            progress_bar = st.progress(0)
            status_text = st.empty()

            status_text.text("종목 데이터 로드 중...")
            progress_bar.progress(10)

            # 종목 데이터 로드
            stocks = load_stocks()

            if not stocks:
                st.warning("등록된 종목이 없습니다.")
            else:
                # 시장 필터링
                filtered = [s for s in stocks if s['market'] in market][:max_stocks]

                status_text.text(f"{len(filtered)}개 종목 데이터 준비 중...")
                progress_bar.progress(20)

                # 종목별 데이터 로드
                db = get_db()
                stock_data = {}

                for i, stock in enumerate(filtered):
                    code = stock['code']
                    name = stock['name']
                    df = db.get_daily_ohlcv(code, limit=252)

                    if df is not None and len(df) >= 20:
                        stock_data[code] = {'df': df, 'name': name}

                    # 진행률 업데이트
                    progress = 20 + int(50 * (i + 1) / len(filtered))
                    progress_bar.progress(progress)

                status_text.text(f"스크리닝 실행 중... ({len(stock_data)}개 종목)")
                progress_bar.progress(75)

                # 스크리너 생성 및 실행
                strategy_list = None if strategy == "전체" else [strategy]
                screener = StockScreener(strategies=strategy_list)
                screener.set_filter_preset(preset)

                results = screener.screen_stocks(stock_data, max_workers=4)

                progress_bar.progress(100)
                status_text.text("완료!")

                if results:
                    st.success(f"🎯 {len(results)}개 매수 신호 발견!")

                    # 결과 DataFrame
                    result_df = screener.to_dataframe()
                    result_df = result_df[[
                        'code', 'name', 'strategy', 'score',
                        'entry_price', 'stop_loss', 'take_profit', 'reason'
                    ]]
                    result_df.columns = [
                        '종목코드', '종목명', '전략', '점수',
                        '진입가', '손절가', '목표가', '매수사유'
                    ]

                    # 가격 포맷팅
                    for col in ['진입가', '손절가', '목표가']:
                        result_df[col] = result_df[col].apply(
                            lambda x: f"{x:,.0f}" if pd.notna(x) else "-"
                        )
                    result_df['점수'] = result_df['점수'].apply(
                        lambda x: f"{x:.2f}"
                    )

                    st.dataframe(
                        result_df,
                        use_container_width=True,
                        hide_index=True
                    )

                    # 전략별 통계
                    st.markdown("---")
                    st.subheader("전략별 통계")
                    by_strategy = screener.get_results_by_strategy()
                    stat_cols = st.columns(len(by_strategy))
                    for i, (strat, res) in enumerate(by_strategy.items()):
                        with stat_cols[i]:
                            st.metric(strat, f"{len(res)}개")

                else:
                    st.info("조건을 만족하는 종목이 없습니다.")

        else:
            stocks = load_stocks()
            if stocks:
                st.success(f"총 {len(stocks)}개 종목 데이터 준비됨")
                st.info("왼쪽에서 설정 후 '스크리닝 실행' 버튼을 클릭하세요.")
            else:
                st.warning("종목 데이터가 없습니다. 데이터 수집을 먼저 실행하세요.")

elif menu == "📈 백테스트":
    st.header("📈 백테스트")
    st.markdown("---")

    col1, col2 = st.columns([1, 2])

    with col1:
        st.subheader("백테스트 설정")

        # 전략 선택
        strategy_options = ["전체", "limit_up", "breakout", "minute15", "minute30"]
        strategy = st.selectbox(
            "전략 선택",
            strategy_options,
            help="'전체' 선택 시 모든 전략을 비교합니다"
        )

        # 종목 선택 방식
        stock_selection = st.radio(
            "종목 선택 방식",
            ["시장 전체", "직접 입력", "주요 종목"],
            horizontal=True
        )

        selected_codes = []

        if stock_selection == "시장 전체":
            # 시장 선택
            bt_market = st.multiselect(
                "시장",
                ["KOSPI", "KOSDAQ"],
                default=["KOSPI", "KOSDAQ"]
            )
            # 분석 종목 수 제한
            max_stocks = st.slider("분석 종목 수", 50, 500, 100, step=50)

        elif stock_selection == "직접 입력":
            bt_market = ["KOSPI", "KOSDAQ"]
            max_stocks = 100

            # 종목 목록 로드
            all_stocks = load_stocks()
            stock_dict = {
                f"{s['name']} ({s['code']})": s['code']
                for s in all_stocks
            }

            # 종목 검색 및 선택 (multiselect)
            selected_items = st.multiselect(
                "종목 검색 (이름 또는 코드)",
                options=list(stock_dict.keys()),
                placeholder="종목명을 입력하세요...",
                help="여러 종목을 선택할 수 있습니다"
            )

            if selected_items:
                selected_codes = [stock_dict[item] for item in selected_items]
                st.caption(f"선택된 종목: {len(selected_codes)}개")

                # 선택된 종목 표시
                with st.expander("선택된 종목 목록"):
                    for item in selected_items:
                        st.write(f"• {item}")

        else:  # 주요 종목
            bt_market = ["KOSPI", "KOSDAQ"]
            max_stocks = 50

            # 주요 종목 프리셋
            major_stocks = {
                "대형주 TOP 10": [
                    "005930", "000660", "035420", "005380", "006400",
                    "035720", "051910", "005490", "028260", "012330"
                ],
                "2차전지/반도체": [
                    "373220", "006400", "051910", "000660", "005930",
                    "247540", "086520", "042700", "091990", "298050"
                ],
                "바이오/헬스케어": [
                    "068270", "207940", "005930", "091990", "326030",
                    "145020", "128940", "141080", "196170", "054950"
                ],
                "금융주": [
                    "105560", "055550", "086790", "024110", "316140",
                    "138930", "029780", "003550", "000810", "032830"
                ],
            }

            preset_choice = st.selectbox(
                "종목 프리셋",
                list(major_stocks.keys())
            )
            selected_codes = major_stocks[preset_choice]
            st.caption(f"선택된 종목: {', '.join(selected_codes[:5])}...")

        # 기간 설정
        days = st.slider("백테스트 기간 (일)", 30, 730, 365)

        # 초기 자본
        initial_capital = st.number_input(
            "초기 자본 (원)",
            min_value=1000000,
            max_value=1000000000,
            value=10000000,
            step=1000000,
            format="%d"
        )

        # 고급 설정 (Expander)
        with st.expander("고급 설정"):
            max_positions = st.slider(
                "최대 동시 보유 종목",
                1, 20, 10
            )
            max_position_pct = st.slider(
                "종목당 최대 투자 비율 (%)",
                5, 50, 10
            )
            use_stop_loss = st.checkbox("손절 사용", value=True)
            use_take_profit = st.checkbox("익절 사용", value=True)
            commission_rate = st.number_input(
                "수수료율 (%)",
                min_value=0.0,
                max_value=1.0,
                value=0.015,
                step=0.001,
                format="%.3f"
            )

        run_backtest = st.button("📊 백테스트 실행", type="primary")

    with col2:
        st.subheader("백테스트 결과")

        if run_backtest:
            progress_bar = st.progress(0)
            status_text = st.empty()

            status_text.text("종목 데이터 로드 중...")
            progress_bar.progress(5)

            # 종목 데이터 로드
            stocks = load_stocks()
            if not stocks:
                st.error("등록된 종목이 없습니다. 데이터 수집을 먼저 실행하세요.")
            else:
                db = get_db()
                stock_data = {}

                # 종목 선택 방식에 따라 처리
                if selected_codes:
                    # 직접 입력 또는 프리셋 선택한 경우
                    codes_to_load = selected_codes
                    status_text.text(f"{len(codes_to_load)}개 지정 종목 데이터 준비 중...")
                else:
                    # 시장 전체 선택한 경우
                    filtered = [s for s in stocks if s['market'] in bt_market]
                    filtered = filtered[:max_stocks]
                    codes_to_load = [s['code'] for s in filtered]
                    status_text.text(f"{len(codes_to_load)}개 종목 데이터 준비 중...")

                progress_bar.progress(10)

                # 종목별 OHLCV 데이터 로드
                for i, code in enumerate(codes_to_load):
                    df = db.get_daily_ohlcv(code, limit=days + 60)

                    if df is not None and len(df) >= 20:
                        # 인덱스가 datetime인지 확인
                        if not isinstance(df.index, pd.DatetimeIndex):
                            df.index = pd.to_datetime(df.index)
                        stock_data[code] = df

                    # 진행률 업데이트
                    progress = 10 + int(40 * (i + 1) / len(codes_to_load))
                    progress_bar.progress(progress)

                if not stock_data:
                    st.error("유효한 데이터가 없습니다.")
                else:
                    status_text.text(f"백테스트 실행 중... ({len(stock_data)}개 종목)")
                    progress_bar.progress(55)

                    # BacktestConfig 설정
                    config = BacktestConfig(
                        initial_capital=initial_capital,
                        commission_rate=commission_rate / 100,
                        max_position_size=max_position_pct / 100,
                        max_positions=max_positions,
                        use_stop_loss=use_stop_loss,
                        use_take_profit=use_take_profit,
                    )

                    try:
                        if strategy == "전체":
                            # 다중 전략 백테스트
                            strategies_to_test = [
                                "limit_up", "breakout", "minute15", "minute30"
                            ]
                            bt = MultiStrategyBacktester(strategies_to_test, config)
                            results = bt.run(stock_data)

                            progress_bar.progress(90)
                            status_text.text("결과 분석 중...")

                            # 전략 비교 테이블
                            st.success("백테스트 완료!")

                            compare_df = bt.compare_strategies()
                            if not compare_df.empty:
                                st.markdown("### 전략별 성과 비교")

                                # 수익률 컬럼 포맷팅
                                display_df = compare_df.copy()
                                for col in display_df.columns:
                                    if '수익률' in col or 'MDD' in col or '승률' in col:
                                        display_df[col] = display_df[col].apply(
                                            lambda x: f"{x:.2f}%"
                                        )
                                    elif col in ['샤프비율', '수익팩터']:
                                        display_df[col] = display_df[col].apply(
                                            lambda x: f"{x:.2f}"
                                        )

                                st.dataframe(
                                    display_df,
                                    use_container_width=True,
                                    hide_index=True
                                )

                                # 최고 성과 전략
                                best = compare_df.iloc[0]
                                st.info(
                                    f"**최고 성과 전략**: {best['전략']} "
                                    f"(수익률 {best['총수익률(%)']:.2f}%)"
                                )

                                # 전략별 상세 결과
                                st.markdown("### 전략별 상세 결과")
                                tabs = st.tabs(list(results.keys()))

                                for i, (strat_name, metrics) in enumerate(
                                    results.items()
                                ):
                                    with tabs[i]:
                                        m_col1, m_col2, m_col3, m_col4 = st.columns(4)
                                        with m_col1:
                                            color = (
                                                "normal"
                                                if metrics.total_return >= 0
                                                else "inverse"
                                            )
                                            st.metric(
                                                "총 수익률",
                                                f"{metrics.total_return_percent:.2f}%",
                                                delta=f"{metrics.total_return:,.0f}원",
                                                delta_color=color
                                            )
                                        with m_col2:
                                            st.metric(
                                                "MDD",
                                                f"{metrics.max_drawdown_percent:.2f}%"
                                            )
                                        with m_col3:
                                            st.metric(
                                                "승률",
                                                f"{metrics.win_rate:.1f}%"
                                            )
                                        with m_col4:
                                            st.metric(
                                                "총 거래",
                                                f"{metrics.total_trades}회"
                                            )

                        else:
                            # 단일 전략 백테스트
                            bt = Backtester(strategy, config)
                            metrics = bt.run(stock_data)

                            progress_bar.progress(90)
                            status_text.text("결과 분석 중...")

                            st.success(f"**{strategy}** 전략 백테스트 완료!")

                            # 주요 지표
                            st.markdown("### 주요 성과 지표")
                            m_col1, m_col2, m_col3, m_col4 = st.columns(4)

                            with m_col1:
                                color = (
                                    "normal"
                                    if metrics.total_return >= 0
                                    else "inverse"
                                )
                                st.metric(
                                    "총 수익률",
                                    f"{metrics.total_return_percent:.2f}%",
                                    delta=f"{metrics.total_return:,.0f}원",
                                    delta_color=color
                                )
                            with m_col2:
                                st.metric(
                                    "연환산 수익률",
                                    f"{metrics.annualized_return:.2f}%"
                                )
                            with m_col3:
                                st.metric(
                                    "최대 낙폭 (MDD)",
                                    f"{metrics.max_drawdown_percent:.2f}%"
                                )
                            with m_col4:
                                st.metric("샤프 비율", f"{metrics.sharpe_ratio:.2f}")

                            # 거래 통계
                            st.markdown("### 거래 통계")
                            t_col1, t_col2, t_col3, t_col4 = st.columns(4)

                            with t_col1:
                                st.metric("총 거래 수", f"{metrics.total_trades}회")
                            with t_col2:
                                st.metric("승률", f"{metrics.win_rate:.1f}%")
                            with t_col3:
                                st.metric("수익 팩터", f"{metrics.profit_factor:.2f}")
                            with t_col4:
                                st.metric(
                                    "평균 보유일",
                                    f"{metrics.avg_holding_days:.1f}일"
                                )

                            # 손익 통계
                            st.markdown("### 손익 통계")
                            p_col1, p_col2, p_col3 = st.columns(3)

                            with p_col1:
                                st.metric(
                                    "평균 수익 거래",
                                    f"{metrics.avg_profit:,.0f}원",
                                    delta=f"{metrics.avg_profit_percent:.2f}%"
                                )
                            with p_col2:
                                st.metric(
                                    "평균 손실 거래",
                                    f"{metrics.avg_loss:,.0f}원",
                                    delta=f"{metrics.avg_loss_percent:.2f}%",
                                    delta_color="inverse"
                                )
                            with p_col3:
                                st.metric(
                                    "평균 거래 손익",
                                    f"{metrics.avg_trade:,.0f}원"
                                )

                            # 자산 곡선 차트
                            equity_df = bt.get_equity_curve()
                            if not equity_df.empty:
                                st.markdown("### 자산 곡선")
                                chart_data = equity_df.set_index('date')['equity']
                                st.line_chart(chart_data)

                            # 거래 내역
                            trades = bt.get_trades()
                            if trades:
                                st.markdown("### 거래 내역")
                                trade_records = []
                                for t in trades:
                                    trade_records.append({
                                        '종목코드': t.code,
                                        '종목명': t.name,
                                        '진입일': str(t.entry_date)[:10],
                                        '진입가': f"{t.entry_price:,.0f}",
                                        '청산일': str(t.exit_date)[:10],
                                        '청산가': f"{t.exit_price:,.0f}",
                                        '손익': f"{t.pnl:,.0f}",
                                        '수익률': f"{t.pnl_percent:.2f}%",
                                        '청산사유': t.exit_reason,
                                    })
                                trade_df = pd.DataFrame(trade_records)
                                st.dataframe(
                                    trade_df,
                                    use_container_width=True,
                                    hide_index=True
                                )

                        progress_bar.progress(100)
                        status_text.text("완료!")

                    except Exception as e:
                        st.error(f"백테스트 실행 중 오류 발생: {str(e)}")
                        import traceback
                        st.code(traceback.format_exc())

        else:
            # 초기 화면
            counts = load_stock_count()

            result_col1, result_col2, result_col3 = st.columns(3)

            with result_col1:
                st.metric("등록 종목", f"{counts['total']:,}개")
            with result_col2:
                st.metric("일봉 데이터", f"{counts['daily_data']:,}건")
            with result_col3:
                st.metric(
                    "데이터 상태",
                    "준비됨" if counts['total'] > 0 else "없음"
                )

            st.markdown("---")
            st.info("왼쪽에서 설정 후 '백테스트 실행' 버튼을 클릭하세요.")

elif menu == "📊 종목 분석":
    st.header("📊 종목 분석")
    st.markdown("---")

    col1, col2 = st.columns([1, 3])

    with col1:
        st.subheader("종목 검색")

        # 종목 목록 로드
        stocks = load_stocks()
        stock_options = {f"{s['code']} - {s['name']}": s['code'] for s in stocks}

        selected = st.selectbox(
            "종목 선택",
            options=["직접 입력"] + list(stock_options.keys())
        )

        if selected == "직접 입력":
            code = st.text_input("종목 코드", placeholder="예: 005930")
        else:
            code = stock_options.get(selected, "")

        analyze_btn = st.button("🔍 분석 실행", type="primary")

    with col2:
        st.subheader("분석 결과")

        if analyze_btn and code:
            with st.spinner(f"{code} 분석 중..."):
                # 종목 데이터 로드
                df = load_stock_data(code, limit=252)

                if df.empty:
                    st.error(f"종목 {code}의 데이터가 없습니다.")
                else:
                    # 종목 정보
                    db = get_db()
                    stock_info = db.get_stock(code)
                    if stock_info:
                        st.info(f"**{stock_info['name']}** ({code}) - {stock_info['market']}")

                    tab1, tab2, tab3 = st.tabs(["기본 정보", "가격 데이터", "차트"])

                    with tab1:
                        latest = df.iloc[-1]
                        col_a, col_b, col_c = st.columns(3)

                        with col_a:
                            st.metric("현재가", f"{latest['close']:,.0f}원")
                        with col_b:
                            st.metric("거래량", f"{latest['volume']:,.0f}")
                        with col_c:
                            if len(df) > 1:
                                prev_close = df.iloc[-2]['close']
                                change = (latest['close'] - prev_close) / prev_close * 100
                                st.metric("등락률", f"{change:.2f}%")

                        st.markdown("---")
                        st.write(f"- 데이터 기간: {len(df)}일")
                        st.write(f"- 최고가: {df['high'].max():,.0f}원")
                        st.write(f"- 최저가: {df['low'].min():,.0f}원")
                        st.write(f"- 평균 거래량: {df['volume'].mean():,.0f}")

                    with tab2:
                        # 최근 데이터 테이블
                        display_df = df.tail(20).copy()
                        display_df = display_df[['open', 'high', 'low', 'close', 'volume']]
                        display_df.columns = ['시가', '고가', '저가', '종가', '거래량']
                        display_df = display_df.sort_index(ascending=False)
                        st.dataframe(display_df, use_container_width=True)

                    with tab3:
                        # 종가 차트
                        st.line_chart(df['close'].tail(60))

        elif not code:
            st.info("왼쪽에서 종목을 선택하거나 코드를 입력하세요.")

elif menu == "⚙️ 설정":
    st.header("⚙️ 설정")
    st.markdown("---")

    tab1, tab2, tab3 = st.tabs(["데이터 현황", "데이터 수집", "시스템 정보"])

    with tab1:
        st.subheader("데이터베이스 현황")

        counts = load_stock_count()

        col1, col2 = st.columns(2)

        with col1:
            st.metric("총 종목 수", f"{counts['total']:,}개")
            st.metric("KOSPI", f"{counts['kospi']:,}개")
            st.metric("KOSDAQ", f"{counts['kosdaq']:,}개")

        with col2:
            st.metric("일봉 데이터", f"{counts['daily_data']:,}건")

            db = get_db()
            avg_per_stock = (counts['daily_data'] / counts['total']
                             if counts['total'] > 0 else 0)
            st.metric("종목당 평균", f"{avg_per_stock:.0f}일")

    with tab2:
        st.subheader("데이터 수집")

        st.markdown("**수집 명령어**")
        st.code("python main.py --mode collect", language="bash")

        st.markdown("**옵션**")
        st.write("- `--market KOSPI` : KOSPI만 수집")
        st.write("- `--market KOSDAQ` : KOSDAQ만 수집")
        st.write("- `--days 365` : 수집 기간 설정")

    with tab3:
        st.subheader("시스템 정보")

        st.write(f"- Python 버전: {sys.version.split()[0]}")
        st.write(f"- 프로젝트 경로: {Path(__file__).parent}")
        st.write(f"- 현재 시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

        db = get_db()
        st.write(f"- DB 경로: {db.db_path}")

# 푸터
st.sidebar.markdown("---")
st.sidebar.markdown(
    """
    <div style='text-align: center; color: gray;'>
        <small>Quant Trading System v1.0</small><br>
        <small>PDF 기반 매매 전략</small>
    </div>
    """,
    unsafe_allow_html=True
)
