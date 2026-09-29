"""
사이드바 공통 UI: 제목, 접힘 방지, 목차 이동, 다시 실행, 임시저장/불러오기
"""
import json
import datetime

import streamlit as st
import streamlit.components.v1 as components

STEP_LABELS = [
    "1. 기업 상세 정보 입력",
    "2. 사전 진단 및 관리 방향성",
    "3. 자료 업로드",
    "4. 최종보고서 생성",
]

_SKIP_TYPES = (bytes, bytearray)
_SKIP_PREFIXES = ('btn_', 'sidebar_', 'form_', 'ai_key_', '_load_done_')


def _keep_sidebar_open():
    """사이드바 강제 표시 유지 (접기 방지)"""
    components.html("""
<script>
(function keepSidebarOpen() {
    function forceOpen() {
        var sidebar = window.parent.document.querySelector('[data-testid="stSidebar"]');
        if (sidebar) {
            sidebar.style.setProperty('transform', 'translateX(0)', 'important');
            sidebar.style.setProperty('visibility', 'visible', 'important');
            sidebar.style.setProperty('display', 'flex', 'important');
        }
        ['collapsedControl','stSidebarCollapseButton'].forEach(function(id) {
            var el = window.parent.document.querySelector('[data-testid="' + id + '"]');
            if (el) el.style.setProperty('display', 'none', 'important');
        });
    }
    forceOpen();
    var observer = new MutationObserver(forceOpen);
    observer.observe(window.parent.document.body, {
        attributes: true, subtree: true, attributeFilter: ['style','class']
    });
})();
</script>
""", height=0)


def _render_step_nav():
    """목차: 클릭 시 해당 단계로 즉시 이동(완료 여부와 무관하게 자유 이동 가능)"""
    st.sidebar.markdown(
        '<div style="font-size:11px;font-weight:700;color:#898F91;text-transform:uppercase;'
        'letter-spacing:.08em;margin:4px 0 6px;">목차</div>',
        unsafe_allow_html=True
    )
    for i, label in enumerate(STEP_LABELS, start=1):
        is_active = st.session_state.get('current_step', 1) == i
        if st.sidebar.button(label, key=f"navbtn_{i}", use_container_width=True,
                              type="primary" if is_active else "secondary"):
            st.session_state['current_step'] = i
            st.rerun()
    st.sidebar.markdown("---")


def _render_temp_save_load():
    """임시저장: 현재 세션 상태를 JSON으로 다운로드 (버튼/내부 위젯 key 제외) / 불러오기"""
    st.sidebar.subheader("임시저장")

    save_state = {}
    for k, v in st.session_state.items():
        if isinstance(v, (_SKIP_TYPES, bool)):  # 불리언은 버튼 상태 — 저장 불필요
            continue
        if any(k.startswith(p) for p in _SKIP_PREFIXES):
            continue
        try:
            json.dumps(v)
            save_state[k] = v
        except (TypeError, ValueError):
            pass

    company_label = st.session_state.get('input_co_name') or st.session_state.get('company_name') or '진단기업'
    st.sidebar.download_button(
        "임시저장 다운로드",
        data=json.dumps(save_state, ensure_ascii=False, indent=2).encode('utf-8'),
        file_name=f"{company_label}_임시저장_{datetime.datetime.now().strftime('%Y%m%d_%H%M')}.json",
        mime="application/json",
        use_container_width=True,
        key="sidebar_save_btn"
    )

    load_file = st.sidebar.file_uploader(
        "📂 불러오기 (.json)", type=["json"], key="sidebar_load_file", label_visibility="collapsed"
    )
    if load_file is not None and not st.session_state.get('_load_done_' + load_file.name):
        loaded = json.loads(load_file.read().decode('utf-8'))
        for k, v in loaded.items():
            if isinstance(v, bool):
                continue
            if any(k.startswith(p) for p in _SKIP_PREFIXES):
                continue
            try:
                st.session_state[k] = v
            except Exception:
                pass
        st.session_state['_load_done_' + load_file.name] = True
        st.sidebar.success("불러오기 완료!")
        st.rerun()


def _render_api_key_check():
    """배포 환경(Streamlit Cloud Secrets)에 Gemini API 키가 제대로 들어갔는지 바로 확인하는 도구.
    파일 업로드까지 가지 않아도 키 등록 여부/실제 호출 가능 여부를 바로 알 수 있게 한다."""
    from sections.ai_client import configured_value, gemini_model

    with st.sidebar.expander("⚙️ API 키 확인"):
        api_key = configured_value("Gemini", "api_key")
        if not api_key:
            st.error("GEMINI_API_KEY가 설정되지 않았습니다.")
            return

        st.caption(f"키 등록됨 (...{api_key[-4:]})")
        if st.button("연결 테스트", key="btn_api_key_test", use_container_width=True):
            model = gemini_model()
            with st.spinner("Gemini API 호출 테스트 중..."):
                try:
                    from google import genai
                    client = genai.Client(api_key=api_key)
                    client.models.generate_content(model=model, contents="ping")
                    st.success(f"연결 성공! (모델: {model})")
                except Exception as error:
                    st.error(f"연결 실패: {error}")


def render_sidebar_chrome():
    """사이드바 상단 공통 영역: 제목 + 목차 + 다시 실행 + 임시저장/불러오기 + API 키 확인"""
    st.sidebar.title("메뉴")
    st.sidebar.markdown("---")

    _keep_sidebar_open()
    _render_step_nav()

    if st.sidebar.button("다시 실행", use_container_width=True):
        st.rerun()

    st.sidebar.markdown("---")
    _render_temp_save_load()

    st.sidebar.markdown("---")
    _render_api_key_check()
