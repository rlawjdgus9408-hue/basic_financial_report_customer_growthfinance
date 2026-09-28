"""
그로스파이낸스 기초재무진단 자동화 시스템 — 고객사 전용판
메인 실행 파일

내부 제작용 버전과 달리, 자료 업로드 뒤로는 사람이 재무 데이터를 검토하거나 지표를
고르거나 종합의견을 다듬는 화면이 없다. 대신 sections.auto_pipeline이 그 전부(지표
계산·추천 지표 5종 그래프 생성·AI 종합의견 작성)를 자동으로 수행하고, 곧바로 최종보고서
생성 화면으로 넘어간다. 그래서 화면에 보이는 단계는 1(기업정보)/2(사전진단)/3(자료업로드)
/4(최종보고서) 네 개뿐이다.

디자인/사이드바/마법사(진행도) 관련 공통 로직은 sections 패키지로 분리돼 있다:
  - sections.styles         전역 CSS
  - sections.session_state  세션 상태 초기화
  - sections.sidebar        사이드바 공통 UI(목차, 다시 실행, 임시저장/불러오기)
  - sections.wizard         설문조사형 단계 이동(안내 문구, 진행도, 다음/이전 버튼)
  - sections.auto_pipeline  자료 업로드 후 자동분석(지표·그래프·AI 종합의견)
  - sections.report         최종보고서 생성(콘텐츠 영역 + 사이드바 실제 생성 로직)
이 파일은 각 단계 섹션을 순서대로 배치하는 오케스트레이션만 담당한다.
"""
import streamlit as st

from sections.styles import inject_global_css
from sections.session_state import init_session_state
from sections.sidebar import render_sidebar_chrome
from sections.wizard import (
    TOTAL_WIZARD_STEPS,
    render_step_intro,
    render_sidebar_progress,
    render_step_nav,
)
from sections.info import render_company_info
from sections.customer_upload import render_customer_upload
from sections.diagnosis import render_diagnosis
from sections.auto_pipeline import run_auto_analysis, pipeline_key
from sections.report import render_report_generation, render_report_sidebar

# 페이지 설정
st.set_page_config(page_title="그로스파이낸스 재무진단 시스템", layout="wide", initial_sidebar_state="expanded")

inject_global_css()
render_sidebar_chrome()

_header_company = st.session_state.get('input_co_name') or st.session_state.get('company_name')
st.title(f"{_header_company + ' ' if _header_company else ''}기초재무진단 보고서")

init_session_state()

# Default values so every variable is defined regardless of which step is active
company_info = {}
template_file = None
check_results = []
score = 0
selected_dirs = []
dir_etc = ''
selected_mats = []
df_bs = df_is = None
years = []
exec_summary = st.session_state.get('exec_summary', '')

current_step = st.session_state.get('current_step', 1)

# 현재 단계만 화면에 보이도록 나머지 단계 컨테이너를 CSS로 숨긴다.
# (모든 단계의 렌더 함수는 매 실행마다 호출되어 데이터 연속성을 유지한다)
_hide_css = "\n".join(f'.st-key-step{_n} {{ display: none !important; }}' for _n in range(1, 5) if _n != current_step)
st.markdown(f"<style>{_hide_css}</style>", unsafe_allow_html=True)

# 진행도는 사이드바 하단에 고정 표시 (1~3단계 설문 흐름에서만, 4단계 제외)
if 1 <= current_step <= TOTAL_WIZARD_STEPS:
    render_sidebar_progress(current_step)

# 1. 기업 상세 정보 입력
with st.container(key="step1"):
    render_step_intro(1)
    company_info = render_company_info()
    render_step_nav(1)

# 2. 사전 진단 및 관리 방향성
with st.container(key="step2"):
    render_step_intro(2)
    check_results, score, selected_dirs, dir_etc, selected_mats = render_diagnosis()
    render_step_nav(2)

# 3. 자료 업로드 (업로드 즉시 AI가 표준 데이터로 변환)
with st.container(key="step3"):
    render_step_intro(3)
    df_bs, df_is, years = render_customer_upload()

    if df_bs is not None and df_is is not None and years:
        # 같은 업로드 결과에 대해 파이프라인(특히 AI 종합의견 생성)을 중복 실행하지 않는다.
        _pkey = pipeline_key(years, df_bs, df_is)
        if st.session_state.get('auto_pipeline_done_for') != _pkey:
            with st.spinner("재무지표를 계산하고 종합의견을 작성하고 있습니다..."):
                run_auto_analysis(df_bs, df_is, years)
            st.session_state['auto_pipeline_done_for'] = _pkey

    render_step_nav(3)

# 4. 최종보고서 생성 (설문 흐름/진행도에는 포함되지 않는 완료 화면)
with st.container(key="step4"):
    render_report_generation(
        company_info=company_info,
        template_file=template_file,
        check_results=check_results,
        score=score,
        selected_dirs=selected_dirs,
        dir_etc=dir_etc,
        selected_mats=selected_mats,
        exec_summary=exec_summary,
    )
    if st.button("← 이전 단계(자료 다시 업로드)", key="btn_prev_4"):
        st.session_state['current_step'] = 3
        st.rerun()

# 사이드바 보고서 생성 (모든 변수가 정의된 후 실행)
exec_summary = st.session_state.get('exec_summary', exec_summary)
render_report_sidebar(
    company_info=company_info,
    template_file=template_file,
    check_results=check_results,
    score=score,
    selected_dirs=selected_dirs,
    dir_etc=dir_etc,
    selected_mats=selected_mats,
    exec_summary=exec_summary,
)
