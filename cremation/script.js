const dataVersion = "20260606-4";
const cremationCsvPath = `cremation_location.csv?v=${dataVersion}`;
const accessCsvPath = `region_access.csv?v=${dataVersion}`;
const feeCsvPath = `cremation_fee.csv?v=${dataVersion}`;

let cremationData = [];
let accessData = [];
let feeData = [];

const input = document.getElementById("regionInput");
const searchButton = document.getElementById("searchButton");
const exampleChips = document.querySelectorAll(".example-chip");
const isEmbedded = window.self !== window.top;

searchButton.addEventListener("click", searchRegion);

exampleChips.forEach((chip) => {
  chip.addEventListener("click", () => {
    input.value = chip.dataset.region;
    searchRegion();
  });
});

input.addEventListener("keydown", function (event) {
  if (event.key === "Enter") {
    searchRegion();
  }
});

window.addEventListener("DOMContentLoaded", async () => {
  try {
    cremationData = await loadCSV(cremationCsvPath);
    accessData = await loadCSV(accessCsvPath);
    feeData = await loadCSV(feeCsvPath);

    console.log("전국 화장시설 데이터:", cremationData);
    console.log("경기 북부 접근성 데이터:", accessData);
    console.log("화장시설 요금 데이터:", feeData);
    notifyParentOfHeight();
  } catch (error) {
    console.error("CSV 로드 실패:", error);
    document.getElementById("errorMessage").textContent =
      "CSV 파일을 불러오지 못했습니다. 파일 위치와 이름을 확인해주세요.";
    notifyParentOfHeight();
  }
});

window.addEventListener("load", notifyParentOfHeight);

document.querySelectorAll("details").forEach((details) => {
  details.addEventListener("toggle", notifyParentOfHeight);
});

if ("ResizeObserver" in window) {
  const resizeObserver = new ResizeObserver(notifyParentOfHeight);
  resizeObserver.observe(document.documentElement);
}

async function loadCSV(path) {
  const response = await fetch(path);

  if (!response.ok) {
    throw new Error(`${path} 파일을 찾을 수 없습니다.`);
  }

  const text = await response.text();
  return parseCSV(text);
}

function parseCSV(csvText) {
  const lines = csvText.trim().split(/\r?\n/);
  const headers = splitCSVLine(lines[0]).map((header) => header.trim());

  return lines.slice(1).map((line) => {
    const values = splitCSVLine(line);
    const row = {};

    headers.forEach((header, index) => {
      row[header] = values[index] ? values[index].trim() : "";
    });

    return row;
  });
}

function splitCSVLine(line) {
  const result = [];
  let current = "";
  let insideQuotes = false;

  for (let i = 0; i < line.length; i++) {
    const char = line[i];

    if (char === '"') {
      insideQuotes = !insideQuotes;
    } else if (char === "," && !insideQuotes) {
      result.push(current);
      current = "";
    } else {
      current += char;
    }
  }

  result.push(current);
  return result;
}

function searchRegion() {
  const rawKeyword = input.value.trim();
  const keyword = normalizeRegionName(rawKeyword);

  const resultSection = document.getElementById("resultSection");
  const errorMessage = document.getElementById("errorMessage");
  const facilityList = document.getElementById("facilityList");

  if (!keyword) {
    resultSection.classList.add("hidden");
    errorMessage.textContent = "지역명을 입력해주세요.";
    return;
  }

  errorMessage.textContent = "";

  const accessMatch = accessData.find((item) => {
    const region = normalizeRegionName(item["region"]);
    const sigungu = normalizeRegionName(item["sigungu"]);
    const sido = normalizeRegionName(item["sido"]);

    return (
      region.includes(keyword) ||
      keyword.includes(region) ||
      sigungu.includes(keyword) ||
      keyword.includes(sigungu) ||
      sido.includes(keyword)
    );
  });

  if (accessMatch) {
    showAccessResult(accessMatch);
    revealResult();
    return;
  }

  const matchedFacilities = cremationData.filter((item) => {
    const sido = normalizeRegionName(item["시도"]);
    const sigungu = normalizeRegionName(item["시군구"]);
    const address = normalizeRegionName(item["주소"]);
    const facilityName = normalizeRegionName(item["시설명"]);

    return (
      sido.includes(keyword) ||
      sigungu.includes(keyword) ||
      address.includes(keyword) ||
      facilityName.includes(keyword)
    );
  });

  if (matchedFacilities.length > 0) {
    showFacilityResult(rawKeyword, matchedFacilities);
    revealResult();
    return;
  }

  document.getElementById("regionName").textContent = rawKeyword;
  document.getElementById("facilityCount").textContent = "0개";
  document.getElementById("nearestFacility").textContent = "데이터 없음";
  document.getElementById("distance").textContent = "확인 필요";
  document.getElementById("grade").textContent = "미산정";

  document.getElementById("comment").textContent =
    "전국 화장시설 목록과 경기 북부 접근성 보완 데이터에서 검색 결과를 찾지 못했습니다. 이 지역은 별도 접근성 데이터 입력이 필요합니다.";

  facilityList.innerHTML = "";
  hideFeeSummary();

  setGradeColor("none");
  revealResult();
}

function revealResult() {
  const resultSection = document.getElementById("resultSection");
  resultSection.classList.remove("hidden");

  window.requestAnimationFrame(() => {
    notifyParentOfHeight();

    if (!isEmbedded) {
      resultSection.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  });
}

function showAccessResult(data) {
  const facilityList = document.getElementById("facilityList");
  const fee = findFacilityFee(data["nearest_facility"]);
  const outside = isOutsideUser(data, data["nearest_facility"]);
  const feeMarkup = fee
    ? `<span class="facility-fee"><b>${outside ? "관외" : "관내"}</b> 화장 비용 ${formatWon(
        getFeeAmount(fee, outside ? "outside" : "inside")
      )}</span>`
    : "";

  document.getElementById("regionName").textContent = `${data["sigungu"]} 화장 지수`;
  document.getElementById("facilityCount").textContent = `${data["facility_count"]}개`;
  document.getElementById("nearestFacility").textContent = data["nearest_facility"];
  document.getElementById("distance").textContent = `약 ${data["distance_km"]}km`;
  document.getElementById("grade").textContent = data["grade"];

  document.getElementById("comment").textContent =
    `${data["comment"]} 가장 가까운 ${data["nearest_facility"]}까지는 자동차 기준 약 ${data["distance_km"]}km, ${data["travel_time"]}이 걸립니다.`;

  facilityList.innerHTML = `
    <div class="facility-item">
      <strong>가장 가까운 화장장: ${data["nearest_facility"]}</strong>
      <p>기준: ${data["distance_basis"]}</p>
      <span>거리 ${data["distance_km"]}km · 예상 이동시간 ${data["travel_time"]}</span>
      ${feeMarkup}
    </div>
  `;

  showFeeSummary(fee, outside);
  setGradeColor(data["grade"]);
}

function showFacilityResult(keyword, facilities) {
  const facilityList = document.getElementById("facilityList");

  const totalCremators = facilities.reduce((sum, item) => {
    const count = Number(item["화장로수"]);
    return sum + (isNaN(count) ? 0 : count);
  }, 0);

  document.getElementById("regionName").textContent = `${keyword} 검색 결과`;
  document.getElementById("facilityCount").textContent = `${facilities.length}개`;
  document.getElementById("nearestFacility").textContent = facilities[0]["시설명"];
  document.getElementById("distance").textContent = "지역 내";
  document.getElementById("grade").textContent = "양호";

  document.getElementById("comment").textContent =
    `전국 화장시설 목록에서 ${facilities.length}개의 화장시설이 확인됩니다. 등록된 화장로 수는 총 ${totalCremators}기입니다.`;

  facilityList.innerHTML = facilities
    .map((item) => {
      return `
        <div class="facility-item">
          <strong>${item["시설명"]}</strong>
          <p>${item["주소"]}</p>
          <span>${item["공-사설 구분"]} · 화장로 ${item["화장로수"]}기 · 전화번호 ${item["전화번호"] || "정보 없음"}</span>
        </div>
      `;
    })
    .join("");

  const firstFee = findFacilityFee(facilities[0]["시설명"]);
  showFeeSummary(firstFee, false, true);
  setGradeColor("양호");
}

function findFacilityFee(facilityName) {
  const normalizedName = normalizeFacilityName(facilityName);

  return feeData.find((item) => {
    const feeFacilityName = item["facility_name"] || item["facility"];
    const normalizedFeeName = normalizeFacilityName(feeFacilityName);

    return (
      normalizedFeeName === normalizedName ||
      normalizedFeeName.includes(normalizedName) ||
      normalizedName.includes(normalizedFeeName)
    );
  });
}

function isOutsideUser(regionData, facilityName) {
  const facility = cremationData.find(
    (item) =>
      normalizeRegionName(item["시설명"]) === normalizeRegionName(facilityName)
  );

  if (!facility) return true;

  const userRegion = normalizeRegionName(regionData["sigungu"]);
  const facilityRegion = normalizeRegionName(
    facility["시군구"] || facility["시도"]
  );

  return userRegion !== facilityRegion;
}

function showFeeSummary(fee, outside, showBoth = false) {
  const feeSummary = document.getElementById("feeSummary");
  const feeType = document.getElementById("feeType");
  const applicableFee = document.getElementById("applicableFee");
  const feeComparison = document.getElementById("feeComparison");
  const feeSource = document.getElementById("feeSource");

  if (!fee) {
    hideFeeSummary();
    return;
  }

  const insideFee = getFeeAmount(fee, "inside");
  const outsideFee = getFeeAmount(fee, "outside");

  feeType.classList.toggle("outside", outside && !showBoth);

  if (showBoth) {
    feeType.textContent = "요금 안내";
    applicableFee.textContent =
      `관내 ${formatWon(insideFee)} · 관외 ${formatWon(outsideFee)}`;
    feeComparison.textContent = "실제 적용 구분은 시설별 거주지 기준에 따라 달라집니다.";
  } else if (outside) {
    const difference = outsideFee - insideFee;
    feeType.textContent = "관외 요금 적용";
    applicableFee.textContent = formatWon(outsideFee);
    feeComparison.textContent =
      `관내 주민 요금 ${formatWon(insideFee)}보다 ${formatWon(difference)} 높습니다.`;
  } else {
    feeType.textContent = "관내 요금 적용";
    applicableFee.textContent = formatWon(insideFee);
    feeComparison.textContent = `관외 이용 요금은 ${formatWon(outsideFee)}입니다.`;
  }

  feeSource.textContent =
    fee["source_note"] ||
    fee["note"] ||
    "일반 성인 시신 화장 요금 기준입니다. 실제 적용 조건은 시설에 확인해주세요.";
  feeSummary.classList.remove("hidden");
}

function hideFeeSummary() {
  document.getElementById("feeSummary").classList.add("hidden");
}

function notifyParentOfHeight() {
  if (!isEmbedded) return;

  window.parent.postMessage(
    {
      type: "cremation-interactive-resize",
      height: document.documentElement.scrollHeight,
    },
    "*"
  );
}

function formatWon(value) {
  if (!Number.isFinite(value)) return "요금 정보 없음";
  return `${value.toLocaleString("ko-KR")}원`;
}

function getFeeAmount(fee, type) {
  const fieldNames =
    type === "outside"
      ? ["corpse_outside", "outside_fee"]
      : ["corpse_inside", "inside_fee"];

  const value = fieldNames
    .map((fieldName) => fee[fieldName])
    .find((fieldValue) => fieldValue !== undefined && fieldValue !== "");

  const amount = Number(value);
  return Number.isFinite(amount) ? amount : NaN;
}

function normalizeFacilityName(text) {
  if (!text) return "";

  return normalizeRegionName(text)
    .replaceAll("화장시설", "")
    .replaceAll("화장장", "")
    .replaceAll("승화원", "")
    .replaceAll("공설", "")
    .replaceAll("시립", "")
    .replace(/[()·\-\s]/g, "");
}

function setGradeColor(grade) {
  const gradeCard = document.querySelector(".grade-card");

  gradeCard.classList.remove("good", "warning", "danger", "none");

  if (grade === "양호" || grade === "보통") {
    gradeCard.classList.add("good");
  } else if (grade === "취약") {
    gradeCard.classList.add("warning");
  } else if (grade === "매우 취약") {
    gradeCard.classList.add("danger");
  } else {
    gradeCard.classList.add("none");
  }
}

function normalizeRegionName(text) {
  if (!text) return "";

  return text
    .replaceAll("특별시", "")
    .replaceAll("광역시", "")
    .replaceAll("특별자치시", "")
    .replaceAll("특별자치도", "")
    .replaceAll("경기도", "경기")
    .replaceAll("강원특별자치도", "강원")
    .replaceAll("충청북도", "충북")
    .replaceAll("충청남도", "충남")
    .replaceAll("전라북도", "전북")
    .replaceAll("전라남도", "전남")
    .replaceAll("경상북도", "경북")
    .replaceAll("경상남도", "경남")
    .replaceAll("제주특별자치도", "제주")
    .replaceAll("시", "")
    .replaceAll("군", "")
    .replaceAll("구", "")
    .replace(/\s/g, "")
    .trim();
}
