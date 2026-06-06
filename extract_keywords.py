#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[2단계] 화장장 뉴스 키워드 추출 - HuggingFace 담당 (CPU·무료·오프라인)

HF 한국어 임베딩(ko-SBERT) + KeyBERT 로 기사별 핵심 키워드를 뽑는다.
LLM 이 매긴 분류(social/emotion) 결과 위에 키워드를 덧붙이고,
사회·감정 카테고리별 대표 키워드도 집계한다.

입력  : output/*_labeled.csv  (없으면 data/*_full.csv 로 fallback)
출력  : output/*_keywords.csv          (기사별 keywords 컬럼 추가)
        output/category_keywords.csv    (카테고리별 상위 키워드 집계)

실행:
  python extract_keywords.py
  python extract_keywords.py output/crematorium_news_full_labeled.csv
환경변수:
  KW_MODEL   임베딩 모델 (기본 jhgan/ko-sroberta-multitask)
  TOP_N      기사당 키워드 수 (기본 8)
  KW_BODY    키워드 추출에 쓸 본문 길이 (기본 3000)
"""

import os
import re
import sys
import glob
import pandas as pd
from collections import Counter

from keybert import KeyBERT
from sentence_transformers import SentenceTransformer
from sklearn.feature_extraction.text import CountVectorizer

# 한국어 명사 추출용 형태소분석기 (Java 불필요). 없으면 정규식 토크나이저로 폴백.
try:
    from kiwipiepy import Kiwi
    _KIWI = Kiwi()
except Exception:
    _KIWI = None

KW_MODEL = os.environ.get("KW_MODEL", "jhgan/ko-sroberta-multitask")
TOP_N = int(os.environ.get("TOP_N", "8"))
KW_BODY = int(os.environ.get("KW_BODY", "3000"))

# 한국어 불용어 (도메인 잡음 포함)
STOPWORDS = set("""
이 그 저 것 수 등 및 또 더 즉 약 위 또한 통해 대한 관련 위해 따라 대해 가장 모든 각각
기자 뉴스 일보 신문 사진 제공 무단 전재 재배포 저작권 앵커 리포트 인터뷰 종합 속보 단독
오늘 어제 내일 이날 지난 올해 최근 현재 당시 이번 다음 이후 이전 그동안 동안
서울 경기 인천 지역 시민 주민 우리 관계자 밝혔다 말했다 전했다 설명했다 강조했다
대표 시장 군수 구청장 위원장 의원 후보 정도 경우 부분 상황 문제 진행 추진 계획 방침
""".split())


def kiwi_tokenizer(text):
    """Kiwi 로 명사(일반명사 NNG, 고유명사 NNP)만 2글자 이상 추출."""
    nouns = []
    for tok in _KIWI.tokenize(text):
        if tok.tag in ("NNG", "NNP") and len(tok.form) >= 2 and tok.form not in STOPWORDS:
            nouns.append(tok.form)
    return nouns


def build_vectorizer():
    if _KIWI is not None:
        # 명사 기반 1~2그램 -> 깨끗한 키워드("화장시설","공원형","동의율" 등)
        return CountVectorizer(tokenizer=kiwi_tokenizer, token_pattern=None,
                               ngram_range=(1, 2), lowercase=False, min_df=1)
    # 폴백: Kiwi 미설치 시 정규식 토크나이저(품질 낮음)
    print("  [경고] kiwipiepy 미설치 -> 정규식 토크나이저 사용(키워드 품질 저하). "
          "pip install kiwipiepy 권장.")
    return CountVectorizer(ngram_range=(1, 2),
                           token_pattern=r"(?u)\b[가-힣A-Za-z][가-힣A-Za-z]+\b",
                           stop_words=list(STOPWORDS), min_df=1)


def clean(text):
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", " ", text)   # 이메일
    text = re.sub(r"https?://\S+", " ", text)                       # URL
    text = re.sub(r"Copyright.*|무단[ ]?전재.*|저작권자.*", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def pick_input():
    labeled = sorted(glob.glob("output/*_labeled.csv"))
    if labeled:
        return labeled
    return sorted(glob.glob("data/*_full.csv"))


def extract_file(infile, kw_model, vectorizer):
    df = pd.read_csv(infile).reset_index(drop=True)
    n = len(df)
    print(f"\n=== {infile} ({n}건) 키워드 추출 ===")
    docs = [clean(str(r.body) if pd.notna(r.get("body")) else "")[:KW_BODY]
            for _, r in df.iterrows()]

    keywords_col = []
    cat_social = {}   # 사회 카테고리별 키워드 카운터
    cat_emotion = {}
    for i, doc in enumerate(docs):
        if len(doc) < 30:
            keywords_col.append("")
            continue
        try:
            kws = kw_model.extract_keywords(
                doc, vectorizer=vectorizer, top_n=TOP_N,
                use_mmr=True, diversity=0.6)
            words = [w for w, _ in kws]
        except Exception:
            words = []
        keywords_col.append("|".join(words))

        # 카테고리별 집계 (라벨 있을 때만)
        if "social_final" in df.columns and pd.notna(df.iloc[i].get("social_final")):
            for cat in str(df.iloc[i]["social_final"]).split("|"):
                cat_social.setdefault(cat, Counter()).update(words)
        if "emotion_final" in df.columns and pd.notna(df.iloc[i].get("emotion_final")):
            cat_emotion.setdefault(str(df.iloc[i]["emotion_final"]), Counter()).update(words)

        if (i + 1) % 200 == 0:
            print(f"  {i+1}/{n}")

    df["keywords"] = keywords_col
    outfile = os.path.join("output", re.sub(r"\.csv$", "_keywords.csv", os.path.basename(infile)))
    os.makedirs("output", exist_ok=True)
    df.to_csv(outfile, index=False, encoding="utf-8-sig")
    print(f"  -> 저장 {outfile}")
    return cat_social, cat_emotion


def save_category_keywords(all_social, all_emotion):
    rows = []
    for axis, store in [("사회적관점", all_social), ("감정적관점", all_emotion)]:
        for cat, counter in store.items():
            top = ", ".join(w for w, _ in counter.most_common(15))
            rows.append({"axis": axis, "category": cat, "top_keywords": top})
    if rows:
        out = pd.DataFrame(rows)
        out.to_csv("output/category_keywords.csv", index=False, encoding="utf-8-sig")
        print("\n[카테고리별 대표 키워드] -> output/category_keywords.csv")
        for r in rows:
            print(f"  [{r['axis']}/{r['category']}] {r['top_keywords']}")


def main():
    files = sys.argv[1:] if len(sys.argv) > 1 else pick_input()
    if not files:
        print("입력 파일이 없습니다. 먼저 classify_llm.py 를 돌리거나 data/ 를 확인하세요.")
        sys.exit(1)
    print(f"임베딩 모델 로딩: {KW_MODEL}")
    st = SentenceTransformer(KW_MODEL)
    kw_model = KeyBERT(model=st)
    vectorizer = build_vectorizer()

    merge_social, merge_emotion = {}, {}
    for f in files:
        cs, ce = extract_file(f, kw_model, vectorizer)
        for cat, cnt in cs.items():
            merge_social.setdefault(cat, Counter()).update(cnt)
        for cat, cnt in ce.items():
            merge_emotion.setdefault(cat, Counter()).update(cnt)

    save_category_keywords(merge_social, merge_emotion)
    print("\n[2단계] 키워드 추출 완료.")


if __name__ == "__main__":
    main()
