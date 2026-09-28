"""
고객사 전용 자동분석 파이프라인.

내부 제작용 앱은 "자료 업로드 -> 재무 데이터 검토 -> 종합의견 작성"을 사람이 단계마다
확인하며 진행하지만, 고객용은 자료를 넣으면 그 뒤로 사람 개입 없이:
  1. 재무지표 계산 (sections.metrics.compute_all_metrics)
  2. 문서에 넣을 지표를 자동 선택 (추천 조합 5종 전체 — 수익성/안정성/활동성/성장성/자본수익성)
  3. 그 5종 지표의 그래프를 이미지로 생성 (보고서 삽입용)
  4. AI가 종합의견(Executive Summary)을 직접 작성 (comment.py와 동일한 규칙/검수 재사용)
을 한 번에 수행한다. 계산 로직 자체는 인터랙티브 화면(metrics.py, comment.py)과 100%
공유하므로, 두 화면이 서로 다른 답을 내는 일이 없다.
"""
import pandas as pd
import plotly.express as px
import streamlit as st

from sections.metrics import (
    compute_all_metrics,
    RECOMMENDED_COMBOS,
    BS_INDICATORS,
    IS_INDICATORS,
    COMMON_INDICATORS,
    _get_metric_val,
    _CHART_LAYOUT,
)
from sections.comment import (
    build_indicator_table,
    _financial_context,
    _system_instruction,
    _plain_text_ai_answer,
    _quick_style_check,
)
from sections.ai_client import configured_value, gemini_model

# RECOMMENDED_COMBOS의 키(사람이 읽는 라벨) -> 보고서 템플릿의 Jinja 변수명.
# assets/templates/[그로스파이낸스]_고객용_템플릿.docx 의 {{ ... }} 자리와 반드시 맞아야 한다.
CHART_TEMPLATE_VARS = {
    "수익성 (얼마나 남기나)": "profitability_chart",
    "안정성 (재무구조가 튼튼한가)": "stability_chart",
    "활동성 (자산을 잘 굴리나)": "activity_chart",
    "성장성 (외형이 커지고 있나)": "growth_chart",
    "자본수익성 (투자 대비 성과)": "roi_chart",
}

_ALL_INDICATOR_ORDER = BS_INDICATORS + IS_INDICATORS + COMMON_INDICATORS


def _split_selected_indicators(indicator_names):
    """지표명 목록을 report.py/comment.py가 기대하는 {'bs':[...], 'is':[...], 'common':[...]}
    구조로 나눈다(원래 출처 분류 기준)."""
    names = set(indicator_names)
    return {
        'bs': [i for i in BS_INDICATORS if i in names],
        'is': [i for i in IS_INDICATORS if i in names],
        'common': [i for i in COMMON_INDICATORS if i in names],
    }


def _build_chart_png(indicators, years, bs_metrics, is_metrics, common_metrics):
    """지표 조합 하나의 연도별 추이 꺾은선 그래프를 PNG 바이트로 만든다.
    (metrics.py의 '지표 조합 그래프'와 같은 방식 — kaleido로 정적 이미지 export)"""
    rows = [
        {'지표': ind, '연도': str(yr), '값': v}
        for ind in indicators
        for yr in years
        for v in [_get_metric_val(ind, yr, bs_metrics, is_metrics, common_metrics)]
        if v is not None
    ]
    if not rows:
        return None
    df = pd.DataFrame(rows)
    fig = px.line(df, x='연도', y='값', color='지표', markers=True)
    fig.update_traces(texttemplate='%{y}', textposition='top center')
    fig.update_layout(
        xaxis=dict(type='category'), yaxis=dict(showgrid=True), legend_title='지표', **_CHART_LAYOUT
    )
    return fig.to_image(format="png", width=1000, height=560, scale=2)


def build_chart_images(bs_metrics, is_metrics, common_metrics, years):
    """추천 조합 5종 각각의 그래프를 {템플릿 변수명: PNG bytes} 로 반환한다.
    kaleido 미설치 등으로 특정 그래프 생성에 실패해도 그 하나만 None으로 건너뛰고
    나머지는 계속 만든다(보고서 생성 자체를 막지 않기 위함)."""
    images = {}
    for combo_name, indicators in RECOMMENDED_COMBOS.items():
        var = CHART_TEMPLATE_VARS.get(combo_name)
        if not var:
            continue
        try:
            images[var] = _build_chart_png(indicators, years, bs_metrics, is_metrics, common_metrics)
        except Exception:
            images[var] = None
    return images


def generate_exec_summary(api_key, model):
    """session_state에 채워진 재무 데이터를 근거로 AI가 종합의견 초안을 바로 작성하게 한다
    (대화형 질문-답변이 아니라 완결된 결과를 한 번에 요청). comment.py의 시스템 지시(ES 작성
    규칙)와 후처리(마크다운 정리 + 자동 검수)를 그대로 재사용해 인터랙티브 화면과 품질 기준을
    맞춘다. 이 파이프라인은 사람이 다시 눌러줄 버튼이 없는 완전 자동 흐름이라, convert.py의
    파일 추출과 같은 방식으로 AI 서버 일시 과부하(503 등)에는 재시도한다."""
    import time as _time

    from google import genai
    from google.genai import types

    from sections.convert import _is_transient_error, _MAX_RETRIES

    question = (
        "지금까지 제공된 재무 데이터를 바탕으로, 기초재무진단보고서 1페이지에 바로 실을 "
        "종합의견(Executive Summary) 초안을 지금 바로 작성해 주세요. 질문에 답하는 형식이 아니라 "
        "완성된 종합의견 본문만 출력하세요."
    )
    prompt = f"""아래 기업 데이터를 근거로 요청에 한국어로 답변하세요.
수치가 없는 내용은 추정하지 말고, 답변은 실무자가 바로 활용할 수 있게 작성하세요.

[기업 데이터]
{_financial_context()}

[요청]
{question}
"""
    client = genai.Client(api_key=api_key)
    config = types.GenerateContentConfig(system_instruction=_system_instruction())

    last_error = None
    for attempt in range(_MAX_RETRIES):
        try:
            response = client.models.generate_content(model=model, contents=prompt, config=config)
            raw = response.text or ""
            cleaned = _plain_text_ai_answer(raw)
            warnings = _quick_style_check(cleaned)
            return cleaned, warnings
        except Exception as error:
            last_error = error
            if not _is_transient_error(error) or attempt == _MAX_RETRIES - 1:
                raise
            _time.sleep(3 * (attempt + 1))
    raise last_error


def pipeline_key(years, df_bs, df_is):
    """같은 업로드 결과에 대해 파이프라인을 중복 실행(=AI 재호출)하지 않기 위한 식별 키."""
    return f"{list(years)}|{len(df_bs)}|{len(df_is)}"


def run_auto_analysis(df_bs, df_is, years):
    """업로드된 BS/IS로 지표 계산 -> 지표 선택 -> 그래프 생성 -> 종합의견 생성까지 한 번에
    수행하고, 최종보고서 생성에 필요한 값들을 session_state에 채운다.

    AI 호출이 실패해도(키 미설정, 네트워크 오류 등) 예외를 밖으로 던지지 않는다 — 종합의견만
    비운 채로 두고 사유를 session_state['auto_pipeline_error']에 남겨, 나머지(지표·그래프)는
    그대로 보고서에 쓸 수 있게 한다."""
    st.session_state.pop('auto_pipeline_error', None)

    bs_metrics, is_metrics, common_metrics = compute_all_metrics(df_bs, df_is, years)
    st.session_state['bs_metrics'] = bs_metrics
    st.session_state['is_metrics'] = is_metrics
    st.session_state['common_metrics'] = common_metrics
    st.session_state['years'] = years

    all_selected = sorted(
        {i for inds in RECOMMENDED_COMBOS.values() for i in inds},
        key=_ALL_INDICATOR_ORDER.index,
    )
    st.session_state['selected_indicators'] = _split_selected_indicators(all_selected)

    _, table_text = build_indicator_table(all_selected, years, bs_metrics, is_metrics, common_metrics)
    st.session_state['selected_indicators_table'] = table_text

    try:
        st.session_state['auto_chart_images'] = build_chart_images(
            bs_metrics, is_metrics, common_metrics, years
        )
    except Exception as error:
        st.session_state['auto_chart_images'] = {}
        st.session_state['auto_pipeline_error'] = f"그래프 생성 중 오류: {error}"

    api_key = configured_value("Gemini", "api_key")
    model = gemini_model()
    if not api_key:
        st.session_state['auto_pipeline_error'] = (
            st.session_state.get('auto_pipeline_error', '')
            + " Gemini API 키가 설정되지 않아 종합의견을 자동 생성하지 못했습니다."
        ).strip()
        st.session_state['txt_exec'] = ''
        st.session_state['exec_summary'] = ''
        return

    try:
        exec_summary, warnings = generate_exec_summary(api_key, model)
        st.session_state['txt_exec'] = exec_summary
        st.session_state['exec_summary'] = exec_summary
        st.session_state['auto_es_warnings'] = warnings
    except Exception as error:
        st.session_state['auto_pipeline_error'] = (
            st.session_state.get('auto_pipeline_error', '') + f" AI 종합의견 생성 중 오류: {error}"
        ).strip()
        st.session_state['txt_exec'] = ''
        st.session_state['exec_summary'] = ''
