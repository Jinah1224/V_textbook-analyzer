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

keywords = ["천재교육", "천재교과서", "지학사", "벽호", "프린피아", "미래엔", "교과서", "동아출판"]
category_keywords = {
    "후원": ["후원", "기탁"], "기부": ["기부"], "협약/MOU": ["협약", "mou"],
    "에듀테크/디지털교육": ["에듀테크", "디지털교육", "ai교육", "스마트교육"],
    "정책": ["정책"], "출판": ["출판"], "인사/채용": ["채용", "교사"],
    "프린트 및 인쇄": ["인쇄", "프린트"], "공급": ["공급"], "교육": ["교육"], "이벤트": ["이벤트", "사은품"]
}
