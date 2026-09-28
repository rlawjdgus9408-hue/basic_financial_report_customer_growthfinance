"""
Section 5: 종합의견
"""
import json
import re
from pathlib import Path

import streamlit as st
import pandas as pd

from sections.ai_client import configured_value, gemini_model, es_guideline_text, ai_comment_extra_rules

_USER_ICON = Path(__file__).parent.parent / "assets" / "icons" / "assistant_icon.webp"
_GEMINI_ICON = Path(__file__).parent.parent / "assets" / "icons" / "gemini_icon.svg"


def _financial_context():
    context = {
        "기업명": st.session_state.get("input_co_name", ""),
        "업종": st.session_state.get("input_biz_minor", "") or st.session_state.get("input_biz_direct", ""),
        "선택 지표": st.session_state.get("selected_indicators", {}),
        "재무상태표 지표": st.session_state.get("bs_metrics", {}),
        "손익계산서 지표": st.session_state.get("is_metrics", {}),
        "공통 지표": st.session_state.get("common_metrics", {}),
    }
    return json.dumps(context, ensure_ascii=False, default=str)


def _has_financial_data():
    return any(
        st.session_state.get(key)
        for key in ("bs_metrics", "is_metrics", "common_metrics")
    )


def _plain_text_ai_answer(answer):
    """AI Markdown 답변을 종합의견용 일반 텍스트로 정리한다."""
    answer = re.sub(r"\*\*(.*?)\*\*", r"\1", answer, flags=re.DOTALL)
    answer = answer.replace("**", "").replace("__", "").replace("`", "")
    answer = re.sub(r"(?m)^\s*#{1,6}\s*", "", answer)
    return answer.strip()


def _quick_style_check(text):
    """종합의견에 반영하기 전, docs/es_guideline.md 규칙 중 scripts/check_es.py가 프로그램적으로
    검사하는 항목(금지 표현/영어 약어/백만원 단위/화살표 개수)만 빠르게 재사용해 걸러본다.

    Claude Code로 ES를 쓸 때는 그 스크립트를 전체(글자수·단락 구성 포함) 돌리도록 스킬이 강제하지만,
    이 앱의 AI 채팅은 Gemini가 바로 답을 생성해 반영하는 구조라 그 검증을 거치지 않는다 — 여기서
    최소한의 표기 규칙 위반만이라도 앱 안에서 바로 잡아준다. 통과 못해도 반영 자체는 막지 않고
    참고용 경고만 보여준다(최종 판단은 사람 몫)."""
    try:
        from scripts import check_es as _es
    except ImportError:
        return []

    report = _es.Report()
    _es.check_banned_phrases(text, report)
    _es.check_abbreviations(text, report)
    _es.check_million_won(text, report)
    _es.check_arrows(text, report)
    return report.errors


def _system_instruction():
    """이 채팅은 곧 기초재무진단보고서의 종합의견(Executive Summary)을 작성/수정하는 용도이므로,
    docs/es_guideline.md의 ES 작성 규칙을 항상 시스템 지시로 강제한다."""
    parts = [
        "당신은 그로스파이낸스의 중소기업 재무분석 전문가이자 보고서 에디터입니다.",
        "이 대화의 결과물은 기초재무진단보고서 1페이지 '종합의견(Executive Summary)'에 그대로 쓰일 수 있으므로, "
        "아래 [ES 작성 규칙]을 반드시 지켜서 답변하세요. 질문이 특정 수치나 해석만 묻는 경우에도 "
        "종합의견에 바로 반영 가능한 톤·표기 규칙(금지 표현, 단위 표기, 화살표 개수, 인과 단정 금지 등)은 항상 따르세요.",
        "확인되지 않은 사실은 추정하지 말고 '확인 불가'라고 답하거나 어떤 데이터가 더 필요한지 되물으세요.",
        "",
        "[ES 작성 규칙]",
        es_guideline_text() or "(규칙 파일을 불러오지 못했습니다. 일반적인 재무분석 전문가 기준으로 신중하게 답변하세요.)",
    ]
    extra = ai_comment_extra_rules()
    if extra:
        parts += ["", "[추가 규칙]", extra]
    return "\n".join(parts)


def _generate_ai_response(provider, model, api_key, question):
    prompt = f"""아래 기업 데이터를 근거로 질문에 한국어로 답변하세요.
수치가 없는 내용은 추정하지 말고, 답변은 실무자가 바로 활용할 수 있게 작성하세요.

[기업 데이터]
{_financial_context()}

[질문]
{question}
"""

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(system_instruction=_system_instruction()),
    )
    return response.text or "응답을 받지 못했습니다."


def render_ai_comment_chat():
    with st.expander("AI 재무 분석 코멘트", expanded=False):
        with st.container(height=620, border=True):
            if not _has_financial_data():
                st.info("재무 엑셀을 업로드하면 재무지표를 바탕으로 더 정확한 분석을 받을 수 있습니다.")

            model = gemini_model()
            configured_key = configured_value("Gemini", "api_key")
            if configured_key:
                api_key = configured_key
                st.caption("Gemini API 키가 로컬 보안 설정에서 로드되었습니다.")
            else:
                api_key = st.text_input(
                    "Gemini API 키 (환경변수 또는 Streamlit secrets 설정 시 생략 가능)",
                    type="password",
                    key="ai_key_gemini",
                ).strip()

            messages = st.session_state.setdefault("ai_messages", [])
            for message in messages:
                avatar = str(_GEMINI_ICON) if message["role"] == "assistant" else str(_USER_ICON)
                with st.chat_message(message["role"], avatar=avatar):
                    st.markdown(message["content"])
                    if message["role"] == "assistant":
                        st.markdown(
                            f'<div class="ai-model-label">{model}</div>',
                            unsafe_allow_html=True,
                        )

            with st.form("ai_question_form", clear_on_submit=True):
                question = st.text_input("질문", placeholder="재무 상태에 대해 질문하세요")
                submitted = st.form_submit_button("질문하기", type="primary")

            if submitted and question.strip():
                question = question.strip()
                messages.append({"role": "user", "content": question})
                if not api_key:
                    answer = "Gemini API 키를 입력하거나 환경변수/Streamlit secrets에 설정해주세요."
                else:
                    try:
                        with st.spinner("재무 데이터를 분석하고 있습니다..."):
                            answer = _generate_ai_response("Gemini", model, api_key, question)
                    except Exception as error:
                        answer = f"AI 응답을 생성하지 못했습니다: {error}"
                messages.append({"role": "assistant", "content": answer})
                st.rerun()

            if messages:
                if st.button("마지막 AI 답변을 종합의견에 반영", key="apply_ai_comment"):
                    last_answer = next(
                        (message["content"] for message in reversed(messages) if message["role"] == "assistant"),
                        "",
                    )
                    if last_answer:
                        cleaned = _plain_text_ai_answer(last_answer)
                        st.session_state["txt_exec"] = cleaned
                        st.session_state["ai_comment_style_warnings"] = _quick_style_check(cleaned)
                        st.rerun()


def build_indicator_table(all_selected, years, bs_metrics, is_metrics, common_metrics):
    """선택된 지표명 목록 -> (표 형태 레코드 리스트, 템플릿용 탭 구분 텍스트).

    render_comments()(인터랙티브 화면)와 auto_pipeline.py(고객용 자동분석)가 공유해,
    '선택된 지표를 표로 만드는 규칙'이 두 군데로 갈라지지 않게 한다."""
    table_data = []
    for ind in all_selected:
        row = {'지표명': ind}
        for yr in years:
            val = next(
                (m[yr][ind] for m in (bs_metrics, is_metrics, common_metrics)
                 if m.get(yr) and ind in m[yr]),
                None
            )
            row[yr] = f"{val:,.2f}" if val is not None else "-"
        table_data.append(row)

    lines = ["■ 주요 재무지표", "지표명\t" + "\t".join(years)]
    for row in table_data:
        lines.append(row['지표명'] + "".join(f"\t{row.get(yr,'-')}" for yr in years))
    table_text = "\n".join(lines)

    return table_data, table_text


def render_comments():
    """종합의견 렌더링"""
    st.markdown("### 5. 종합의견")

    # 선택된 지표 기반 표 표시
    selected_indicators = st.session_state.get('selected_indicators', {})
    if selected_indicators and any(selected_indicators.get(k) for k in ('bs', 'is', 'common')):
        st.markdown("#### 문서 포함 선택된 재무지표")

        years       = st.session_state.get('years', [])
        bs_metrics  = st.session_state.get('bs_metrics', {})
        is_metrics  = st.session_state.get('is_metrics', {})
        common_metrics = st.session_state.get('common_metrics', {})

        all_selected = (selected_indicators.get('bs', [])
                        + selected_indicators.get('is', [])
                        + selected_indicators.get('common', []))

        if all_selected and years:
            table_data, table_text = build_indicator_table(
                all_selected, years, bs_metrics, is_metrics, common_metrics
            )

            df_selected = pd.DataFrame(table_data)
            st.dataframe(df_selected.set_index('지표명'), use_container_width=True)
            st.caption("※ 문서 포함을 선택한 지표입니다.")

            st.session_state.selected_indicators_table = table_text


    render_ai_comment_chat()

    # AI 답변을 방금 반영했다면, ES 작성 규칙(§4) 위반 여부를 한 번 알려준다 (1회성 — 표시 후 바로 지움).
    style_warnings = st.session_state.pop("ai_comment_style_warnings", None)
    if style_warnings:
        st.warning(
            "방금 반영한 내용에 ES 작성 규칙 위반이 있습니다 — 직접 확인해 고쳐주세요:\n"
            + "\n".join(f"- {w}" for w in style_warnings)
        )

    # 글머리 자동 추가: 위젯 렌더링 전에 session_state 값을 미리 처리
    _current = st.session_state.get('txt_exec', st.session_state.get('exec_summary', ''))
    if _current:
        lines = []
        for line in _current.split('\n'):
            stripped = line.strip()
            lines.append(('▪ ' + stripped) if stripped and not stripped.startswith('▪') else line)
        _bulleted = '\n'.join(lines)
        if _bulleted != _current:
            st.session_state['txt_exec'] = _bulleted

    exec_summary = st.text_area(
        "종합의견 (Executive Summary)",
        value=st.session_state.get('exec_summary', ''),
        height=200,
        key="txt_exec",
        help="입력 후 커서를 벗어나면 각 문단 앞에 ▪ 글머리가 자동으로 추가됩니다."
    )

    char_count = len(exec_summary) if exec_summary else 0
    st.caption(f"글자수: {char_count}/2000자  |  커서 이동 시 ▪ 글머리 자동 추가")
    if char_count > 2000:
        st.warning("A4 1장 기준(2000자)을 초과했습니다.")

    return exec_summary
