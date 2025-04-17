import streamlit as st
import pandas as pd
import re
from datetime import datetime, timedelta
import chardet
import requests
from bs4 import BeautifulSoup
import time
from io import BytesIO

st.set_page_config(page_title="📚 AI 기반 교과서 관련 동향 분석기", layout="wide")
st.title("📚 카카오톡 분석 & 뉴스 수집 통합 앱")

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
    return "O" if any(w in text for w in complaint_keywords) else "X"

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
            h, mi = int(h), int(mi)
            h += 12 if ampm == "오후" and h != 12 else 0
            h = 0 if ampm == "오전" and h == 12 else h
            dt = datetime(int(y), int(m), int(d), h, mi)
            if sender.strip() != "오픈채팅봇":
                parsed.append({"날짜": dt.date(), "시간": dt.time(), "보낸 사람": sender.strip(), "메시지": msg.strip()})
        elif m2 := pattern2.match(line):
            sender, ampm, h, mi, msg = m2.groups()
            h, mi = int(h), int(mi)
            h += 12 if ampm == "오후" and h != 12 else 0
            h = 0 if ampm == "오전" and h == 12 else h
            if current_date and sender.strip() != "오픈채팅봇":
                parsed.append({"날짜": current_date, "시간": datetime.strptime(f"{h}:{mi}", "%H:%M").time(), "보낸 사람": sender.strip(), "메시지": msg.strip()})
        elif d := date_pattern.match(line):
            y, m, d = map(int, d.groups())
            current_date = datetime(y, m, d).date()
    return pd.DataFrame(parsed)

# -------------------------------
# 뉴스 수집 함수
# -------------------------------
news_keywords = ["천재교육", "천재교과서", "지학사", "벽호", "프린피아", "미래엔", "교과서", "동아출판"]
category_keywords = {
    "후원": ["후원", "기탁"], "기부": ["기부"], "협약/MOU": ["협약", "mou"],
    "에듀테크/디지털교육": ["에듀테크", "디지털교육", "ai교육", "스마트교육"],
    "정책": ["정책"], "출판": ["출판"], "인사/채용": ["채용", "교사"],
    "프린트 및 인쇄": ["인쇄", "프린트"], "공급": ["공급"], "교육": ["교육"], "이벤트": ["이벤트", "사은품"]
}

def get_news_date(url):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, "html.parser")
        meta = soup.find("meta", {"property": "article:published_time"})
        return meta["content"][:10].replace("-", ".") if meta else "날짜 없음"
    except:
        return "날짜 오류"

def check_publisher(text):
    for pub in news_keywords:
        if pub.replace(" ", "") in text.replace(" ", ""):
            return pub
    return "기타"

def categorize_news(text):
    text = text.lower()
    for cat, words in category_keywords.items():
        if any(w in text for w in words):
            return cat
    return "기타"

def contains_textbook(text):
    return "O" if "교과서" in text or "발행사" in text else "X"

def crawl_news_quick(keyword, pages=3):
    headers = {"User-Agent": "Mozilla/5.0"}
    results, seen = [], set()
    for page in range(1, pages + 1):
        start = (page - 1) * 10 + 1
        url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sort=1&nso=so:dd,p:2w&start={start}"
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "html.parser")
        articles = soup.select("#main_pack .list_news .news_area")
        for a in articles:
            try:
                title_tag = a.select_one("a.news_tit")
                title, link = title_tag.get("title"), title_tag.get("href")
                if link in seen:
                    continue
                seen.add(link)
                summary_tag = a.select_one(".dsc_txt_wrap")
                summary = summary_tag.get_text(strip=True) if summary_tag else ""
                press_tag = a.select_one(".info_group a")
                press = press_tag.get_text(strip=True) if press_tag else "언론사 없음"
                full_text = (title + " " + summary).lower()
                results.append({
                    "출판사명": check_publisher(full_text),
                    "카테고리": categorize_news(full_text),
                    "날짜": get_news_date(link),
                    "제목": title,
                    "URL": link,
                    "요약": summary,
                    "언론사": press,
                    "본문내_교과서_또는_발행사_언급": contains_textbook(full_text)
                })
            except:
                continue
        time.sleep(0.3)
    return pd.DataFrame(results)

# -------------------------------
# UI 구성
# -------------------------------
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
            df_kakao["카테고리"] = df_kakao["메시지"].apply(classify_category)
            df_kakao["출판사"] = df_kakao["메시지"].apply(extract_kakao_publisher)
            df_kakao["과목"] = df_kakao["메시지"].apply(extract_subject)
            df_kakao["불만 여부"] = df_kakao["메시지"].apply(detect_complaint)
            st.success(f"✅ 총 {len(df_kakao)}개 메시지 분석 완료!")
            st.dataframe(df_kakao)
            csv = df_kakao.to_csv(index=False).encode("utf-8")
            st.download_button("📥 카카오톡 CSV 저장", csv, "kakao_cleaned.csv", "text/csv")

with tab2:
    st.subheader("출판사 관련 뉴스 크롤링 (최근 2주)")
    selected_keywords = st.multiselect("🔎 기본 키워드 선택", news_keywords, default=news_keywords)
    if selected_keywords and st.button("뉴스 수집 시작"):
        progress = st.progress(0)
        all_news = []
        for i, kw in enumerate(selected_keywords):
            df = crawl_news_quick(kw)
            all_news.append(df)
            progress.progress((i+1)/len(selected_keywords))
        df_news = pd.concat(all_news, ignore_index=True)
        st.success("✅ 뉴스 수집 완료!")
        st.dataframe(df_news)
        buffer = BytesIO()
        with pd.ExcelWriter(buffer, engine='xlsxwriter') as writer:
            df_news.to_excel(writer, index=False, sheet_name="뉴스결과")
        st.download_button("📥 뉴스 엑셀 저장", buffer.getvalue(), "news_result.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
