# 화장장 뉴스 분류 + 키워드 분석 (역할 분담 파이프라인)

다른 환경(CPU·무료)에서 실행하는 패키지. **분류는 LLM, 키워드는 HuggingFace** 가 담당.

기사 1건을 두 축으로 분류:
- **사회적 관점** (다중라벨): 수급부족 / 님비갈등 / 행정회피 / 제도장벽 / 인식개선 / 기타
- **감정적 관점** (단일라벨): 우려 / 분노 / 촉구 / 중립 / 기대

추가로 기사별·카테고리별 **핵심 키워드**를 추출.

---

## 폴더 구조
```
main/
├─ classify_llm.py        # [1단계] LLM 분류 (정확도 최우선, 무료 API)
├─ extract_keywords.py    # [2단계] HF 키워드 추출 (ko-SBERT + KeyBERT, CPU)
├─ requirements.txt
├─ .env.example           # API 설정 템플릿
├─ data/                  # 입력 (본문 전문 포함)
│  ├─ crematorium_news_full.csv
│  └─ crematorium_news_local_admin_full.csv
└─ output/                # 결과 (자동 생성)
   ├─ *_labeled.csv          # 1단계 결과 (분류)
   ├─ *_keywords.csv         # 2단계 결과 (분류+키워드)
   └─ category_keywords.csv  # 카테고리별 대표 키워드
```

입력 `body` 컬럼이 **기사 본문 전체**다. (`summary` 는 참고용 짧은 요약)

---

## ✅ 실행 체크리스트

### 0. 사전 준비
- [ ] Python 3.9+ 설치 확인 (`python --version`)
- [ ] 가상환경 생성·활성화 (권장)
      `python -m venv .venv && source .venv/bin/activate`  (Windows: `.venv\Scripts\activate`)
- [ ] 의존성 설치 `pip install -r requirements.txt`
- [ ] `data/` 에 두 CSV 가 있는지 확인

### 1. LLM API 키 발급 (무료 중 택1)
- [ ] **HyperCLOVA X**: https://www.ncloud.com/product/aiService/clovaStudio → 콘솔 → CLOVA Studio → API 키
      (신규 크레딧 최대 30만원 / 3개월: https://www.ncloud.com/main/creditEvent)
- [ ] 또는 **Gemini**: https://aistudio.google.com/apikey
- [ ] 또는 **Groq**: https://console.groq.com/keys
- [ ] 또는 **OpenRouter**: https://openrouter.ai/keys

### 2. 환경 설정
- [ ] `cp .env.example .env`
- [ ] `.env` 에서 사용할 프로바이더 블록 주석 해제 후 `LLM_API_KEY` 입력
- [ ] (정확도 최대화 원하면) `.env` 의 `SELF_CONSISTENCY=3`

### 3. [1단계] LLM 분류 실행
- [ ] `python classify_llm.py`
- [ ] 무료 RPM 제한으로 느리면 그냥 두거나, 끊기면 **다시 실행**(자동 resume)
- [ ] `output/*_labeled.csv` 생성 확인 (사회/감정/근거/신뢰도 컬럼)

### 4. [2단계] HF 키워드 추출 실행
- [ ] `python extract_keywords.py`  (1단계 결과를 자동으로 입력으로 사용)
- [ ] 첫 실행 시 임베딩 모델(ko-SBERT, 약 400MB) 자동 다운로드
- [ ] `output/*_keywords.csv` 및 `output/category_keywords.csv` 확인

### 5. 결과 점검
- [ ] `is_crematorium_topic=false` (주제무관) / `is_political=true` 행을 분석에서 제외할지 결정
- [ ] `confidence` 낮은 행 표본 검수 (필요 시 SELF_CONSISTENCY 올려 재실행)

---

## 산출 컬럼
| 컬럼 | 설명 | 생성 단계 |
|---|---|---|
| `social_final` | 사회적 관점 라벨(다중, `\|` 구분) | LLM |
| `emotion_final` | 감정적 관점 라벨(단일) | LLM |
| `is_crematorium_topic` | 국내 화장장 주제 여부 | LLM |
| `is_political` / `is_animal` | 정치 중심 / 동물화장장 표시 | LLM |
| `confidence` / `rationale` | 분류 확신도 / 근거 1문장 | LLM |
| `keywords` | 기사 핵심 키워드(`\|` 구분) | HF |

---

## 참고
- 모델 교체는 `.env` 의 `LLM_BASE_URL`/`LLM_MODEL` 만 바꾸면 됨 (코드 수정 불필요).
- 정확도 vs 무료한도: `SELF_CONSISTENCY`(다수결 횟수)와 `RATE_DELAY`(요청간격)로 조절.
- 키워드 품질을 더 높이려면 `KW_MODEL=BAAI/bge-m3` 로 바꿔 실행 가능(느리지만 정밀).
- 형태소분석기(konlpy/Java) 불필요 — 정규식 토크나이저로 동작.
