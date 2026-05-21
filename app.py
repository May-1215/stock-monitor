import streamlit as st
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import pandas as pd
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import WATCHLIST, ALERT_THRESHOLD, AUTO_REFRESH_SECONDS
from stock_data import get_stock_history, get_stock_realtime, get_all_stocks_realtime, search_stock
from technical_indicators import calc_all_indicators
from signals import analyze_buy_signals, analyze_sell_signals, scan_buy_opportunities
from alerts import check_watchlist_alerts, scan_market_alerts

st.set_page_config(page_title="A股智能监控系统", page_icon="📈", layout="wide")

if "watchlist" not in st.session_state:
    st.session_state.watchlist = list(WATCHLIST)

if "portfolio" not in st.session_state:
    st.session_state.portfolio = {}


def render_sidebar():
    with st.sidebar:
        st.title("📈 A股智能监控")
        page = st.radio(
            "功能导航",
            ["📊 实时监控", "🕯️ K线图表", "🔔 涨跌预警", "🛒 买入选股", "💰 持仓卖出"],
            index=0,
        )

        st.markdown("---")
        st.subheader("自选股管理")
        new_stock = st.text_input("添加股票代码", placeholder="如 000001")
        if st.button("➕ 添加"):
            if new_stock and new_stock not in st.session_state.watchlist:
                st.session_state.watchlist.append(new_stock)
                st.rerun()

        if st.session_state.watchlist:
            st.write("当前自选股：")
            for i, code in enumerate(st.session_state.watchlist):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(code)
                with col2:
                    if st.button("✖", key=f"del_{i}"):
                        st.session_state.watchlist.remove(code)
                        st.rerun()

        st.markdown("---")
        st.subheader("持仓管理")
        hold_code = st.text_input("持仓股票代码", placeholder="如 600519", key="hold_code")
        hold_cost = st.number_input("持仓成本价", min_value=0.0, value=0.0, step=0.01, key="hold_cost")
        hold_qty = st.number_input("持仓数量(股)", min_value=0, value=100, step=100, key="hold_qty")
        if st.button("📌 添加持仓"):
            if hold_code:
                st.session_state.portfolio[hold_code] = {
                    "cost": hold_cost,
                    "qty": hold_qty,
                }
                st.rerun()

        if st.session_state.portfolio:
            st.write("当前持仓：")
            for code in list(st.session_state.portfolio.keys()):
                info = st.session_state.portfolio[code]
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.text(f"{code} 成本:{info['cost']}")
                with col2:
                    if st.button("✖", key=f"del_hold_{code}"):
                        del st.session_state.portfolio[code]
                        st.rerun()

        return page


def render_realtime_monitor():
    st.header("📊 实时行情监控")
    if not st.session_state.watchlist:
        st.warning("请先在左侧添加自选股！")
        return

    cols = st.columns(min(len(st.session_state.watchlist), 4))
    for i, symbol in enumerate(st.session_state.watchlist):
        with cols[i % 4]:
            info = get_stock_realtime(symbol)
            if not info:
                st.error(f"{symbol} 数据获取失败")
                continue
            pct = info.get("pct_change", 0)
            color = "🟢" if pct > 0 else "🔴" if pct < 0 else "⚪"
            st.metric(
                label=f"{color} {info.get('name', symbol)}",
                value=f"¥{info.get('price', 0):.2f}",
                delta=f"{pct:+.2f}%",
            )
            st.caption(
                f"开:{info.get('open', 0):.2f} "
                f"高:{info.get('high', 0):.2f} "
                f"低:{info.get('low', 0):.2f}"
            )
            st.caption(
                f"量:{info.get('volume', 0)/10000:.0f}万手 "
                f"换手:{info.get('turnover', 0):.2f}%"
            )

    st.markdown("---")
    st.subheader("自选股行情汇总")
    all_data = []
    for symbol in st.session_state.watchlist:
        info = get_stock_realtime(symbol)
        if info:
            all_data.append(info)
    if all_data:
        summary_df = pd.DataFrame(all_data)
        display_cols = ["symbol", "name", "price", "pct_change", "change",
                        "amplitude", "high", "low", "open", "volume", "turnover"]
        display_cols = [c for c in display_cols if c in summary_df.columns]
        st.dataframe(
            summary_df[display_cols],
            use_container_width=True,
            hide_index=True,
        )


def render_kline_chart():
    st.header("🕯️ K线图表与技术指标")
    col1, col2 = st.columns([1, 3])
    with col1:
        symbol = st.selectbox("选择股票", st.session_state.watchlist, key="kline_symbol")
        days = st.selectbox("数据范围", [30, 60, 90, 120, 250], index=2, key="kline_days")
        show_ma = st.checkbox("均线(MA)", value=True, key="show_ma")
        show_boll = st.checkbox("布林带", value=False, key="show_boll")
        show_macd = st.checkbox("MACD", value=True, key="show_macd")
        show_rsi = st.checkbox("RSI", value=True, key="show_rsi")
        show_kdj = st.checkbox("KDJ", value=False, key="show_kdj")
        show_vol = st.checkbox("成交量", value=True, key="show_vol")

    if not symbol:
        st.warning("请选择股票")
        return

    with st.spinner("加载K线数据..."):
        df = get_stock_history(symbol, days=days)
        if df.empty:
            st.error("数据获取失败")
            return
        df = calc_all_indicators(df)

    with col2:
        subplot_count = 1
        row_heights = [0.5]
        if show_vol:
            subplot_count += 1
            row_heights.append(0.12)
        if show_macd:
            subplot_count += 1
            row_heights.append(0.13)
        if show_rsi:
            subplot_count += 1
            row_heights.append(0.12)
        if show_kdj:
            subplot_count += 1
            row_heights.append(0.13)

        fig = make_subplots(
            rows=subplot_count, cols=1,
            shared_xaxes=True,
            vertical_spacing=0.03,
            row_heights=row_heights,
        )

        row = 1
        fig.add_trace(go.Candlestick(
            x=df["date"], open=df["open"], high=df["high"],
            low=df["low"], close=df["close"],
            name="K线",
            increasing_line_color="red",
            decreasing_line_color="green",
        ), row=row, col=1)

        if show_ma:
            for p in [5, 10, 20, 60]:
                col_name = f"ma{p}"
                if col_name in df.columns:
                    fig.add_trace(go.Scatter(
                        x=df["date"], y=df[col_name],
                        name=f"MA{p}", mode="lines",
                        line=dict(width=1),
                    ), row=row, col=1)

        if show_boll and "boll_upper" in df.columns:
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["boll_upper"],
                name="BOLL上轨", mode="lines",
                line=dict(width=1, dash="dash"),
            ), row=row, col=1)
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["boll_mid"],
                name="BOLL中轨", mode="lines",
                line=dict(width=1),
            ), row=row, col=1)
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["boll_lower"],
                name="BOLL下轨", mode="lines",
                line=dict(width=1, dash="dash"),
            ), row=row, col=1)

        row += 1
        if show_vol:
            colors = ["red" if c >= o else "green" for c, o in zip(df["close"], df["open"])]
            fig.add_trace(go.Bar(
                x=df["date"], y=df["volume"],
                name="成交量", marker_color=colors,
            ), row=row, col=1)
            if "vol_ma5" in df.columns:
                fig.add_trace(go.Scatter(
                    x=df["date"], y=df["vol_ma5"],
                    name="VOL MA5", mode="lines",
                    line=dict(width=1),
                ), row=row, col=1)

        row += 1
        if show_macd and "dif" in df.columns:
            fig.add_trace(go.Bar(
                x=df["date"], y=df["macd"],
                name="MACD柱",
                marker_color=["red" if v >= 0 else "green" for v in df["macd"]],
            ), row=row, col=1)
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["dif"],
                name="DIF", mode="lines",
                line=dict(width=1),
            ), row=row, col=1)
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["dea"],
                name="DEA", mode="lines",
                line=dict(width=1),
            ), row=row, col=1)

        row += 1
        if show_rsi and "rsi14" in df.columns:
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["rsi14"],
                name="RSI14", mode="lines",
                line=dict(width=1),
            ), row=row, col=1)
            fig.add_hline(y=70, line_dash="dash", line_color="red", row=row, col=1)
            fig.add_hline(y=30, line_dash="dash", line_color="green", row=row, col=1)

        row += 1
        if show_kdj and "k" in df.columns:
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["k"],
                name="K", mode="lines",
                line=dict(width=1),
            ), row=row, col=1)
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["d"],
                name="D", mode="lines",
                line=dict(width=1),
            ), row=row, col=1)
            fig.add_trace(go.Scatter(
                x=df["date"], y=df["j"],
                name="J", mode="lines",
                line=dict(width=1),
            ), row=row, col=1)

        fig.update_layout(
            height=800,
            xaxis_rangeslider_visible=False,
            template="plotly_white",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        st.plotly_chart(fig, use_container_width=True)

    st.subheader("最新技术指标数值")
    last = df.iloc[-1]
    indicator_data = {}
    for col in df.columns:
        if col in ["date", "open", "close", "high", "low", "volume", "amount",
                    "amplitude", "pct_change", "change", "turnover"]:
            continue
        indicator_data[col] = round(float(last[col]), 4) if pd.notna(last[col]) else "N/A"
    if indicator_data:
        st.json(indicator_data)


def render_alerts():
    st.header("🔔 涨跌幅预警")
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("自选股预警")
        threshold = st.number_input(
            "涨跌幅阈值(%)", min_value=1.0, max_value=20.0,
            value=ALERT_THRESHOLD, step=0.5, key="alert_threshold",
        )
        if st.button("🔍 检查自选股预警"):
            with st.spinner("检查中..."):
                alerts = check_watchlist_alerts(
                    st.session_state.watchlist, threshold
                )
            if alerts:
                for a in alerts:
                    icon = "🔴" if a["alert_type"] == "大跌" else "🟢"
                    st.warning(
                        f"{icon} **{a['name']}({a['symbol']})** "
                        f"当前价: ¥{a['price']:.2f} "
                        f"涨跌幅: {a['pct_change']:+.2f}% "
                        f"触发{a['alert_type']}预警(阈值±{a['threshold']}%)"
                    )
            else:
                st.success("自选股暂无预警 ✅")

    with col2:
        st.subheader("全市场异动扫描")
        market_threshold = st.number_input(
            "全市场阈值(%)", min_value=3.0, max_value=20.0,
            value=5.0, step=0.5, key="market_threshold",
        )
        if st.button("🔍 扫描全市场异动"):
            with st.spinner("扫描中，请耐心等待..."):
                df = scan_market_alerts(threshold=market_threshold, top_n=30)
            if not df.empty:
                st.dataframe(df, use_container_width=True, hide_index=True)
            else:
                st.info("当前无显著异动")


def render_buy_scan():
    st.header("🛒 每日买入选股")
    st.markdown("""
    基于技术指标综合分析，筛选当日出现买入信号的股票。
    评分规则：MA金叉(+2)、MACD金叉(+2)、KDJ超卖回升(+1)、RSI超卖回升(+1)、
    放量突破(+1)、布林下轨支撑(+1)、站上5日均线(+1)，总分≥3分推荐买入。
    """)

    col1, col2 = st.columns([1, 3])
    with col1:
        top_n = st.number_input("返回数量", min_value=5, max_value=50, value=20, key="buy_top_n")
        st.info("将扫描全市场A股，耗时较长，请耐心等待。")
        scan_btn = st.button("🚀 开始扫描买入机会", type="primary")

    with col2:
        if scan_btn:
            with st.spinner("正在扫描全市场买入信号，请耐心等待(可能需要几分钟)..."):
                all_stocks = get_all_stocks_realtime()
                if all_stocks.empty:
                    st.error("获取市场数据失败")
                    return
                filtered = all_stocks[
                    (all_stocks["price"] > 0) &
                    (all_stocks["pct_change"].abs() < 9.5) &
                    (all_stocks["turnover"] > 1) &
                    (all_stocks["total_mv"] > 5e9)
                ]
                result = scan_buy_opportunities(filtered, top_n=top_n)
            if not result.empty:
                st.success(f"发现 {len(result)} 只股票有买入信号！")
                for _, row in result.iterrows():
                    with st.expander(
                        f"⭐ {row['name']}({row['symbol']}) - 评分:{row['score']} - "
                        f"现价:¥{row['price']:.2f} 涨跌:{row['pct_change']:+.2f}%"
                    ):
                        st.write(f"**买入理由：** {row['reasons']}")
            else:
                st.info("今日暂无符合条件的买入机会")


def render_sell_analysis():
    st.header("💰 持仓卖出分析")
    if not st.session_state.portfolio:
        st.warning("请先在左侧添加持仓股票！")
        return

    for code, info in st.session_state.portfolio.items():
        st.subheader(f"📊 {code}")
        col1, col2, col3 = st.columns(3)

        realtime = get_stock_realtime(code)
        if realtime:
            cur_price = realtime.get("price", 0)
            pct = realtime.get("pct_change", 0)
            profit = (cur_price - info["cost"]) * info["qty"]
            profit_pct = (cur_price - info["cost"]) / info["cost"] * 100 if info["cost"] > 0 else 0

            with col1:
                st.metric("当前价格", f"¥{cur_price:.2f}", f"{pct:+.2f}%")
            with col2:
                st.metric("持仓盈亏", f"¥{profit:+.2f}", f"{profit_pct:+.2f}%")
            with col3:
                st.metric("持仓市值", f"¥{cur_price * info['qty']:,.2f}")

        hist = get_stock_history(code, days=90)
        if not hist.empty:
            sell_signals = analyze_sell_signals(hist)
            buy_signals = analyze_buy_signals(hist)

            if sell_signals:
                for sig in sell_signals:
                    st.error(
                        f"⚠️ **卖出信号** (评分:{sig['score']}) - "
                        f"理由：{'；'.join(sig['reasons'])}"
                    )
            else:
                st.success("暂无卖出信号，可继续持有 ✅")

            if buy_signals:
                for sig in buy_signals:
                    st.info(
                        f"📌 **加仓信号** (评分:{sig['score']}) - "
                        f"理由：{'；'.join(sig['reasons'])}"
                    )

        st.markdown("---")


def main():
    page = render_sidebar()

    if page == "📊 实时监控":
        render_realtime_monitor()
    elif page == "🕯️ K线图表":
        render_kline_chart()
    elif page == "🔔 涨跌预警":
        render_alerts()
    elif page == "🛒 买入选股":
        render_buy_scan()
    elif page == "💰 持仓卖出":
        render_sell_analysis()


if __name__ == "__main__":
    main()
