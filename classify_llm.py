#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
[1단계] 화장장 뉴스 분류 - LLM 담당 (정확도 최우선, CPU·무료 API)

본문 '전문'을 무료 LLM API 에 넣어 codebook 기준으로 두 축 분류:
  축1 사회적 관점 (다중라벨): 수급부족 / 님비갈등 / 행정회피 / 제도장벽 / 인식개선 / 기타
  축2 감정적 관점 (단일라벨): 우려 / 분노 / 촉구 / 중립 / 기대
추가 출력: 주제적합성(국내 화장장 여부) / 정치 / 동물 / 근거 / 신뢰도

OpenAI 호환 Chat Completions 엔드포인트면 무엇이든 사용 가능.
.env 에 LLM_BASE_URL / LLM_MODEL / LLM_API_KEY 설정 (.env.example 참고).

실행:
  python classify_llm.py                          # data/ 의 두 파일 모두
  python classify_llm.py data/crematorium_news_full.csv   # 특정 파일만
  SELF_CONSISTENCY=3 python classify_llm.py       # 3회 다수결(정확도↑)

무료 API 는 분당 요청수(RPM) 제한 -> RATE_DELAY 로 조절.
중간에 끊겨도 다시 실행하면 link 기준으로 이어서 진행(resume).
"""

import os
import re
import sys
import json
import time
import requests
import pandas as pd


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                # .env 값이 우선순위를 갖도록 os.environ[k] = v 사용
                os.environ[k.strip()] = v.strip().strip('"').strip("'")


load_dotenv()

# ---------------------------------------------------------------------------
INPUT_FILES = ["data/crematorium_news_full.csv",
               "data/crematorium_news_local_admin_full.csv"]

BASE_URL = os.environ.get("LLM_BASE_URL", "https://clovastudio.stream.ntruss.com/v1/openai").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "HCX-DASH-002")
API_KEY = os.environ.get("LLM_API_KEY", "")

RATE_DELAY = float(os.environ.get("RATE_DELAY", "2.0"))
MAX_RETRY = int(os.environ.get("MAX_RETRY", "5"))
BODY_CHARS = int(os.environ.get("BODY_CHARS", "6000"))
SELF_CONSISTENCY = int(os.environ.get("SELF_CONSISTENCY", "1"))
SAVE_EVERY = 20

SOCIAL_LABELS = ["수급부족", "님비갈등", "행정회피", "제도장벽", "인식개선", "기타"]
EMOTION_LABELS = ["우려", "분노", "촉구", "중립", "기대"]

# ---------------------------------------------------------------------------
SYSTEM_PROMPT = """당신은 한국 '국내 화장장(화장시설)' 관련 뉴스 기사를 분류하는 전문 어노테이터다.
아래 정의(codebook)를 엄격히 따르고, 반드시 JSON 하나만 출력한다.

[축1] 사회적 관점 (해당되는 것 모두, 1~3개 선택)
- 수급부족: 화장로·예약 부족, 화장 적체·대란, 가동률 한계, 사망 급증 대응 등 '용량/수급' 문제
- 님비갈등: 화장장 입지를 둘러싼 주민 반대·집회·혐오시설 갈등 등 '주민 충돌'
- 행정회피: 지자체의 책임 회피·떠넘기기·관할 다툼·소극행정 등 '행정 태도' 비판
- 제도장벽: 법·조례·동의율·인허가·도시계획 등 '제도/규제'로 인한 난항
- 인식개선: 화장문화 확산, 시설 현대화·공원화, 화장률 상승, 수용·긍정 분위기 등 '인식 변화'
- 기타: 위에 해당 없음(부고·단신, 화장장을 장지로만 스친 언급, 주제 무관 등)

[축2] 감정적 관점 (정확히 1개)
- 우려: 걱정·불안·위기감이 지배적
- 분노: 분노·규탄·격앙된 항의가 지배적
- 촉구: 대책 요구·호소·촉구가 지배적
- 중립: 감정색 없이 사실 전달
- 기대: 기대·환영·안도 등 긍정이 지배적

[중요 규칙]
1. 해외 화장장이거나 국내 화장장과 무관하면 is_crematorium_topic=false, social=["기타"], emotion="중립".
2. 정치(선거·정당·후보) 중심 기사이면 is_political=true.
3. 반려동물(동물) 화장장이면 is_animal=true.
4. rationale 은 본문 표현 근거로 1문장.
5. confidence 는 0~1 분류 확신도.

출력 형식(JSON만, 다른 텍스트 금지):
{"is_crematorium_topic": true, "is_political": false, "is_animal": false,
 "social": ["..."], "emotion": "...", "confidence": 0.0, "rationale": "..."}"""

FEWSHOT = [
    {"role": "user",
     "content": "제목: 화장장 부족에 '사흘장' 속출…유족들 발 동동\n본문: 코로나19로 사망자가 급증하면서 화장로 예약이 밀려 사흘장, 나흘장이 속출하고 있다. 유족들은 \"부모님을 모실 곳이 없다\"며 분통을 터뜨렸다. 시는 화장로 가동 시간을 늘렸지만 역부족이다."},
    {"role": "assistant",
     "content": '{"is_crematorium_topic": true, "is_political": false, "is_animal": false, "social": ["수급부족"], "emotion": "분노", "rationale": "화장로 예약 적체로 사흘장이 속출하고 유족이 분통을 터뜨림.", "confidence": 0.9}'},
    {"role": "user",
     "content": "제목: ○○군 화장장 건립 백지화 촉구…주민 1000명 집회\n본문: 주민들은 혐오시설이라며 화장장 건립을 결사반대했다. 군이 동의율 기준을 낮춘 조례를 추진하자 주민들은 \"행정이 주민을 무시한다\"며 즉각 철회를 요구했다."},
    {"role": "assistant",
     "content": '{"is_crematorium_topic": true, "is_political": false, "is_animal": false, "social": ["님비갈등", "제도장벽", "행정회피"], "emotion": "촉구", "rationale": "주민이 혐오시설 반대 집회를 열고 조례 추진에 철회를 요구함.", "confidence": 0.85}'},
    {"role": "user",
     "content": "제목: 시립화장장 새 단장…공원형 추모시설로 재개장\n본문: 낡은 화장시설을 공원형으로 새로 단장해 시민들이 환영하고 있다. 화장률이 높아지는 가운데 깨끗하고 쾌적한 환경으로 거듭났다는 평가다."},
    {"role": "assistant",
     "content": '{"is_crematorium_topic": true, "is_political": false, "is_animal": false, "social": ["인식개선"], "emotion": "기대", "rationale": "공원형 재단장으로 시민들이 환영하고 긍정적으로 평가함.", "confidence": 0.88}'},
]


# ---------------------------------------------------------------------------
def build_body(row):
    body = str(row.body) if pd.notna(row.get("body")) else ""
    if len(body) <= BODY_CHARS:
        return body
    head = body[: int(BODY_CHARS * 0.7)]
    tail = body[-int(BODY_CHARS * 0.3):]
    return head + " […중략…] " + tail


def call_llm(title, body):
    if "generativelanguage.googleapis.com" in BASE_URL:
        # Native Gemini API Support
        prompt_parts = [SYSTEM_PROMPT]
        for f in FEWSHOT:
            prefix = "Q: " if f["role"] == "user" else "A: "
            prompt_parts.append(f"{prefix}{f['content']}")
        prompt_parts.append(f"Q: 제목: {title}\n본문: {body}")
        
        url = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent?key={API_KEY}"
        payload = {
            "contents": [{
                "parts": [{"text": "\n\n".join(prompt_parts)}]
            }],
            "generationConfig": {
                "temperature": 0.0,
                "maxOutputTokens": 400,
                "responseMimeType": "application/json"
            }
        }
        for attempt in range(MAX_RETRY):
            try:
                r = requests.post(url, json=payload, timeout=60)
            except requests.RequestException:
                time.sleep(2 ** attempt); continue
            if r.status_code == 200:
                try:
                    res = r.json()
                    return parse_json(res["candidates"][0]["content"]["parts"][0]["text"])
                except Exception:
                    time.sleep(2 ** attempt); continue
            print(f"    [Native Gemini HTTP {r.status_code}] {r.text[:150]}")
            time.sleep(2 ** attempt)
        return None

    # Original OpenAI-compatible logic with Clova Studio Header Support
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + FEWSHOT
    messages.append({"role": "user", "content": f"제목: {title}\n본문: {body}"})
    payload = {"model": MODEL, "messages": messages, "temperature": 0.0,
               "max_tokens": 400}
    
    # 기본 헤더 설정
    headers = {"Content-Type": "application/json"}
    
    if "clovastudio" in BASE_URL:
        # 클로바 스튜디오는 전용 헤더만 사용하는 것이 더 안정적입니다
        headers["X-NCP-CLOVASTUDIO-API-KEY"] = API_KEY
        # 서비스 앱 키인 경우 APIGW 키가 필수입니다
        if os.environ.get("APIGW_API_KEY"):
            headers["X-NCP-APIGW-API-KEY"] = os.environ.get("APIGW_API_KEY")
        # 일부 환경에서는 Authorization을 중복으로 보내면 40104 오류가 발생하므로 제외합니다.
    else:
        # 일반 OpenAI 호환 API (Groq, OpenRouter 등)
        headers["Authorization"] = f"Bearer {API_KEY}"

    for attempt in range(MAX_RETRY):
        try:
            r = requests.post(f"{BASE_URL}/chat/completions",
                              headers=headers, json=payload, timeout=60)
        except requests.RequestException:
            time.sleep(2 ** attempt); continue
        if r.status_code == 200:
            return parse_json(r.json()["choices"][0]["message"]["content"])
        if r.status_code == 429:
            wait = _retry_after(r) or (2 ** attempt) * 5
            print(f"    [429] {wait:.0f}초 대기"); time.sleep(wait); continue
        if r.status_code == 400 and "response_format" in payload:
            payload.pop("response_format"); continue
        print(f"    [HTTP {r.status_code}] {r.text[:150]}")
        time.sleep(2 ** attempt)
    return None


def _retry_after(resp):
    try:
        return float(resp.headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


def parse_json(txt):
    if not txt:
        return None
    m = re.search(r"\{.*\}", txt, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def normalize(d):
    if not isinstance(d, dict):
        return None
    soc = d.get("social") or []
    if isinstance(soc, str):
        soc = [soc]
    soc = [s for s in soc if s in SOCIAL_LABELS] or ["기타"]
    emo = d.get("emotion") if d.get("emotion") in EMOTION_LABELS else "중립"
    return {
        "social_final": "|".join(dict.fromkeys(soc)),
        "emotion_final": emo,
        "is_crematorium_topic": bool(d.get("is_crematorium_topic", True)),
        "is_political": bool(d.get("is_political", False)),
        "is_animal": bool(d.get("is_animal", False)),
        "confidence": d.get("confidence", ""),
        "rationale": str(d.get("rationale", ""))[:300],
    }


def majority(results):
    from collections import Counter
    emo = Counter(r["emotion_final"] for r in results).most_common(1)[0][0]
    soc_cnt = Counter()
    for r in results:
        for s in r["social_final"].split("|"):
            soc_cnt[s] += 1
    half = len(results) / 2
    soc = [s for s, c in soc_cnt.items() if c >= half and s != "기타"] or ["기타"]
    base = results[0].copy()
    base["social_final"] = "|".join(soc)
    base["emotion_final"] = emo
    return base


OUT_COLS = ["social_final", "emotion_final", "is_crematorium_topic",
            "is_political", "is_animal", "confidence", "rationale"]


def classify_file(infile):
    if not os.path.exists(infile):
        print(f"[건너뜀] {infile} 없음"); return
    outfile = re.sub(r"\.csv$", "_labeled.csv", os.path.basename(infile))
    outfile = os.path.join("output", outfile)
    os.makedirs("output", exist_ok=True)

    df = pd.read_csv(infile).reset_index(drop=True)
    n = len(df)

    done = {}
    if os.path.exists(outfile):
        prev = pd.read_csv(outfile)
        for _, r in prev.iterrows():
            done[str(r.get("link"))] = r.to_dict()
        print(f"  [resume] 기존 {len(done)}건 -> 이어서")

    print(f"\n=== {infile} ({n}건) | 모델 {MODEL} ===")
    rows, processed = [], 0
    for i, row in df.iterrows():
        key = str(row.get("link"))
        if key in done:
            rows.append(done[key]); continue
        title = str(row.get("title", ""))
        body = build_body(row)
        results = []
        for _ in range(max(1, SELF_CONSISTENCY)):
            parsed = normalize(call_llm(title, body))
            if parsed:
                results.append(parsed)
            time.sleep(RATE_DELAY)
        label = majority(results) if len(results) > 1 else (
            results[0] if results else {c: "" for c in OUT_COLS})
        rec = row.to_dict(); rec.update(label); rows.append(rec)
        processed += 1
        if processed % SAVE_EVERY == 0:
            pd.DataFrame(rows).to_csv(outfile, index=False, encoding="utf-8-sig")
            print(f"  {i+1}/{n} (신규 {processed}) 체크포인트")

    out = pd.DataFrame(rows)
    out.to_csv(outfile, index=False, encoding="utf-8-sig")
    print(f"  -> 저장 {outfile} ({len(out)}건)")
    print("  [사회]", out.social_final.dropna().str.split("|").explode().value_counts().to_dict())
    print("  [감정]", out.emotion_final.value_counts().to_dict())


def main():
    if not API_KEY:
        print("LLM_API_KEY 가 필요합니다. .env 를 설정하세요 (.env.example 참고)."); sys.exit(1)
    files = sys.argv[1:] if len(sys.argv) > 1 else INPUT_FILES
    print(f"엔드포인트:{BASE_URL} | 모델:{MODEL} | 자기일관성:{SELF_CONSISTENCY}회")
    for f in files:
        classify_file(f)
    print("\n[1단계] 분류 완료. -> 다음: python extract_keywords.py")


if __name__ == "__main__":
    main()
