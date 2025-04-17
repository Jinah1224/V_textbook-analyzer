
import streamlit as st
import pandas as pd
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
import re
import time
import chardet

# -------------------------------
# 뉴스 크롤링 설정
# -------------------------------
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

                date = get_news_date(link)
                try:
                    if datetime.strptime(date, "%Y.%m.%d").date() < two_weeks_ago:
                        continue
                except:
                    continue

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

def get_news_date(url):
    try:
        res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
        soup = BeautifulSoup(res.text, 'lxml')
        meta = soup.find("meta", {"property": "article:published_time"})
        if meta and meta.get("content"):
            return meta["content"][:10].replace("-", ".")
        return "날짜 없음"
    except:
        return "날짜 오류"

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

# -------------------------------
# 카카오톡 분석
# -------------------------------
kakao_categories = {
    "채택: 선정 기준/평가": ["평가표", "기준", "추천의견서", "선정기준"],
    "채택: 위원회 운영": ["위원회", "협의회", "대표교사", "위원"],
    "채택: 회의/심의 진행": ["회의", "심의", "회의록", "심사"],
    "배송": ["배송", "왔어요", "전시본", "지도서"],
    "주문": ["공문", "정산", "나이스", "에듀파인", "마감일"],
    "출판사": ["자료", "기프티콘", "교사용", "회수", "요청"]
}
publishers = ["미래엔", "비상", "동아", "아이스크림", "천재", "지학사"]
subjects = ["국어", "수학", "사회", "과학", "영어"]
complaint_keywords = ["안 왔어요", "늦게", "없어요", "문제", "헷갈려", "불편"]

def analyze_kakao(text):
    pattern = re.compile(r"\[(.*?)\] \[(오전|오후) (\d{1,2}):(\d{2})\] (.+)")
    date_pattern = re.compile(r"-+ (\d{4})년 (\d{1,2})월 (\d{1,2})일")
    lines = text.splitlines()
    current_date = None
    data = []

    for line in lines:
        if date_match := date_pattern.match(line):
            year, month, day = map(int, date_match.groups())
            current_date = datetime(year, month, day).date()
            continue
        match = pattern.match(line)
        if match and current_date:
            sender, ampm, hour, minute, message = match.groups()
            hour = int(hour)
            minute = int(minute)
            if ampm == "오후" and hour != 12:
                hour += 12
            elif ampm == "오전" and hour == 12:
                hour = 0
            time_obj = datetime.strptime(f"{hour}:{minute}", "%H:%M").time()
            data.append({
                "날짜": current_date,
                "시간": time_obj,
                "보낸 사람": sender.strip(),
                "메시지": message.strip(),
                "카테고리": classify_category(message),
                "출판사": extract_kakao_publisher(message),
                "과목": extract_subject(message),
                "불만 여부": detect_complaint(message)
            })
    return pd.DataFrame(data)

def classify_category(text):
    for cat, keywords in kakao_categories.items():
        if any(k in text for k in keywords):
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
    return any(word in text for word in complaint_keywords)

# -------------------------------
# Streamlit 앱 구성
# -------------------------------
st.set_page_config(page_title="📚 커뮤니티 & 뉴스 분석기", layout="wide")
st.title("📚 교과서 커뮤니티 대화 분석기 + 뉴스 수집기")

tab1, tab2 = st.tabs(["💬 카카오톡 분석", "📰 뉴스 크롤링"])

# Tab 1: 카카오톡 분석
with tab1:
    st.subheader("카카오톡 .txt 파일 업로드")
    uploaded_file = st.file_uploader("카카오톡 대화 파일을 업로드하세요", type="txt")
    if uploaded_file:
        raw_bytes = uploaded_file.read()
        detected = chardet.detect(raw_bytes)
        encoding = detected["encoding"] or "utf-8"
        text = raw_bytes.decode(encoding, errors="ignore")

        st.write("📌 감지된 인코딩:", encoding)
        df_kakao = analyze_kakao(text)

        if df_kakao.empty:
            st.warning("⚠️ 메시지를 파싱할 수 없습니다. 파일 형식이나 내용 구조를 확인해주세요.")
        else:
            st.success(f"✅ 총 {len(df_kakao)}개의 메시지를 분석했습니다!")
            st.dataframe(df_kakao)
            st.download_button("📥 분석 결과 다운로드", df_kakao.to_csv(index=False).encode("utf-8"), "카카오톡_분석결과.csv", "text/csv")

# Tab 2: 뉴스 수집
with tab2:
    st.subheader("출판사 관련 뉴스 크롤링 (최근 2주)")
    if st.button("📰 뉴스 수집 시작"):
        progress = st.progress(0)
        collected = []
        with st.spinner("뉴스를 열심히 모으는 중입니다..."):
            for i, kw in enumerate(keywords):
                df = crawl_news_quick(kw, pages=3)
                collected.append(df)
                progress.progress((i + 1) / len(keywords))
        df_news = pd.concat(collected, ignore_index=True)
        st.success("✅ 뉴스 수집 완료!")
        st.dataframe(df_news)
        st.download_button("📥 뉴스 데이터 다운로드", df_news.to_csv(index=False).encode("utf-8"), "출판사_뉴스.csv", "text/csv")
