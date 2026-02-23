window.__full_ui_loaded = true;

const els = {
  chatList: document.getElementById("chat-list"),
  newChat: document.getElementById("new-chat"),
  clearChats: document.getElementById("clear-chats"),
  chat: document.getElementById("chat"),

  question: document.getElementById("question"),
  run: document.getElementById("run"),
  stop: document.getElementById("stop"),
  status: document.getElementById("status"),
  approveExample: document.getElementById("approve-example"),
  approveStatus: document.getElementById("approve-status"),

  chips: document.getElementById("chips"),
  runDemo: document.getElementById("run-demo"),

  latest: document.getElementById("latest"),
  copyLatest: document.getElementById("copy-latest"),
  copyInsight: document.getElementById("copy-insight"),

  statDeals: document.getElementById("stat-deals"),
  statRevenue: document.getElementById("stat-revenue"),
  statPipeline: document.getElementById("stat-pipeline"),
  statClosedWon: document.getElementById("stat-closed-won"),

  toggleDetails: document.getElementById("toggle-details"),
  details: document.getElementById("details"),

  // Details panel
  timing: document.getElementById("timing"),
  final: document.getElementById("final"),
  results: document.getElementById("results"),
  resultsMeta: document.getElementById("results-meta"),
  sql: document.getElementById("sql"),
  prompt: document.getElementById("prompt"),
  raw: document.getElementById("raw"),
  validator: document.getElementById("validator"),
  validatorMeta: document.getElementById("validator-meta"),
  debug: document.getElementById("debug"),

  copyPrompt: document.getElementById("copy-prompt"),
  copySql: document.getElementById("copy-sql"),
  copyRaw: document.getElementById("copy-raw"),
  downloadCsv: document.getElementById("download-csv"),
  copyDebug: document.getElementById("copy-debug"),

  refreshTables: document.getElementById("refresh-tables"),
  tableSearch: document.getElementById("table-search"),
  tablePicker: document.getElementById("table-picker"),
  copyScope: document.getElementById("copy-scope"),

  loadMetricRules: document.getElementById("load-metric-rules"),
  saveMetricRules: document.getElementById("save-metric-rules"),
  metricRules: document.getElementById("metric-rules"),
  filterRegion: document.getElementById("filter-region"),
  filterCurrency: document.getElementById("filter-currency"),
  filterStage: document.getElementById("filter-stage"),
  queryContextBadges: document.getElementById("query-context-badges"),
  kpiQuarter: document.getElementById("kpi-quarter"),
  kpiRevenue: document.getElementById("kpi-revenue"),
  kpiMargin: document.getElementById("kpi-margin"),
  kpiGap: document.getElementById("kpi-gap"),
  kpiCoverage: document.getElementById("kpi-coverage"),
};

function on(el, eventName, handler) {
  if (!el) return;
  el.addEventListener(eventName, handler);
}

function initGlobalErrorHandlers() {
  window.addEventListener("error", (event) => {
    const message = event?.error?.message || event?.message || "Script error";
    console.error("[full_ui] window.error:", event?.error || event);
    setStatus(`UI error: ${message}`);
  });
  window.addEventListener("unhandledrejection", (event) => {
    console.error("[full_ui] unhandledrejection:", event?.reason || event);
    const message = event?.reason?.message || String(event?.reason || "Promise rejection");
    setStatus(`UI error: ${message}`);
  });
}

const STORAGE_KEY = "sqlfromllm.chatui.chats.v1";
const RECENTS_KEY = "sqlfromllm.chatui.recents.v1";
const SCOPE_KEY = "sqlfromllm.chatui.scope.v1";
const METRIC_RULES_KEY = "sqlfromllm.chatui.metric_rules.v1";
const REGION_KEY = "sqlfromllm.chatui.region.v1";
const CURRENCY_KEY = "sqlfromllm.chatui.currency.v1";
const STAGE_BUCKET_KEY = "sqlfromllm.chatui.stage_bucket.v1";
const CRO_DEMO_INDEX_KEY = "sqlfromllm.chatui.cro_demo_idx.v1";
const CRO_DEMO_QUESTIONS = [
  "Are we on track to hit this month margin target?",
  "Which are our top 5 pipeline deals this month, and what percentage of total pipeline margin does each contribute?",
  "How much pipeline is in Commit vs Best Case vs Early Stage?",
  "How much margin we create last month vs budget",
  "Show top 5 deals in Pipeline by margin with deal name",
  "What is our pipeline coverage revenue for next quarter with revenue type name",
  "list top 10 sales person with their first name and last name this year",
  "show 10 deals revenue in pipeline this year with deal name",
  "compare q3 and q4 revenue for last year for each revenue type",
  "what to expect as a revenue and margin for next month",
];
const WELCOME_MESSAGES = [
  "Hi there.",
  "Ask me a sales question related to revenue, margin, or budget.",
  "I will try my best to respond with the right insights.",
];
const ALLOWED_STAGE_BUCKETS = new Set([
  "not_applied",
  "closed_won_forecast",
  "forecast",
  "bridge",
  "upside",
  "closed_won",
  "pipeline",
]);
const STAGE_LABELS = {
  not_applied: "Not Applied",
  closed_won_forecast: "Closed Won + Forecast",
  forecast: "Forecast",
  bridge: "Bridge",
  upside: "Upside",
  closed_won: "Closed Won",
  pipeline: "Pipeline",
};

function nowIso() {
  return new Date().toISOString();
}

function makeId() {
  if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
    return crypto.randomUUID();
  }
  return `chat_${Date.now()}_${Math.random().toString(36).slice(2, 10)}`;
}

function safeJsonParse(text, fallback) {
  try {
    return JSON.parse(text);
  } catch {
    return fallback;
  }
}

function loadChats() {
  return safeJsonParse(localStorage.getItem(STORAGE_KEY) || "[]", []);
}

function saveChats(chats) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(chats));
}

function newChat() {
  return {
    id: makeId(),
    name: "New chat",
    createdAt: nowIso(),
    messages: [],
    welcomeShown: false,
  };
}

let chats = loadChats();
let activeChatId = chats[0]?.id || null;
let activeAbort = null;
let lastResponse = null;
let pendingStageQuestion = null;
let tableNames = [];
let selectedTables = new Set(safeJsonParse(localStorage.getItem(SCOPE_KEY) || "[]", []));
let recents = safeJsonParse(localStorage.getItem(RECENTS_KEY) || "[]", []);
let selectedRegion = localStorage.getItem(REGION_KEY) || "GBR";
let selectedCurrency = localStorage.getItem(CURRENCY_KEY) || "GBP";
let selectedStageBucket = localStorage.getItem(STAGE_BUCKET_KEY) || "not_applied";

function syncCurrencyFromRegion() {
  selectedCurrency = selectedRegion === "CAN" ? "CAD" : "GBP";
  localStorage.setItem(CURRENCY_KEY, selectedCurrency);
}

function renderContextBadges() {
  if (!els.queryContextBadges) return;
  const regionLabel = selectedRegion === "CAN" ? "CAN" : "UK";
  const stageLabel = STAGE_LABELS[selectedStageBucket] || "Not Applied";
  const currencyLabel = selectedCurrency === "CAD" ? "CAD" : "GBP";
  els.queryContextBadges.innerHTML = `
    <span class="context-badge region">🌍 ${regionLabel}</span>
    <span class="context-badge stage">🧭 ${stageLabel}</span>
    <span class="context-badge currency">💱 ${currencyLabel}</span>
  `;
}

function formatKpiThousands(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  const symbol = selectedCurrency === "CAD" ? "C$" : "£";
  return `${symbol}${Math.round(n)}K`;
}

function formatKpiCoverage(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return "-";
  return `${n.toFixed(2)}x`;
}

async function fetchKpiStrip() {
  if (!els.kpiRevenue || !els.kpiMargin || !els.kpiGap || !els.kpiCoverage) return;
  try {
    const params = new URLSearchParams({
      region: selectedRegion,
      reporting_currency: selectedCurrency,
      stage_bucket: selectedStageBucket,
    });
    const res = await fetch(`/api/kpi_strip?${params.toString()}`, { cache: "no-store" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed");
    const kpis = data.kpis || {};
    els.kpiRevenue.textContent = formatKpiThousands(kpis.revenue_k);
    els.kpiMargin.textContent = formatKpiThousands(kpis.margin_k);
    els.kpiGap.textContent = formatKpiThousands(kpis.gap_k);
    els.kpiCoverage.textContent = formatKpiCoverage(kpis.coverage_ratio);
    if (els.kpiQuarter) els.kpiQuarter.textContent = data.quarter || "This quarter";
  } catch {
    els.kpiRevenue.textContent = "-";
    els.kpiMargin.textContent = "-";
    els.kpiGap.textContent = "-";
    els.kpiCoverage.textContent = "-";
    if (els.kpiQuarter) els.kpiQuarter.textContent = "This quarter";
  }
}

function setStatus(text) {
  if (els.status) els.status.textContent = text;
}

function setApproveEnabled(enabled) {
  if (!els.approveExample) return;
  els.approveExample.disabled = !enabled;
}

function setIfPresent(el, value) {
  if (!el) return;
  el.textContent = value;
}

function activeChat() {
  return chats.find((c) => c.id === activeChatId) || null;
}

function renderChatList() {
  els.chatList.innerHTML = "";
  chats.forEach((chat) => {
    const item = document.createElement("div");
    item.className = "chat-item" + (chat.id === activeChatId ? " active" : "");

    const name = document.createElement("div");
    name.className = "name";
    name.textContent = chat.name;

    const desc = document.createElement("div");
    desc.className = "desc";
    const last = chat.messages[chat.messages.length - 1];
    desc.textContent = last ? last.content.slice(0, 44) : "No messages";

    item.appendChild(name);
    item.appendChild(desc);

    item.addEventListener("click", () => {
      activeChatId = chat.id;
      render();
    });

    item.addEventListener("dblclick", () => {
      const next = prompt("Rename chat", chat.name);
      if (!next) return;
      chat.name = next;
      saveChats(chats);
      renderChatList();
    });

    els.chatList.appendChild(item);
  });
}

function pushMessage(role, content, extra = {}) {
  const chat = activeChat();
  if (!chat) return;
  chat.messages.push({ role, content, at: nowIso(), ...extra });
  if (chat.name === "New chat" && role === "user") {
    chat.name = content.slice(0, 32);
  }
  saveChats(chats);
  renderChatList();
  renderChat();
}

function renderChat() {
  const chat = activeChat();
  els.chat.innerHTML = "";
  if (!chat) return;

  chat.messages.forEach((m) => {
    const bubble = document.createElement("div");
    bubble.className = `bubble ${m.role}`;
    if (m.kind === "bar_chart" && m.chart && Array.isArray(m.chart.labels)) {
      const title = document.createElement("div");
      title.style.fontWeight = "800";
      title.style.marginBottom = "8px";
      title.textContent = m.content || "Bar chart";
      bubble.appendChild(title);
      bubble.appendChild(renderInlineBarChart(m.chart));
    } else if (m.kind === "line_chart" && m.chart && Array.isArray(m.chart.labels)) {
      const title = document.createElement("div");
      title.style.fontWeight = "800";
      title.style.marginBottom = "8px";
      title.textContent = m.content || "Line chart";
      bubble.appendChild(title);
      bubble.appendChild(renderInlineLineChart(m.chart));
    } else if (m.kind === "table" && m.table && Array.isArray(m.table.columns)) {
      bubble.appendChild(renderInlineTable(m.table.columns, m.table.rows || []));
    } else if (m.kind === "stage_prompt" && Array.isArray(m.options)) {
      const title = document.createElement("div");
      title.style.fontWeight = "800";
      title.style.marginBottom = "8px";
      title.textContent = m.content || "Select a stage scope";
      bubble.appendChild(title);

      const row = document.createElement("div");
      row.style.display = "flex";
      row.style.flexWrap = "wrap";
      row.style.gap = "8px";

      m.options.forEach((opt) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "chip";
        btn.textContent = opt.label;
        btn.addEventListener("click", () => {
          selectedStageBucket = opt.value;
          localStorage.setItem(STAGE_BUCKET_KEY, selectedStageBucket);
          renderContextBadges();
          fetchKpiStrip();
          // Remove the prompt message after selection.
          if (activeChat()) {
            activeChat().messages = activeChat().messages.filter((msg) => msg !== m);
            saveChats(chats);
            renderChat();
          }
          if (pendingStageQuestion) {
            const q = pendingStageQuestion;
            pendingStageQuestion = null;
            runQuery(q, { forceRun: true });
          }
        });
        row.appendChild(btn);
      });
      bubble.appendChild(row);
    } else {
      bubble.textContent = m.content;
    }

    const small = document.createElement("div");
    small.className = "small";
    small.textContent = new Date(m.at).toLocaleString();

    bubble.appendChild(small);
    els.chat.appendChild(bubble);
  });
  els.chat.scrollTop = els.chat.scrollHeight;
}

function queueWelcomeMessages(chatId) {
  const chat = chats.find((c) => c.id === chatId);
  if (!chat || chat.welcomeShown) return;
  chat.welcomeShown = true;
  saveChats(chats);

  WELCOME_MESSAGES.forEach((msg, idx) => {
    setTimeout(() => {
      if (activeChatId !== chatId) return;
      pushMessage("assistant", msg);
    }, 2000 * (idx + 1));
  });
}

function renderInlineBarChart(chartData) {
  const labels = chartData.labels || [];
  const series = Array.isArray(chartData.series) ? chartData.series : [];
  const palette = ["#ff7a18", "#2ec5ff", "#55c000"];
  const maxVal = Math.max(
    1,
    ...series.flatMap((s) => s.values.map((v) => (Number.isFinite(v) ? v : 0)))
  );
  const wrap = document.createElement("div");
  wrap.style.display = "grid";
  wrap.style.gridTemplateColumns = "36px 1fr";
  wrap.style.gap = "10px";
  wrap.style.minWidth = "360px";
  wrap.style.maxWidth = "620px";

  const yAxis = document.createElement("div");
  yAxis.style.display = "grid";
  yAxis.style.gridTemplateRows = "repeat(5, 1fr)";
  yAxis.style.alignItems = "end";
  yAxis.style.height = "200px";
  yAxis.style.fontSize = "10px";
  yAxis.style.color = "var(--subtle)";
  [maxVal, maxVal * 0.75, maxVal * 0.5, maxVal * 0.25, 0].forEach((tick) => {
    const t = document.createElement("div");
    t.textContent = formatAxisValue(tick);
    yAxis.appendChild(t);
  });

  const chartWrap = document.createElement("div");
  chartWrap.style.display = "grid";
  chartWrap.style.gridTemplateRows = "1fr auto";

  if (series.length) {
    const legend = document.createElement("div");
    legend.style.display = "flex";
    legend.style.flexWrap = "wrap";
    legend.style.gap = "10px";
    legend.style.fontSize = "11px";
    legend.style.color = "var(--subtle)";
    legend.style.marginBottom = "6px";
    series.slice(0, 2).forEach((s, idx) => {
      const item = document.createElement("div");
      item.style.display = "flex";
      item.style.alignItems = "center";
      item.style.gap = "6px";
      const swatch = document.createElement("span");
      swatch.style.width = "10px";
      swatch.style.height = "10px";
      swatch.style.borderRadius = "50%";
      swatch.style.background = palette[idx % palette.length];
      item.appendChild(swatch);
      const label = document.createElement("span");
      label.textContent = s.name || `Series ${idx + 1}`;
      item.appendChild(label);
      legend.appendChild(item);
    });
    chartWrap.appendChild(legend);
  }

  const chart = document.createElement("div");
  chart.style.display = "grid";
  chart.style.gridTemplateColumns = `repeat(${Math.min(labels.length, 8)}, minmax(0, 1fr))`;
  chart.style.gap = "12px";
  chart.style.alignItems = "end";
  chart.style.padding = "8px 6px 0";
  chart.style.borderBottom = "1px solid rgba(148,163,184,0.5)";
  chart.style.height = "200px";

  labels.slice(0, 8).forEach((label, idx) => {
    const col = document.createElement("div");
    col.style.display = "grid";
    col.style.gap = "6px";
    col.style.alignItems = "end";
    col.style.justifyItems = "center";

    const barGroup = document.createElement("div");
    barGroup.style.display = "flex";
    barGroup.style.alignItems = "flex-end";
    barGroup.style.justifyContent = "center";
    barGroup.style.gap = "6px";
    barGroup.style.height = "160px";
    barGroup.style.width = "56px";

    series.slice(0, 2).forEach((s, sIdx) => {
      const value = Number(s.values[idx] ?? 0);
      const heightPct = Math.max(4, Math.round((value / maxVal) * 100));
      const bar = document.createElement("div");
      bar.style.height = `${heightPct}%`;
      bar.style.width = "20px";
      bar.style.borderRadius = "6px 6px 3px 3px";
      bar.style.background = palette[sIdx % palette.length];
      bar.style.display = "flex";
      bar.style.alignItems = "flex-end";
      bar.style.justifyContent = "center";
      bar.style.position = "relative";
      bar.title = `${s.name}: ${formatAxisValue(value)}`;
      const label = document.createElement("div");
      label.style.position = "absolute";
      label.style.top = "-16px";
      label.style.fontSize = "10px";
      label.style.fontWeight = "700";
      label.style.color = "#0f172a";
      label.textContent = formatAxisValue(value);
      bar.appendChild(label);
      barGroup.appendChild(bar);
    });

    const name = document.createElement("div");
    name.style.fontSize = "11px";
    name.style.color = "var(--subtle)";
    name.style.textAlign = "center";
    name.style.maxWidth = "70px";
    name.style.whiteSpace = "nowrap";
    name.style.overflow = "hidden";
    name.style.textOverflow = "ellipsis";
    name.textContent = String(label);

    col.appendChild(barGroup);
    col.appendChild(name);
    chart.appendChild(col);
  });

  const xAxis = document.createElement("div");
  xAxis.style.display = "flex";
  xAxis.style.justifyContent = "space-between";
  xAxis.style.fontSize = "10px";
  xAxis.style.color = "var(--subtle)";
  xAxis.style.padding = "4px 6px 0";
  xAxis.textContent = "";

  chartWrap.appendChild(chart);
  chartWrap.appendChild(xAxis);
  wrap.appendChild(yAxis);
  wrap.appendChild(chartWrap);
  return wrap;
}

function renderInlineLineChart(chartData) {
  const labels = chartData.labels || [];
  const series = Array.isArray(chartData.series) ? chartData.series : [];
  if (!labels.length || !series.length) return document.createElement("div");
  const safeValues = series.flatMap((s) => s.values.map((v) => (Number.isFinite(v) ? v : 0)));
  const minVal = Math.min(...safeValues);
  const maxVal = Math.max(...safeValues);
  const span = Math.max(1, maxVal - minVal);

  const width = 420;
  const height = 160;
  const padding = 18;
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${width} ${height}`);
  svg.setAttribute("width", "100%");
  svg.setAttribute("height", String(height));

  const palette = ["#ff7a18", "#2ec5ff", "#55c000"];
  series.slice(0, 2).forEach((s, sIdx) => {
    const points = s.values.map((v, idx) => {
      const x = padding + (idx / Math.max(1, labels.length - 1)) * (width - padding * 2);
      const y = height - padding - ((Number(v || 0) - minVal) / span) * (height - padding * 2);
      return { x, y };
    });
    const d = points.map((p, idx) => `${idx === 0 ? "M" : "L"}${p.x},${p.y}`).join(" ");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    path.setAttribute("stroke", palette[sIdx % palette.length]);
    path.setAttribute("stroke-width", "3");
    path.setAttribute("stroke-linecap", "round");
    path.setAttribute("stroke-linejoin", "round");
    svg.appendChild(path);

    points.forEach(({ x, y }) => {
      const circle = document.createElementNS("http://www.w3.org/2000/svg", "circle");
      circle.setAttribute("cx", String(x));
      circle.setAttribute("cy", String(y));
      circle.setAttribute("r", "3");
      circle.setAttribute("fill", palette[sIdx % palette.length]);
      svg.appendChild(circle);
    });
  });

  const wrap = document.createElement("div");
  wrap.style.minWidth = "320px";
  wrap.style.maxWidth = "560px";
  wrap.appendChild(svg);

  const axis = document.createElement("div");
  axis.style.display = "flex";
  axis.style.justifyContent = "space-between";
  axis.style.fontSize = "11px";
  axis.style.color = "var(--subtle)";
  axis.style.marginTop = "4px";
  const minLabel = document.createElement("span");
  minLabel.textContent = formatAxisValue(minVal);
  const maxLabel = document.createElement("span");
  maxLabel.textContent = formatAxisValue(maxVal);
  axis.appendChild(minLabel);
  axis.appendChild(maxLabel);
  wrap.appendChild(axis);

  const labelRow = document.createElement("div");
  labelRow.style.display = "grid";
  labelRow.style.gridTemplateColumns = `repeat(${Math.min(labels.length, 6)}, minmax(0,1fr))`;
  labelRow.style.gap = "6px";
  labelRow.style.marginTop = "6px";
  labels.slice(0, 6).forEach((label) => {
    const span = document.createElement("span");
    span.style.fontSize = "11px";
    span.style.color = "var(--subtle)";
    span.style.textAlign = "center";
    span.textContent = String(label);
    labelRow.appendChild(span);
  });
  wrap.appendChild(labelRow);

  const legend = document.createElement("div");
  legend.style.display = "flex";
  legend.style.flexWrap = "wrap";
  legend.style.gap = "10px";
  legend.style.fontSize = "11px";
  legend.style.color = "var(--subtle)";
  legend.style.marginTop = "6px";
  series.slice(0, 2).forEach((s, idx) => {
    const item = document.createElement("div");
    item.style.display = "flex";
    item.style.alignItems = "center";
    item.style.gap = "6px";
    const swatch = document.createElement("span");
    swatch.style.width = "10px";
    swatch.style.height = "10px";
    swatch.style.borderRadius = "50%";
    swatch.style.background = palette[idx % palette.length];
    item.appendChild(swatch);
    const label = document.createElement("span");
    label.textContent = s.name || `Series ${idx + 1}`;
    item.appendChild(label);
    legend.appendChild(item);
  });
  wrap.appendChild(legend);
  return wrap;
}

function formatAxisValue(value) {
  if (!Number.isFinite(value)) return String(value);
  const symbol = selectedCurrency === "CAD" ? "C$" : "£";
  return `${symbol}${Math.round(value)}k`;
}

function renderInlineTable(columns, rows) {
  const table = document.createElement("table");
  table.className = "inline-table";
  const thead = document.createElement("thead");
  const headerRow = document.createElement("tr");
  columns.forEach((col) => {
    const th = document.createElement("th");
    th.textContent = col;
    headerRow.appendChild(th);
  });
  thead.appendChild(headerRow);
  table.appendChild(thead);

  const tbody = document.createElement("tbody");
  rows.slice(0, 12).forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((cell, idx) => {
      const td = document.createElement("td");
      td.textContent = formatCellForDisplay(columns[idx], cell);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  const wrap = document.createElement("div");
  wrap.appendChild(table);
  if (rows.length > 12) {
    const more = document.createElement("div");
    more.className = "small";
    more.textContent = `+ ${rows.length - 12} more rows`;
    wrap.appendChild(more);
  }
  return wrap;
}

function setCopyButtonsEnabled(enabled) {
  els.copyPrompt.disabled = !enabled;
  els.copySql.disabled = !enabled;
  els.copyRaw.disabled = !enabled;
  els.copyDebug.disabled = !enabled;
  els.downloadCsv.disabled = !enabled;
}

function toCsv(columns, rows) {
  const esc = (v) => {
    const s = v === null || v === undefined ? "" : String(v);
    // Quote fields containing newlines, commas, or double quotes.
    if (/[\n\r,"]/u.test(s)) return '"' + s.replaceAll('"', '""') + '"';
    return s;
  };
  const out = [];
  out.push(columns.map(esc).join(","));
  rows.forEach((r) => out.push(r.map(esc).join(",")));
  return out.join("\n");
}

function formatCellForDisplay(colName, cell) {
  if (cell === null || cell === undefined) return "";
  const c = String(colName || "").toLowerCase();
  const isThousands = c.includes("thousand") || c.endsWith("_k");
  if (!isThousands) return String(cell);
  const n = Number(cell);
  if (!Number.isFinite(n)) return String(cell);
  const symbol = selectedCurrency === "CAD" ? "C$" : "£";
  return `${symbol}${Math.round(n)}K`;
}

function renderResults(columns, rows) {
  els.resultsMeta.textContent = `${rows.length} rows`;

  if (!columns?.length) {
    els.results.textContent = "No results.";
    return;
  }

  const table = document.createElement("table");
  table.className = "results-table";

  const thead = document.createElement("thead");
  const trh = document.createElement("tr");
  columns.forEach((c) => {
    const th = document.createElement("th");
    th.textContent = c;
    trh.appendChild(th);
  });
  thead.appendChild(trh);

  const tbody = document.createElement("tbody");
  rows.slice(0, 200).forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((cell, idx) => {
      const td = document.createElement("td");
      td.textContent = formatCellForDisplay(columns[idx], cell);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });

  table.appendChild(thead);
  table.appendChild(tbody);

  els.results.innerHTML = "";
  els.results.appendChild(table);
}

function buildChatAnswer(columns, rows) {
  if (!columns?.length || !rows?.length) return "No results.";
  if (rows.length === 1 && columns.length === 1) {
    return `${columns[0]}: ${formatCellForDisplay(columns[0], rows[0][0])}`;
  }
  const limit = Math.min(rows.length, 8);
  const lines = [columns.join(" | ")];
  for (let i = 0; i < limit; i += 1) {
    const row = rows[i];
    lines.push(
      row
        .map((cell, idx) => formatCellForDisplay(columns[idx], cell))
        .join(" | ")
    );
  }
  if (rows.length > limit) lines.push(`... ${rows.length - limit} more rows`);
  return lines.join("\n");
}

function tidyNarrative(text) {
  let t = String(text || "").replace(/\r/g, "").trim();
  if (!t) return "";
  if (t.includes("*")) {
    const parts = t
      .split("*")
      .map((p) => p.replace(/\s+/g, " ").trim())
      .filter(Boolean);
    if (parts.length > 1) {
      t = parts.join("\n");
    } else {
      t = parts[0] || "";
    }
  }
  t = t.replace(/\s+/g, " ").replace(/\.{2,}/g, ".").trim();
  t = t.replace(/\n{2,}/g, "\n");
  return t;
}

function choosePresentation(question, intent, columns, rows) {
  const q = String(question || "").toLowerCase();
  const p = String(intent?.presentation || "").toLowerCase();
  if (p.includes("bar")) return "bar";
  if (p.includes("line")) return "line";
  if (p.includes("table")) return "table";
  if (p.includes("text") || p.includes("summary")) return "text";
  if (q.includes("bar chart")) return "bar";
  if (q.includes("line chart")) return "line";
  if (q.includes("table")) return "table";
  return "text";
}

function wantsBarChart(question, intent) {
  const q = String(question || "").toLowerCase();
  const p = String(intent?.presentation || "").toLowerCase();
  return q.includes("bar chart") || p.includes("bar");
}

function extractBarChartData(columns, rows) {
  if (!Array.isArray(columns) || !Array.isArray(rows) || !columns.length || !rows.length) return null;
  let categoryIdx = -1;
  const valueIdxs = [];

  for (let i = 0; i < columns.length; i += 1) {
    const isNumeric = rows.every((r) => r[i] === null || r[i] === undefined || Number.isFinite(Number(r[i])));
    if (!isNumeric && categoryIdx === -1) categoryIdx = i;
    if (isNumeric) valueIdxs.push(i);
  }
  if (categoryIdx === -1 || valueIdxs.length === 0) return null;
  const seriesIdxs = valueIdxs.slice(0, 2);
  const sliced = rows.slice(0, 12);
  const labels = sliced.map((r) => String(r[categoryIdx]));
  const series = seriesIdxs.map((idx) => ({
    name: columns[idx],
    values: sliced.map((r) => Number(r[idx])),
  }));
  return {
    labels,
    series,
    category: columns[categoryIdx],
    metrics: series.map((s) => s.name),
  };
}

function validateClientSide(sqlText) {
  const s = (sqlText || "").toLowerCase();
  const issues = [];
  if (!s.includes("select") && !s.includes("with")) issues.push("Not a SELECT/CTE.");
  if (s.includes(" limit ") || s.endsWith(" limit")) issues.push("LIMIT is not valid T-SQL.");
  return issues;
}

function setPanelText(el, value) {
  el.textContent = value || "";
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
  } catch {
    // ignore
  }
}

function renderChips() {
  els.chips.innerHTML = "";
  recents.slice(0, 5).forEach((q) => {
    const chip = document.createElement("button");
    chip.type = "button";
    chip.className = "chip";
    chip.textContent = q;
    chip.addEventListener("click", () => {
      els.question.value = q;
      els.question.focus();
    });
    els.chips.appendChild(chip);
  });
}

function addRecent(question) {
  const q = question.trim();
  if (!q) return;
  recents = [q, ...recents.filter((x) => x !== q)].slice(0, 5);
  localStorage.setItem(RECENTS_KEY, JSON.stringify(recents));
  renderChips();
}

async function fetchTables() {
  els.refreshTables.disabled = true;
  try {
    const res = await fetch("/api/tables", { cache: "no-store" });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Failed");
    tableNames = data.tables || [];
    renderTablePicker();
  } catch {
    tableNames = [];
    renderTablePicker();
  } finally {
    els.refreshTables.disabled = false;
  }
}

function renderTablePicker() {
  const q = (els.tableSearch.value || "").toLowerCase().trim();
  const filtered = q ? tableNames.filter((t) => t.toLowerCase().includes(q)) : tableNames;
  els.tablePicker.innerHTML = "";

  filtered.forEach((name) => {
    const wrap = document.createElement("label");
    wrap.className = "table-option";

    const checkbox = document.createElement("input");
    checkbox.type = "checkbox";
    checkbox.checked = selectedTables.has(name);

    checkbox.addEventListener("change", () => {
      if (checkbox.checked) selectedTables.add(name);
      else selectedTables.delete(name);
      localStorage.setItem(SCOPE_KEY, JSON.stringify(Array.from(selectedTables)));
    });

    const code = document.createElement("code");
    code.textContent = name;

    wrap.appendChild(checkbox);
    wrap.appendChild(code);
    els.tablePicker.appendChild(wrap);
  });
}

function askStageForQuestion(question) {
  pendingStageQuestion = question;
  const options = [
    { value: "not_applied", label: "Not Applied" },
    { value: "closed_won_forecast", label: "Closed Won + Forecast" },
    { value: "forecast", label: "Forecast" },
    { value: "bridge", label: "Bridge" },
    { value: "upside", label: "Upside" },
    { value: "closed_won", label: "Closed Won" },
    { value: "pipeline", label: "Pipeline" },
  ];
  pushMessage("assistant", "Which stage scope should I use?", {
    kind: "stage_prompt",
    options,
  });
}

async function runQuery(questionOverride = null, opts = {}) {
  let rawQuestion = questionOverride ?? els.question.value ?? "";
  if (
    rawQuestion &&
    typeof rawQuestion === "object" &&
    "type" in rawQuestion &&
    "target" in rawQuestion
  ) {
    rawQuestion = els.question.value ?? "";
  }
  const question = String(rawQuestion).trim();
  if (!question) return;
  if (!opts.forceRun) {
    if (!activeChatId) {
      const c = newChat();
      chats.unshift(c);
      activeChatId = c.id;
    }
    // Always ask for stage selection per question.
    pushMessage("user", question);
    addRecent(question);
    askStageForQuestion(question);
    els.question.value = "";
    return;
  }
  if (!question) return;

  // Basic client-side visibility for debugging.
  console.log("[full_ui] sending question:", question);

  if (!activeChatId) {
    const c = newChat();
    chats.unshift(c);
    activeChatId = c.id;
  }

  setStatus("Running...");
  els.run.disabled = true;
  els.stop.disabled = false;

  setCopyButtonsEnabled(false);
  setApproveEnabled(false);
  if (els.approveStatus) els.approveStatus.textContent = "Not saved";
  setPanelText(els.prompt, "Working...");
  setPanelText(els.sql, "Working...");
  setPanelText(els.raw, "Working...");
  setPanelText(els.final, "Working...");
  setPanelText(els.validator, "Working...");
  setPanelText(els.debug, "Working...");
  els.results.textContent = "Working...";
  els.resultsMeta.textContent = "";
  els.timing.textContent = "";

  activeAbort = new AbortController();
  const started = performance.now();

  const payload = {
    query: question,
    ui: {
      scope_tables: Array.from(selectedTables),
      region: selectedRegion,
      reporting_currency: selectedCurrency,
      stage_bucket: selectedStageBucket,
    },
  };

  try {
    // Step 1: Question -> Intent
    const intentRes = await fetch("/api/intent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        query: question,
        region: selectedRegion,
        reporting_currency: selectedCurrency,
        stage_bucket: selectedStageBucket,
      }),
      signal: activeAbort.signal,
    });
    const intentData = await intentRes.json();
    console.log("[full_ui] /api/intent status:", intentRes.status, "ok:", intentRes.ok, intentData);

    if (!intentRes.ok) {
      lastResponse = { ok: false, status: intentRes.status, data: intentData, payload };
      setPanelText(els.prompt, intentData.detail || intentData.error || "Intent step failed");
      setPanelText(els.sql, "Error");
      setPanelText(els.raw, intentData.raw || "");
      setPanelText(els.final, intentData.error || "Intent step failed");
      setPanelText(els.validator, "Intent step failed");
      els.results.textContent = intentData.error || "Error";
      setPanelText(els.debug, JSON.stringify({ payload, intent_response: intentData }, null, 2));
      pushMessage("assistant", intentData.error || "Intent step failed");
      els.latest.textContent = intentData.error || "Intent step failed";
      setStatus("Failed");
      if (els.approveStatus) els.approveStatus.textContent = "Not saved";
      return;
    }

    const intent = intentData.intent;
    const route = intentData.route || intent?._route || "normal_intent";

    // Step 2: Intent -> SQL
    const res = await fetch("/api/sql_from_intent", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        intent,
        route,
        question,
        region: selectedRegion,
        reporting_currency: selectedCurrency,
        stage_bucket: selectedStageBucket,
        include_narrative: true,
      }),
      signal: activeAbort.signal,
    });

    const data = await res.json();
    console.log("[full_ui] /api/sql_from_intent status:", res.status, "ok:", res.ok, data);
    lastResponse = { ok: res.ok, status: res.status, data, payload: { ...payload, intent } };

    const elapsedMs = Math.round(performance.now() - started);
    els.timing.textContent = `${elapsedMs} ms`;

    if (!res.ok) {
      setPanelText(els.prompt, data.prompt || data.detail || data.error || "Error");
      setPanelText(els.sql, data.sql || "Error");
      setPanelText(els.raw, data.llm_raw || "");
      setPanelText(els.final, data.error || "Error");

      const issues = validateClientSide(data.sql || "");
      els.validatorMeta.textContent = issues.length ? "FAIL" : "";
      setPanelText(els.validator, issues.length ? issues.join("\n") : "Server rejected.");

      els.results.textContent = data.error || "Error";
      setPanelText(
        els.debug,
        JSON.stringify({ payload, intent_response: intentData, sql_response: data }, null, 2)
      );

      pushMessage("assistant", data.error || "Error");
      els.latest.textContent = data.error || "Error";
      setStatus("Failed");
      if (els.approveStatus) els.approveStatus.textContent = "Not saved";
      return;
    }

    setPanelText(els.prompt, data.prompt || "");
    setPanelText(els.sql, data.sql || "");
    setPanelText(els.raw, data.llm_raw || "");

    const issues = validateClientSide(data.sql || "");
    els.validatorMeta.textContent = issues.length ? "WARN" : "PASS";
    setPanelText(els.validator, issues.length ? issues.join("\n") : "OK");

    renderResults(data.columns || [], data.rows || []);

    const narrativeText = data.narrative ? tidyNarrative(data.narrative) : "";
    const fallbackText = buildChatAnswer(data.columns || [], data.rows || []);
    const answerText = narrativeText || fallbackText;
    setPanelText(els.final, answerText);
    els.latest.textContent = answerText || "";

    setPanelText(
      els.debug,
      JSON.stringify({ payload, intent_response: intentData, sql_response: data }, null, 2)
    );
    const presentation = choosePresentation(question, intent, data.columns || [], data.rows || []);
    const chartData =
      presentation === "bar" || presentation === "line"
        ? extractBarChartData(data.columns || [], data.rows || [])
        : null;
    if (chartData && presentation === "bar") {
      const metricLabel = chartData.metrics ? chartData.metrics.join(" vs ") : chartData.metric;
      pushMessage("assistant", `Bar chart (${metricLabel} by ${chartData.category})`, {
        kind: "bar_chart",
        chart: chartData,
      });
    } else if (chartData && presentation === "line") {
      const metricLabel = chartData.metrics ? chartData.metrics.join(" vs ") : chartData.metric;
      pushMessage("assistant", `Line chart (${metricLabel} over ${chartData.category})`, {
        kind: "line_chart",
        chart: chartData,
      });
    } else if (presentation === "table") {
      pushMessage("assistant", "", {
        kind: "table",
        table: { columns: data.columns || [], rows: data.rows || [] },
      });
    } else {
      pushMessage("assistant", answerText || "Done.");
    }

    // Snapshot placeholders: if the query returned one-row aggregates with obvious column names.
    if (data.columns && data.rows && data.rows.length === 1) {
      const row = data.rows[0];
      const colMap = {};
      data.columns.forEach((c, idx) => {
        colMap[String(c).toLowerCase()] = row[idx];
      });
      if (colMap.deals !== undefined) setIfPresent(els.statDeals, String(colMap.deals));
      if (colMap.total_revenue !== undefined) setIfPresent(els.statRevenue, String(colMap.total_revenue));
      if (colMap.pipeline_sum !== undefined) setIfPresent(els.statPipeline, String(colMap.pipeline_sum));
      if (colMap.closed_won_sum !== undefined) setIfPresent(els.statClosedWon, String(colMap.closed_won_sum));
    }

    setCopyButtonsEnabled(true);
    els.copySql.disabled = !(data.sql || "").trim();
    els.copyPrompt.disabled = !(data.prompt || "").trim();
    els.copyRaw.disabled = !(data.llm_raw || "").trim();
    setApproveEnabled(Boolean((data.sql || "").trim()));
    if (els.approveStatus) els.approveStatus.textContent = "Ready to save";

    setStatus("Done");
  } catch (e) {
    console.error("[full_ui] request failed:", e);
    const msg = e?.name === "AbortError" ? "Cancelled" : "Failed to fetch";
    setPanelText(els.final, msg);
    setPanelText(els.prompt, msg);
    setPanelText(els.sql, msg);
    setPanelText(els.raw, msg);
    setPanelText(els.validator, msg);
    els.results.textContent = msg;
    setPanelText(els.debug, JSON.stringify({ payload, error: String(e) }, null, 2));
    pushMessage("assistant", msg);
    els.latest.textContent = msg;
    setStatus("Failed");
    setApproveEnabled(false);
    if (els.approveStatus) els.approveStatus.textContent = "Not saved";
  } finally {
    els.run.disabled = false;
    els.stop.disabled = true;
    activeAbort = null;
  }
}

async function approveLatestExample() {
  if (!lastResponse?.ok || !lastResponse?.data?.sql || !lastResponse?.payload?.query) {
    if (els.approveStatus) els.approveStatus.textContent = "Nothing to approve";
    return;
  }
  const question = String(lastResponse.payload.query || "").trim();
  const sql = String(lastResponse.data.sql || "").trim();
  if (!question || !sql) {
    if (els.approveStatus) els.approveStatus.textContent = "Missing question/sql";
    return;
  }
  const route = String(lastResponse.data.route_used || "").trim();
  const tags = [
    "approved",
    route || "unknown_route",
    selectedRegion,
    selectedCurrency,
    selectedStageBucket,
  ];
  const notes = `Approved from full_ui. Final answer: ${String(els.final?.textContent || "").slice(0, 300)}`;
  try {
    if (els.approveStatus) els.approveStatus.textContent = "Saving...";
    const res = await fetch("/api/examples", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, sql, tags, notes }),
    });
    const data = await res.json();
    if (!res.ok) throw new Error(data.error || "Save failed");
    if (els.approveStatus) els.approveStatus.textContent = `Saved as #${data.id}`;
    setApproveEnabled(false);
  } catch (err) {
    if (els.approveStatus) els.approveStatus.textContent = `Save failed: ${err?.message || err}`;
  }
}

function render() {
  if (!activeChatId && chats.length) activeChatId = chats[0].id;
  renderChatList();
  renderChat();
  renderChips();
}

on(els.newChat, "click", () => {
  const c = newChat();
  chats.unshift(c);
  activeChatId = c.id;
  saveChats(chats);
  render();
  queueWelcomeMessages(c.id);
});

on(els.clearChats, "click", () => {
  chats = [];
  activeChatId = null;
  saveChats(chats);
  render();
});

on(els.run, "click", () => runQuery());
on(els.approveExample, "click", approveLatestExample);
on(els.stop, "click", () => {
  if (activeAbort) activeAbort.abort();
});

on(els.question, "keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    event.preventDefault();
    runQuery();
  }
});

on(els.toggleDetails, "click", () => {
  if (!els.details) return;
  els.details.hidden = !els.details.hidden;
});

on(els.copyPrompt, "click", () => copyText(els.prompt?.textContent || ""));
on(els.copySql, "click", () => copyText(els.sql?.textContent || ""));
on(els.copyRaw, "click", () => copyText(els.raw?.textContent || ""));

on(els.copyDebug, "click", () => {
  const bundle = {
    at: nowIso(),
    payload: lastResponse?.payload,
    response: lastResponse?.data,
  };
  copyText(JSON.stringify(bundle, null, 2));
});

on(els.downloadCsv, "click", () => {
  if (!lastResponse?.ok) return;
  const data = lastResponse.data;
  const csv = toCsv(data.columns || [], data.rows || []);
  const blob = new Blob([csv], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `results_${Date.now()}.csv`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  URL.revokeObjectURL(url);
});

on(els.tableSearch, "input", renderTablePicker);
on(els.refreshTables, "click", fetchTables);
on(els.copyScope, "click", () => copyText(Array.from(selectedTables).join("\n")));

on(els.copyLatest, "click", () => copyText(els.latest?.textContent || ""));
on(els.copyInsight, "click", () => {
  const text = [
    `Deals: ${els.statDeals?.textContent || "-"}`,
    `Total Revenue: ${els.statRevenue?.textContent || "-"}`,
    `Pipeline Sum: ${els.statPipeline?.textContent || "-"}`,
    `Closed Won Sum: ${els.statClosedWon?.textContent || "-"}`,
  ].join("\n");
  copyText(text);
});

on(els.runDemo, "click", () => {
  const rawIdx = Number(localStorage.getItem(CRO_DEMO_INDEX_KEY) || "0");
  const idx = Number.isFinite(rawIdx) ? rawIdx % CRO_DEMO_QUESTIONS.length : 0;
  const demo = CRO_DEMO_QUESTIONS[idx];
  localStorage.setItem(CRO_DEMO_INDEX_KEY, String((idx + 1) % CRO_DEMO_QUESTIONS.length));
  els.question.value = demo;
  els.details.hidden = true;
  runQuery();
});

on(els.loadMetricRules, "click", async () => {
  const cached = localStorage.getItem(METRIC_RULES_KEY);
  if (cached) {
    els.metricRules.value = cached;
    return;
  }
  try {
    const res = await fetch("/metric_rules.json", { cache: "no-store" });
    const text = await res.text();
    els.metricRules.value = text;
  } catch {
    els.metricRules.value = "";
  }
});

on(els.saveMetricRules, "click", () => {
  localStorage.setItem(METRIC_RULES_KEY, els.metricRules.value || "");
});

on(els.filterRegion, "change", () => {
  const value = (els.filterRegion.value || "GBR").toUpperCase();
  selectedRegion = value === "CAN" ? "CAN" : "GBR";
  localStorage.setItem(REGION_KEY, selectedRegion);
  syncCurrencyFromRegion();
  renderContextBadges();
  fetchKpiStrip();
});

on(els.filterStage, "change", () => {
  const value = (els.filterStage.value || "not_applied").toLowerCase();
  selectedStageBucket = ALLOWED_STAGE_BUCKETS.has(value) ? value : "not_applied";
  localStorage.setItem(STAGE_BUCKET_KEY, selectedStageBucket);
  renderContextBadges();
  fetchKpiStrip();
});

(function init() {
  console.log("[full_ui] init");
  initGlobalErrorHandlers();
  if (!els.run || !els.question) {
    setStatus("UI init failed: missing elements");
    return;
  }
  if (els.filterRegion) {
    els.filterRegion.value = selectedRegion === "CAN" ? "CAN" : "GBR";
  }
  syncCurrencyFromRegion();
  if (els.filterStage) {
    if (!ALLOWED_STAGE_BUCKETS.has(selectedStageBucket)) selectedStageBucket = "not_applied";
    els.filterStage.value = selectedStageBucket;
  }
  renderContextBadges();
  setStatus("Ready");
  if (!chats.length) {
    const c = newChat();
    chats = [c];
    activeChatId = c.id;
    saveChats(chats);
  }
  render();
  fetchKpiStrip();
  queueWelcomeMessages(activeChatId);
  fetchTables();
  window.__full_ui_booted = true;
})();
