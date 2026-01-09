#!/usr/bin/env python3
"""
퀀트 트레이딩 대시보드 - 모바일 최적화
"""

import streamlit as st
import pandas as pd
import sys
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).resolve().parent))

from data import get_db
from screener import StockScreener
from backtest import Backtester, BacktestConfig, MultiStrategyBacktester

# 페이지 설정
st.set_page_config(
    page_title="퀀트",
    page_icon="📈",
    layout="centered",
    initial_sidebar_state="collapsed"
)

# 세션 상태
if 'menu' not in st.session_state:
    st.session_state.menu = "home"

# CSS 스타일
st.markdown("""
<style>
    /* 기본 설정 */
    [data-testid="stSidebar"], [data-testid="collapsedControl"] {
        display: none !important;
    }
    .block-container {
        padding: 1rem !important;
        max-width: 100% !important;
    }

    /* 탭 네비게이션 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0;
        background: #1a1a2e;
        border-radius: 12px;
        padding: 4px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        border-radius: 8px;
        color: #888;
        font-weight: 500;
        font-size: 0.85rem;
    }
    .stTabs [aria-selected="true"] {
        background: #4FC3F7 !important;
        color: #000 !important;
    }

    /* 카드 스타일 */
    .card {
        background: linear-gradient(145deg, #1e1e2e, #252535);
        border-radius: 16px;
        padding: 1.2rem;
        margin: 0.5rem 0;
        border: 1px solid rgba(255,255,255,0.05);
    }
    .card-title {
        font-size: 0.75rem;
        color: #888;
        margin-bottom: 0.3rem;
    }
    .card-value {
        font-size: 1.5rem;
        font-weight: 700;
        color: #fff;
    }
    .card-sub {
        font-size: 0.7rem;
        color: #4FC3F7;
    }

    /* 헤더 */
    .page-header {
        font-size: 1.3rem;
        font-weight: 700;
        color: #fff;
        margin: 1rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid #4FC3F7;
    }

    /* 메트릭 */
    [data-testid="stMetricValue"] {
        font-size: 1.4rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.8rem !important;
        color: #888 !important;
    }

    /* 버튼 */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        transform: translateY(-1px);
        box-shadow: 0 4px 12px rgba(79,195,247,0.3);
    }

    /* 입력 필드 */
    .stSelectbox, .stMultiSelect, .stSlider {
        margin-bottom: 0.8rem;
    }

    /* 전략 카드 */
    .strategy-card {
        background: #1e1e2e;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
        border-left: 3px solid #4FC3F7;
    }
    .strategy-name {
        font-weight: 600;
        color: #fff;
        margin-bottom: 0.3rem;
    }
    .strategy-desc {
        font-size: 0.75rem;
        color: #888;
    }

    /* 결과 테이블 */
    .dataframe {
        font-size: 0.8rem !important;
    }

    /* 차트 */
    [data-testid="stArrowVegaLiteChart"] {
        border-radius: 12px;
        overflow: hidden;
    }
</style>
""", unsafe_allow_html=True)


# 데이터 로드 함수
@st.cache_data(ttl=60)
def load_stocks():
    db = get_db()
    return db.get_all_active_stocks()


@st.cache_data(ttl=60)
def load_stock_count():
    db = get_db()
    return {
        'total': db.get_row_count('stocks'),
        'kospi': len(db.get_stocks_by_market('KOSPI')),
        'kosdaq': len(db.get_stocks_by_market('KOSDAQ')),
        'daily_data': db.get_row_count('daily_ohlcv'),
    }


@st.cache_data(ttl=60)
def load_stock_data(code: str, limit: int = 100):
    db = get_db()
    return db.get_daily_ohlcv(code, limit=limit)


# URL 파라미터 처리
if 'menu' in st.query_params:
    st.session_state.menu = st.query_params['menu']

# 탭 네비게이션
tabs = st.tabs(["홈", "스크리닝", "백테스트", "분석", "설정"])

# ===== 홈 탭 =====
with tabs[0]:
    counts = load_stock_count()

    # 요약 카드
    st.markdown("""
    <div class="card">
        <div class="card-title">총 종목</div>
        <div class="card-value">{:,}</div>
        <div class="card-sub">KOSPI {:,} / KOSDAQ {:,}</div>
    </div>
    """.format(counts['total'], counts['kospi'], counts['kosdaq']),
    unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        st.markdown("""
        <div class="card">
            <div class="card-title">일봉 데이터</div>
            <div class="card-value">{:,}</div>
        </div>
        """.format(counts['daily_data']), unsafe_allow_html=True)
    with col2:
        st.markdown("""
        <div class="card">
            <div class="card-title">전략</div>
            <div class="card-value">4개</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown('<div class="page-header">전략 소개</div>', unsafe_allow_html=True)

    strategies = [
        ("상한가 따라잡기", "상한가 후 눌림목 진입", "고위험"),
        ("돌파 매매", "박스권 상단 돌파", "중위험"),
        ("15분봉", "단기 분봉 매매", "중위험"),
        ("30분봉", "스윙 분봉 매매", "저위험"),
    ]

    for name, desc, risk in strategies:
        st.markdown(f"""
        <div class="strategy-card">
            <div class="strategy-name">{name}</div>
            <div class="strategy-desc">{desc} · {risk}</div>
        </div>
        """, unsafe_allow_html=True)

# ===== 스크리닝 탭 =====
with tabs[1]:
    st.markdown('<div class="page-header">종목 스크리닝</div>', unsafe_allow_html=True)

    col1, col2 = st.columns(2)
    with col1:
        strategy = st.selectbox(
            "전략",
            ["전체", "limit_up", "breakout", "minute15", "minute30"],
            key="screen_strategy"
        )
    with col2:
        preset = st.selectbox(
            "필터",
            ["default", "aggressive", "conservative"],
            format_func=lambda x: {"default": "기본", "aggressive": "공격적",
                                   "conservative": "보수적"}[x],
            key="screen_preset"
        )

    market = st.multiselect(
        "시장", ["KOSPI", "KOSDAQ"],
        default=["KOSPI", "KOSDAQ"],
        key="screen_market"
    )

    stocks = load_stocks()
    total = len(stocks) if stocks else 1000
    max_stocks = st.slider("분석 종목 수", 100, min(500, total), 200, 50,
                           key="screen_count")

    if st.button("스크리닝 실행", type="primary", use_container_width=True,
                 key="run_screen"):
        if not stocks:
            st.error("종목 데이터가 없습니다")
        else:
            progress = st.progress(0)
            status = st.empty()

            status.info("데이터 로드 중...")
            filtered = [s for s in stocks if s['market'] in market][:max_stocks]

            db = get_db()
            stock_data = {}

            for i, stock in enumerate(filtered):
                df = db.get_daily_ohlcv(stock['code'], limit=252)
                if df is not None and len(df) >= 20:
                    stock_data[stock['code']] = {'df': df, 'name': stock['name']}
                progress.progress((i + 1) / len(filtered) * 0.7)

            status.info("분석 중...")
            strategy_list = None if strategy == "전체" else [strategy]
            screener = StockScreener(strategies=strategy_list)
            screener.set_filter_preset(preset)
            results = screener.screen_stocks(stock_data, max_workers=4)

            progress.progress(1.0)

            if results:
                status.success(f"{len(results)}개 신호 발견!")
                result_df = screener.to_dataframe()
                display_df = result_df[['name', 'strategy', 'entry_price']].copy()
                display_df.columns = ['종목', '전략', '진입가']
                display_df['진입가'] = display_df['진입가'].apply(
                    lambda x: f"{x:,.0f}" if pd.notna(x) else "-")
                st.dataframe(display_df, use_container_width=True, hide_index=True)
            else:
                status.warning("조건에 맞는 종목이 없습니다")

# ===== 백테스트 탭 =====
with tabs[2]:
    st.markdown('<div class="page-header">백테스트</div>', unsafe_allow_html=True)

    bt_strategy = st.selectbox(
        "전략",
        ["전체", "limit_up", "breakout", "minute15", "minute30"],
        key="bt_strategy"
    )

    stock_mode = st.radio("종목 선택", ["프리셋", "시장별", "직접선택"],
                          horizontal=True, key="bt_mode")

    selected_codes = []
    bt_market = ["KOSPI"]
    bt_max = 100

    if stock_mode == "프리셋":
        presets = {
            "대형주 TOP5": ["005930", "000660", "035420", "005380", "006400"],
            "반도체": ["005930", "000660", "042700", "403870"],
            "바이오": ["068270", "207940", "091990", "326030"],
        }
        preset_name = st.selectbox("프리셋", list(presets.keys()), key="bt_preset")
        selected_codes = presets[preset_name]
        st.caption(f"{len(selected_codes)}개 종목 선택됨")

    elif stock_mode == "시장별":
        bt_market = st.multiselect("시장", ["KOSPI", "KOSDAQ"],
                                   default=["KOSPI"], key="bt_market")
        bt_max = st.slider("종목 수", 50, 200, 100, 25, key="bt_max")

    else:
        all_stocks = load_stocks()
        stock_dict = {s['name']: s['code'] for s in all_stocks}
        selected = st.multiselect("종목 검색", list(stock_dict.keys()),
                                  key="bt_stocks")
        selected_codes = [stock_dict[n] for n in selected]

    days = st.slider("백테스트 기간 (일)", 60, 365, 180, 30, key="bt_days")

    if st.button("백테스트 실행", type="primary", use_container_width=True,
                 key="run_bt"):
        stocks = load_stocks()
        if not stocks:
            st.error("데이터 없음")
        else:
            progress = st.progress(0)
            status = st.empty()

            status.info("데이터 준비 중...")
            db = get_db()
            stock_data = {}

            if selected_codes:
                codes = selected_codes
            else:
                filtered = [s for s in stocks if s['market'] in bt_market][:bt_max]
                codes = [s['code'] for s in filtered]

            for i, code in enumerate(codes):
                df = db.get_daily_ohlcv(code, limit=days + 60)
                if df is not None and len(df) >= 20:
                    if not isinstance(df.index, pd.DatetimeIndex):
                        df.index = pd.to_datetime(df.index)
                    stock_data[code] = df
                progress.progress((i + 1) / len(codes) * 0.5)

            if not stock_data:
                st.error("유효한 데이터가 없습니다")
            else:
                status.info("백테스트 실행 중...")
                config = BacktestConfig(initial_capital=10000000, max_positions=10)

                try:
                    if bt_strategy == "전체":
                        strats = ["limit_up", "breakout", "minute15", "minute30"]
                        bt = MultiStrategyBacktester(strats, config)
                        bt.run(stock_data)
                        progress.progress(0.9)

                        df = bt.compare_strategies()
                        if not df.empty:
                            display = df[['전략', '총수익률(%)', '승률(%)']].copy()
                            display['총수익률(%)'] = display['총수익률(%)'].apply(
                                lambda x: f"{x:.1f}%")
                            display['승률(%)'] = display['승률(%)'].apply(
                                lambda x: f"{x:.1f}%")
                            st.dataframe(display, use_container_width=True,
                                        hide_index=True)
                    else:
                        bt = Backtester(bt_strategy, config)
                        metrics = bt.run(stock_data)
                        progress.progress(0.9)

                        col1, col2 = st.columns(2)
                        with col1:
                            delta = "+" if metrics.total_return_percent > 0 else ""
                            st.metric("총 수익률",
                                     f"{delta}{metrics.total_return_percent:.1f}%")
                        with col2:
                            st.metric("승률", f"{metrics.win_rate:.1f}%")

                        equity = bt.get_equity_curve()
                        if not equity.empty:
                            st.line_chart(equity.set_index('date')['equity'])

                    progress.progress(1.0)
                    status.success("완료!")

                except Exception as e:
                    st.error(f"오류: {e}")

# ===== 분석 탭 =====
with tabs[3]:
    st.markdown('<div class="page-header">종목 분석</div>', unsafe_allow_html=True)

    stocks = load_stocks()
    stock_dict = {s['name']: s['code'] for s in stocks}

    selected = st.selectbox("종목 선택", list(stock_dict.keys()), key="analysis_stock")
    code = stock_dict.get(selected, "")

    if st.button("분석", type="primary", use_container_width=True, key="run_analysis"):
        if code:
            df = load_stock_data(code, limit=252)

            if df.empty:
                st.error("데이터 없음")
            else:
                db = get_db()
                info = db.get_stock(code)

                if info:
                    st.markdown(f"""
                    <div class="card">
                        <div class="card-title">{info['name']} ({code})</div>
                        <div class="card-value">{df.iloc[-1]['close']:,.0f}원</div>
                    </div>
                    """, unsafe_allow_html=True)

                if len(df) > 1:
                    prev = df.iloc[-2]['close']
                    curr = df.iloc[-1]['close']
                    change = (curr - prev) / prev * 100

                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("전일대비", f"{change:+.2f}%")
                    with col2:
                        st.metric("고가", f"{df.iloc[-1]['high']:,.0f}")
                    with col3:
                        st.metric("저가", f"{df.iloc[-1]['low']:,.0f}")

                st.line_chart(df['close'].tail(60))

                with st.expander("최근 거래 데이터"):
                    recent = df.tail(10)[['open', 'high', 'low', 'close', 'volume']]
                    recent.columns = ['시가', '고가', '저가', '종가', '거래량']
                    st.dataframe(recent, use_container_width=True)

# ===== 설정 탭 =====
with tabs[4]:
    st.markdown('<div class="page-header">시스템 정보</div>', unsafe_allow_html=True)

    counts = load_stock_count()

    col1, col2 = st.columns(2)
    with col1:
        st.metric("전체 종목", f"{counts['total']:,}")
        st.metric("KOSPI", f"{counts['kospi']:,}")
    with col2:
        st.metric("KOSDAQ", f"{counts['kosdaq']:,}")
        st.metric("일봉 데이터", f"{counts['daily_data']:,}")

    st.markdown("---")

    st.markdown(f"""
    <div class="card">
        <div class="card-title">시스템</div>
        <div class="strategy-desc">
            Python {sys.version.split()[0]}<br>
            {datetime.now().strftime('%Y-%m-%d %H:%M')}<br>
            DB: {get_db().db_path.name}
        </div>
    </div>
    """, unsafe_allow_html=True)
