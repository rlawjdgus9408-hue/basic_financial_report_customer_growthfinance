"""
고객사 전용: 최종보고서 생성이 끝나면 내부(cjw, 알파 재무팀)에 알림 메일을 보낸다.
회사 자체 메일 서버(하이웍스, SMTP)를 통해 발송하며, 계정 정보는
.streamlit/secrets.toml에서만 읽는다(코드/저장소에는 절대 남기지 않음).

secrets.toml에 필요한 값 (아직 안 정해졌으면 비워둬도 앱은 정상 동작하고,
메일 발송 버튼만 "설정 필요" 상태로 비활성화된다):

    SMTP_HOST = "smtps.hiworks.com"
    SMTP_PORT = 465
    SMTP_USER = "발신계정@도메인"
    SMTP_PASSWORD = "비밀번호(또는 앱 비밀번호)"
    SMTP_FROM = "발신계정@도메인"   # 생략하면 SMTP_USER와 동일하게 처리
"""
import smtplib
from email.message import EmailMessage

import streamlit as st

RECIPIENTS = ["cjw@alphabrothers.co.kr", "finance2@alphabrothers.co.kr"]

_DEFAULT_HOST = "smtps.hiworks.com"
_DEFAULT_PORT = 465


def _smtp_config():
    try:
        secrets = st.secrets
    except Exception:
        secrets = {}
    host = secrets.get("SMTP_HOST", _DEFAULT_HOST)
    port = int(secrets.get("SMTP_PORT", _DEFAULT_PORT) or _DEFAULT_PORT)
    user = (secrets.get("SMTP_USER", "") or "").strip()
    password = secrets.get("SMTP_PASSWORD", "") or ""
    sender = (secrets.get("SMTP_FROM", "") or user).strip()
    return host, port, user, password, sender


def is_configured():
    """SMTP 계정이 secrets.toml에 설정돼 있는지 — 버튼을 보여줄지 말지 판단용."""
    _, _, user, password, _ = _smtp_config()
    return bool(user and password)


def send_report_notification(company_name, contact, report_bytes, report_filename):
    """보고서 생성 완료 알림 메일을 cjw/알파 재무팀 앞으로 보낸다.
    본문에 문의 회사명·연락처를 넣고, 생성된 .docx 보고서를 첨부한다."""
    host, port, user, password, sender = _smtp_config()
    if not (user and password):
        raise RuntimeError("SMTP 계정이 설정되지 않았습니다 (.streamlit/secrets.toml 확인 필요).")

    msg = EmailMessage()
    msg["From"] = sender
    msg["To"] = ", ".join(RECIPIENTS)
    msg["Subject"] = f"[기초재무진단] {company_name or '(회사명 미입력)'} 보고서 생성 알림"
    msg.set_content(
        "고객사 자동분석 보고서가 생성되었습니다.\n\n"
        f"문의 회사명: {company_name or '(미입력)'}\n"
        f"연락처: {contact or '(미입력)'}\n\n"
        "첨부된 보고서 파일을 확인해 주세요.\n"
        "(본 메일은 기초재무진단 자동화 시스템이 자동으로 발송했습니다.)"
    )
    msg.add_attachment(
        report_bytes,
        maintype="application",
        subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename=report_filename,
    )

    with smtplib.SMTP_SSL(host, port, timeout=20) as server:
        server.login(user, password)
        server.send_message(msg)
