#!/usr/bin/env python3
"""
퀀트 트레이딩 대시보드 - 데스크탑 버전
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
from strategies import get_all_strategies, get_strategy

# 페이지 설정
st.set_page_config(
    page_title="퀀트 트레이딩 시스템",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

# CSS 스타일 - 데스크탑 버전
st.markdown("""
<style>
    /* 사이드바 스타일 */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1a2e 0%, #16213e 100%);
        padding-top: 1rem;
    }
    [data-testid="stSidebar"] .stRadio > label {
        color: #fff !important;
        font-weight: 600;
    }

    /* 메인 컨테이너 */
    .main .block-container {
        padding: 2rem 3rem !important;
        max-width: 1400px;
    }

    /* 카드 스타일 */
    .metric-card {
        background: linear-gradient(145deg, #1e1e2e, #252535);
        border-radius: 16px;
        padding: 1.5rem;
        margin: 0.5rem 0;
        border: 1px solid rgba(255,255,255,0.05);
        box-shadow: 0 4px 20px rgba(0,0,0,0.2);
    }
    .metric-title {
        font-size: 0.85rem;
        color: #888;
        margin-bottom: 0.5rem;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .metric-value {
        font-size: 2rem;
        font-weight: 700;
        color: #fff;
    }
    .metric-sub {
        font-size: 0.8rem;
        color: #4FC3F7;
        margin-top: 0.3rem;
    }

    /* 페이지 헤더 */
    .page-header {
        font-size: 1.8rem;
        font-weight: 700;
        color: #fff;
        margin-bottom: 1.5rem;
        padding-bottom: 0.8rem;
        border-bottom: 3px solid #4FC3F7;
    }

    /* 섹션 헤더 */
    .section-header {
        font-size: 1.2rem;
        font-weight: 600;
        color: #4FC3F7;
        margin: 1.5rem 0 1rem 0;
    }

    /* 메트릭 스타일 */
    [data-testid="stMetricValue"] {
        font-size: 1.6rem !important;
        font-weight: 700 !important;
    }
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem !important;
        color: #888 !important;
    }
    [data-testid="stMetricDelta"] {
        font-size: 0.85rem !important;
    }

    /* 버튼 */
    .stButton > button {
        border-radius: 10px !important;
        font-weight: 600 !important;
        padding: 0.6rem 2rem !important;
        transition: all 0.2s !important;
    }
    .stButton > button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(79,195,247,0.3);
    }

    /* 전략 카드 */
    .strategy-card {
        background: linear-gradient(145deg, #1e1e2e, #252535);
        border-radius: 12px;
        padding: 1.2rem;
        margin: 0.8rem 0;
        border-left: 4px solid #4FC3F7;
        transition: transform 0.2s;
    }
    .strategy-card:hover {
        transform: translateX(5px);
    }
    .strategy-name {
        font-weight: 600;
        font-size: 1.1rem;
        color: #fff;
        margin-bottom: 0.4rem;
    }
    .strategy-desc {
        font-size: 0.85rem;
        color: #888;
    }
    .strategy-risk {
        display: inline-block;
        padding: 0.2rem 0.6rem;
        border-radius: 20px;
        font-size: 0.7rem;
        margin-top: 0.5rem;
    }
    .risk-high { background: #ff6b6b; color: #fff; }
    .risk-mid { background: #feca57; color: #000; }
    .risk-low { background: #1dd1a1; color: #fff; }

    /* 신호 카드 */
    .signal-card {
        background: linear-gradient(145deg, #1e1e2e, #252535);
        border-radius: 12px;
        padding: 1.5rem;
        margin: 1rem 0;
        border-left: 4px solid #00d26a;
    }
    .signal-card.no-signal {
        border-left-color: #666;
    }

    /* 데이터프레임 스타일 */
    .dataframe {
        font-size: 0.9rem !important;
    }

    /* 차트 컨테이너 */
    [data-testid="stArrowVegaLiteChart"] {
        border-radius: 12px;
        overflow: hidden;
        background: rgba(30,30,46,0.5);
        padding: 1rem;
    }

    /* 정보 박스 */
    .info-box {
        background: rgba(79, 195, 247, 0.1);
        border: 1px solid rgba(79, 195, 247, 0.3);
        border-radius: 10px;
        padding: 1rem;
        margin: 1rem 0;
    }

    /* 탭 스타일 */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
    }
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px 8px 0 0;
        padding: 10px 20px;
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


# 사이드바 네비게이션
with st.sidebar:
    st.markdown("## 📈 퀀트 시스템")
    st.markdown("---")

    menu = st.radio(
        "메뉴",
        ["🏠 홈", "🔍 스크리닝", "📈 백테스트", "📊 종목분석", "⚙️ 설정"],
        label_visibility="collapsed"
    )

    st.markdown("---")
    st.markdown(f"**업데이트**: {datetime.now().strftime('%Y-%m-%d')}")


# ===== 홈 =====
if menu == "🏠 홈":
    st.markdown('<div class="page-header">퀀트 트레이딩 대시보드</div>', unsafe_allow_html=True)

    counts = load_stock_count()

    # 상단 메트릭 카드
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">총 종목</div>
            <div class="metric-value">{counts['total']:,}</div>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">KOSPI</div>
            <div class="metric-value">{counts['kospi']:,}</div>
        </div>
        """, unsafe_allow_html=True)

    with col3:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">KOSDAQ</div>
            <div class="metric-value">{counts['kosdaq']:,}</div>
        </div>
        """, unsafe_allow_html=True)

    with col4:
        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">일봉 데이터</div>
            <div class="metric-value">{counts['daily_data']:,}</div>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("")

    # 전략 소개
    col_left, col_right = st.columns([2, 1])

    with col_left:
        st.markdown('<div class="section-header">📋 전략 목록</div>', unsafe_allow_html=True)

        strategies = [
            ("상한가 따라잡기 (limit_up)", "상한가 기록 후 박스권 조정 → 돌파 매수", "high"),
            ("돌파 매매 (breakout)", "기준봉 출현 후 눌림 → 고가 돌파 매수", "mid"),
            ("15분봉 전략 (minute15)", "15분봉 기반 단기 모멘텀 매매", "mid"),
            ("30분봉 전략 (minute30)", "30분봉 기반 스윙 트레이딩", "low"),
        ]

        for name, desc, risk in strategies:
            risk_class = f"risk-{risk}"
            risk_text = {"high": "고위험", "mid": "중위험", "low": "저위험"}[risk]
            st.markdown(f"""
            <div class="strategy-card">
                <div class="strategy-name">{name}</div>
                <div class="strategy-desc">{desc}</div>
                <span class="strategy-risk {risk_class}">{risk_text}</span>
            </div>
            """, unsafe_allow_html=True)

    with col_right:
        st.markdown('<div class="section-header">💡 빠른 시작</div>', unsafe_allow_html=True)

        st.markdown("""
        <div class="info-box">
            <strong>1. 스크리닝</strong><br>
            원하는 전략으로 종목 필터링<br><br>
            <strong>2. 백테스트</strong><br>
            과거 데이터로 전략 검증<br><br>
            <strong>3. 종목분석</strong><br>
            개별 종목 상세 분석
        </div>
        """, unsafe_allow_html=True)


# ===== 스크리닝 =====
elif menu == "🔍 스크리닝":
    st.markdown('<div class="page-header">종목 스크리닝</div>', unsafe_allow_html=True)

    # 설정 영역
    col1, col2, col3 = st.columns(3)

    with col1:
        strategy = st.selectbox(
            "전략 선택",
            ["전체", "limit_up", "breakout", "minute15", "minute30"],
            key="screen_strategy"
        )

    with col2:
        preset = st.selectbox(
            "필터 프리셋",
            ["default", "aggressive", "conservative"],
            format_func=lambda x: {"default": "기본", "aggressive": "공격적", "conservative": "보수적"}[x],
            key="screen_preset"
        )

    with col3:
        market = st.multiselect(
            "시장",
            ["KOSPI", "KOSDAQ"],
            default=["KOSPI", "KOSDAQ"],
            key="screen_market"
        )

    stocks = load_stocks()
    total = len(stocks) if stocks else 1000

    col1, col2 = st.columns([3, 1])
    with col1:
        max_stocks = st.slider("분석 종목 수", 100, min(500, total), 200, 50, key="screen_count")
    with col2:
        st.write("")
        st.write("")
        run_screen = st.button("🔍 스크리닝 실행", type="primary", use_container_width=True)

    if run_screen:
        if not stocks:
            st.error("종목 데이터가 없습니다")
        else:
            progress = st.progress(0)
            status = st.empty()

            status.info("📊 데이터 로드 중...")
            filtered = [s for s in stocks if s['market'] in market][:max_stocks]

            db = get_db()
            stock_data = {}

            for i, stock in enumerate(filtered):
                df = db.get_daily_ohlcv(stock['code'], limit=252)
                if df is not None and len(df) >= 20:
                    stock_data[stock['code']] = {'df': df, 'name': stock['name']}
                progress.progress((i + 1) / len(filtered) * 0.7)

            status.info("🔄 전략 분석 중...")
            strategy_list = None if strategy == "전체" else [strategy]
            screener = StockScreener(strategies=strategy_list)
            screener.set_filter_preset(preset)
            results = screener.screen_stocks(stock_data, max_workers=4)

            progress.progress(1.0)

            if results:
                status.success(f"✅ {len(results)}개 신호 발견!")

                result_df = screener.to_dataframe()
                display_df = result_df[['name', 'strategy', 'entry_price', 'stop_loss', 'take_profit']].copy()
                display_df.columns = ['종목명', '전략', '진입가', '손절가', '목표가']

                for col in ['진입가', '손절가', '목표가']:
                    display_df[col] = display_df[col].apply(lambda x: f"{x:,.0f}" if pd.notna(x) else "-")

                st.dataframe(display_df, use_container_width=True, hide_index=True, height=400)
            else:
                status.warning("⚠️ 조건에 맞는 종목이 없습니다")


# ===== 백테스트 =====
elif menu == "📈 백테스트":
    st.markdown('<div class="page-header">백테스트</div>', unsafe_allow_html=True)

    # 설정 탭
    tab1, tab2 = st.tabs(["⚙️ 설정", "📊 결과"])

    with tab1:
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("##### 전략 설정")
            bt_strategy = st.selectbox(
                "전략",
                ["전체", "limit_up", "breakout", "minute15", "minute30"],
                key="bt_strategy"
            )

            days = st.slider("백테스트 기간 (일)", 60, 365, 180, 30, key="bt_days")

        with col2:
            st.markdown("##### 종목 설정")
            stock_mode = st.radio("종목 선택 방식", ["프리셋", "시장별", "직접선택"], horizontal=True, key="bt_mode")

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
                st.info(f"📌 {len(selected_codes)}개 종목 선택됨")

            elif stock_mode == "시장별":
                bt_market = st.multiselect("시장", ["KOSPI", "KOSDAQ"], default=["KOSPI"], key="bt_market")
                bt_max = st.slider("종목 수", 50, 200, 100, 25, key="bt_max")

            else:
                all_stocks = load_stocks()
                stock_dict = {s['name']: s['code'] for s in all_stocks}
                selected = st.multiselect("종목 검색", list(stock_dict.keys()), key="bt_stocks")
                selected_codes = [stock_dict[n] for n in selected]

        st.markdown("---")
        run_bt = st.button("🚀 백테스트 실행", type="primary", use_container_width=True)

    if run_bt:
        with tab2:
            stocks = load_stocks()
            if not stocks:
                st.error("데이터 없음")
            else:
                progress = st.progress(0)
                status = st.empty()

                status.info("📊 데이터 준비 중...")
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
                    status.info("🔄 백테스트 실행 중...")
                    config = BacktestConfig(initial_capital=10000000, max_positions=10)

                    try:
                        if bt_strategy == "전체":
                            strats = ["limit_up", "breakout", "minute15", "minute30"]
                            bt = MultiStrategyBacktester(strats, config)
                            bt.run(stock_data)
                            progress.progress(0.9)

                            st.markdown("##### 📊 전략 비교 결과")
                            df = bt.compare_strategies()
                            if not df.empty:
                                st.dataframe(df, use_container_width=True, hide_index=True)
                        else:
                            bt = Backtester(bt_strategy, config)
                            metrics = bt.run(stock_data)
                            progress.progress(0.9)

                            st.markdown(f"##### 📊 {bt_strategy} 전략 결과")

                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                delta = "+" if metrics.total_return_percent > 0 else ""
                                st.metric("총 수익률", f"{delta}{metrics.total_return_percent:.1f}%")
                            with col2:
                                st.metric("승률", f"{metrics.win_rate:.1f}%")
                            with col3:
                                st.metric("MDD", f"{metrics.max_drawdown_percent:.1f}%")
                            with col4:
                                st.metric("총 거래", f"{metrics.total_trades}건")

                            equity = bt.get_equity_curve()
                            if not equity.empty:
                                st.markdown("##### 📈 자산 곡선")
                                st.line_chart(equity.set_index('date')['equity'])

                        progress.progress(1.0)
                        status.success("✅ 백테스트 완료!")

                    except Exception as e:
                        st.error(f"오류: {e}")


# ===== 종목분석 =====
elif menu == "📊 종목분석":
    st.markdown('<div class="page-header">종목 분석</div>', unsafe_allow_html=True)

    stocks = load_stocks()
    stock_dict = {s['name']: s['code'] for s in stocks}

    col1, col2 = st.columns([3, 1])
    with col1:
        selected = st.selectbox("종목 선택", list(stock_dict.keys()), key="analysis_stock")
    with col2:
        st.write("")
        st.write("")
        run_analysis = st.button("🔍 분석 실행", type="primary", use_container_width=True)

    code = stock_dict.get(selected, "")

    if run_analysis and code:
        df = load_stock_data(code, limit=252)

        if df.empty:
            st.error("데이터 없음")
        else:
            db = get_db()
            info = db.get_stock(code)

            # 기본 정보 카드
            col1, col2 = st.columns([1, 2])

            with col1:
                if info:
                    st.markdown(f"""
                    <div class="metric-card">
                        <div class="metric-title">{info['name']} ({code})</div>
                        <div class="metric-value">{df.iloc[-1]['close']:,.0f}원</div>
                        <div class="metric-sub">{info.get('market', '')} · {info.get('sector', '기타')}</div>
                    </div>
                    """, unsafe_allow_html=True)

                if len(df) > 1:
                    prev = df.iloc[-2]['close']
                    curr = df.iloc[-1]['close']
                    change = (curr - prev) / prev * 100

                    col_a, col_b = st.columns(2)
                    with col_a:
                        st.metric("전일대비", f"{change:+.2f}%")
                        st.metric("시가", f"{df.iloc[-1]['open']:,.0f}")
                    with col_b:
                        st.metric("고가", f"{df.iloc[-1]['high']:,.0f}")
                        st.metric("저가", f"{df.iloc[-1]['low']:,.0f}")

            with col2:
                st.markdown("##### 📈 가격 추이 (60일)")
                st.line_chart(df['close'].tail(60))

            st.markdown("---")

            # 전략 신호 분석
            st.markdown('<div class="section-header">🎯 전략 신호 분석</div>', unsafe_allow_html=True)

            strategies = get_all_strategies()
            signal_found = False

            cols = st.columns(2)
            col_idx = 0

            for strategy in strategies.values():
                try:
                    signal = strategy.generate_signal(df, code, selected)
                    if signal:
                        signal_found = True
                        with cols[col_idx % 2]:
                            st.markdown(f"""
                            <div class="signal-card">
                                <div class="strategy-name">✅ {strategy.name} - 매수 신호</div>
                                <div class="strategy-desc">{signal.reason}</div>
                            </div>
                            """, unsafe_allow_html=True)

                            c1, c2, c3 = st.columns(3)
                            with c1:
                                st.metric("진입가", f"{signal.price:,.0f}원")
                            with c2:
                                if signal.stop_loss:
                                    sl_pct = (signal.stop_loss - signal.price) / signal.price * 100
                                    st.metric("손절가", f"{signal.stop_loss:,.0f}원", f"{sl_pct:.1f}%")
                                else:
                                    st.metric("손절가", "-")
                            with c3:
                                if signal.take_profit:
                                    tp_pct = (signal.take_profit - signal.price) / signal.price * 100
                                    st.metric("목표가", f"{signal.take_profit:,.0f}원", f"+{tp_pct:.1f}%")
                                else:
                                    st.metric("목표가", "-")

                            if hasattr(signal, 'strength') and signal.strength:
                                st.progress(signal.strength, text=f"신호 강도: {signal.strength*100:.0f}%")

                        col_idx += 1
                except Exception:
                    pass

            if not signal_found:
                st.markdown("""
                <div class="signal-card no-signal">
                    <div class="strategy-name">현재 매매 신호 없음</div>
                    <div class="strategy-desc">모든 전략에서 조건을 충족하지 않습니다.</div>
                </div>
                """, unsafe_allow_html=True)

            st.markdown("---")

            # 최근 거래 데이터
            with st.expander("📋 최근 거래 데이터 (10일)", expanded=False):
                recent = df.tail(10)[['open', 'high', 'low', 'close', 'volume']].copy()
                recent.columns = ['시가', '고가', '저가', '종가', '거래량']
                recent['거래량'] = recent['거래량'].apply(lambda x: f"{x:,.0f}")
                for col in ['시가', '고가', '저가', '종가']:
                    recent[col] = recent[col].apply(lambda x: f"{x:,.0f}")
                st.dataframe(recent, use_container_width=True)


# ===== 설정 =====
elif menu == "⚙️ 설정":
    st.markdown('<div class="page-header">시스템 설정</div>', unsafe_allow_html=True)

    counts = load_stock_count()

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("##### 📊 데이터베이스 현황")

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">데이터 요약</div>
            <table style="width:100%; color:#fff; margin-top:10px;">
                <tr><td>전체 종목</td><td style="text-align:right; font-weight:600;">{counts['total']:,}</td></tr>
                <tr><td>KOSPI</td><td style="text-align:right; font-weight:600;">{counts['kospi']:,}</td></tr>
                <tr><td>KOSDAQ</td><td style="text-align:right; font-weight:600;">{counts['kosdaq']:,}</td></tr>
                <tr><td>일봉 데이터</td><td style="text-align:right; font-weight:600;">{counts['daily_data']:,}</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    with col2:
        st.markdown("##### ⚙️ 시스템 정보")

        st.markdown(f"""
        <div class="metric-card">
            <div class="metric-title">환경</div>
            <table style="width:100%; color:#fff; margin-top:10px;">
                <tr><td>Python</td><td style="text-align:right; font-weight:600;">{sys.version.split()[0]}</td></tr>
                <tr><td>현재 시간</td><td style="text-align:right; font-weight:600;">{datetime.now().strftime('%Y-%m-%d %H:%M')}</td></tr>
                <tr><td>DB 파일</td><td style="text-align:right; font-weight:600;">{get_db().db_path.name}</td></tr>
            </table>
        </div>
        """, unsafe_allow_html=True)

    st.markdown("---")

    st.markdown("##### 📝 전략 파라미터")

    with st.expander("limit_up (상한가) 전략", expanded=False):
        st.markdown("""
        - **상한가 임계값**: 29% 이상
        - **조정 기간**: 3~5일
        - **지지 임계값**: ±3%
        """)

    with st.expander("breakout (돌파) 전략", expanded=False):
        st.markdown("""
        - **기준봉 임계값**: 5% 이상 상승
        - **거래량 비율**: 3배 이상
        - **돌파 임계값**: 1%
        """)
