const $ = (id) => document.getElementById(id);
const stateNames = {PENDING: "待處理", LEASED: "處理中", DONE: "已完成", FAIL: "失敗", DEFERRED: "延後重試"};
let categoryPage = 1;
let jobPage = 1;
let selectedCode = "";
let selectedName = "";
let categoryTotal = 0;
let jobTotal = 0;
let categoryTimer;
let jobTimer;

async function getJson(url) {
  const response = await fetch(url, {cache: "no-store"});
  const result = await response.json();
  if (!response.ok) throw new Error(result.error || `HTTP ${response.status}`);
  return result;
}

function setText(id, value) {
  $(id).textContent = value == null || value === "" ? "—" : String(value);
}

function formatDate(value) {
  if (!value) return "—";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? String(value) : date.toLocaleString("zh-TW", {hour12: false});
}

function cell(row, value, className = "") {
  const node = document.createElement("td");
  node.textContent = value == null || value === "" ? "—" : String(value);
  if (className) node.className = className;
  row.append(node);
  return node;
}

function emptyRow(body, columns, message) {
  const row = document.createElement("tr");
  const item = document.createElement("td");
  item.colSpan = columns;
  item.className = "empty";
  item.textContent = message;
  row.append(item);
  body.replaceChildren(row);
}

async function loadStatus() {
  try {
    const data = await getJson("/api/status");
    if (data.status === "NO_RUN") {
      setText("run-status", "尚無擷取工作");
      ["metric-done", "metric-running", "metric-pending", "metric-warning", "metric-interval", "run-id", "snapshot-date", "progress-count", "progress-percent"].forEach((id) => setText(id, "—"));
      $("progress-fill").style.width = "0%";
      $("blocked-banner").hidden = true;
      return;
    }
    const labels = {RUNNING: "正在擷取", QUEUED: "排隊中", BLOCKED: "擷取暫停", PARTIAL: "部分完成", COMPLETE: "已完成", COMPLETE_WITH_WARNINGS: "完成（含警告）"};
    setText("run-status", labels[data.status] || data.status);
    setText("run-id", data.runId);
    setText("snapshot-date", `資料日期 ${data.snapshotDate || "—"}`);
    setText("progress-count", `${data.completedCategories} / ${data.selectedCategories} 類已完成`);
    setText("progress-percent", `${data.progressPercent}%`);
    $("progress-fill").style.width = `${Math.min(100, data.progressPercent)}%`;
    setText("metric-done", `${data.completedCategories} / ${data.selectedCategories}`);
    setText("metric-running", data.runningCategories);
    setText("metric-pending", data.pendingCategories);
    setText("metric-warning", data.warningCategories);
    setText("metric-interval", data.intervalSeconds == null ? "—" : `${data.intervalSeconds}s / 下限 ${data.minimumIntervalSeconds}s`);
    $("blocked-banner").hidden = !data.gateBlocked;
    setText("updated-at", `資料庫最近更新：${formatDate(data.gateUpdatedAt || data.updatedAt)} · 每 10 秒自動更新`);
  } catch (error) {
    setText("run-status", "資料庫連線中斷");
    setText("updated-at", error.message);
  }
}

function qualityLabel(item) {
  if (!item.captureStatus) return "尚無已提交批次";
  if (item.captureStatus === "COMPLETE" && (!item.paginationStatus || item.paginationStatus === "PASS")) return "完整";
  if (item.captureStatus === "COMPLETE") return `分頁 ${item.paginationStatus}`;
  return item.captureStatus.replaceAll("_", " ");
}

async function loadCategories() {
  const params = new URLSearchParams({page: String(categoryPage)});
  const search = $("category-search").value.trim();
  const state = $("state-filter").value;
  if (search) params.set("search", search);
  if (state) params.set("state", state);
  const body = $("category-rows");
  try {
    const data = await getJson(`/api/categories?${params}`);
    categoryTotal = data.total;
    setText("category-total", `${categoryTotal} 個類別`);
    if (!data.categories.length) {
      emptyRow(body, 7, "沒有符合條件的職業類別。");
    } else {
      const fragment = document.createDocumentFragment();
      for (const item of data.categories) {
        const row = document.createElement("tr");
        row.dataset.code = item.code;
        if (selectedCode === item.code) row.classList.add("selected");
        cell(row, item.code, "code-cell");
        cell(row, item.name, "name-cell");
        const stateCell = cell(row, "");
        const pill = document.createElement("span");
        pill.className = `state-pill state-${item.state}`;
        pill.textContent = stateNames[item.state] || item.state;
        stateCell.append(pill);
        cell(row, item.attempts);
        const batch = cell(row, "", "batch-cell");
        if (item.batchId) {
          const date = document.createElement("strong");
          date.textContent = `${item.batchDate} · ${item.area || "全台"}`;
          const rows = document.createElement("span");
          rows.textContent = `${item.rowCount ?? 0} 筆 · ${item.pages ?? 0} 頁`;
          batch.append(date, rows);
        } else {
          batch.textContent = "尚無已提交批次";
        }
        const quality = cell(row, "");
        const badge = document.createElement("span");
        badge.className = `quality-pill${item.captureStatus && item.captureStatus !== "COMPLETE" ? " quality-warning" : ""}`;
        badge.textContent = qualityLabel(item);
        quality.append(badge);
        fragment.append(row);
      }
      body.replaceChildren(fragment);
    }
    const pages = Math.max(1, Math.ceil(categoryTotal / data.pageSize));
    setText("category-page-label", `第 ${data.page} / ${pages} 頁 · ${categoryTotal} 筆`);
    $("category-prev").disabled = data.page <= 1;
    $("category-next").disabled = data.page >= pages;
  } catch (error) {
    emptyRow(body, 7, `讀取類別失敗：${error.message}`);
  }
}

async function loadJobs() {
  const body = $("job-rows");
  if (!selectedCode) return;
  const params = new URLSearchParams({jobcat: selectedCode, page: String(jobPage)});
  const search = $("job-search").value.trim();
  if (search) params.set("search", search);
  try {
    const data = await getJson(`/api/jobs?${params}`);
    $("jobs-heading").textContent = `${selectedCode} · ${selectedName}`;
    $("jobs-note").hidden = true;
    $("job-search").disabled = false;
    if (!data.batch) {
      setText("batch-meta", "尚無已提交批次");
      $("job-search").disabled = true;
      emptyRow(body, 5, "此職類尚無已提交批次；擷取中的頁面會在職類完成後一併提交。");
      setText("job-page-label", "—");
      $("job-prev").disabled = true;
      $("job-next").disabled = true;
      return;
    }
    setText("batch-meta", `${data.batch.date} · ${data.batch.area || "全台"} · ${data.batch.rowCount} 筆`);
    if (data.batch.captureStatus !== "COMPLETE" || (data.batch.paginationStatus && data.batch.paginationStatus !== "PASS")) {
      const note = $("jobs-note");
      note.hidden = false;
      note.textContent = `此批次狀態：${data.batch.captureStatus || "—"} / 分頁 ${data.batch.paginationStatus || "—"}。原始內容保留供檢視，品質警告不代表 Gold 可用。`;
      note.className = "notice notice-warning";
    }
    if (!data.jobs.length) {
      emptyRow(body, 5, "此頁沒有符合搜尋條件的職缺。");
    } else {
      const fragment = document.createDocumentFragment();
      for (const job of data.jobs) {
        const row = document.createElement("tr");
        cell(row, job.jobNo, "code-cell");
        cell(row, job.jobName, "name-cell");
        cell(row, job.company);
        cell(row, job.area);
        cell(row, `salaryLow: ${job.salaryLow ?? "—"} · salaryHigh: ${job.salaryHigh ?? "—"}`);
        row.tabIndex = 0;
        row.setAttribute("role", "button");
        row.setAttribute("aria-label", `檢視 ${job.jobName || job.jobNo} 原始資料`);
        row.addEventListener("click", () => showJob(job));
        row.addEventListener("keydown", (event) => { if (event.key === "Enter") showJob(job); });
        fragment.append(row);
      }
      body.replaceChildren(fragment);
    }
    const pages = Math.max(1, Math.ceil(data.total / data.pageSize));
    setText("job-page-label", `第 ${data.page} / ${pages} 頁 · 搜尋結果 ${data.total} 筆`);
    $("job-prev").disabled = data.page <= 1;
    $("job-next").disabled = data.page >= pages;
  } catch (error) {
    emptyRow(body, 5, `讀取職缺失敗：${error.message}`);
  }
}

function showJob(job) {
  $("job-detail-title").textContent = `${job.jobNo || "職缺"} · ${job.jobName || "原始資料"}`;
  $("job-json").textContent = JSON.stringify(job.payload, null, 2);
  $("job-detail").hidden = false;
}

$("category-rows").addEventListener("click", (event) => {
  const row = event.target.closest("tr[data-code]");
  if (!row) return;
  selectedCode = row.dataset.code;
  selectedName = row.querySelector(".name-cell").textContent;
  jobPage = 1;
  $("job-search").value = "";
  $("job-detail").hidden = true;
  loadCategories();
  loadJobs();
});
$("category-search").addEventListener("input", () => { categoryPage = 1; clearTimeout(categoryTimer); categoryTimer = setTimeout(loadCategories, 250); });
$("state-filter").addEventListener("change", () => { categoryPage = 1; loadCategories(); });
$("job-search").addEventListener("input", () => { jobPage = 1; clearTimeout(jobTimer); jobTimer = setTimeout(loadJobs, 250); });
$("category-prev").addEventListener("click", () => { if (categoryPage > 1) { categoryPage--; loadCategories(); } });
$("category-next").addEventListener("click", () => { categoryPage++; loadCategories(); });
$("job-prev").addEventListener("click", () => { if (jobPage > 1) { jobPage--; loadJobs(); } });
$("job-next").addEventListener("click", () => { jobPage++; loadJobs(); });
$("refresh").addEventListener("click", () => { loadStatus(); loadCategories(); if (selectedCode) loadJobs(); });
$("close-detail").addEventListener("click", () => { $("job-detail").hidden = true; });
loadStatus();
loadCategories();
setInterval(() => { loadStatus(); loadCategories(); if (selectedCode) loadJobs(); }, 10000);