# 전국 화장장 관할 구역 지도

화장장 부족 문제 데이터저널리즘 기획 — 인터랙티브 지도

## 🔗 배포 주소
GitHub Pages 활성화 후 아래 주소에서 접근 가능:
```
https://{GitHub아이디}.github.io/{저장소명}/
```

## 📁 파일 구성
```
index.html   ← 지도 메인 페이지
korea.json   ← 전국 시군구 GeoJSON (GADM 2018 기준)
README.md    ← 이 파일
```

## 🗺 기능
- 전국 시군구 관할 화장장 색상 구분
- 마우스 오버 → 지역명 + 관할 화장장명
- 마커 클릭 → 관내·관외 요금 상세 (일반 성인 화장 기준)
- 우측 범례: 시·도별 화장장 목록 + 관내→관외 요금

## 📊 데이터 출처
- 전국 공설 화장시설 공개 사용료 (일반 성인 시신 기준)
- 시설별 감면·협약에 따라 실제 적용 금액은 다를 수 있음

## 🚀 GitHub Pages 배포 방법
1. 이 저장소를 GitHub에 push
2. Settings → Pages → Source: `main` 브랜치, `/ (root)` 선택
3. Save → 몇 분 후 배포 완료

## 기사 삽입 방법 (iframe)
```html
<iframe
  src="https://{GitHub아이디}.github.io/{저장소명}/"
  width="100%"
  height="700"
  frameborder="0"
  allowfullscreen>
</iframe>
```
