"""
Section 6: 최종보고서 생성
"""
import io
import time
import datetime

import streamlit as st
from docxtpl import DocxTemplate


def render_report_generation(**_):
    """최종보고서 생성 렌더링 (콘텐츠 영역 — 실제 생성/다운로드는 사이드바에서)"""
    st.markdown("---")
    st.markdown("### 6. 최종보고서 생성")
    st.info("사이드바의 '보고서 생성' 버튼을 클릭하여 보고서를 생성하세요.")
    st.caption(
        "※ 본 보고서는 AI가 자동으로 생성한 결과로, 실제와 다르거나 정확하지 않을 수 있습니다. "
        "정확한 재무 분석이 필요하시면 그로스파이낸스에 문의해 주세요."
    )


def render_report_sidebar(company_info, template_file, check_results, score,
                           selected_dirs, dir_etc, selected_mats, exec_summary):
    """사이드바의 '보고서 생성' 버튼 — 실제 docx 렌더링과 다운로드 버튼."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("최종보고서")

    if not template_file:
        return

    if st.sidebar.button("보고서 생성", use_container_width=True):
        progress_text = "데이터를 분석하여 보고서를 생성 중입니다. 잠시만 기다려주세요..."
        my_bar = st.sidebar.progress(0, text=progress_text)

        for percent_complete in range(100):
            time.sleep(0.015)
            my_bar.progress(percent_complete + 1, text=progress_text)

        my_bar.empty()

        doc = DocxTemplate(template_file)

        context = {
            'today': datetime.datetime.now().strftime("%Y. %m."),
            'company_name': company_info.get('company_name', ''),
            'biz_type': company_info.get('biz_type', ''),
            'ceo_name': company_info.get('ceo_name', ''),
            'biz_start_date': company_info.get('biz_start_date', ''),
            'biz_no': company_info.get('biz_no', ''),
            'phone': company_info.get('phone', ''),
            'email': company_info.get('email', ''),
            'address': company_info.get('address', ''),
            'emp_count': company_info.get('emp_count', ''),
            'erp_system': ', '.join(company_info.get('erp_system', [])) if isinstance(company_info.get('erp_system'), list) else company_info.get('erp_system', ''),
            'special_note': company_info.get('special_note', ''),
            'exec_summary': exec_summary,
            'finance_comment': st.session_state.get('selected_indicators_table', ''),
            'score': score
        }

        for i, res in enumerate(check_results):
            num = i + 1
            is_yes = (res == "예")
            context[f'r{num}y'] = "■" if is_yes else "□"
            context[f'r{num}n'] = "■" if not is_yes else "□"
            context[f's{num}y'] = "■" if is_yes else "□"
            context[f's{num}n'] = "■" if not is_yes else "□"

        for i, opt in enumerate(["안정적 성장", "투자 유치 (사업확장)", "IPO/M&A 등 Exit"]):
            context[f'd{i+1}'] = "■" if opt in selected_dirs else "□"

        context['d_etc'] = "■" if dir_etc else "□"
        context['d_etc_val'] = dir_etc if dir_etc else "          "

        for i, opt in enumerate(["사업자등록증", "재무제표", "회사소개서", "기타 양식"]):
            context[f'm{i+1}'] = "■" if opt in selected_mats else "□"

        doc.render(context)
        output = io.BytesIO()
        doc.save(output)

        file_name_prefix = company_info.get('company_name', '') or "진단기업"
        st.session_state['report_bytes'] = output.getvalue()
        created_date = datetime.datetime.now().strftime('%Y%m%d')
        st.session_state['report_filename'] = f"{file_name_prefix}_재무진단보고서_{created_date}.docx"
        st.session_state['report_company'] = file_name_prefix
        st.sidebar.success("보고서 생성 완료!")

    if st.session_state.get('report_bytes'):
        file_name_prefix = st.session_state.get('report_company', '진단기업')
        st.sidebar.download_button(
            f"{file_name_prefix} 보고서 다운로드",
            data=st.session_state['report_bytes'],
            file_name=st.session_state['report_filename'],
            use_container_width=True
        )
        st.sidebar.caption(
            "※ AI 자동 생성 결과로 부정확할 수 있습니다. 정확한 분석은 그로스파이낸스에 문의해 주세요."
        )
