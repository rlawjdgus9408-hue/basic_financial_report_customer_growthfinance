"""
설문조사형 단계 이동 도우미: 단계별 안내 문구, 사이드바 진행도, 업로드 대기 placeholder,
다음/이전 단계 버튼.
"""
import streamlit as st

TOTAL_WIZARD_STEPS = 3  # 진행도/설문 흐름은 1~3단계 기준 (4단계는 최종 생성 화면)

STEP_INTROS = {
    1: "안녕하세요, 그로스파이낸스입니다 👋<br>기초재무진단보고서 작성을 위한 <b>기본정보</b>를 입력해 주세요."
       "<br><br>※ 본 보고서는 AI가 자동으로 생성한 결과로, 실제와 다르거나 정확하지 않을 수 있습니다.",
    2: "귀사의 현재 재무·경영 관리 수준을 파악하기 위한 <b>설문 단계</b>입니다.<br><br>"
       "1. 각 항목에 대해 <b>예/아니오 중 하나</b>를 선택해 주세요.<br>"
       "2. 재무관리를 하시는 <b>목적(방향성)</b>을 선택해 주시고, 해당 사항이 없다면 <b>기타 항목에 직접 작성</b>해 주세요.<br>"
       "3. 현재 <b>보유하신 회사 자료</b>도 선택해 주세요.",
    3: "마지막 입력 단계입니다! <b>표준 재무제표(재무상태표) 및 손익계산서</b> 등의 자료를 업로드해 주세요. "
       "다른 파일 형식이어도 상관없습니다 — AI가 자동으로 분석해서 다음 화면에서 바로 보고서를 만들어 드려요.",
}


def render_step_intro(step):
    text = STEP_INTROS.get(step)
    if not text:
        return
    st.markdown(f"""
    <div style="display:flex; gap:12px; align-items:flex-start;
                background:#1A1A1A; border:1px solid #2A2A2A; border-left:4px solid #FADB15;
                border-radius:0 8px 8px 0; padding:14px 18px; margin-bottom:22px;">
        <div style="flex-shrink:0; width:30px; height:30px; border-radius:50%; background:#FADB15;
                    display:flex; align-items:center; justify-content:center; font-size:15px;">💬</div>
        <div style="font-size:14px; line-height:1.6; color:#D0D0D0; padding-top:4px;">{text}</div>
    </div>
    """, unsafe_allow_html=True)


def _progress_message(percent):
    remaining = 100 - percent
    if percent >= 100:
        return "모든 입력이 완료되었습니다! 🎉"
    if percent >= 70:
        return "거의 다 완료했어요! 🙌"
    if percent >= 50:
        return f"절반 넘게 진행했어요! {remaining}% 남았어요"
    if percent > 0:
        return f"{remaining}% 남았어요"
    return "입력을 시작해 주세요"


def render_sidebar_progress(step, total=TOTAL_WIZARD_STEPS):
    """사이드바 하단에 고정(sticky)되는 애니메이션 진행도 바.
    (본문 하단 고정은 사이드바의 '보고서 생성' 버튼 등과 겹치는 문제가 있어,
     겹침 없이 항상 보이는 사이드바 하단 고정 방식을 사용한다.)
    진행도는 '완료한 단계' 기준이므로 현재 단계 진입 시점에는 아직 반영하지 않는다.
    (예: 1단계 진입 시 0% → 1단계를 마치고 2단계로 넘어가면 20%)"""
    percent = int(round((step - 1) / total * 100))
    message = _progress_message(percent)
    with st.sidebar.container(key="gf_progress_dock"):
        st.markdown(f"""
        <div style="font-size:11px; font-weight:700; color:#9AA0A6; text-transform:uppercase; letter-spacing:.06em; margin-bottom:6px;">진행도</div>
        <div style="font-size:12px; font-weight:600; color:#D0D0D0; margin-bottom:7px;">{message}</div>
        <div class="gf-progress-track">
            <div class="gf-progress-fill" style="width:{percent}%;"></div>
        </div>
        <div style="text-align:right; font-size:11px; color:#9AA0A6; margin-top:5px;">{step} / {total} 단계 · {percent}%</div>
        """, unsafe_allow_html=True)


def render_step_nav(step, total=TOTAL_WIZARD_STEPS):
    col_prev, col_next = st.columns([1, 2])
    with col_prev:
        if step > 1:
            if st.button("← 이전 단계", key=f"btn_prev_{step}", use_container_width=True):
                st.session_state['current_step'] = step - 1
                st.rerun()
    with col_next:
        next_label = "다음 단계로 →" if step < total else "입력 완료, 보고서 생성하러 가기 →"
        if st.button(next_label, key=f"btn_next_{step}", type="primary", use_container_width=True):
            st.session_state['current_step'] = step + 1
            st.rerun()
