#!/usr/bin/env python3
"""
주식 퀀트 트레이딩 시스템 - Streamlit 대시보드 (모바일 최적화)
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

# 페이지 설정 - 모바일 최적화
st.set_page_config(
    page_title="Quant Trading",
    page_icon="📈",
    layout="centered",  # 모바일에 적합한 centered 레이아웃
    initial_sidebar_state="collapsed"  # 사이드바 기본 접힘
)

# 모바일 최적화 CSS
st.markdown("""
<style>
    /* 모바일 최적화 */
    .block-container {
        padding: 1rem 0.5rem !important;
        max-width: 100% !important;
    }

    /* 메인 헤더 */
    .main-header {
        font-size: 1.5rem;
        font-weight: bold;
        color: #4FC3F7;
        text-align: center;
        margin-bottom: 0.5rem;
    }

    /* 메트릭 카드 모바일 최적화 */
    [data-testid="stMetricValue"] {
        font-size: 1.3rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.7rem !important;
    }

    /* 버튼 모바일 최적화 */
    .stButton > button {
        width: 100% !important;
        padding: 0.75rem !important;
        font-size: 1rem !important;
    }

    /* 입력 필드 모바일 최적화 */
    .stSelectbox, .stMultiSelect, .stSlider, .stNumberInput {
        margin-bottom: 0.5rem !important;
    }

    /* 데이터프레임 스크롤 */
    .stDataFrame {
        font-size: 0.8rem !important;
    }

    /* 탭 모바일 최적화 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
    }
    .stTabs [data-baseweb="tab"] {
        padding: 0.5rem 1rem;
        font-size: 0.9rem;
    }

    /* 사이드바 너비 조정 */
    [data-testid="stSidebar"] {
        min-width: 200px !important;
        max-width: 250px !important;
    }

    /* 다크모드 텍스트 */
    .stMarkdown p, .stMarkdown li {
        color: #E0E0E0;
    }
    h1, h2, h3 {
        color: #FFFFFF !important;
    }

    /* 카드 스타일 */
    .info-card {
        background: rgba(255,255,255,0.05);
        border-radius: 10px;
        padding: 1rem;
        margin: 0.5rem 0;
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


# 사이드바 - 간소화
with st.sidebar:
    st.title("📊 메뉴")
    menu = st.radio(
        "",
        ["🏠 홈", "🔍 스크리닝", "📈 백테스트", "📊 종목분석", "⚙️ 설정"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.caption("Quant Trading v1.0")

# 메인 컨텐츠
if menu == "🏠 홈":
    st.markdown('<h1 class="main-header">📈 퀀트 트레이딩</h1>', unsafe_allow_html=True)

    # DB에서 실제 데이터 로드
    counts = load_stock_count()

    # 주요 지표 - 2x2 그리드
    col1, col2 = st.columns(2)
    with col1:
        st.metric("📊 종목", f"{counts['total']:,}")
    with col2:
        st.metric("📅 데이터", f"{counts['daily_data']:,}")

    col3, col4 = st.columns(2)
    with col3:
        st.metric("📈 전략", "4개")
    with col4:
        st.metric("🎯 상태", "정상")

    st.markdown("---")

    # 시장별 현황
    st.subheader("📊 시장 현황")
    st.info(f"**KOSPI** {counts['kospi']:,}개 | **KOSDAQ** {counts['kosdaq']:,}개")

    st.markdown("---")

    # 전략 소개 - 접히는 형태
    st.subheader("📋 전략")

    with st.expander("상한가 따라잡기 (limit_up)", expanded=False):
        st.write("상한가 종목의 눌림목 진입")
        st.caption("타임프레임: 일봉 | 위험도: 높음")

    with st.expander("돌파 매매 (breakout)", expanded=False):
        st.write("박스권 상단 돌파 시 매수")
        st.caption("타임프레임: 일봉 | 위험도: 중간")

    with st.expander("15분봉 전략 (minute15)", expanded=False):
        st.write("15분봉 기반 단기 매매")
        st.caption("타임프레임: 15분봉 | 위험도: 중간")

    with st.expander("30분봉 전략 (minute30)", expanded=False):
        st.write("30분봉 기반 스윙 매매")
        st.caption("타임프레임: 30분봉 | 위험도: 낮음")

elif menu == "🔍 스크리닝":
    st.markdown('<h1 class="main-header">🔍 종목 스크리닝</h1>', unsafe_allow_html=True)

    # 필터 프리셋
    PRESET_INFO = {
        "default": {"name": "기본", "desc": "거래량 10만+, 20일선 위"},
        "aggressive": {"name": "공격적", "desc": "급등주, 정배열"},
        "conservative": {"name": "보수적", "desc": "안정적, 박스권"},
        "volume_focus": {"name": "거래량", "desc": "거래량 급증"},
        "breakout": {"name": "돌파", "desc": "52주 신고가 근접"},
    }

    # 설정 영역
    strategy = st.selectbox(
        "전략",
        ["전체", "limit_up", "breakout", "minute15", "minute30"]
    )

    preset = st.selectbox(
        "필터",
        list(PRESET_INFO.keys()),
        format_func=lambda x: f"{PRESET_INFO[x]['name']} - {PRESET_INFO[x]['desc']}"
    )

    market = st.multiselect(
        "시장",
        ["KOSPI", "KOSDAQ"],
        default=["KOSPI", "KOSDAQ"]
    )

    total_stocks = len(load_stocks()) if load_stocks() else 3000
    max_stocks = st.slider(
        "분석 종목 수",
        100, min(1000, total_stocks), 300, step=100
    )

    run_screening = st.button("🔍 스크리닝 실행", type="primary", use_container_width=True)

    st.markdown("---")

    # 결과 영역
    if run_screening:
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("종목 데이터 로드 중...")
        progress_bar.progress(10)

        stocks = load_stocks()

        if not stocks:
            st.warning("등록된 종목이 없습니다.")
        else:
            filtered = [s for s in stocks if s['market'] in market][:max_stocks]

            status_text.text(f"{len(filtered)}개 종목 분석 중...")
            progress_bar.progress(20)

            db = get_db()
            stock_data = {}

            for i, stock in enumerate(filtered):
                code = stock['code']
                name = stock['name']
                df = db.get_daily_ohlcv(code, limit=252)

                if df is not None and len(df) >= 20:
                    stock_data[code] = {'df': df, 'name': name}

                progress = 20 + int(50 * (i + 1) / len(filtered))
                progress_bar.progress(progress)

            status_text.text(f"스크리닝 실행 중...")
            progress_bar.progress(75)

            strategy_list = None if strategy == "전체" else [strategy]
            screener = StockScreener(strategies=strategy_list)
            screener.set_filter_preset(preset)

            results = screener.screen_stocks(stock_data, max_workers=4)

            progress_bar.progress(100)
            status_text.text("완료!")

            if results:
                st.success(f"🎯 {len(results)}개 매수 신호!")

                result_df = screener.to_dataframe()
                result_df = result_df[['code', 'name', 'strategy', 'score', 'entry_price', 'reason']]
                result_df.columns = ['코드', '종목명', '전략', '점수', '진입가', '사유']

                result_df['진입가'] = result_df['진입가'].apply(
                    lambda x: f"{x:,.0f}" if pd.notna(x) else "-"
                )
                result_df['점수'] = result_df['점수'].apply(lambda x: f"{x:.1f}")

                st.dataframe(result_df, use_container_width=True, hide_index=True)

                # 전략별 요약
                by_strategy = screener.get_results_by_strategy()
                cols = st.columns(len(by_strategy))
                for i, (strat, res) in enumerate(by_strategy.items()):
                    with cols[i]:
                        st.metric(strat, f"{len(res)}")
            else:
                st.info("조건을 만족하는 종목이 없습니다.")
    else:
        stocks = load_stocks()
        if stocks:
            st.info(f"📊 {len(stocks):,}개 종목 준비됨")
        else:
            st.warning("데이터 수집이 필요합니다.")

elif menu == "📈 백테스트":
    st.markdown('<h1 class="main-header">📈 백테스트</h1>', unsafe_allow_html=True)

    # 전략 선택
    strategy = st.selectbox(
        "전략",
        ["전체", "limit_up", "breakout", "minute15", "minute30"]
    )

    # 종목 선택
    stock_selection = st.radio(
        "종목 선택",
        ["주요 종목", "시장 전체", "직접 입력"],
        horizontal=True
    )

    selected_codes = []

    if stock_selection == "주요 종목":
        major_stocks = {
            "대형주 TOP10": ["005930", "000660", "035420", "005380", "006400",
                           "035720", "051910", "005490", "028260", "012330"],
            "2차전지/반도체": ["373220", "006400", "051910", "000660", "005930",
                            "247540", "086520", "042700", "091990", "298050"],
            "바이오": ["068270", "207940", "091990", "326030", "145020"],
            "금융": ["105560", "055550", "086790", "024110", "316140"],
        }

        preset_choice = st.selectbox("프리셋", list(major_stocks.keys()))
        selected_codes = major_stocks[preset_choice]
        st.caption(f"선택: {len(selected_codes)}개 종목")

    elif stock_selection == "시장 전체":
        bt_market = st.multiselect("시장", ["KOSPI", "KOSDAQ"], default=["KOSPI", "KOSDAQ"])
        max_stocks = st.slider("종목 수", 50, 300, 100, step=50)

    else:  # 직접 입력
        all_stocks = load_stocks()
        stock_dict = {f"{s['name']} ({s['code']})": s['code'] for s in all_stocks}

        selected_items = st.multiselect(
            "종목 검색",
            options=list(stock_dict.keys()),
            placeholder="종목명 입력..."
        )

        if selected_items:
            selected_codes = [stock_dict[item] for item in selected_items]
            st.caption(f"선택: {len(selected_codes)}개")

    # 기간 및 자본
    days = st.slider("기간 (일)", 30, 730, 365)

    with st.expander("고급 설정"):
        initial_capital = st.number_input(
            "초기 자본 (원)", 1000000, 100000000, 10000000, step=1000000
        )
        max_positions = st.slider("최대 보유 종목", 1, 20, 10)

    run_backtest = st.button("📊 백테스트 실행", type="primary", use_container_width=True)

    st.markdown("---")

    if run_backtest:
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("데이터 로드 중...")
        progress_bar.progress(5)

        stocks = load_stocks()
        if not stocks:
            st.error("종목 데이터가 없습니다.")
        else:
            db = get_db()
            stock_data = {}

            if selected_codes:
                codes_to_load = selected_codes
            else:
                filtered = [s for s in stocks if s['market'] in bt_market][:max_stocks]
                codes_to_load = [s['code'] for s in filtered]

            status_text.text(f"{len(codes_to_load)}개 종목 준비 중...")
            progress_bar.progress(10)

            for i, code in enumerate(codes_to_load):
                df = db.get_daily_ohlcv(code, limit=days + 60)

                if df is not None and len(df) >= 20:
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    stock_data[code] = df

                progress = 10 + int(40 * (i + 1) / len(codes_to_load))
                progress_bar.progress(progress)

            if not stock_data:
                st.error("유효한 데이터가 없습니다.")
            else:
                status_text.text("백테스트 실행 중...")
                progress_bar.progress(55)

                config = BacktestConfig(
                    initial_capital=initial_capital,
                    max_positions=max_positions,
                )

                try:
                    if strategy == "전체":
                        strategies_to_test = ["limit_up", "breakout", "minute15", "minute30"]
                        bt = MultiStrategyBacktester(strategies_to_test, config)
                        results = bt.run(stock_data)

                        progress_bar.progress(90)
                        st.success("백테스트 완료!")

                        compare_df = bt.compare_strategies()
                        if not compare_df.empty:
                            st.subheader("전략별 비교")

                            # 간소화된 결과 테이블
                            display_df = compare_df[['전략', '총수익률(%)', '승률(%)', '총거래수']].copy()
                            display_df['총수익률(%)'] = display_df['총수익률(%)'].apply(lambda x: f"{x:.1f}%")
                            display_df['승률(%)'] = display_df['승률(%)'].apply(lambda x: f"{x:.1f}%")

                            st.dataframe(display_df, use_container_width=True, hide_index=True)

                            best = compare_df.iloc[0]
                            st.info(f"🏆 최고: **{best['전략']}** ({best['총수익률(%)']:.1f}%)")
                    else:
                        bt = Backtester(strategy, config)
                        metrics = bt.run(stock_data)

                        progress_bar.progress(90)
                        st.success(f"**{strategy}** 백테스트 완료!")

                        # 결과 표시 - 2x2 그리드
                        col1, col2 = st.columns(2)
                        with col1:
                            color = "normal" if metrics.total_return >= 0 else "inverse"
                            st.metric("수익률", f"{metrics.total_return_percent:.1f}%",
                                     delta=f"{metrics.total_return:,.0f}원", delta_color=color)
                        with col2:
                            st.metric("MDD", f"{metrics.max_drawdown_percent:.1f}%")

                        col3, col4 = st.columns(2)
                        with col3:
                            st.metric("승률", f"{metrics.win_rate:.1f}%")
                        with col4:
                            st.metric("거래", f"{metrics.total_trades}회")

                        # 자산 곡선
                        equity_df = bt.get_equity_curve()
                        if not equity_df.empty:
                            st.subheader("자산 곡선")
                            chart_data = equity_df.set_index('date')['equity']
                            st.line_chart(chart_data)

                        # 거래 내역
                        trades = bt.get_trades()
                        if trades:
                            with st.expander(f"거래 내역 ({len(trades)}건)"):
                                trade_records = []
                                for t in trades:
                                    trade_records.append({
                                        '종목': t.name[:6],
                                        '진입': str(t.entry_date)[:10],
                                        '수익률': f"{t.pnl_percent:.1f}%",
                                    })
                                st.dataframe(pd.DataFrame(trade_records),
                                           use_container_width=True, hide_index=True)

                    progress_bar.progress(100)
                    status_text.text("완료!")

                except Exception as e:
                    st.error(f"오류: {str(e)}")
    else:
        counts = load_stock_count()
        col1, col2 = st.columns(2)
        with col1:
            st.metric("종목", f"{counts['total']:,}개")
        with col2:
            st.metric("데이터", f"{counts['daily_data']:,}건")
        st.info("설정 후 '백테스트 실행' 버튼을 클릭하세요.")

elif menu == "📊 종목분석":
    st.markdown('<h1 class="main-header">📊 종목 분석</h1>', unsafe_allow_html=True)

    # 종목 선택
    stocks = load_stocks()
    stock_options = {f"{s['name']} ({s['code']})": s['code'] for s in stocks}

    selected = st.selectbox(
        "종목 선택",
        options=list(stock_options.keys()),
        placeholder="종목명 검색..."
    )

    code = stock_options.get(selected, "") if selected else ""

    analyze_btn = st.button("🔍 분석", type="primary", use_container_width=True)

    st.markdown("---")

    if analyze_btn and code:
        with st.spinner("분석 중..."):
            df = load_stock_data(code, limit=252)

            if df.empty:
                st.error(f"데이터 없음: {code}")
            else:
                db = get_db()
                stock_info = db.get_stock(code)
                if stock_info:
                    st.info(f"**{stock_info['name']}** ({code})")

                latest = df.iloc[-1]

                # 기본 정보
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("현재가", f"{latest['close']:,.0f}원")
                with col2:
                    if len(df) > 1:
                        prev_close = df.iloc[-2]['close']
                        change = (latest['close'] - prev_close) / prev_close * 100
                        st.metric("등락률", f"{change:.2f}%")

                col3, col4 = st.columns(2)
                with col3:
                    st.metric("거래량", f"{latest['volume']:,.0f}")
                with col4:
                    st.metric("데이터", f"{len(df)}일")

                # 차트
                st.subheader("📈 가격 차트")
                st.line_chart(df['close'].tail(60))

                # 상세 데이터
                with st.expander("최근 데이터"):
                    display_df = df.tail(10).copy()
                    display_df = display_df[['close', 'volume']]
                    display_df.columns = ['종가', '거래량']
                    display_df = display_df.sort_index(ascending=False)
                    st.dataframe(display_df, use_container_width=True)

    elif not selected:
        st.info("종목을 선택하세요.")

elif menu == "⚙️ 설정":
    st.markdown('<h1 class="main-header">⚙️ 설정</h1>', unsafe_allow_html=True)

    counts = load_stock_count()

    st.subheader("📊 데이터 현황")

    col1, col2 = st.columns(2)
    with col1:
        st.metric("총 종목", f"{counts['total']:,}개")
        st.metric("KOSPI", f"{counts['kospi']:,}개")
    with col2:
        st.metric("KOSDAQ", f"{counts['kosdaq']:,}개")
        st.metric("일봉", f"{counts['daily_data']:,}건")

    st.markdown("---")

    st.subheader("📝 시스템 정보")
    st.write(f"- Python: {sys.version.split()[0]}")
    st.write(f"- 시간: {datetime.now().strftime('%Y-%m-%d %H:%M')}")

    db = get_db()
    st.write(f"- DB: {db.db_path.name}")

    st.markdown("---")

    with st.expander("데이터 수집 명령어"):
        st.code("python main.py --mode collect", language="bash")
        st.caption("옵션: --market KOSPI/KOSDAQ, --days 365")
