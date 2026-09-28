"""
Section 3 (고객용): 재무제표 파일을 업로드하면 검토 화면 없이 바로 AI로 표준 데이터로
변환한다.

내부 제작용의 '다른 형식 파일 변환' 화면(sections/convert.py)과 같은 AI 추출 엔진을
그대로 재사용하지만, "RAW 엑셀"이라는 내부 개념이나 검토·수정 표, RAW 다운로드 버튼을
고객에게 노출하지 않는다 — 업로드하면 바로 다음 단계(보고서 생성)로 넘어간다. 여러 연도가
서로 다른 파일로 나뉘어 있어도(예: 2023년, 2024년 파일이 별도) 한 번에 여러 개를 올릴 수
있는 것도 동일하다.
"""
import streamlit as st

from sections.convert import (
    _extract_financial_data,
    _slice_entries_for_year,
    _validate_year_aligned,
    _build_combined_rows,
    _combined_to_dataframe,
    _file_key,
    _is_transient_error,
)
from sections.ai_client import configured_value, gemini_model


def render_customer_upload():
    """업로드 -> AI 분석까지 자동으로 수행하고 (df_bs, df_is, years)를 반환한다.
    아직 업로드가 없거나 분석에 실패하면 (None, None, [])를 반환한다."""
    st.markdown("### 3. 재무제표 업로드")
    st.caption(
        "재무상태표·손익계산서가 포함된 파일을 업로드해 주세요 (엑셀/PDF/이미지, 여러 파일 "
        "선택 가능 — 연도별로 파일이 나뉘어 있어도 됩니다). 업로드하면 AI가 자동으로 분석해 "
        "다음 단계에서 바로 보고서를 만들어 드립니다."
    )

    source_files = st.file_uploader(
        "재무제표 파일 업로드",
        type=["xlsx", "xls", "pdf", "png", "jpg", "jpeg"],
        accept_multiple_files=True,
        key="customer_source_file",
    )
    if not source_files:
        st.session_state.pop("customer_upload_result_key", None)
        return None, None, []

    file_key = _file_key(source_files, None)
    if st.session_state.get("customer_upload_result_key") == file_key:
        st.success("분석 완료 — 다음 단계에서 보고서를 생성하세요.")
        return (
            st.session_state["customer_df_bs"],
            st.session_state["customer_df_is"],
            st.session_state["customer_years"],
        )

    api_key = configured_value("Gemini", "api_key")
    if not api_key:
        st.error("Gemini API 키가 설정되지 않았습니다. 관리자(그로스파이낸스)에게 문의해주세요.")
        return None, None, []

    status_area = st.empty()
    try:
        model = gemini_model()
        bs_by_year, is_by_year = {}, {}
        skipped_files = []
        dropped_accounts = []

        with st.spinner("파일을 분석하고 있습니다..."):
            for idx, f in enumerate(source_files):
                status_area.info(f"({idx + 1}/{len(source_files)}) '{f.name}' 분석 중...")
                data = _extract_financial_data(
                    f.getvalue(), f.name, api_key, model,
                    status=lambda msg: status_area.warning(msg),
                )
                yrs = data.get("years", [])
                if not yrs:
                    skipped_files.append(f.name)
                    continue

                bs_entries, bs_dropped = _validate_year_aligned(data.get("balance_sheet", []), yrs)
                is_entries, is_dropped = _validate_year_aligned(data.get("income_statement", []), yrs)
                if bs_dropped or is_dropped:
                    dropped_accounts += bs_dropped + is_dropped

                for yr in yrs:
                    bs_by_year[yr] = _slice_entries_for_year(bs_entries, yrs, yr)
                    is_by_year[yr] = _slice_entries_for_year(is_entries, yrs, yr)
        status_area.empty()

        if skipped_files:
            st.warning(f"연도 정보를 인식하지 못해 건너뛴 파일: {', '.join(skipped_files)}")

        sorted_years = sorted(bs_by_year.keys())
        if not sorted_years:
            st.error("업로드한 파일에서 연도 정보를 인식하지 못했습니다. 파일을 확인하고 다시 시도해주세요.")
            return None, None, []

        bs_combined = _build_combined_rows([], bs_by_year, sorted_years)
        is_combined = _build_combined_rows([], is_by_year, sorted_years)
        df_bs = _combined_to_dataframe(bs_combined, [], sorted_years)
        df_is = _combined_to_dataframe(is_combined, [], sorted_years)

        st.session_state["customer_df_bs"] = df_bs
        st.session_state["customer_df_is"] = df_is
        st.session_state["customer_years"] = sorted_years
        st.session_state["customer_upload_result_key"] = file_key
        st.success("파일 분석이 완료됐습니다 — 다음 단계에서 보고서를 생성하세요.")
        return df_bs, df_is, sorted_years
    except Exception as error:
        status_area.empty()
        if _is_transient_error(error):
            st.error(
                "AI 서버가 일시적으로 혼잡합니다(503 UNAVAILABLE). 잠시 후 다시 시도해주세요."
            )
        else:
            st.error(f"파일 분석 중 오류가 발생했습니다: {error}")
        return None, None, []
