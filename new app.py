
import streamlit as st
import pandas as pd
import re
from datetime import datetime
import chardet
import requests
from bs4 import BeautifulSoup
import time
from datetime import timedelta

# -----------------------
# 공통 설정
# -----------------------
st.set_page_config(page_title="📚 교과서 커뮤니티 분석기", layout="wide")
st.title("📚 카카오톡 분석 + 뉴스 수집 통합 앱")

# -----------------------
# 뉴스 크롤링 관련 함수
# -----------------------
keywords = ["천재교육", "천재교과서", "지학사", "벽호", "프린피아", "미래엔", "교과서", "동아출판"]
category_keywords = {
    "후원": ["후원", "기탁"],
    "기부": ["기부"],
    "협약/MOU": ["협약", "mou"],
    "에듀테크/디지털교육": ["에듀테크", "디지털교육", "ai교육", "스마트교육"],
    "정책": ["정책"],
    "출판": ["출판"],
    "인사/채용": ["채용", "교사"],
    "프린트 및 인쇄": ["인쇄", "프린트"],
    "공급": ["공급"],
    "교육": ["교육"],
    "이벤트": ["이벤트", "사은품"]
}

def crawl_news_quick(keyword, pages=3):
    headers = {"User-Agent": "Mozilla/5.0"}
    results = []
    seen = set()
    today = datetime.today().date()
    two_weeks_ago = today - timedelta(days=14)
    for page in range(1, pages + 1):
        start = (page - 1) * 10 + 1
        url = f"https://search.naver.com/search.naver?where=news&query={keyword}&sort=1&nso=so:dd,p:2w&start={start}"
        res = requests.get(url, headers=headers)
        soup = BeautifulSoup(res.text, "lxml")
        articles = soup.select(".news_area")
        for a in articles:
            try:
                title = a.select_one(".news_tit").get("title")
                link = a.select_one(".news_tit").get("href")
                summary = a.select_one(".dsc_txt_wrap").get_text(strip=True)
                press = a.select_one(".info_group a").get_text(strip=True)
                if link in seen or summary in seen:
                    continue
                seen.add(link)
                seen.add(summary)
                date = "날짜 없음"
                full_text = (title + " " + summary).lower()
                results.append({
                    "출판사명": check_publisher(full_text),
                    "카테고리": categorize_news(full_text),
                    "날짜": date,
                    "제목": title,
                    "URL": link,
                    "요약": summary,
                    "언론사": press,
                    "내용점검": match_keyword_flag(full_text),
                    "본문내_교과서_또는_발행사_언급": contains_textbook(full_text)
                })
            except:
                continue
        time.sleep(0.3)
    return pd.DataFrame(results)

def categorize_news(text):
    text = text.lower()
    for cat, words in category_keywords.items():
        if any(w in text for w in words):
            return cat
    return "기타"

def check_publisher(text):
    for pub in keywords:
        if pub.lower() in text:
            return pub
    return "기타"

def match_keyword_flag(text):
    return "O" if any(pub.lower() in text for pub in keywords) else "X"

def contains_textbook(text):
    return "O" if "교과서" in text or "발행사" in text else "X"

# -----------------------
# 카카오톡 파서 (2가지 형식 모두 대응)
# -----------------------
def parse_kakao_text(text):
    parsed = []
    # 유형 1: 2024년 9월 2일 오후 4:13, 사용자 : 메시지
    pattern1 = re.compile(r"(\d{4})년 (\d{1,2})월 (\d{1,2})일 (오전|오후)? (\d{1,2}):(\d{2}), (.+?) : (.+)")
    # 유형 2: [사용자] [오전 4:13] 메시지 (이전 날짜줄 필요)
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
                "날짜": dt.date(), "시간": dt.time(), "보낸 사람": sender.strip(), "메시지": msg.strip()
            })
        elif m2 := pattern2.match(line):
            sender, ampm, h, mi, msg = m2.groups()
            if current_date:
                h = int(h)
                mi = int(mi)
                if ampm == "오후" and h != 12:
                    h += 12
                elif ampm == "오전" and h == 12:
                    h = 0
                t = datetime.strptime(f"{h}:{mi}", "%H:%M").time()
                if sender.strip() != "오픈채팅봇":
                parsed.append({
                    "날짜": current_date, "시간": t, "보낸 사람": sender.strip(), "메시지": msg.strip()
                })
        elif d := date_pattern.match(line):
            y, m, d = map(int, d.groups())
            current_date = datetime(y, m, d).date()
    return pd.DataFrame(parsed)

# -----------------------
# 탭 UI 구성
# -----------------------
tab1, tab2 = st.tabs(["💬 카카오톡 분석", "📰 뉴스 수집"])

with tab1:
    st.subheader("카카오톡 대화파일 업로드 (.txt)")
    uploaded = st.file_uploader("카톡 txt 파일을 업로드하세요", type="txt")
    if uploaded:
        raw_bytes = uploaded.read()
        encoding = chardet.detect(raw_bytes)["encoding"] or "utf-8"
        text = raw_bytes.decode(encoding, errors="ignore")
        df_kakao = parse_kakao_text(text)
        if df_kakao.empty:
            st.warning("❗ 메시지를 추출할 수 없습니다. 다른 형식의 파일일 수 있어요.")
        else:
            st.success(f"✅ 총 {len(df_kakao)}개 메시지를 분석했어요!")
            st.dataframe(df_kakao)
            st.download_button("📥 CSV로 저장하기", df_kakao.to_csv(index=False).encode("utf-8"), "kakao_analyzed.csv", "text/csv")

with tab2:
    st.subheader("출판사 관련 뉴스 (최근 2주)")
    if st.button("뉴스 수집 시작"):
        progress = st.progress(0)
        all_news = []
        for i, kw in enumerate(keywords):
            df = crawl_news_quick(kw)
            all_news.append(df)
            progress.progress((i+1)/len(keywords))
        df_news = pd.concat(all_news, ignore_index=True)
        st.success("✅ 뉴스 수집 완료!")
        st.dataframe(df_news)
        st.download_button("📥 뉴스 저장", df_news.to_csv(index=False).encode("utf-8"), "news_result.csv", "text/csv")
