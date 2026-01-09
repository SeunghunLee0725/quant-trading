#!/usr/bin/env python3
"""
주식 퀀트 트레이딩 시스템 - Streamlit 대시보드 (모바일 최적화 + 하단 메뉴)
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
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 세션 상태로 메뉴 관리
if 'menu' not in st.session_state:
    st.session_state.menu = "home"

# 모바일 최적화 CSS + 하단 고정 메뉴
st.markdown("""
<style>
    /* 사이드바 완전히 숨기기 */
    [data-testid="stSidebar"] {
        display: none !important;
    }
    [data-testid="collapsedControl"] {
        display: none !important;
    }

    /* 모바일 최적화 */
    .block-container {
        padding: 0.5rem !important;
        max-width: 100% !important;
    }

    /* 메인 헤더 */
    .main-header {
        font-size: 1.4rem;
        font-weight: bold;
        color: #4FC3F7;
        text-align: center;
        margin: 0.5rem 0;
    }

    /* 메트릭 카드 모바일 최적화 */
    [data-testid="stMetricValue"] {
        font-size: 1.2rem !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.75rem !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.65rem !important;
    }

    /* 버튼 모바일 최적화 */
    .stButton > button {
        width: 100% !important;
        padding: 0.6rem !important;
        font-size: 0.95rem !important;
    }

    /* 데이터프레임 스크롤 */
    .stDataFrame {
        font-size: 0.75rem !important;
    }

    /* 다크모드 텍스트 */
    .stMarkdown p, .stMarkdown li {
        color: #E0E0E0;
    }
    h1, h2, h3 {
        color: #FFFFFF !important;
    }

    /* 상단 네비게이션 바 (고정 아님 - Streamlit 헤더 아래 배치) */
    .top-nav {
        background: rgba(30,33,40,0.95);
        border: 1px solid rgba(255,255,255,0.1);
        border-radius: 10px;
        display: flex;
        justify-content: space-around;
        align-items: center;
        padding: 10px 5px;
        margin: calc(0.5rem + 10px) 0 1rem 0;
    }

    .nav-item {
        text-decoration: none;
        color: #888;
        font-size: 0.85rem;
        padding: 8px 12px;
        border-radius: 8px;
        transition: all 0.2s;
        font-weight: 500;
        cursor: pointer;
    }

    .nav-item:hover {
        color: #4FC3F7;
        background: rgba(79,195,247,0.1);
    }

    .nav-item.active {
        color: #4FC3F7;
        background: rgba(79,195,247,0.15);
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


# 상단 네비게이션 바 (HTML)
def render_top_nav():
    current = st.session_state.menu
    st.markdown(f"""
    <div class="top-nav">
        <span class="nav-item {'active' if current == 'home' else ''}" onclick="window.location.href='?menu=home'">홈</span>
        <span class="nav-item {'active' if current == 'screen' else ''}" onclick="window.location.href='?menu=screen'">스크리닝</span>
        <span class="nav-item {'active' if current == 'backtest' else ''}" onclick="window.location.href='?menu=backtest'">백테스트</span>
        <span class="nav-item {'active' if current == 'analysis' else ''}" onclick="window.location.href='?menu=analysis'">분석</span>
        <span class="nav-item {'active' if current == 'settings' else ''}" onclick="window.location.href='?menu=settings'">설정</span>
    </div>
    """, unsafe_allow_html=True)


# URL 쿼리 파라미터로 메뉴 상태 관리
query_params = st.query_params
if 'menu' in query_params:
    st.session_state.menu = query_params['menu']

menu = st.session_state.menu

# 상단 네비게이션 렌더링
render_top_nav()

# 메인 컨텐츠
if menu == "home":
    st.markdown('<h1 class="main-header">📈 퀀트 트레이딩</h1>', unsafe_allow_html=True)

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
    st.info(f"**KOSPI** {counts['kospi']:,}개 | **KOSDAQ** {counts['kosdaq']:,}개")

    st.markdown("---")

    # 전략 소개
    st.subheader("📋 전략")

    with st.expander("상한가 따라잡기", expanded=False):
        st.caption("상한가 종목 눌림목 진입 | 일봉 | 위험↑")

    with st.expander("돌파 매매", expanded=False):
        st.caption("박스권 상단 돌파 | 일봉 | 위험 중")

    with st.expander("15분봉 전략", expanded=False):
        st.caption("15분봉 단기매매 | 분봉 | 위험 중")

    with st.expander("30분봉 전략", expanded=False):
        st.caption("30분봉 스윙매매 | 분봉 | 위험↓")

elif menu == "screen":
    st.markdown('<h1 class="main-header">🔍 스크리닝</h1>', unsafe_allow_html=True)

    # 필터 프리셋
    PRESET_INFO = {
        "default": {"name": "기본", "desc": "거래량 10만+"},
        "aggressive": {"name": "공격적", "desc": "급등주"},
        "conservative": {"name": "보수적", "desc": "안정적"},
        "volume_focus": {"name": "거래량", "desc": "급증"},
        "breakout": {"name": "돌파", "desc": "신고가"},
    }

    strategy = st.selectbox("전략", ["전체", "limit_up", "breakout", "minute15", "minute30"])
    preset = st.selectbox("필터", list(PRESET_INFO.keys()),
                         format_func=lambda x: f"{PRESET_INFO[x]['name']}")
    market = st.multiselect("시장", ["KOSPI", "KOSDAQ"], default=["KOSPI", "KOSDAQ"])

    total_stocks = len(load_stocks()) if load_stocks() else 3000
    max_stocks = st.slider("종목 수", 100, min(1000, total_stocks), 300, step=100)

    run_screening = st.button("🔍 실행", type="primary", use_container_width=True)

    if run_screening:
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("로드 중...")
        progress_bar.progress(10)

        stocks = load_stocks()

        if not stocks:
            st.warning("종목이 없습니다.")
        else:
            filtered = [s for s in stocks if s['market'] in market][:max_stocks]

            status_text.text(f"{len(filtered)}개 분석 중...")
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

            status_text.text("스크리닝...")
            progress_bar.progress(75)

            strategy_list = None if strategy == "전체" else [strategy]
            screener = StockScreener(strategies=strategy_list)
            screener.set_filter_preset(preset)

            results = screener.screen_stocks(stock_data, max_workers=4)

            progress_bar.progress(100)
            status_text.text("완료!")

            if results:
                st.success(f"🎯 {len(results)}개 신호!")

                result_df = screener.to_dataframe()
                result_df = result_df[['name', 'strategy', 'entry_price']]
                result_df.columns = ['종목', '전략', '진입가']
                result_df['진입가'] = result_df['진입가'].apply(
                    lambda x: f"{x:,.0f}" if pd.notna(x) else "-"
                )

                st.dataframe(result_df, use_container_width=True, hide_index=True)
            else:
                st.info("조건에 맞는 종목 없음")
    else:
        stocks = load_stocks()
        if stocks:
            st.info(f"📊 {len(stocks):,}개 종목 준비됨")

elif menu == "backtest":
    st.markdown('<h1 class="main-header">📈 백테스트</h1>', unsafe_allow_html=True)

    strategy = st.selectbox("전략", ["전체", "limit_up", "breakout", "minute15", "minute30"])

    stock_selection = st.radio("종목", ["프리셋", "전체", "직접"], horizontal=True)

    selected_codes = []

    if stock_selection == "프리셋":
        major_stocks = {
            "대형주": ["005930", "000660", "035420", "005380", "006400"],
            "반도체": ["373220", "006400", "051910", "000660", "005930"],
            "바이오": ["068270", "207940", "091990", "326030", "145020"],
        }
        preset_choice = st.selectbox("프리셋", list(major_stocks.keys()))
        selected_codes = major_stocks[preset_choice]
        st.caption(f"{len(selected_codes)}개 종목")

    elif stock_selection == "전체":
        bt_market = st.multiselect("시장", ["KOSPI", "KOSDAQ"], default=["KOSPI"])
        max_stocks = st.slider("수", 50, 200, 100, step=50)

    else:
        all_stocks = load_stocks()
        stock_dict = {f"{s['name']}": s['code'] for s in all_stocks}
        selected_items = st.multiselect("종목", options=list(stock_dict.keys()))
        if selected_items:
            selected_codes = [stock_dict[item] for item in selected_items]

    days = st.slider("기간(일)", 30, 365, 180)

    run_backtest = st.button("📊 실행", type="primary", use_container_width=True)

    if run_backtest:
        progress_bar = st.progress(0)
        status_text = st.empty()

        status_text.text("로드 중...")
        progress_bar.progress(5)

        stocks = load_stocks()
        if not stocks:
            st.error("데이터 없음")
        else:
            db = get_db()
            stock_data = {}

            if selected_codes:
                codes_to_load = selected_codes
            else:
                filtered = [s for s in stocks if s['market'] in bt_market][:max_stocks]
                codes_to_load = [s['code'] for s in filtered]

            status_text.text(f"{len(codes_to_load)}개 준비...")
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
                st.error("데이터 없음")
            else:
                status_text.text("실행 중...")
                progress_bar.progress(55)

                config = BacktestConfig(initial_capital=10000000, max_positions=10)

                try:
                    if strategy == "전체":
                        strategies_to_test = ["limit_up", "breakout", "minute15", "minute30"]
                        bt = MultiStrategyBacktester(strategies_to_test, config)
                        results = bt.run(stock_data)

                        progress_bar.progress(90)
                        st.success("완료!")

                        compare_df = bt.compare_strategies()
                        if not compare_df.empty:
                            display_df = compare_df[['전략', '총수익률(%)', '승률(%)']].copy()
                            display_df['총수익률(%)'] = display_df['총수익률(%)'].apply(lambda x: f"{x:.1f}%")
                            display_df['승률(%)'] = display_df['승률(%)'].apply(lambda x: f"{x:.1f}%")
                            st.dataframe(display_df, use_container_width=True, hide_index=True)
                    else:
                        bt = Backtester(strategy, config)
                        metrics = bt.run(stock_data)

                        progress_bar.progress(90)
                        st.success("완료!")

                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("수익률", f"{metrics.total_return_percent:.1f}%")
                        with col2:
                            st.metric("승률", f"{metrics.win_rate:.1f}%")

                        equity_df = bt.get_equity_curve()
                        if not equity_df.empty:
                            st.line_chart(equity_df.set_index('date')['equity'])

                    progress_bar.progress(100)
                    status_text.text("완료!")

                except Exception as e:
                    st.error(f"오류: {str(e)}")
    else:
        counts = load_stock_count()
        st.info(f"📊 {counts['total']:,}개 종목 | {counts['daily_data']:,}건 데이터")

elif menu == "analysis":
    st.markdown('<h1 class="main-header">📊 종목분석</h1>', unsafe_allow_html=True)

    stocks = load_stocks()
    stock_options = {f"{s['name']}": s['code'] for s in stocks}

    selected = st.selectbox("종목", options=list(stock_options.keys()))
    code = stock_options.get(selected, "") if selected else ""

    analyze_btn = st.button("🔍 분석", type="primary", use_container_width=True)

    if analyze_btn and code:
        with st.spinner("분석 중..."):
            df = load_stock_data(code, limit=252)

            if df.empty:
                st.error("데이터 없음")
            else:
                db = get_db()
                stock_info = db.get_stock(code)
                if stock_info:
                    st.info(f"**{stock_info['name']}** ({code})")

                latest = df.iloc[-1]

                col1, col2 = st.columns(2)
                with col1:
                    st.metric("현재가", f"{latest['close']:,.0f}")
                with col2:
                    if len(df) > 1:
                        prev_close = df.iloc[-2]['close']
                        change = (latest['close'] - prev_close) / prev_close * 100
                        st.metric("등락", f"{change:.2f}%")

                st.line_chart(df['close'].tail(60))

                with st.expander("상세"):
                    display_df = df.tail(5)[['close', 'volume']]
                    display_df.columns = ['종가', '거래량']
                    st.dataframe(display_df, use_container_width=True)

elif menu == "settings":
    st.markdown('<h1 class="main-header">⚙️ 설정</h1>', unsafe_allow_html=True)

    counts = load_stock_count()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("종목", f"{counts['total']:,}")
        st.metric("KOSPI", f"{counts['kospi']:,}")
    with col2:
        st.metric("KOSDAQ", f"{counts['kosdaq']:,}")
        st.metric("일봉", f"{counts['daily_data']:,}")

    st.markdown("---")

    st.caption(f"Python {sys.version.split()[0]}")
    st.caption(f"{datetime.now().strftime('%Y-%m-%d %H:%M')}")

    db = get_db()
    st.caption(f"DB: {db.db_path.name}")

