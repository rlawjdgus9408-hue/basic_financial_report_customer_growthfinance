"""
Section 3-1: 재무지표 연도별 추이
"""
import streamlit as st
import pandas as pd
import plotly.express as px

# ── 공통 설정 ────────────────────────────────────────────────────────────────
_CHART_CONFIG = {
    'toImageButtonOptions': {'format': 'png', 'filename': 'chart', 'height': 500, 'width': 800, 'scale': 2},
    'displayModeBar': True,
    'displaylogo': False,
}

# 그래프는 페이지가 검정이어도 흰 배경 카드로 표시한다 — 화면 가독성뿐 아니라, PNG
# 다운로드(툴바의 카메라 아이콘) 결과물도 이 배경을 그대로 따라가기 때문에 검정 배경으로
# 두면 다운로드한 이미지가 보기/인쇄하기 어려워진다.
_CHART_LAYOUT = dict(
    template='plotly_white',
    paper_bgcolor='#FFFFFF',
    plot_bgcolor='#FFFFFF',
    font=dict(color='#191919'),
)

BS_INDICATORS = [
    '유동비율', '당좌비율', '현금비율', '부채비율', '자기자본비율',
    '유동부채비율', '비유동자산비율', '재고자산비율',
    '매출채권회전율', '재고자산회전율', '총자산회전율',
]
IS_INDICATORS = [
    '매출총이익률', '판매관리비율', '영업이익률', '순이익률', '매출원가율',
    'EBITDA마진', '비용구조비율',
    '매출액증가율', '총이익증가율', '영업이익증가율', '순이익증가율',
]
COMMON_INDICATORS = [
    'ROA', 'ROE', 'ROIC', 'EPS',
    '부채대비현금비율', '이자보상배율', '자본회전율',
    '자산대비영업이익률', '자본대비영업이익률',
]

# "지표 조합 그래프"에서 매번 30여 개 중 직접 고르지 않아도 되도록, 재무분석 목적별로
# 자주 함께 보는 지표를 미리 묶어둔 추천 조합. BS/IS/공통 출처 구분과는 달리 "무엇을
# 확인하려는가" 기준으로 묶는다.
RECOMMENDED_COMBOS = {
    "수익성 (얼마나 남기나)":      ['매출총이익률', '영업이익률', '순이익률', 'ROE'],
    "안정성 (재무구조가 튼튼한가)":  ['유동비율', '부채비율', '자기자본비율', '이자보상배율'],
    "활동성 (자산을 잘 굴리나)":    ['매출채권회전율', '재고자산회전율', '총자산회전율'],
    "성장성 (외형이 커지고 있나)":  ['매출액증가율', '영업이익증가율', '순이익증가율'],
    "자본수익성 (투자 대비 성과)":  ['ROA', 'ROE', 'ROIC'],
}


def find_account(df, keywords, years):
    """계정 검색 — 연도별 값 딕셔너리 반환.

    일부 RAW 파일은 본문 계정과 별도로 "영업이익률", "매출액증가율(%)" 같은 비율 요약 행을
    같은 표 안에 함께 담고 있다. 이런 행이 "영업이익" 같은 금액 키워드에 우연히 걸려
    (예: "영업이익률"이 "영업이익"을 포함) 금액 대신 비율값(예: 0.097)이 잘못 쓰이는 사고가
    실제로 있었다 — 라벨에 "률"이나 "%"가 있으면 애초에 매칭 대상에서 제외한다."""
    for kw in keywords:
        matches = df[
            df['계정과목'].str.contains(kw, case=False, na=False)
            & ~df['계정과목'].str.contains('률|%', case=False, na=False)
        ]
        if not matches.empty:
            row = matches.iloc[0]
            result = {}
            for yr in years:
                if yr in row.index:
                    try:
                        result[yr] = float(row[yr]) if pd.notna(row[yr]) else 0
                    except (ValueError, TypeError):
                        result[yr] = 0
            return result
    return None


def _get_metric_val(indicator, yr, bs_metrics, is_metrics, common_metrics):
    """세 지표 딕셔너리에서 값 탐색"""
    for m in (bs_metrics, is_metrics, common_metrics):
        if m.get(yr) and indicator in m[yr]:
            return m[yr][indicator]
    return None


def _metrics_df(metrics, indicators, years):
    """지표 딕셔너리 → 표시용 DataFrame"""
    df = pd.DataFrame(index=indicators, columns=years)
    for yr in years:
        for ind in indicators:
            val = metrics.get(yr, {}).get(ind)
            if val is not None:
                df.loc[ind, yr] = val
    return df.astype(str).replace({'nan': '-', 'None': '-'})


def _indicator_buttons(prefix, indicators, columns=4):
    selected = []
    cols = st.columns(columns)
    for i, indicator in enumerate(indicators):
        state_key = f"doc_{prefix}_{indicator}"
        is_selected = st.session_state.get(state_key, False)
        with cols[i % columns]:
            if st.button(
                indicator,
                key=f"indicator_btn_{prefix}_{indicator}",
                type="primary" if is_selected else "secondary",
                use_container_width=True,
            ):
                st.session_state[state_key] = not is_selected
                st.rerun()
        if is_selected:
            selected.append(indicator)
    return selected


# ── 지표 계산 ────────────────────────────────────────────────────────────────

def calculate_bs_metrics(bs_accounts, is_accounts, years):
    metrics = {}
    for yr in years:
        m = {}
        ca   = bs_accounts.get('유동자산') or {}
        cl   = bs_accounts.get('유동부채') or {}
        inv  = bs_accounts.get('재고자산') or {}
        cash = bs_accounts.get('현금및현금성자산') or {}
        liab = bs_accounts.get('부채총계') or {}
        eq   = bs_accounts.get('자본총계') or {}
        tot_ast = bs_accounts.get('자산총계') or {}
        nca  = bs_accounts.get('비유동자산') or {}
        ar   = bs_accounts.get('매출채권') or {}
        rev  = is_accounts.get('매출액') or {}
        cogs = is_accounts.get('매출원가') or {}

        cl_v    = cl.get(yr, 0)
        ca_v    = ca.get(yr, 0)
        eq_v    = eq.get(yr, 0)
        ast_v   = tot_ast.get(yr, 0)

        if ca and cl and cl_v:
            m['유동비율']    = round(ca_v / cl_v * 100, 2)
            m['당좌비율']    = round((ca_v - inv.get(yr, 0)) / cl_v * 100, 2)
            m['유동부채비율'] = round(cl_v / ca_v * 100, 2) if ca_v else None
        if cash and cl and cl_v:
            m['현금비율']    = round(cash.get(yr, 0) / cl_v * 100, 2)
        if eq and eq_v:
            m['부채비율']    = round(liab.get(yr, 0) / eq_v * 100, 2)
        if tot_ast and ast_v:
            m['자기자본비율']   = round(eq_v / ast_v * 100, 2)
            m['비유동자산비율'] = round(nca.get(yr, 0) / ast_v * 100, 2) if nca else None
        if inv and ca_v:
            m['재고자산비율'] = round(inv.get(yr, 0) / ca_v * 100, 2)
        if ar and rev and ar.get(yr, 0):
            m['매출채권회전율'] = round(rev.get(yr, 0) / ar.get(yr, 0), 2)
        if inv and cogs and inv.get(yr, 0):
            m['재고자산회전율'] = round(cogs.get(yr, 0) / inv.get(yr, 0), 2)
        if rev and tot_ast and ast_v:
            m['총자산회전율'] = round(rev.get(yr, 0) / ast_v, 2)

        metrics[yr] = {k: v for k, v in m.items() if v is not None}
    return metrics


def calculate_is_metrics(is_accounts, years):
    metrics = {}
    for yr in years:
        m = {}
        rev   = is_accounts.get('매출액') or {}
        cogs  = is_accounts.get('매출원가') or {}
        gross = is_accounts.get('매출총이익') or {}
        op    = is_accounts.get('영업이익') or {}
        ebitda = is_accounts.get('EBITDA') or {}
        net   = is_accounts.get('당기순이익') or {}
        sga   = is_accounts.get('판매관리비') or {}
        rev_v = rev.get(yr, 0)

        if rev_v:
            if gross: m['매출총이익률'] = round(gross.get(yr, 0) / rev_v * 100, 2)
            if sga:   m['판매관리비율'] = round(sga.get(yr, 0)   / rev_v * 100, 2)
            if op:    m['영업이익률']   = round(op.get(yr, 0)    / rev_v * 100, 2)
            if net:   m['순이익률']     = round(net.get(yr, 0)   / rev_v * 100, 2)
            if cogs:  m['매출원가율']   = round(cogs.get(yr, 0)  / rev_v * 100, 2)
            if ebitda: m['EBITDA마진'] = round(ebitda.get(yr, 0) / rev_v * 100, 2)
        if sga and cogs and cogs.get(yr, 0):
            m['비용구조비율'] = round(sga.get(yr, 0) / cogs.get(yr, 0) * 100, 2)

        idx = years.index(yr)
        if idx > 0:
            prev = years[idx - 1]
            def _yoy(acc):
                p = acc.get(prev, 0)
                return round((acc.get(yr, 0) - p) / abs(p) * 100, 2) if p else None
            if rev:   m['매출액증가율']  = _yoy(rev)
            if gross: m['총이익증가율']  = _yoy(gross)
            if op:    m['영업이익증가율'] = _yoy(op)
            if net:   m['순이익증가율']  = _yoy(net)

        metrics[yr] = {k: v for k, v in m.items() if v is not None}
    return metrics


def calculate_common_metrics(bs_accounts, is_accounts, years):
    metrics = {}
    for yr in years:
        m = {}
        tot_ast = bs_accounts.get('자산총계') or {}
        eq      = bs_accounts.get('자본총계') or {}
        liab    = bs_accounts.get('부채총계') or {}
        rev     = is_accounts.get('매출액') or {}
        net     = is_accounts.get('당기순이익') or {}
        op      = is_accounts.get('영업이익') or {}
        cl      = bs_accounts.get('유동부채') or {}
        cash    = bs_accounts.get('현금및현금성자산') or {}
        cap     = bs_accounts.get('자본금') or {}
        opex    = is_accounts.get('영업외비용') or {}

        ast_v = tot_ast.get(yr, 0)
        eq_v  = eq.get(yr, 0)

        if net and tot_ast and ast_v: m['ROA']  = round(net.get(yr, 0) / ast_v * 100, 2)
        if net and eq      and eq_v:  m['ROE']  = round(net.get(yr, 0) / eq_v  * 100, 2)
        ic = ast_v - cl.get(yr, 0)
        if op and tot_ast and ic:     m['ROIC'] = round(op.get(yr, 0)  / ic    * 100, 2)
        if cap and net:
            shares = cap.get(yr, 0) / 1000
            if shares > 0: m['EPS'] = round(net.get(yr, 0) / shares, 0)
        if cash and liab and liab.get(yr, 0):
            m['부채대비현금비율'] = round(cash.get(yr, 0) / liab.get(yr, 0) * 100, 2)
        if op and opex and opex.get(yr, 0):
            m['이자보상배율'] = round(op.get(yr, 0) / abs(opex.get(yr, 0)), 2)
        if rev and eq      and eq_v:  m['자본회전율']       = round(rev.get(yr, 0) / eq_v  , 2)
        if op  and tot_ast and ast_v: m['자산대비영업이익률'] = round(op.get(yr, 0)  / ast_v * 100, 2)
        if op  and eq      and eq_v:  m['자본대비영업이익률'] = round(op.get(yr, 0)  / eq_v  * 100, 2)

        metrics[yr] = {k: v for k, v in m.items() if v is not None}
    return metrics


def compute_all_metrics(df_bs, df_is, years):
    """BS/IS에서 계정을 추출해 세 지표 딕셔너리(bs_metrics, is_metrics, common_metrics)를
    계산한다. 인터랙티브 화면(render_financial_metrics)과 고객용 자동분석 파이프라인
    (auto_pipeline.py) 양쪽에서 공유해, 계정 키워드 목록이 두 군데로 갈라지지 않게 한다."""
    bs_accounts = {
        '현금및현금성자산': find_account(df_bs, ['현금', '현금성자산', '예금', '당좌예금'], years),
        '단기금융자산':     find_account(df_bs, ['단기금융자산', '단기투자', '유동금융자산'], years),
        '매출채권':        find_account(df_bs, ['매출채권', '외상매출금', '거래외채권', '채권'], years),
        '재고자산':        find_account(df_bs, ['재고자산', '재고', '상품', '제품', '반제품', '원재료', '재공품'], years),
        '유동자산':        find_account(df_bs, ['유동자산'], years),
        '비유동자산':      find_account(df_bs, ['비유동자산', '고정자산', '투자자산'], years),
        '자산총계':        find_account(df_bs, ['자산총계', '총자산', '자산합계'], years),
        '유동부채':        find_account(df_bs, ['유동부채'], years),
        '부채총계':        find_account(df_bs, ['부채총계', '총부채', '부채합계'], years),
        '자본총계':        find_account(df_bs, ['자본총계', '자본합계', '순자산', '자본'], years),
        '자본금':          find_account(df_bs, ['자본금', '납입자본', '설립자본'], years),
    }
    is_accounts = {
        '매출액':    find_account(df_is, ['매출액', '매출', '수익', '총매출', '사업수익'], years),
        '매출원가':  find_account(df_is, ['매출원가', '원가', '판매원가', '제품원가'], years),
        '매출총이익': find_account(df_is, ['매출총이익', '매출총손익', 'gross', '총이익'], years),
        '판매관리비': find_account(df_is, ['판매관리비', '판매비', '관리비', '운영비'], years),
        '영업이익':  find_account(df_is, ['영업이익', '영업손익', '운영이익', '본이익'], years),
        'EBITDA':    find_account(df_is, ['EBITDA', '에비타'], years),
        '당기순이익': find_account(df_is, ['당기순이익', '당기순손익', '순이익', '당기순손실'], years),
        '영업외비용': find_account(df_is, ['영업외비용', '금융비용', '이자비용'], years),
    }

    bs_metrics     = calculate_bs_metrics(bs_accounts, is_accounts, years)
    is_metrics     = calculate_is_metrics(is_accounts, years)
    common_metrics = calculate_common_metrics(bs_accounts, is_accounts, years)
    return bs_metrics, is_metrics, common_metrics


# ── 렌더링 ───────────────────────────────────────────────────────────────────

def render_financial_metrics(df_bs, df_is, years):
    st.markdown("---")
    st.markdown("### 3-1. 재무지표 연도별 추이")

    if not years:
        st.warning("연도 정보가 없습니다.")
        return

    bs_metrics, is_metrics, common_metrics = compute_all_metrics(df_bs, df_is, years)

    # ── 문서 포함 지표 선택 ──
    st.markdown("#### 문서 포함 지표 선택")

    col_reset, _ = st.columns([1, 4])
    with col_reset:
        if st.button("다시 선택하기", key="reset_indicators"):
            for prefix, inds in (('bs', BS_INDICATORS), ('is', IS_INDICATORS), ('common', COMMON_INDICATORS)):
                for ind in inds:
                    st.session_state[f"doc_{prefix}_{ind}"] = False
            st.rerun()

    st.markdown("**BS 지표**")
    selected_bs = _indicator_buttons("bs", BS_INDICATORS)

    st.markdown("**IS 지표**")
    selected_is = _indicator_buttons("is", IS_INDICATORS)

    st.markdown("**공통 지표**")
    selected_common = _indicator_buttons("common", COMMON_INDICATORS)

    st.session_state['selected_indicators'] = {'bs': selected_bs, 'is': selected_is, 'common': selected_common}

    # ── 지표 표 ──
    tab_bs, tab_is, tab_common = st.tabs(["재무상태표 (BS) 지표", "손익계산서 (IS) 지표", "공통 지표"])
    with tab_bs:
        st.dataframe(_metrics_df(bs_metrics, BS_INDICATORS, years), use_container_width=True)
    with tab_is:
        st.dataframe(_metrics_df(is_metrics, IS_INDICATORS, years), use_container_width=True)
    with tab_common:
        st.dataframe(_metrics_df(common_metrics, COMMON_INDICATORS, years), use_container_width=True)

    # ── 그래프 ──
    st.markdown("#### 재무지표 그래프")
    all_indicators = BS_INDICATORS + IS_INDICATORS + COMMON_INDICATORS
    graph_mode = st.radio("그래프 표시 방식", ["개별 지표 그래프", "지표 조합 그래프"], horizontal=True, key="graph_mode")

    if graph_mode == "개별 지표 그래프":
        sel = st.selectbox("표시할 지표 선택", all_indicators, key="graph_single")
        chart_data = [
            {'연도': str(yr), '값': v}
            for yr in years
            for v in [_get_metric_val(sel, yr, bs_metrics, is_metrics, common_metrics)]
            if v is not None
        ]
        if chart_data:
            fig = px.line(pd.DataFrame(chart_data), x='연도', y='값', markers=True, title=f"{sel} 연도별 추이")
            fig.update_traces(texttemplate='%{y}', textposition='top center')
            fig.update_layout(xaxis=dict(type='category'), yaxis=dict(showgrid=True), **_CHART_LAYOUT)
            st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

    else:
        st.caption("보려는 목적에 맞는 추천 조합을 고르면 아래 선택창이 자동으로 채워집니다. 이후 직접 더하거나 빼도 됩니다.")
        combo_cols = st.columns(len(RECOMMENDED_COMBOS))
        for col, (combo_name, combo_indicators) in zip(combo_cols, RECOMMENDED_COMBOS.items()):
            with col:
                if st.button(combo_name, key=f"combo_{combo_name}", use_container_width=True):
                    st.session_state["chart_options"] = [i for i in combo_indicators if i in all_indicators]
                    st.rerun()

        chart_options = st.multiselect("표시할 지표 선택 (복수)", all_indicators, default=all_indicators[:4], key="chart_options")
        chart_type    = st.radio("그래프 유형", ["선 그래프", "묶음 막대 그래프"], horizontal=True, key="chart_type")

        if chart_options:
            chart_data = [
                {'지표': ind, '연도': str(yr), '값': v}
                for ind in chart_options
                for yr in years
                for v in [_get_metric_val(ind, yr, bs_metrics, is_metrics, common_metrics)]
                if v is not None
            ]
            if chart_data:
                df_chart = pd.DataFrame(chart_data)
                if chart_type == "선 그래프":
                    fig = px.line(df_chart, x='연도', y='값', color='지표', markers=True)
                    fig.update_traces(texttemplate='%{y}', textposition='top center')
                else:
                    fig = px.bar(df_chart, x='연도', y='값', color='지표', barmode='group')
                    fig.update_traces(texttemplate='%{y}', textposition='outside')
                fig.update_layout(
                    title="재무지표 연도별 추이",
                    xaxis=dict(type='category'), yaxis=dict(showgrid=True),
                    legend_title="지표",
                    **_CHART_LAYOUT,
                )
                st.plotly_chart(fig, use_container_width=True, config=_CHART_CONFIG)

    return bs_metrics, is_metrics, common_metrics, years
