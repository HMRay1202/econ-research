"use strict";

const state = {
  papers: [],
  selectedPaper: null,
  cards: [],
  chunks: new Map(),
  deepReads: [],
  usage: null,
};

const byId = (id) => document.getElementById(id);

async function api(path, options = {}) {
  const response = await fetch(path, options);
  if (!response.ok) {
    let detail = `${response.status} ${response.statusText}`;
    try {
      const body = await response.json();
      detail = body.detail || detail;
    } catch (_) {
      // A non-JSON failure still has a useful HTTP status.
    }
    throw new Error(detail);
  }
  return response.status === 204 ? null : response.json();
}

function showError(error) {
  const banner = byId("error-banner");
  banner.textContent = error instanceof Error ? error.message : String(error);
  banner.hidden = false;
  window.setTimeout(() => { banner.hidden = true; }, 7000);
}

function node(tag, className, text) {
  const element = document.createElement(tag);
  if (className) element.className = className;
  if (text !== undefined) element.textContent = text;
  return element;
}

function formatDate(value) {
  return value ? new Intl.DateTimeFormat("zh-CN", {
    dateStyle: "medium", timeStyle: "short",
  }).format(new Date(value)) : "未知时间";
}

function formatMoney(value) {
  return `$${Number(value || 0).toFixed(6)}`;
}

async function refreshHeader() {
  try {
    const [health, usage] = await Promise.all([api("/health"), api("/api/usage")]);
    byId("health-pill").textContent = health.status === "ok" ? "本地服务正常" : "服务异常";
    byId("call-total").textContent = usage.summary.call_count;
    byId("cost-total").textContent = formatMoney(usage.summary.estimated_cost_usd);
  } catch (error) {
    byId("health-pill").textContent = "连接失败";
    showError(error);
  }
}

async function loadPapers(selectId = null) {
  try {
    state.papers = await api("/api/papers");
    byId("paper-total").textContent = state.papers.length;
    renderPaperList();
    const target = selectId || state.selectedPaper?.id || state.papers[0]?.id;
    if (target) await selectPaper(target);
  } catch (error) {
    showError(error);
  }
}

function renderPaperList() {
  const list = byId("paper-list");
  list.replaceChildren();
  if (!state.papers.length) {
    list.append(node("p", "muted", "还没有论文。请导入第一份 PDF。"));
    return;
  }
  for (const paper of state.papers) {
    const button = node("button", "paper-item");
    button.type = "button";
    button.classList.toggle("active", paper.id === state.selectedPaper?.id);
    button.append(
      node("strong", "", paper.title || paper.source_filename),
      node("small", "", `${paper.status} · ${paper.year || "年份未知"}`),
    );
    button.addEventListener("click", () => selectPaper(paper.id));
    list.append(button);
  }
}

async function selectPaper(paperId) {
  const paper = state.papers.find((item) => item.id === paperId);
  if (!paper) return;
  state.selectedPaper = paper;
  renderPaperList();
  byId("welcome-panel").hidden = true;
  byId("paper-workspace").hidden = false;
  byId("paper-title").textContent = paper.title || paper.source_filename;
  byId("paper-status").textContent = `${paper.status.toUpperCase()} · ${paper.source_filename}`;
  byId("paper-meta").textContent = [
    paper.authors?.join(", "), paper.year, `ID ${paper.id}`,
  ].filter(Boolean).join(" · ");
  byId("original-link").href = `/api/papers/${paper.id}/files/original`;
  byId("parsed-link").href = `/api/papers/${paper.id}/files/parsed`;
  try {
    const [cards, chunks, deepReads, usage] = await Promise.all([
      api(`/api/papers/${paper.id}/cards`),
      api(`/api/papers/${paper.id}/chunks`),
      api(`/api/papers/${paper.id}/deep-reads`),
      api(`/api/papers/${paper.id}/usage?include_calls=true`),
    ]);
    state.cards = cards;
    state.chunks = new Map(chunks.map((chunk) => [chunk.ordinal, chunk]));
    state.deepReads = deepReads;
    state.usage = usage;
    populateCardTypes();
    renderCards();
    renderDeepReads();
    renderUsage();
  } catch (error) {
    showError(error);
  }
}

function populateCardTypes() {
  const select = byId("card-type-filter");
  const current = select.value;
  select.replaceChildren(new Option("全部类型", ""));
  const types = [...new Set(state.cards.map((card) => card.type))].sort();
  for (const type of types) select.add(new Option(type, type));
  select.value = types.includes(current) ? current : "";
}

function renderCards() {
  const list = byId("card-list");
  const type = byId("card-type-filter").value;
  const query = byId("card-text-filter").value.trim().toLowerCase();
  const cards = state.cards.filter((card) => {
    const matchesType = !type || card.type === type;
    const haystack = [card.title, card.content, card.section, ...(card.tags || [])]
      .filter(Boolean).join(" ").toLowerCase();
    return matchesType && (!query || haystack.includes(query));
  });
  byId("card-count").textContent = cards.length;
  list.replaceChildren();
  if (!cards.length) {
    list.append(node("p", "muted", "没有符合当前条件的卡片。"));
    return;
  }
  for (const card of cards) {
    const article = node("article", "research-card");
    const top = node("div", "card-topline");
    top.append(node("span", "badge", card.type), node("span", "claim", card.claim_kind));
    article.append(top, node("h4", "", card.title), node("p", "", card.content));
    const tags = node("div", "tags");
    for (const tag of card.tags || []) tags.append(node("span", "tag", `#${tag}`));
    article.append(tags);
    const provenance = node("div", "provenance");
    const parts = [card.section, card.chunk_ordinal !== null ? `chunk ${card.chunk_ordinal}` : null]
      .filter(Boolean);
    provenance.append(node("span", "", parts.join(" · ") || "未提供来源定位"));
    if (card.chunk_ordinal !== null && state.chunks.has(card.chunk_ordinal)) {
      const sourceButton = node("button", "source-button", "查看原文依据");
      sourceButton.type = "button";
      sourceButton.addEventListener("click", () => showSource(card.chunk_ordinal));
      provenance.append(document.createTextNode(" · "), sourceButton);
    }
    article.append(provenance);
    list.append(article);
  }
}

function showSource(ordinal) {
  const chunk = state.chunks.get(ordinal);
  if (!chunk) return;
  byId("source-title").textContent = chunk.section || `Chunk ${ordinal}`;
  byId("source-content").textContent = chunk.text;
  byId("source-dialog").showModal();
}

function renderDeepReads() {
  const list = byId("deep-read-list");
  list.replaceChildren();
  if (!state.deepReads.length) {
    list.append(node("p", "muted", "尚未生成深读报告。"));
    return;
  }
  for (const report of state.deepReads) {
    const button = node("button", "report-item");
    button.type = "button";
    button.append(
      node("strong", "", report.focus || "综合深读"),
      node("small", "", formatDate(report.created_at)),
    );
    button.addEventListener("click", () => openReport(report.id));
    list.append(button);
  }
}

async function openReport(reportId) {
  try {
    const report = await api(`/api/deep-reads/${reportId}`);
    byId("report-title").textContent = report.focus || "综合深读";
    byId("report-content").textContent = report.report;
    const download = byId("report-download");
    download.href = `/api/deep-reads/${report.id}/download`;
    download.hidden = false;
  } catch (error) {
    showError(error);
  }
}

function renderUsage() {
  if (!state.usage) return;
  const summary = state.usage.summary;
  const metrics = [
    [summary.call_count, "调用次数"],
    [summary.total_tokens.toLocaleString(), "总 tokens"],
    [summary.input_tokens.toLocaleString(), "输入 tokens"],
    [summary.output_tokens.toLocaleString(), "输出 tokens"],
    [`${(summary.total_duration_ms / 1000).toFixed(2)}s`, "累计耗时"],
    [formatMoney(summary.estimated_cost_usd), "估算费用"],
  ];
  const cards = byId("usage-summary");
  cards.replaceChildren();
  for (const [value, label] of metrics) {
    const metric = node("div", "metric-card");
    metric.append(node("strong", "", value), node("span", "", label));
    cards.append(metric);
  }
  const wrapper = byId("usage-calls");
  wrapper.replaceChildren();
  if (!state.usage.calls?.length) {
    wrapper.append(node("p", "muted", "遥测启用后尚无可显示的调用。"));
    return;
  }
  const table = node("table");
  const head = node("thead");
  const headerRow = node("tr");
  for (const label of ["时间", "操作", "模型", "输入", "输出", "耗时", "费用", "状态"])
    headerRow.append(node("th", "", label));
  head.append(headerRow);
  const body = node("tbody");
  for (const call of state.usage.calls) {
    const row = node("tr");
    const values = [
      formatDate(call.started_at), call.operation, call.model,
      call.input_tokens.toLocaleString(), call.output_tokens.toLocaleString(),
      `${(call.duration_ms / 1000).toFixed(2)}s`,
      call.estimated_cost_usd === null ? "未定价" : formatMoney(call.estimated_cost_usd),
      call.status,
    ];
    for (const value of values) row.append(node("td", "", value));
    body.append(row);
  }
  table.append(head, body);
  wrapper.append(table);
}

function activateTab(name) {
  for (const tab of document.querySelectorAll(".tab"))
    tab.classList.toggle("active", tab.dataset.tab === name);
  for (const panel of document.querySelectorAll(".tab-panel"))
    panel.hidden = panel.id !== `${name}-panel`;
}

async function uploadPaper(event) {
  event.preventDefault();
  const input = byId("pdf-file");
  if (!input.files.length) return;
  const button = byId("upload-button");
  button.disabled = true;
  button.textContent = "正在解析并生成卡片…";
  try {
    const form = new FormData();
    form.append("file", input.files[0]);
    const result = await api("/api/papers", { method: "POST", body: form });
    input.value = "";
    byId("selected-file").textContent = result.duplicate ? "该论文已存在。" : "导入完成。";
    await Promise.all([loadPapers(result.paper.id), refreshHeader()]);
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
    button.textContent = "导入并生成卡片";
  }
}

async function generateDeepRead(event) {
  event.preventDefault();
  if (!state.selectedPaper) return;
  if (!window.confirm("这会调用 Terra 并产生费用。确认继续吗？")) return;
  const button = byId("deep-read-button");
  button.disabled = true;
  button.textContent = "Terra 正在深读…";
  try {
    const focus = byId("deep-read-focus").value.trim() || null;
    const report = await api(`/api/papers/${state.selectedPaper.id}/deep-read`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ focus }),
    });
    byId("report-title").textContent = report.focus || "综合深读";
    byId("report-content").textContent = report.report;
    byId("report-download").href = `/api/deep-reads/${report.id}/download`;
    byId("report-download").hidden = false;
    await Promise.all([selectPaper(state.selectedPaper.id), refreshHeader()]);
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
    button.textContent = "调用 Terra";
  }
}

async function runSearch(event) {
  event.preventDefault();
  const query = byId("search-query").value.trim();
  if (!query) return;
  try {
    const results = await api(`/api/search?q=${encodeURIComponent(query)}&limit=50`);
    const container = byId("search-results");
    container.replaceChildren();
    if (!results.length) container.append(node("p", "muted", "没有找到匹配结果。"));
    for (const result of results) {
      const item = node("article", "search-result");
      const button = node("button", "", result.title || `${result.entity_type} result`);
      button.type = "button";
      button.addEventListener("click", async () => {
        await selectPaper(result.paper_id);
        byId("search-panel").hidden = true;
      });
      item.append(
        node("span", "badge", result.entity_type),
        document.createTextNode(" "),
        button,
        node("p", "", result.snippet),
      );
      container.append(item);
    }
    byId("search-panel").hidden = false;
  } catch (error) {
    showError(error);
  }
}

function wireEvents() {
  byId("upload-form").addEventListener("submit", uploadPaper);
  byId("pdf-file").addEventListener("change", (event) => {
    byId("selected-file").textContent = event.target.files[0]?.name || "尚未选择文件";
  });
  byId("refresh-papers").addEventListener("click", () => loadPapers());
  byId("card-type-filter").addEventListener("change", renderCards);
  byId("card-text-filter").addEventListener("input", renderCards);
  byId("deep-read-form").addEventListener("submit", generateDeepRead);
  byId("search-form").addEventListener("submit", runSearch);
  byId("close-search").addEventListener("click", () => { byId("search-panel").hidden = true; });
  byId("close-source").addEventListener("click", () => byId("source-dialog").close());
  for (const tab of document.querySelectorAll(".tab"))
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
}

async function start() {
  wireEvents();
  await Promise.all([refreshHeader(), loadPapers()]);
}

start();
