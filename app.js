const runButton = document.getElementById("run");
const questionInput = document.getElementById("question");
const statusEl = document.getElementById("status");
const promptEl = document.getElementById("prompt");
const sqlEl = document.getElementById("sql");
const llmRawEl = document.getElementById("llm-raw");
const resultsEl = document.getElementById("results");
const narrativeEl = document.getElementById("narrative");
const finalAnswerEl = document.getElementById("final-answer");

function setStatus(text) {
  statusEl.textContent = text;
}

function formatCellForDisplay(colName, cell) {
  if (cell === null || cell === undefined) return "";
  const c = String(colName || "").toLowerCase();
  const isThousands = c.includes("thousand") || c.endsWith("_k");
  if (!isThousands) return String(cell);
  const n = Number(cell);
  if (!Number.isFinite(n)) return String(cell);
  return `${Math.round(n)}K`;
}

function renderResults(columns, rows) {
  if (!columns || !columns.length) {
    resultsEl.textContent = "No results.";
    return;
  }
  const table = document.createElement("table");
  table.className = "results-table";
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
  rows.forEach((row) => {
    const tr = document.createElement("tr");
    row.forEach((cell, idx) => {
      const td = document.createElement("td");
      td.textContent = formatCellForDisplay(columns[idx], cell);
      tr.appendChild(td);
    });
    tbody.appendChild(tr);
  });
  table.appendChild(tbody);

  resultsEl.innerHTML = "";
  resultsEl.appendChild(table);
}

async function runQuery() {
  const question = questionInput.value.trim();
  if (!question) return;
  setStatus("Running...");
  promptEl.textContent = "Working...";
  sqlEl.textContent = "Working...";
  if (llmRawEl) llmRawEl.textContent = "Working...";
  resultsEl.textContent = "Working...";
  narrativeEl.textContent = "Working...";
  if (finalAnswerEl) finalAnswerEl.textContent = "Working...";

  try {
    const response = await fetch("/api/sql", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query: question }),
    });
    const data = await response.json();
    if (!response.ok) {
      promptEl.textContent = data.detail || data.error || "Error";
      sqlEl.textContent = data.sql || "Error";
      if (llmRawEl) llmRawEl.textContent = data.llm_raw || "";
      resultsEl.textContent = data.error || "Error";
      narrativeEl.textContent = data.error || "Error";
      if (finalAnswerEl) finalAnswerEl.textContent = data.error || "Error";
      setStatus("Failed");
      return;
    }
    promptEl.textContent = data.prompt || "";
    sqlEl.textContent = data.sql || "";
    if (llmRawEl) llmRawEl.textContent = data.llm_raw || "";
    renderResults(data.columns || [], data.rows || []);
    narrativeEl.textContent = data.narrative || "";
    if (finalAnswerEl) finalAnswerEl.textContent = data.narrative || "";
    setStatus("Done");
  } catch (err) {
    promptEl.textContent = "Error";
    sqlEl.textContent = "Error";
    if (llmRawEl) llmRawEl.textContent = "Error";
    resultsEl.textContent = "Failed to fetch";
    narrativeEl.textContent = "Failed to fetch";
    if (finalAnswerEl) finalAnswerEl.textContent = "Failed to fetch";
    setStatus("Failed");
  }
}

runButton.addEventListener("click", runQuery);
questionInput.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && (event.ctrlKey || event.metaKey)) {
    runQuery();
  }
});
