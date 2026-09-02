"use strict";

const state = {
  papers: [],
  selectedPaper: null,
  cards: [],
  chunks: new Map(),
  deepReads: [],
  usage: null,
  uploadJobs: new Map(),
  uploadEvents: new Map(),
};

const byId = (id) => document.getElementById(id);

const markdownRenderer = new marked.Renderer();
markdownRenderer.html = () => "";

const markdownSanitizerOptions = {
  ALLOWED_TAGS: [
    "a", "blockquote", "br", "code", "del", "em", "h1", "h2", "h3", "h4", "h5", "h6",
    "hr", "li", "ol", "p", "pre", "s", "strong", "table", "tbody", "td", "th", "thead",
    "tr", "ul",
  ],
  ALLOWED_ATTR: ["href", "title"],
  ALLOWED_URI_REGEXP: /^(?:(?:https?|mailto):|[^a-z]|[a-z+.-]+(?:[^a-z+.-:]|$))/i,
};

const mathDelimiterPlaceholders = {
  displayOpen: "\uE000econ-research-display-open\uE001",
  displayClose: "\uE000econ-research-display-close\uE001",
  inlineOpen: "\uE000econ-research-inline-open\uE001",
  inlineClose: "\uE000econ-research-inline-close\uE001",
};

function preserveMathDelimiters(markdown) {
  return markdown
    .replaceAll("\\[", mathDelimiterPlaceholders.displayOpen)
    .replaceAll("\\]", mathDelimiterPlaceholders.displayClose)
    .replaceAll("\\(", mathDelimiterPlaceholders.inlineOpen)
    .replaceAll("\\)", mathDelimiterPlaceholders.inlineClose);
}

function restoreMathDelimiters(html) {
  return html
    .replaceAll(mathDelimiterPlaceholders.displayOpen, "\\[")
    .replaceAll(mathDelimiterPlaceholders.displayClose, "\\]")
    .replaceAll(mathDelimiterPlaceholders.inlineOpen, "\\(")
    .replaceAll(mathDelimiterPlaceholders.inlineClose, "\\)");
}

DOMPurify.addHook("afterSanitizeAttributes", (element) => {
  if (element.tagName === "A" && element.hasAttribute("href")) {
    element.setAttribute("target", "_blank");
    element.setAttribute("rel", "noopener noreferrer");
  }
});

function linkChunkReferences(container) {
  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const textNodes = [];
  while (walker.nextNode()) textNodes.push(walker.currentNode);
  for (const textNode of textNodes) {
    if (textNode.parentElement?.closest("a, code, pre")) continue;
    const parts = textNode.textContent.split(/(\[chunk\s+\d+\])/gi);
    if (parts.length === 1) continue;
    const fragment = document.createDocumentFragment();
    for (const part of parts) {
      const match = /^\[chunk\s+(\d+)\]$/i.exec(part);
      const ordinal = match ? Number(match[1]) : null;
      if (ordinal !== null && state.chunks.has(ordinal)) {
        const button = node("button", "chunk-reference", part);
        button.type = "button";
        button.addEventListener("click", () => showSource(ordinal));
        fragment.append(button);
      } else {
        fragment.append(document.createTextNode(part));
      }
    }
    textNode.replaceWith(fragment);
  }
}

function renderMarkdown(container, markdown) {
  const unsafeHtml = marked.parse(preserveMathDelimiters(markdown), {
    gfm: true,
    breaks: false,
    renderer: markdownRenderer,
  });
  const safeHtml = restoreMathDelimiters(DOMPurify.sanitize(unsafeHtml, markdownSanitizerOptions));
  const fragment = document.createRange().createContextualFragment(safeHtml);
  container.replaceChildren(fragment);
  linkChunkReferences(container);
  renderMathInElement(container, {
    delimiters: [
      { left: "$$", right: "$$", display: true },
      { left: "\\[", right: "\\]", display: true },
      { left: "$", right: "$", display: false },
      { left: "\\(", right: "\\)", display: false },
    ],
    ignoredTags: ["code", "option", "pre", "script", "style", "textarea"],
    strict: "warn",
    throwOnError: false,
    trust: false,
  });
  replaceMathErrors(container);
}

function replaceMathErrors(container) {
  for (const error of container.querySelectorAll(".katex-error")) {
    const fallback = node("div", "formula-fallback");
    const notice = node("small", "muted", "公式无法安全渲染；请核对原始 PDF。显示未验证 LaTeX：");
    const pre = document.createElement("pre");
    const code = document.createElement("code");
    code.className = "language-latex";
    code.textContent = error.textContent || "[LaTeX rendering failed]";
    pre.append(code);
    fallback.append(notice, pre);
    error.replaceWith(fallback);
  }
}

function renderCardContent(container, markdown) {
  renderMarkdown(container, markdown);
}

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

function renderUploadJobs() {
  const list = byId("upload-jobs");
  list.replaceChildren();
  for (const job of state.uploadJobs.values()) {
    const row = node("div", "upload-job");
    const label = node("span", "", `${job.source_filename} · ${job.stage}`);
    const progress = document.createElement("progress");
    progress.max = 100;
    progress.value = job.progress;
    const detail = node(
      "small", "muted",
      `${job.progress}% · ${job.message || "正在等待后台更新。"}${job.error ? ` · ${job.error}` : ""}`,
    );
    const timestamps = node(
      "small", "muted upload-timing",
      `已运行 ${formatElapsed(job.started_at || job.created_at)} · 最近更新 ${formatDate(job.updated_at)}`,
    );
    const events = state.uploadEvents.get(job.id) || [];
    const timeline = node("ol", "upload-events");
    events.slice(-4).reverse().forEach((event) => {
      timeline.append(node("li", "", `${formatDate(event.created_at)} · ${event.message}`));
    });
    row.append(label, progress, detail, timestamps);
    if (timeline.childElementCount) row.append(timeline);
    list.append(row);
  }
}

function formatElapsed(startedAt) {
  if (!startedAt) return "刚刚开始";
  const seconds = Math.max(0, Math.floor((Date.now() - new Date(startedAt).getTime()) / 1000));
  return seconds < 60 ? `${seconds} 秒` : `${Math.floor(seconds / 60)} 分 ${seconds % 60} 秒`;
}

async function loadUploadEvents(jobId) {
  const events = await api(`/api/uploads/${jobId}/events`);
  state.uploadEvents.set(jobId, events);
}

function uploadWithProgress(file) {
  return new Promise((resolve, reject) => {
    const request = new XMLHttpRequest();
    const form = new FormData();
    form.append("file", file);
    request.open("POST", "/api/uploads");
    request.responseType = "json";
    request.upload.onprogress = (event) => {
      if (!event.lengthComputable) return;
      state.uploadJobs.set(`local:${file.name}`, {
        source_filename: file.name, stage: "uploading", progress: Math.round(event.loaded / event.total * 20),
      });
      renderUploadJobs();
    };
    request.onerror = () => reject(new Error("上传连接中断，请检查本地服务终端。"));
    request.onload = () => {
      const body = request.response || {};
      if (request.status >= 200 && request.status < 300) resolve(body);
      else reject(new Error(body.detail || `${request.status} ${request.statusText}`));
    };
    request.send(form);
  });
}

async function watchUpload(job) {
  state.uploadJobs.delete(`local:${job.source_filename}`);
  state.uploadJobs.set(job.id, job);
  renderUploadJobs();
  while (["queued", "running"].includes(job.status)) {
    await new Promise((resolve) => window.setTimeout(resolve, 2000));
    job = await api(`/api/uploads/${job.id}`);
    await loadUploadEvents(job.id);
    state.uploadJobs.set(job.id, job);
    renderUploadJobs();
  }
  if (job.status === "succeeded") {
    await Promise.all([loadPapers(job.paper_id), refreshHeader(), loadGlobalUsage()]);
    if (job.duplicate_of) {
      byId("selected-file").textContent = job.paper_id === job.duplicate_of
        ? "文件已存在，已打开原有论文。"
        : "已导入；系统发现可能是已有论文的另一份版本，请在论文库中核对。";
    }
  } else if (job.status !== "interrupted") {
    showError(`${job.source_filename}: ${job.error || "导入失败"}`);
  }
}

async function restoreUploadJobs() {
  const jobs = await api("/api/uploads");
  await Promise.all(jobs.map(async (job) => {
    state.uploadJobs.set(job.id, job);
    await loadUploadEvents(job.id);
  }));
  renderUploadJobs();
  jobs.forEach((job) => { void watchUpload(job); });
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
    const includeArchived = byId("include-archived")?.checked;
    state.papers = await api(`/api/papers?include_archived=${includeArchived ? "true" : "false"}`);
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
  byId("archive-paper").textContent = paper.archived_at
    ? "恢复已移除论文"
    : "移除论文（可恢复）";
  byId("paper-meta").textContent = [
    paper.authors?.join(", "), paper.year,
    paper.title_source === "manual" ? "手动标题" : null,
    paper.year_source === "manual" ? "手动年份" : null,
    formulaSummary(paper),
    `ID ${paper.id}`,
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

function formulaSummary(paper) {
  if (paper.formula_status === "not_run" || paper.formula_status === "disabled") return null;
  const summary = `公式：发现 ${paper.formula_detected || 0}，识别 ${paper.formula_recognized || 0}`;
  if (paper.formula_status === "unavailable") return `${summary}（${paper.formula_error || "公式依赖不可用"}）`;
  if (paper.formula_fallback) return `${summary}，回退 ${paper.formula_fallback}（${paper.formula_error || "识别失败"}）`;
  return summary;
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
    const content = node("div", "card-content");
    renderCardContent(content, card.content);
    article.append(top, node("h4", "", card.title), content);
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
  renderMarkdown(byId("source-content"), chunk.text);
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
    renderMarkdown(byId("report-content"), report.report);
    const download = byId("report-download");
    download.href = `/api/deep-reads/${report.id}/download`;
    download.hidden = false;
  } catch (error) {
    showError(error);
  }
}

function renderUsage() {
  if (!state.usage) return;
  renderUsageReport(state.usage, "usage-summary", "usage-calls");
}

function renderUsageReport(report, summaryId, callsId) {
  const summary = report.summary;
  const metrics = [
    [summary.call_count, "调用次数"],
    [summary.total_tokens.toLocaleString(), "总 tokens"],
    [summary.input_tokens.toLocaleString(), "输入 tokens"],
    [summary.output_tokens.toLocaleString(), "输出 tokens"],
    [`${(summary.total_duration_ms / 1000).toFixed(2)}s`, "累计耗时"],
    [formatMoney(summary.estimated_cost_usd), "估算费用"],
  ];
  const cards = byId(summaryId);
  cards.replaceChildren();
  for (const [value, label] of metrics) {
    const metric = node("div", "metric-card");
    metric.append(node("strong", "", value), node("span", "", label));
    cards.append(metric);
  }
  const wrapper = byId(callsId);
  wrapper.replaceChildren();
  if (!report.calls?.length) {
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
  for (const call of report.calls) {
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

async function loadGlobalUsage() {
  try {
    const report = await api("/api/usage?include_calls=true");
    renderUsageReport(report, "global-usage-summary", "global-usage-calls");
  } catch (error) {
    showError(error);
  }
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
  button.textContent = "正在加入队列…";
  try {
    const jobs = [];
    for (const file of input.files) jobs.push(await uploadWithProgress(file));
    input.value = "";
    byId("selected-file").textContent = `已加入 ${jobs.length} 个导入任务。`;
    jobs.forEach((job) => { void watchUpload(job); });
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
    button.textContent = "加入导入队列";
  }
}

async function regenerateCards() {
  if (!state.selectedPaper) return;
  if (!window.confirm("这会调用 Luna 并产生费用。确认重新生成当前论文的卡片吗？")) return;
  const button = byId("regenerate-cards");
  button.disabled = true;
  try {
    const result = await api(`/api/papers/${state.selectedPaper.id}/card-generations`, { method: "POST" });
    if (result.status === "failed") showError(result.error || "卡片生成失败，可稍后重试。");
    await selectPaper(state.selectedPaper.id);
    await Promise.all([refreshHeader(), loadGlobalUsage()]);
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
  }
}

async function reparsePaper() {
  if (!state.selectedPaper) return;
  if (!window.confirm("将从保留的原始 PDF 重新解析正文和公式，不调用 LLM，也不会自动重新生成卡片。继续吗？")) return;
  const button = byId("reparse-paper");
  button.disabled = true;
  button.textContent = "正在解析…";
  try {
    await api(`/api/papers/${state.selectedPaper.id}/reparse`, { method: "POST" });
    await loadPapers(state.selectedPaper.id);
  } catch (error) {
    showError(error);
  } finally {
    button.disabled = false;
    button.textContent = "重新解析公式";
  }
}

async function editPaperTitle() {
  if (!state.selectedPaper) return;
  const title = window.prompt("输入论文标题：", state.selectedPaper.title || "");
  if (title === null) return;
  try {
    const updated = await api(`/api/papers/${state.selectedPaper.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ title }),
    });
    await loadPapers(updated.id);
  } catch (error) {
    showError(error);
  }
}

async function editPaperYear() {
  if (!state.selectedPaper) return;
  const value = window.prompt(
    "输入出版年份（1000–2100）；留空可清除年份：",
    state.selectedPaper.year ?? "",
  );
  if (value === null) return;
  const trimmed = value.trim();
  if (trimmed && !/^\d{4}$/.test(trimmed)) {
    showError("年份须为四位数字，或留空清除。");
    return;
  }
  try {
    const updated = await api(`/api/papers/${state.selectedPaper.id}`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ year: trimmed ? Number(trimmed) : null }),
    });
    await loadPapers(updated.id);
  } catch (error) {
    showError(error);
  }
}

async function archivePaper() {
  if (!state.selectedPaper) return;
  const archived = Boolean(state.selectedPaper.archived_at);
  if (!window.confirm(
    archived ? "确认恢复这篇论文吗？" : "移除后论文将从默认列表隐藏，但不会删除原始文件或历史记录。确认继续吗？"
  )) return;
  try {
    const path = archived
      ? `/api/papers/${state.selectedPaper.id}/restore`
      : `/api/papers/${state.selectedPaper.id}`;
    await api(path, { method: archived ? "POST" : "DELETE" });
    if (!archived) {
      state.selectedPaper = null;
      byId("paper-workspace").hidden = true;
      byId("welcome-panel").hidden = false;
    }
    await loadPapers(archived ? state.selectedPaper?.id : null);
  } catch (error) {
    showError(error);
  }
}

async function permanentlyDeletePaper() {
  if (!state.selectedPaper) return;
  const confirmation = window.prompt(
    `这会永久删除“${state.selectedPaper.title || state.selectedPaper.source_filename}”及其 PDF、解析文本、卡片、精读报告和调用记录。\n\n输入 DELETE 确认：`
  );
  if (confirmation !== "DELETE") return;
  try {
    await api(`/api/papers/${state.selectedPaper.id}/purge`, { method: "DELETE" });
    state.selectedPaper = null;
    byId("paper-workspace").hidden = true;
    byId("welcome-panel").hidden = false;
    await Promise.all([loadPapers(), refreshHeader(), loadGlobalUsage()]);
  } catch (error) {
    showError(error);
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
    renderMarkdown(byId("report-content"), report.report);
    byId("report-download").href = `/api/deep-reads/${report.id}/download`;
    byId("report-download").hidden = false;
    await Promise.all([selectPaper(state.selectedPaper.id), refreshHeader(), loadGlobalUsage()]);
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
    byId("selected-file").textContent = event.target.files.length
      ? `已选择 ${event.target.files.length} 个文件` : "尚未选择文件";
  });
  byId("refresh-papers").addEventListener("click", () => loadPapers());
  byId("include-archived").addEventListener("change", () => loadPapers());
  byId("refresh-global-usage").addEventListener("click", loadGlobalUsage);
  byId("card-type-filter").addEventListener("change", renderCards);
  byId("card-text-filter").addEventListener("input", renderCards);
  byId("deep-read-form").addEventListener("submit", generateDeepRead);
  byId("edit-paper-title").addEventListener("click", editPaperTitle);
  byId("edit-paper-year").addEventListener("click", editPaperYear);
  byId("reparse-paper").addEventListener("click", reparsePaper);
  byId("regenerate-cards").addEventListener("click", regenerateCards);
  byId("archive-paper").addEventListener("click", archivePaper);
  byId("delete-paper").addEventListener("click", permanentlyDeletePaper);
  byId("search-form").addEventListener("submit", runSearch);
  byId("close-search").addEventListener("click", () => { byId("search-panel").hidden = true; });
  byId("close-source").addEventListener("click", () => byId("source-dialog").close());
  for (const tab of document.querySelectorAll(".tab"))
    tab.addEventListener("click", () => activateTab(tab.dataset.tab));
}

async function start() {
  wireEvents();
  await Promise.all([refreshHeader(), loadPapers(), loadGlobalUsage(), restoreUploadJobs()]);
}

start();
