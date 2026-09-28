"""
Section 4 (고객용): 최종보고서 생성

내부 제작용과 달리 사람이 지표를 고르거나 종합의견을 다듬는 과정이 없다 — 자료 업로드
직후 sections.auto_pipeline이 이미 지표 계산·그래프 생성·AI 종합의견 작성까지 끝내
session_state에 채워뒀으므로, 여기서는 그 결과를 고객용 템플릿에 그대로 채워 넣기만 한다.
보고서가 만들어지면 (SMTP 설정이 돼 있을 때) 내부 담당자에게 메일로도 전송할 수 있다.
"""
import io
import time
import datetime
from pathlib import Path

import streamlit as st
from docxtpl import DocxTemplate, InlineImage
from docx.shared import Mm

from sections import email_notify

_CUSTOMER_TEMPLATE = Path(__file__).parent.parent / "assets" / "templates" / "[그로스파이낸스]_고객용_템플릿.docx"


def render_report_generation(**_):
    """최종보고서 생성 렌더링 (콘텐츠 영역 — 실제 생성/다운로드는 사이드바에서)"""
    st.markdown("---")
    st.markdown("### 4. 최종보고서 생성")
    st.info("사이드바의 '보고서 생성' 버튼을 클릭하여 보고서를 생성하세요.")
    st.caption(
        "※ 본 보고서는 AI가 자동으로 생성한 결과로, 실제와 다르거나 정확하지 않을 수 있습니다. "
        "정확한 재무 분석이 필요하시면 그로스파이낸스에 문의해 주세요."
    )

    pipeline_error = st.session_state.get('auto_pipeline_error')
    if pipeline_error:
        st.warning(f"자동분석 중 일부 항목에 문제가 있었습니다: {pipeline_error}")


def _build_report_bytes(company_info, template_path, check_results, score,
                         selected_dirs, dir_etc, selected_mats, exec_summary):
    doc = DocxTemplate(template_path)

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
        'score': score,
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

    # 재무지표 그래프 5종(수익성/안정성/활동성/성장성/자본수익성) — auto_pipeline이 미리
    # 만들어둔 PNG 바이트를 문서에 끼워 넣는다. 특정 그래프 생성에 실패했으면(kaleido 오류 등)
    # 그 자리만 빈 문자열로 둬 문서 생성 자체는 막지 않는다.
    chart_images = st.session_state.get('auto_chart_images') or {}
    for var, png_bytes in chart_images.items():
        context[var] = InlineImage(doc, io.BytesIO(png_bytes), width=Mm(150)) if png_bytes else ""

    doc.render(context)
    output = io.BytesIO()
    doc.save(output)
    return output.getvalue()


def render_report_sidebar(company_info, template_file, check_results, score,
                           selected_dirs, dir_etc, selected_mats, exec_summary):
    """사이드바의 '보고서 생성' 버튼 — 실제 docx 렌더링, 다운로드, (설정 시) 내부 메일 전송."""
    st.sidebar.markdown("---")
    st.sidebar.subheader("최종보고서")

    template_path = str(_CUSTOMER_TEMPLATE) if _CUSTOMER_TEMPLATE.exists() else template_file
    if not template_path:
        st.sidebar.error("보고서 템플릿 파일을 찾을 수 없습니다.")
        return

    if st.sidebar.button("보고서 생성", use_container_width=True):
        progress_text = "데이터를 분석하여 보고서를 생성 중입니다. 잠시만 기다려주세요..."
        my_bar = st.sidebar.progress(0, text=progress_text)

        for percent_complete in range(100):
            time.sleep(0.015)
            my_bar.progress(percent_complete + 1, text=progress_text)

        my_bar.empty()

        report_bytes = _build_report_bytes(
            company_info, template_path, check_results, score,
            selected_dirs, dir_etc, selected_mats, exec_summary,
        )

        file_name_prefix = company_info.get('company_name', '') or "진단기업"
        st.session_state['report_bytes'] = report_bytes
        created_date = datetime.datetime.now().strftime('%Y%m%d')
        st.session_state['report_filename'] = f"{file_name_prefix}_재무진단보고서_{created_date}.docx"
        st.session_state['report_company'] = file_name_prefix
        st.session_state.pop('report_email_sent', None)
        st.sidebar.success("보고서 생성 완료!")

    auto_es_warnings = st.session_state.get('auto_es_warnings')
    if auto_es_warnings:
        st.sidebar.warning(
            "자동 생성된 종합의견에 표기 규칙 위반이 있어 확인이 필요합니다:\n"
            + "\n".join(f"- {w}" for w in auto_es_warnings)
        )

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

        if email_notify.is_configured():
            if st.sidebar.button("이사님께 결과 전송", use_container_width=True, key="btn_send_report_email"):
                try:
                    email_notify.send_report_notification(
                        company_name=company_info.get('company_name', ''),
                        contact=company_info.get('phone', ''),
                        report_bytes=st.session_state['report_bytes'],
                        report_filename=st.session_state['report_filename'],
                    )
                    st.session_state['report_email_sent'] = True
                    st.sidebar.success(f"{', '.join(email_notify.RECIPIENTS)}에 메일을 보냈습니다.")
                except Exception as error:
                    st.sidebar.error(f"메일 전송에 실패했습니다: {error}")
            elif st.session_state.get('report_email_sent'):
                st.sidebar.caption("✓ 이미 전송했습니다.")
        else:
            st.sidebar.caption("※ 메일 발송 계정이 아직 설정되지 않아 '결과 전송' 버튼은 숨겨져 있습니다.")
