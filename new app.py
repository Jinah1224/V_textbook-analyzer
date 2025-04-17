import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import chardet
import requests
from bs4 import BeautifulSoup
import time
import io

st.set_page_config(page_title="📚 AI 기반 교과서 관련 동향 분석기", layout="wide")
st.markdown("""
    <style>
    .stMultiSelect > div > div {
        border-radius: 1rem;
        background-color: #f0f2f6;
        padding: 0.4rem 0.6rem;
    }
    .stMultiSelect div[data-baseweb="tag"] {
        background-color: #eef0f4;
        color: #333;
        border-radius: 8px;
        font-weight: 500;
    }
    .stMultiSelect div[data-baseweb="tag"] span {
        font-size: 14px;
    }
    </style>
""", unsafe_allow_html=True)

st.title("📚 카카오톡 분석 + 뉴스 수집 통합 앱")

# -------------------------------
# 카카오톡 분석 기준 및 함수
# -------------------------------
kakao_categories = {
    "채택: 선정 기준/평가": ["평가표", "기준", "추천의견서", "선정기준"],
    "채택: 위원회 운영": ["위원회", "협의회", "대표교사", "위원"],
    "채택: 회의/심의 진행": ["회의", "회의록", "심의", "심사", "운영"],
    "배송": ["배송"],
    "배송: 지도서/전시본 도착": ["도착", "왔어요", "전시본", "지도서", "박스"],
    "배송: 라벨/정리 업무": ["라벨", "분류", "정리", "전시 준비"],
    "주문: 시스템 사용": ["나이스", "에듀파인", "등록", "입력"],
    "주문: 공문/정산": ["공문", "정산", "마감일", "요청"],
    "출판사: 자료 수령/이벤트": ["보조자료", "자료", "기프티콘", "이벤트"],
    "출판사: 자료 회수/요청": ["회수", "요청", "교사용"]
}
publishers = ["미래엔", "비상", "동아", "아이스크림", "천재", "좋은책", "지학사", "대교", "이룸", "명진", "천재교육"]
subjects = ["국어", "수학", "사회", "과학", "영어", "도덕", "음악", "미술", "체육"]
complaint_keywords = ["안 왔어요", "아직", "늦게", "없어요", "오류", "문제", "왜", "헷갈려", "불편", "안옴", "지연", "안보여요", "못 받았", "힘들어요"]

def classify_category(text):
    for cat, words in kakao_categories.items():
        if any(w in text for w in words):
            return cat
    return "기타"

def extract_kakao_publisher(text):
    for pub in publishers:
        if pub in text:
            return pub
    return None

def extract_subject(text):
    for sub in subjects:
        if sub in text:
            return sub
    return None

def detect_complaint(text):
    return any(w in text for w in complaint_keywords)

def parse_kakao_text(text):
    parsed = []
    pattern1 = re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일 (오전|오후)? (\d{1,2}):(\d{2}), (.+?) : (.+)")
    pattern2 = re.compile(r"\[(.*?)\] \[(오전|오후) (\d{1,2}):(\d{2})\] (.+)")
    date_pattern = re.compile(r"-+ (\d{4})년 (\d{1,2})월 (\d{1,2})일")
    lines = text.splitlines()
    current_date = None
    for line in lines:
        if m1 := pattern1.match(line):
            y, m, d, ampm, h, mi, sender, msg = m1.groups()
            h = int(h)
            mi = int(mi)
            if ampm == "오후" and h != 12:
                h += 12
            elif ampm == "오전" and h == 12:
                h = 0
            dt = datetime(int(y), int(m), int(d), h, mi)
            if sender.strip() != "오픈채팅봇":
                parsed.append({
                    "날짜": dt.date(), "시간": dt.time(),
                    "보낸 사람": sender.strip(), "메시지": msg.strip(),
                    "카테고리": classify_category(msg),
                    "출판사": extract_kakao_publisher(msg),
                    "과목": extract_subject(msg),
                    "불만 여부": detect_complaint(msg)
                })
        elif m2 := pattern2.match(line):
            sender, ampm, h, mi, msg = m2.groups()
            if current_date and sender.strip() != "오픈채팅봇":
                h = int(h)
                mi = int(mi)
                if ampm == "오후" and h != 12:
                    h += 12
                elif ampm == "오전" and h == 12:
                    h = 0
                t = datetime.strptime(f"{h}:{mi}", "%H:%M").time()
                parsed.append({
                    "날짜": current_date, "시간": t,
                    "보낸 사람": sender.strip(), "메시지": msg.strip(),
                    "카테고리": classify_category(msg),
                    "출판사": extract_kakao_publisher(msg),
                    "과목": extract_subject(msg),
                    "불만 여부": detect_complaint(msg)
                })
        elif d := date_pattern.match(line):
            y, m, d = map(int, d.groups())
            current_date = datetime(y, m, d).date()
    return pd.DataFrame(parsed)

# 뉴스 관련 함수 등은 그대로 유지
# Streamlit 탭

tab1, tab2 = st.tabs(["💬 카카오톡 분석", "📰 뉴스 수집"])

with tab1:
    st.subheader("카카오톡 .txt 업로드")
    uploaded = st.file_uploader("카카오톡 대화 텍스트 파일 업로드", type="txt")
    if uploaded:
        raw_bytes = uploaded.read()
        encoding = chardet.detect(raw_bytes)["encoding"] or "utf-8"
        text = raw_bytes.decode(encoding, errors="ignore")
        df_kakao = parse_kakao_text(text)
        if df_kakao.empty:
            st.warning("❗ 메시지를 추출할 수 없습니다.")
        else:
            st.success(f"✅ 총 {len(df_kakao)}개 메시지 분석 완료!")
            st.dataframe(df_kakao)
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
                df_kakao.to_excel(writer, index=False)
            st.download_button(
                label="📥 카카오톡 엑셀 저장",
                data=buffer.getvalue(),
                file_name="kakao_cleaned.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

with tab2:
    st.subheader("출판사 관련 뉴스 크롤링(최근 2주)")
    selected_keywords = st.multiselect("🔎 기본 키워드 선택", keywords, default=keywords)
    if selected_keywords:
        if st.button("뉴스 수집 시작"):
            progress = st.progress(0)
            all_news = []
            for i, kw in enumerate(selected_keywords):
                df = crawl_news_quick(kw)
                all_news.append(df)
                progress.progress((i+1)/len(selected_keywords))
            df_news = pd.concat(all_news, ignore_index=True)
            st.success("✅ 뉴스 수집 완료!")
            st.dataframe(df_news)
            news_buffer = io.BytesIO()
            with pd.ExcelWriter(news_buffer, engine="xlsxwriter") as writer:
                df_news.to_excel(writer, index=False)
            st.download_button(
                label="📥 뉴스 엑셀 저장",
                data=news_buffer.getvalue(),
                file_name="news_result.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
