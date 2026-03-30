const LANG_STORAGE_KEY = "operator_ui.language";

const translations = {
  zh: {
    pageTitle: "运营工作台仪表盘",
    rail: { operator: "运营", controlSurface: "控制台" },
    masthead: {
      eyebrow: "Phase 6 运营工作台仪表盘",
      title: "运营工作台与运行态 Shell",
      copy: "在同一个仪表化控制面中完成运营卡分诊、复核压力检查，以及运行证据审计。",
    },
    aria: { languageSwitch: "语言切换", modeSwitch: "运营控制面模式" },
    lang: { zh: "中文", en: "EN" },
    mode: { workspace: "运营工作台", runtime: "运行态 Shell" },
    hero: {
      waiting: "正在等待工作台数据",
      workspaceReady: "工作台已就绪",
      selectedRun: "已选择 {runId}",
      selectedCard: "运营卡 {cardId}",
      runtimeLaneFailed: "运行态通道失败",
      workspaceLoadFailed: "工作台载入失败",
      initialLoadFailed: "初始载入失败",
    },
    common: { refresh: "刷新", na: "未提供", all: "全部", open: "打开", closed: "已关闭", yes: "是", no: "否", none: "无" },
    status: {
      pass: "通过", warn: "告警", fail: "失败", failed: "失败", blocked: "阻塞", running: "运行中", pending: "等待中", unknown: "未知",
      success: "通过", completed: "已完成", open: "打开", closed: "已关闭", all: "全部",
    },
    workspace: {
      kicker: "运营工作台", overviewTitle: "总览信号带", waiting: "工作台正在等待运营数据。", emptyOverview: "尚未载入工作台总览。",
      inboxKicker: "运营收件箱", inboxTitle: "跨 Run 卡片", emptyCardsLoaded: "尚未载入运营卡片。", emptyCardsFiltered: "当前筛选条件下没有运营卡片。",
      selectedCardKicker: "当前卡片", noCardSelected: "尚未选择运营卡片", selectCardHint: "选择一张运营卡片以查看决策上下文。", openRuntimeButton: "打开 Runtime 通道",
      decisionTitle: "决策上下文", emptyDecision: "尚未载入决策上下文。", reviewKicker: "复核负载", reviewTitle: "复核负载", emptyReview: "尚未载入复核负载。",
      kpiKicker: "KPI 快照", kpiTitle: "KPI 快照", emptyKpi: "尚未载入 KPI 快照。", driftKicker: "治理漂移", driftTitle: "治理漂移", emptyDrift: "尚未载入治理漂移。",
      refreshing: "正在刷新运营工作台...", refreshed: "运营工作台已刷新。", noDecisionTitle: "当前无需运营决策", noDecisionSummary: "这个 run 当前没有需要继续跟进的运营卡。",
      crossLaneHint: "跨通道钻取仍然锚定到运行态产物检查器。",
    },
    filters: {
      status: "状态", cardType: "卡片类型", priority: "优先级", targetLocale: "目标语言区域", targetLocalePlaceholder: "如 en-US", all: "全部",
      status_open: "打开", status_all: "全部", status_closed: "已关闭",
    },
    runtime: {
      launcherKicker: "启动器", launcherTitle: "代表性 Smoke Run", launcherHint: "默认沿用当前 pipeline 的既有参数。", inputCsv: "输入 CSV", inputPlaceholder: "输入 CSV 路径",
      targetLanguage: "目标语言", verifyMode: "验证模式", verifyModeFull: "完整", verifyModePreflight: "预检", launchButton: "启动 Run",
      recentRunsKicker: "最近 Run", timelineTitle: "Run 时间线", selectedRunKicker: "当前 Run", noRunSelected: "尚未选择 Run", runHint: "选择一个 run 以检查阶段状态和证据。",
      emptyTimeline: "尚未选择 run。", emptyTimelineData: "这个 run 还没有时间线数据。", verificationKicker: "验证", verifyTitle: "验证摘要", emptyVerify: "尚未载入验证报告。",
      issuesKicker: "问题", issueTitle: "问题摘要", emptyIssue: "尚未载入问题报告。", artifactsKicker: "产物", artifactsTitle: "日志、报告与清单",
      artifactHint: "产物预览受 allow-list 限制，并绑定到当前选中 run 的 manifest。", emptyArtifactPanel: "选择一个产物后可在此预览。", noRunsDiscovered: "尚未发现任何 run。",
      noArtifacts: "这个 run 没有声明任何产物。", refreshingInventory: "正在刷新运行态清单...", inventoryRefreshed: "运行态清单已刷新。", launchingRun: "正在启动代表性 smoke run...",
      runLaunched: "Run {runId} 已启动。", runDirectory: "Run 目录：{runDir}", artifactNoTextPreview: "该产物没有文本预览。", selectArtifactPreview: "选择一个产物后可在此预览。",
    },
    labels: {
      status: "状态", overall: "整体", issueCount: "问题数", qaRows: "QA 行数", total: "总数", severities: "严重级别", stages: "阶段数", topIssues: "重点问题",
      bySeverity: "按严重级别", byStage: "按阶段", activeCard: "当前卡片", run: "Run", summary: "摘要", recommendedActions: "建议动作", artifactRefs: "产物引用",
      evidenceRefs: "证据引用", adrRefs: "ADR 引用", pendingReviewTickets: "待复核票数", totalReviewTickets: "复核票总数", workloadDetails: "负载明细",
      manualIntervention: "人工介入率", feedbackClosure: "反馈关闭率", kpiDetails: "KPI 明细", driftCount: "漂移数", reasons: "原因数", driftReasons: "漂移原因",
      required: "必需", missing: "缺失", openCards: "打开卡片", runtime: "运行状态", verify: "验证", target: "目标语言", pending: "挂起",
      artifactStatePresent: "存在", artifactStateMissing: "缺失", stageCountsNone: "尚无线索时间线", noIssueHighlights: "没有重点问题。",
    },
    overview: {
      openCards: "打开卡片", openCardsSupport: "当前所有活跃 run 上尚未关闭的运营动作。", runsWithOpenCards: "存在未关闭卡片的 Run",
      runsWithOpenCardsSupport: "需要运营跟进的不同 run 数量。", pendingReviewTickets: "待复核票数", pendingReviewTicketsSupport: "当前仍在等待人工复核的工作量。",
      runsWithDrift: "存在漂移的 Run", runsWithDriftSupport: "治理或 KPI 漂移已浮现的 run 数量。", runtimeHealth: "运行健康", recentRuns: "最近 Run", noRecentRuns: "暂无最近 run。",
    },
    cardType: { review_ticket: "人工复核", runtime_alert: "运行告警", governance_drift: "治理漂移", kpi_watch: "KPI 关注", decision_required: "运营决策" },
    cardTitle: {
      reviewTicket: "复核票 {id}", runtimePassed: "运行通过", runtimeWarn: "运行完成但有告警", runtimeBlocked: "运行受阻", runtimeFailed: "运行失败",
      governanceDrift: "检测到治理漂移", kpiWatch: "复核负载需要关注", decisionRequired: "需要运营决策",
    },
    artifactRef: {
      manifest: "manifest", verify_report: "验证报告", review_tickets: "复核票据", feedback_log: "反馈日志", kpi_report: "KPI 报告",
      operator_cards: "运营卡片", operator_summary_json: "运营摘要 JSON", operator_summary_md: "运营摘要 Markdown",
    },
    metricKey: {
      total_review_tickets: "复核票总数", pending_review_tickets: "待复核票数", feedback_entries: "反馈条目", manual_intervention_rate: "人工介入率",
      feedback_closure_rate: "反馈关闭率", drift_count: "漂移数", reasons: "原因", open_operator_cards: "打开运营卡片", pass: "通过", warn: "告警",
      fail: "失败", failed: "失败", blocked: "阻塞", running: "运行中", pending: "等待中", unknown: "未知",
    },
    action: {
      "archive run evidence": "归档 run 证据", "continue to the next planned scope": "继续推进下一个规划范围", "inspect blocking stage": "检查阻断阶段",
      "rerun after fixing runtime failure": "修复运行失败后重新运行", "inspect blocked gates": "检查被阻塞的关卡", "resolve review or governance blockers": "解决复核或治理阻塞项",
      "inspect warning-producing stages": "检查产生告警的阶段", "confirm no manual follow-up is needed": "确认无需人工后续跟进", "assign reviewer": "分配复核人",
      "record feedback decision": "记录反馈决策", "confirm ticket closure": "确认票据关闭", "inspect lifecycle and KPI artifacts": "检查生命周期与 KPI 产物",
      "rebuild operator summary after correcting drift": "修正漂移后重建运营摘要", "inspect open review tickets": "检查未关闭复核票", "track feedback closure": "跟踪反馈关闭情况",
      "review open operator cards": "检查未关闭运营卡片",
    },
    stageName: { Connectivity: "连接检查", "Smoke Verify": "Smoke Verify 检查" },
  },
  en: {
    pageTitle: "Operator Workspace Dashboard",
    rail: { operator: "Operator", controlSurface: "Control Surface" },
    masthead: {
      eyebrow: "Phase 6 Operator Workspace Dashboard",
      title: "Operator Workspace And Runtime Shell",
      copy: "Triage operator cards, inspect review pressure, and audit runtime evidence from one instrumented control surface.",
    },
    aria: { languageSwitch: "Language switch", modeSwitch: "Operator surface mode" },
    lang: { zh: "中文", en: "EN" },
    mode: { workspace: "Operator Workspace", runtime: "Runtime Shell" },
    hero: {
      waiting: "Waiting for workspace data", workspaceReady: "Workspace ready", selectedRun: "Selected {runId}", selectedCard: "Operator card {cardId}",
      runtimeLaneFailed: "Runtime lane failed", workspaceLoadFailed: "Workspace load failed", initialLoadFailed: "Initial load failed",
    },
    common: { refresh: "Refresh", na: "n/a", all: "all", open: "open", closed: "closed", yes: "yes", no: "no", none: "none" },
    status: {
      pass: "pass", warn: "warn", fail: "fail", failed: "fail", blocked: "blocked", running: "running", pending: "pending", unknown: "unknown",
      success: "pass", completed: "completed", open: "open", closed: "closed", all: "all",
    },
    workspace: {
      kicker: "Operator Workspace", overviewTitle: "Overview Ribbon", waiting: "Workspace is waiting for operator data.", emptyOverview: "No workspace overview loaded yet.",
      inboxKicker: "Operator Inbox", inboxTitle: "Cross-Run Cards", emptyCardsLoaded: "No operator cards loaded yet.", emptyCardsFiltered: "No operator cards match the current filters.",
      selectedCardKicker: "Selected Card", noCardSelected: "No operator card selected", selectCardHint: "Select an operator card to inspect decision context.", openRuntimeButton: "Open Runtime Lane",
      decisionTitle: "Decision Context", emptyDecision: "No decision context loaded.", reviewKicker: "Review Workload", reviewTitle: "Review Workload", emptyReview: "No review workload loaded.",
      kpiKicker: "KPI Snapshot", kpiTitle: "KPI Snapshot", emptyKpi: "No KPI snapshot loaded.", driftKicker: "Governance Drift", driftTitle: "Governance Drift", emptyDrift: "No governance drift loaded.",
      refreshing: "Refreshing operator workspace...", refreshed: "Operator workspace refreshed.", noDecisionTitle: "No operator decision required",
      noDecisionSummary: "This run currently has no operator cards requiring follow-up.", crossLaneHint: "Cross-lane drilldown stays anchored to the runtime artifact inspector.",
    },
    filters: { status: "Status", cardType: "Card Type", priority: "Priority", targetLocale: "Target Locale", targetLocalePlaceholder: "for example en-US", all: "all", status_open: "open", status_all: "all", status_closed: "closed" },
    runtime: {
      launcherKicker: "Launcher", launcherTitle: "Representative Smoke Run", launcherHint: "Use the current pipeline defaults behind the shell.", inputCsv: "Input CSV", inputPlaceholder: "Path to input CSV",
      targetLanguage: "Target Language", verifyMode: "Verify Mode", verifyModeFull: "full", verifyModePreflight: "preflight", launchButton: "Launch Run",
      recentRunsKicker: "Recent Runs", timelineTitle: "Run Timeline", selectedRunKicker: "Selected Run", noRunSelected: "No run selected", runHint: "Choose a run to inspect stage status and evidence.",
      emptyTimeline: "No run selected yet.", emptyTimelineData: "No timeline data yet for this run.", verificationKicker: "Verification", verifyTitle: "Verify Summary", emptyVerify: "No verify report loaded.",
      issuesKicker: "Issues", issueTitle: "Issue Summary", emptyIssue: "No issue report loaded.", artifactsKicker: "Artifacts", artifactsTitle: "Logs, Reports, And Manifest",
      artifactHint: "Artifact preview is allow-list based and tied to the selected run manifest.", emptyArtifactPanel: "Select an artifact to preview it here.", noRunsDiscovered: "No runs discovered yet.",
      noArtifacts: "No artifacts declared for this run.", refreshingInventory: "Refreshing runtime inventory...", inventoryRefreshed: "Runtime inventory refreshed.", launchingRun: "Launching representative smoke run...",
      runLaunched: "Run {runId} launched.", runDirectory: "Run directory: {runDir}", artifactNoTextPreview: "Artifact has no text preview.", selectArtifactPreview: "Select an artifact to preview it here.",
    },
    labels: {
      status: "Status", overall: "Overall", issueCount: "Issue Count", qaRows: "QA Rows", total: "Total", severities: "Severities", stages: "Stages", topIssues: "Top Issues",
      bySeverity: "By Severity", byStage: "By Stage", activeCard: "Active Card", run: "Run", summary: "Summary", recommendedActions: "Recommended Actions", artifactRefs: "Artifact Refs",
      evidenceRefs: "Evidence Refs", adrRefs: "ADR Refs", pendingReviewTickets: "Pending Review Tickets", totalReviewTickets: "Total Review Tickets", workloadDetails: "Workload Details",
      manualIntervention: "Manual Intervention", feedbackClosure: "Feedback Closure", kpiDetails: "KPI Details", driftCount: "Drift Count", reasons: "Reasons", driftReasons: "Drift Reasons",
      required: "required", missing: "missing", openCards: "open cards", runtime: "runtime", verify: "verify", target: "target", pending: "pending", artifactStatePresent: "present",
      artifactStateMissing: "missing", stageCountsNone: "no timeline yet", noIssueHighlights: "No issue highlights.",
    },
    overview: {
      openCards: "Open Cards", openCardsSupport: "Current open operator actions across active runs.", runsWithOpenCards: "Runs With Open Cards",
      runsWithOpenCardsSupport: "Distinct runs requiring operator attention.", pendingReviewTickets: "Pending Review Tickets", pendingReviewTicketsSupport: "Human review workload currently waiting.",
      runsWithDrift: "Runs With Drift", runsWithDriftSupport: "Runs where governance or KPI drift is visible.", runtimeHealth: "Runtime Health", recentRuns: "Recent Runs", noRecentRuns: "No recent runs.",
    },
    cardType: { review_ticket: "review_ticket", runtime_alert: "runtime_alert", governance_drift: "governance_drift", kpi_watch: "kpi_watch", decision_required: "decision_required" },
    cardTitle: {
      reviewTicket: "Review ticket {id}", runtimePassed: "Runtime passed", runtimeWarn: "Runtime completed with warnings", runtimeBlocked: "Runtime blocked", runtimeFailed: "Runtime failed",
      governanceDrift: "Governance drift detected", kpiWatch: "Review workload requires monitoring", decisionRequired: "Operator decision required",
    },
    artifactRef: {
      manifest: "manifest", verify_report: "verify_report", review_tickets: "review_tickets", feedback_log: "feedback_log", kpi_report: "kpi_report",
      operator_cards: "operator_cards", operator_summary_json: "operator_summary_json", operator_summary_md: "operator_summary_md",
    },
    metricKey: {
      total_review_tickets: "total_review_tickets", pending_review_tickets: "pending_review_tickets", feedback_entries: "feedback_entries", manual_intervention_rate: "manual_intervention_rate",
      feedback_closure_rate: "feedback_closure_rate", drift_count: "drift_count", reasons: "reasons", open_operator_cards: "open_operator_cards", pass: "pass", warn: "warn",
      fail: "fail", failed: "fail", blocked: "blocked", running: "running", pending: "pending", unknown: "unknown",
    },
    action: {},
    stageName: { Connectivity: "Connectivity", "Smoke Verify": "Smoke Verify" },
  },
};

const state = {
  language: getStoredLanguage(),
  mode: "workspace",
  runs: [],
  selectedRunId: null,
  selectedRunDetail: null,
  selectedArtifactKey: null,
  selectedArtifact: null,
  workspaceOverview: null,
  workspaceCards: [],
  selectedCardId: null,
  selectedWorkspaceRunId: null,
  workspaceDetail: null,
  heroMessage: { status: "unknown", key: "hero.waiting", vars: {}, raw: false },
  workspaceFeedbackMessage: { key: "workspace.waiting", vars: {}, raw: false },
  launchFeedbackMessage: { key: "runtime.launcherHint", vars: {}, raw: false },
};

const ui = {
  heroStatus: document.getElementById("hero-status"),
  workspaceModeButton: document.getElementById("mode-workspace"),
  runtimeModeButton: document.getElementById("mode-runtime"),
  languageZhButton: document.getElementById("lang-zh"),
  languageEnButton: document.getElementById("lang-en"),
  workspaceView: document.getElementById("workspace-view"),
  runtimeView: document.getElementById("runtime-view"),
  workspaceFeedback: document.getElementById("workspace-feedback"),
  overviewRibbon: document.getElementById("overview-ribbon"),
  workspaceCards: document.getElementById("workspace-cards"),
  workspaceFilters: document.getElementById("workspace-filters"),
  workspaceRefreshButton: document.getElementById("workspace-refresh-button"),
  cardStatusFilter: document.getElementById("card-status-filter"),
  cardTypeFilter: document.getElementById("card-type-filter"),
  cardPriorityFilter: document.getElementById("card-priority-filter"),
  cardLocaleFilter: document.getElementById("card-locale-filter"),
  workspaceRunTitle: document.getElementById("workspace-run-title"),
  workspaceRunMeta: document.getElementById("workspace-run-meta"),
  openRuntimeButton: document.getElementById("open-runtime-button"),
  decisionContext: document.getElementById("decision-context"),
  reviewWorkload: document.getElementById("review-workload"),
  kpiSnapshot: document.getElementById("kpi-snapshot"),
  governanceDrift: document.getElementById("governance-drift"),
  launchFeedback: document.getElementById("launch-feedback"),
  launcherForm: document.getElementById("launcher-form"),
  refreshButton: document.getElementById("refresh-button"),
  runsList: document.getElementById("runs-list"),
  runTitle: document.getElementById("run-title"),
  runMeta: document.getElementById("run-meta"),
  timelinePanel: document.getElementById("timeline-panel"),
  verifySummary: document.getElementById("verify-summary"),
  issueSummary: document.getElementById("issue-summary"),
  artifactList: document.getElementById("artifact-list"),
  artifactPanel: document.getElementById("artifact-panel"),
};

function getStoredLanguage() {
  try {
    const stored = localStorage.getItem(LANG_STORAGE_KEY);
    if (stored === "en" || stored === "zh") {
      return stored;
    }
  } catch (error) {
    return "zh";
  }
  return "zh";
}

function persistLanguage(language) {
  try {
    localStorage.setItem(LANG_STORAGE_KEY, language);
  } catch (error) {
    return;
  }
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[char]));
}

function interpolate(template, vars = {}) {
  return String(template).replace(/\{(\w+)\}/g, (_, key) => String(vars[key] ?? ""));
}

function t(key, vars = {}, fallback = key) {
  const table = translations[state.language] || translations.zh;
  const value = key.split(".").reduce((current, segment) => {
    if (current && typeof current === "object" && segment in current) {
      return current[segment];
    }
    return null;
  }, table);
  if (typeof value !== "string") {
    return fallback;
  }
  return interpolate(value, vars);
}

function normalizeStatus(status) {
  const normalized = String(status || "unknown").trim().toLowerCase();
  if (["pass", "passed", "success", "ok"].includes(normalized)) {
    return "pass";
  }
  if (normalized === "completed") {
    return "completed";
  }
  if (["warn", "warning"].includes(normalized)) {
    return "warn";
  }
  if (["fail", "failed", "error"].includes(normalized)) {
    return "fail";
  }
  if (["blocked", "running", "pending", "open", "closed", "all"].includes(normalized)) {
    return normalized;
  }
  return "unknown";
}

function displayStatusText(status) {
  const normalized = normalizeStatus(status);
  return t(`status.${normalized}`, {}, normalized);
}

function displayBool(value) {
  return value ? t("common.yes") : t("common.no");
}

function displayMaybeValue(value) {
  return value ? String(value) : t("common.na");
}

function displayVerifyMode(value) {
  if (value === "full") {
    return t("runtime.verifyModeFull");
  }
  if (value === "preflight") {
    return t("runtime.verifyModePreflight");
  }
  return displayMaybeValue(value);
}

function displayCardType(cardType) {
  return t(`cardType.${cardType}`, {}, cardType || t("common.na"));
}

function displayStageName(name) {
  return t(`stageName.${name}`, {}, name);
}

function displayArtifactRefKey(key) {
  return t(`artifactRef.${key}`, {}, key);
}

function displayMetricKey(key) {
  return t(`metricKey.${key}`, {}, key);
}

function displayActionText(action) {
  return t(`action.${action}`, {}, action);
}

function displayCardTitle(card) {
  if (!card) {
    return "";
  }
  const rawTitle = String(card.title || "");
  if (card.card_type === "review_ticket" && rawTitle.startsWith("Review ticket ")) {
    return t("cardTitle.reviewTicket", { id: rawTitle.slice("Review ticket ".length) });
  }
  if (card.card_type === "runtime_alert") {
    if (/Runtime passed/i.test(rawTitle)) return t("cardTitle.runtimePassed");
    if (/Runtime completed with warnings/i.test(rawTitle)) return t("cardTitle.runtimeWarn");
    if (/Runtime blocked/i.test(rawTitle)) return t("cardTitle.runtimeBlocked");
    if (/Runtime failed/i.test(rawTitle)) return t("cardTitle.runtimeFailed");
  }
  if (card.card_type === "governance_drift") return t("cardTitle.governanceDrift");
  if (card.card_type === "kpi_watch") return t("cardTitle.kpiWatch");
  if (card.card_type === "decision_required") return t("cardTitle.decisionRequired");
  return rawTitle || card.card_id || "";
}

function displayCardSummary(card, rawSummary = card?.summary || "") {
  if (state.language === "en") {
    return rawSummary;
  }
  if (rawSummary === "Persisted operator summary shows this run is already triaged.") {
    return "已持久化的运营摘要显示该 run 已完成分诊。";
  }
  if (card?.card_type === "review_ticket" && rawSummary.startsWith("needs manual review")) {
    return rawSummary.replace("needs manual review", "需要人工复核").replace("; reason_codes=", "；原因代码=");
  }
  if (card?.card_type === "decision_required") {
    const match = rawSummary.match(/^(\d+) open operator cards require follow-up before archival\.$/);
    if (match) {
      return `${match[1]} 张未关闭运营卡片需要处理后才能归档。`;
    }
  }
  if (card?.card_type === "runtime_alert") {
    const match = rawSummary.match(/^Manifest\/verify resolved runtime health to ([a-z_]+)\.$/i);
    if (match) {
      return `Manifest/verify 判定运行健康状态为 ${displayStatusText(match[1])}。`;
    }
  }
  return rawSummary;
}

function statusMarkup(status, label) {
  const normalized = normalizeStatus(status);
  const displayLabel = label || displayStatusText(normalized);
  return `<span class="status-${normalized}"><span class="status-dot status-${normalized}"></span>${escapeHtml(displayLabel)}</span>`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || payload.error || `Request failed: ${response.status}`);
  }
  return response.json();
}

function renderHeroStatus() {
  const message = state.heroMessage.raw ? state.heroMessage.key : t(state.heroMessage.key, state.heroMessage.vars);
  ui.heroStatus.innerHTML = statusMarkup(state.heroMessage.status, message);
}

function setHeroStatus(status, key, vars = {}, options = {}) {
  state.heroMessage = { status, key, vars, raw: Boolean(options.raw) };
  renderHeroStatus();
}

function renderWorkspaceFeedback() {
  ui.workspaceFeedback.textContent = state.workspaceFeedbackMessage.raw ? state.workspaceFeedbackMessage.key : t(state.workspaceFeedbackMessage.key, state.workspaceFeedbackMessage.vars);
}

function setWorkspaceFeedback(key, vars = {}, options = {}) {
  state.workspaceFeedbackMessage = { key, vars, raw: Boolean(options.raw) };
  renderWorkspaceFeedback();
}

function renderLaunchFeedback() {
  ui.launchFeedback.textContent = state.launchFeedbackMessage.raw ? state.launchFeedbackMessage.key : t(state.launchFeedbackMessage.key, state.launchFeedbackMessage.vars);
}

function setLaunchFeedback(key, vars = {}, options = {}) {
  state.launchFeedbackMessage = { key, vars, raw: Boolean(options.raw) };
  renderLaunchFeedback();
}

function setMode(mode) {
  state.mode = mode;
  const workspaceActive = mode === "workspace";
  ui.workspaceModeButton.classList.toggle("active", workspaceActive);
  ui.runtimeModeButton.classList.toggle("active", !workspaceActive);
  ui.workspaceView.classList.toggle("hidden", !workspaceActive);
  ui.runtimeView.classList.toggle("hidden", workspaceActive);
}

function translateStaticDocument() {
  document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en";
  document.title = t("pageTitle");
  ui.languageZhButton.classList.toggle("active", state.language === "zh");
  ui.languageZhButton.setAttribute("aria-pressed", state.language === "zh" ? "true" : "false");
  ui.languageEnButton.classList.toggle("active", state.language === "en");
  ui.languageEnButton.setAttribute("aria-pressed", state.language === "en" ? "true" : "false");

  document.querySelectorAll("[data-i18n]").forEach((element) => {
    element.textContent = t(element.dataset.i18n);
  });
  document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => {
    element.setAttribute("placeholder", t(element.dataset.i18nPlaceholder));
  });
  document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => {
    element.setAttribute("aria-label", t(element.dataset.i18nAriaLabel));
  });
}

function applyLanguage(language, options = {}) {
  state.language = language === "en" ? "en" : "zh";
  if (options.persist !== false) {
    persistLanguage(state.language);
  }
  translateStaticDocument();
  renderHeroStatus();
  renderWorkspaceFeedback();
  renderLaunchFeedback();
  renderWorkspaceOverview();
  renderWorkspaceCards();
  if (state.workspaceDetail) {
    renderWorkspaceDetail(state.workspaceDetail);
  } else {
    renderEmptyWorkspaceSelection();
  }
  if (state.selectedRunDetail) {
    renderRuntimeDetail(state.selectedRunDetail);
  } else {
    renderEmptyRuntimeSelection();
  }
  if (state.selectedArtifact) {
    renderArtifactPreview(state.selectedArtifact);
  } else if (!state.selectedRunDetail) {
    renderEmptyArtifactPreview();
  }
}

function workspaceQueryString() {
  const params = new URLSearchParams();
  params.set("status", ui.cardStatusFilter.value || "open");
  if (ui.cardTypeFilter.value) params.set("card_type", ui.cardTypeFilter.value);
  if (ui.cardPriorityFilter.value) params.set("priority", ui.cardPriorityFilter.value);
  if (ui.cardLocaleFilter.value.trim()) params.set("target_locale", ui.cardLocaleFilter.value.trim());
  params.set("limit", "25");
  return params.toString();
}

function renderList(items, emptyLabel, options = {}) {
  if (!items || !items.length) {
    return `<div class="empty-state">${escapeHtml(emptyLabel)}</div>`;
  }
  const formatter = options.formatter || ((item) => item);
  return `<ul class="list-block">${items.map((item) => `<li>${escapeHtml(formatter(item))}</li>`).join("")}</ul>`;
}

function renderPills(items) {
  if (!items || !items.length) return "";
  return `<div class="pill-row">${items.map((item) => `<span class="pill">${escapeHtml(item)}</span>`).join("")}</div>`;
}

function toMetricCells(payload, emptyLabel, options = {}) {
  const entries = Object.entries(payload || {});
  if (!entries.length) {
    return `<div class="empty-state">${escapeHtml(emptyLabel)}</div>`;
  }
  const keyFormatter = options.keyFormatter || ((key) => key);
  const valueFormatter = options.valueFormatter || ((value) => (typeof value === "object" ? JSON.stringify(value) : value));
  return `
    <div class="kv-grid">
      ${entries.map(([key, value]) => `
        <article class="kv-cell">
          <span class="kv-key">${escapeHtml(keyFormatter(key))}</span>
          <span class="kv-value ${options.mono ? "mono" : ""}">${escapeHtml(valueFormatter(value, key))}</span>
        </article>
      `).join("")}
    </div>
  `;
}

function renderMetricStrip(items) {
  return `
    <div class="metric-strip">
      ${items.map((item) => `
        <article class="metric-chip">
          <span class="metric-label">${escapeHtml(item.label)}</span>
          <span class="metric-value">${escapeHtml(item.value)}</span>
        </article>
      `).join("")}
    </div>
  `;
}

function summarizeStageCounts(stageCounts) {
  const entries = Object.entries(stageCounts || {});
  if (!entries.length) {
    return t("labels.stageCountsNone");
  }
  return entries.map(([key, value]) => `${displayStatusText(key)}:${value}`).join(" · ");
}

function preferredArtifactKey(run) {
  const allowed = new Set(run.allowed_artifact_keys || []);
  const preferred = ["run_manifest", "smoke_verify_report", "smoke_issues_report", "smoke_verify_log"];
  for (const key of preferred) {
    if (allowed.has(key)) return key;
  }
  const previewable = (run.artifacts || []).find((artifact) => artifact.previewable && allowed.has(artifact.key));
  return previewable ? previewable.key : "";
}

function renderEmptyArtifactPreview() {
  ui.artifactPanel.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.emptyArtifactPanel"))}</div>`;
}

function renderArtifactPreview(artifact) {
  if (!artifact) {
    renderEmptyArtifactPreview();
    return;
  }
  const body = artifact.content || (artifact.json ? JSON.stringify(artifact.json, null, 2) : t("runtime.artifactNoTextPreview"));
  ui.artifactPanel.innerHTML = `
    <div class="artifact-header">
      <strong>${escapeHtml(artifact.key)}</strong>
      <span class="kv-value mono">${escapeHtml(artifact.path)}</span>
    </div>
    <pre>${escapeHtml(body)}</pre>
  `;
}

function renderRunsRail() {
  if (!state.runs.length) {
    ui.runsList.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.noRunsDiscovered"))}</div>`;
    return;
  }

  ui.runsList.innerHTML = state.runs.map((run) => {
    const selected = run.run_id === state.selectedRunId ? "selected" : "";
    return `
      <button type="button" class="run-card ${selected}" data-run-id="${escapeHtml(run.run_id)}">
        <strong>${escapeHtml(run.run_id)}</strong>
        <div class="run-meta">
          <span>${statusMarkup(run.overall_status)}</span>
          <span>${escapeHtml(displayMaybeValue(run.target_lang))}</span>
          <span>${escapeHtml(displayVerifyMode(run.verify_mode))}</span>
        </div>
        <p>${escapeHtml(summarizeStageCounts(run.stage_counts))}</p>
      </button>
    `;
  }).join("");

  ui.runsList.querySelectorAll("[data-run-id]").forEach((element) => {
    element.addEventListener("click", () => {
      loadRunDetail(element.dataset.runId).catch(handleRuntimeError);
      setMode("runtime");
    });
  });
}

function renderEmptyRuntimeSelection() {
  ui.runTitle.textContent = t("runtime.noRunSelected");
  ui.runMeta.textContent = t("runtime.runHint");
  ui.timelinePanel.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.emptyTimeline"))}</div>`;
  ui.verifySummary.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.emptyVerify"))}</div>`;
  ui.issueSummary.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.emptyIssue"))}</div>`;
  ui.artifactList.innerHTML = "";
  renderEmptyArtifactPreview();
}

function renderRuntimeDetail(run) {
  state.selectedRunId = run.run_id;
  state.selectedRunDetail = run;

  ui.runTitle.textContent = run.run_id;
  ui.runMeta.innerHTML = renderPills([
    `${t("labels.overall")} ${displayStatusText(run.overall_status)}`,
    `${t("labels.verify")} ${displayVerifyMode(run.verify_mode)}`,
    `${t("labels.target")} ${displayMaybeValue(run.target_lang)}`,
    `${t("labels.pending")} ${displayBool(run.pending)}`,
  ]) + `<p class="panel-note">${escapeHtml(t("runtime.runDirectory", { runDir: run.run_dir || t("common.na") }))}</p>`;

  const stages = run.stages || [];
  ui.timelinePanel.innerHTML = stages.length ? stages.map((stage) => `
      <article class="timeline-stage">
        <header>
          <strong>${escapeHtml(displayStageName(stage.name))}</strong>
          ${statusMarkup(stage.status)}
        </header>
        ${renderPills([
          `${t("labels.required")} ${displayBool(stage.required)}`,
          `${t("labels.missing")} ${stage.missing_required_files?.length || 0}`,
        ])}
      </article>
    `).join("") : `<div class="empty-state">${escapeHtml(t("runtime.emptyTimelineData"))}</div>`;

  const verify = run.verify || {};
  ui.verifySummary.innerHTML = `
    ${renderMetricStrip([
      { label: t("labels.status"), value: displayStatusText(verify.status || "unknown") },
      { label: t("labels.overall"), value: displayStatusText(verify.overall || "unknown") },
      { label: t("labels.issueCount"), value: verify.issue_count || 0 },
      { label: t("labels.qaRows"), value: (verify.qa_rows || []).length },
    ])}
    <article class="detail-section">
      <h4>${escapeHtml(t("labels.qaRows"))}</h4>
      <pre>${escapeHtml((verify.qa_rows || []).join("\n") || t("runtime.emptyVerify"))}</pre>
    </article>
  `;

  const issueSummary = run.issue_summary || {};
  const topIssues = issueSummary.top || [];
  ui.issueSummary.innerHTML = `
    ${renderMetricStrip([
      { label: t("labels.total"), value: issueSummary.total || 0 },
      { label: t("labels.severities"), value: Object.keys(issueSummary.by_severity || {}).length },
      { label: t("labels.stages"), value: Object.keys(issueSummary.by_stage || {}).length },
      { label: t("labels.topIssues"), value: topIssues.length },
    ])}
    <article class="detail-section">
      <h4>${escapeHtml(t("labels.bySeverity"))}</h4>
      ${toMetricCells(issueSummary.by_severity || {}, t("runtime.emptyIssue"), { keyFormatter: displayMetricKey })}
    </article>
    <article class="detail-section">
      <h4>${escapeHtml(t("labels.byStage"))}</h4>
      ${toMetricCells(issueSummary.by_stage || {}, t("runtime.emptyIssue"), { keyFormatter: displayMetricKey })}
    </article>
    <article class="detail-section">
      <h4>${escapeHtml(t("labels.topIssues"))}</h4>
      ${topIssues.length ? `<ul class="list-block">${topIssues.map((issue) => `<li>${escapeHtml(`${issue.severity} · ${issue.stage} · ${issue.error_code || "no-code"}`)}</li>`).join("")}</ul>` : `<div class="empty-state">${escapeHtml(t("labels.noIssueHighlights"))}</div>`}
    </article>
  `;

  const artifacts = run.artifacts || [];
  ui.artifactList.innerHTML = artifacts.length ? artifacts.map((artifact) => `
      <button type="button" class="artifact-button ${artifact.key === state.selectedArtifactKey ? "active" : ""}" data-artifact-key="${escapeHtml(artifact.key)}">
        <strong>${escapeHtml(artifact.key)}</strong>
        <div class="run-meta">
          <span>${escapeHtml(artifact.kind)}</span>
          <span>${escapeHtml(artifact.exists ? t("labels.artifactStatePresent") : t("labels.artifactStateMissing"))}</span>
        </div>
      </button>
    `).join("") : `<div class="empty-state">${escapeHtml(t("runtime.noArtifacts"))}</div>`;

  ui.artifactList.querySelectorAll("[data-artifact-key]").forEach((element) => {
    element.addEventListener("click", () => {
      loadArtifact(run.run_id, element.dataset.artifactKey).catch(handleRuntimeError);
    });
  });

  renderRunsRail();
}

function renderWorkspaceOverview() {
  const overview = state.workspaceOverview;
  if (!overview) {
    ui.overviewRibbon.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyOverview"))}</div>`;
    return;
  }

  const recentRunsMarkup = (overview.recent_runs || []).slice(0, 4).map((run) => `
      <button type="button" class="recent-run-chip" data-run-id="${escapeHtml(run.run_id)}">
        <strong>${escapeHtml(run.run_id)}</strong>
        <div class="run-meta">
          <span>${statusMarkup(run.overall_status)}</span>
          <span>${escapeHtml(displayMaybeValue(run.target_lang))}</span>
        </div>
      </button>
    `).join("");

  ui.overviewRibbon.innerHTML = `
    <article class="ribbon-card"><p class="panel-kicker">${escapeHtml(t("overview.openCards"))}</p><span class="ribbon-value">${escapeHtml(overview.open_card_count || 0)}</span><p class="ribbon-support">${escapeHtml(t("overview.openCardsSupport"))}</p></article>
    <article class="ribbon-card"><p class="panel-kicker">${escapeHtml(t("overview.runsWithOpenCards"))}</p><span class="ribbon-value">${escapeHtml(overview.runs_with_open_cards || 0)}</span><p class="ribbon-support">${escapeHtml(t("overview.runsWithOpenCardsSupport"))}</p></article>
    <article class="ribbon-card"><p class="panel-kicker">${escapeHtml(t("overview.pendingReviewTickets"))}</p><span class="ribbon-value">${escapeHtml(overview.open_review_tickets || 0)}</span><p class="ribbon-support">${escapeHtml(t("overview.pendingReviewTicketsSupport"))}</p></article>
    <article class="ribbon-card"><p class="panel-kicker">${escapeHtml(t("overview.runsWithDrift"))}</p><span class="ribbon-value">${escapeHtml(overview.runs_with_drift || 0)}</span><p class="ribbon-support">${escapeHtml(t("overview.runsWithDriftSupport"))}</p></article>
    <article class="ribbon-card"><p class="panel-kicker">${escapeHtml(t("overview.runtimeHealth"))}</p>${toMetricCells(overview.runtime_health_counts || {}, t("workspace.emptyOverview"), { keyFormatter: displayMetricKey })}</article>
    <article class="ribbon-card"><p class="panel-kicker">${escapeHtml(t("overview.recentRuns"))}</p><div class="recent-run-stack">${recentRunsMarkup || `<div class="empty-state">${escapeHtml(t("overview.noRecentRuns"))}</div>`}</div></article>
  `;

  ui.overviewRibbon.querySelectorAll("[data-run-id]").forEach((element) => {
    element.addEventListener("click", () => {
      openRunInRuntimeLane(element.dataset.runId).catch(handleRuntimeError);
    });
  });
}

function renderWorkspaceCards() {
  if (!state.workspaceCards.length) {
    ui.workspaceCards.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyCardsFiltered"))}</div>`;
    return;
  }

  ui.workspaceCards.innerHTML = state.workspaceCards.map((card) => {
    const selected = card.card_id === state.selectedCardId ? "selected" : "";
    return `
      <button type="button" class="workspace-card ${selected}" data-card-id="${escapeHtml(card.card_id)}">
        <strong>${escapeHtml(displayCardTitle(card))}</strong>
        <div class="workspace-card-meta">
          <span>${statusMarkup(card.status)}</span>
          <span>${escapeHtml(card.priority)}</span>
          <span>${escapeHtml(displayCardType(card.card_type))}</span>
          <span>${escapeHtml(displayMaybeValue(card.target_locale))}</span>
        </div>
        <p>${escapeHtml(displayCardSummary(card))}</p>
      </button>
    `;
  }).join("");

  ui.workspaceCards.querySelectorAll("[data-card-id]").forEach((element) => {
    element.addEventListener("click", () => {
      selectWorkspaceCard(element.dataset.cardId).catch(handleWorkspaceError);
    });
  });
}

function findSelectedCard() {
  return state.workspaceCards.find((card) => card.card_id === state.selectedCardId) || null;
}

function displayDecisionTitle(context, selectedCard) {
  if (selectedCard) return displayCardTitle(selectedCard);
  if (context.title === "No operator decision required") return t("workspace.noDecisionTitle");
  return context.title || t("workspace.noCardSelected");
}

function displayDecisionSummary(context, selectedCard) {
  if (selectedCard) return displayCardSummary(selectedCard, context.summary || selectedCard.summary || "");
  if (context.summary === "This run currently has no operator cards requiring follow-up.") return t("workspace.noDecisionSummary");
  return context.summary || t("workspace.emptyDecision");
}

function renderDecisionContext(detail) {
  const context = detail.decision_context || {};
  const selectedCard = findSelectedCard();
  ui.decisionContext.innerHTML = `
    ${renderMetricStrip([{ label: t("labels.activeCard"), value: context.card_id || t("common.none") }, { label: t("labels.run"), value: detail.run_id || t("common.na") }])}
    <article class="detail-section"><h4>${escapeHtml(t("labels.summary"))}</h4><p><strong>${escapeHtml(displayDecisionTitle(context, selectedCard))}</strong></p><p>${escapeHtml(displayDecisionSummary(context, selectedCard))}</p></article>
    <article class="detail-section"><h4>${escapeHtml(t("labels.recommendedActions"))}</h4>${renderList(context.recommended_actions || [], t("workspace.emptyDecision"), { formatter: displayActionText })}</article>
    <article class="detail-section"><h4>${escapeHtml(t("labels.artifactRefs"))}</h4>${toMetricCells(context.artifact_refs || {}, t("workspace.emptyDecision"), { mono: true, keyFormatter: displayArtifactRefKey })}</article>
    <article class="detail-section"><h4>${escapeHtml(t("labels.evidenceRefs"))}</h4>${renderList(context.evidence_refs || [], t("workspace.emptyDecision"))}</article>
    <article class="detail-section"><h4>${escapeHtml(t("labels.adrRefs"))}</h4>${renderList(context.adr_refs || [], t("workspace.emptyDecision"))}</article>
  `;
}

function renderWorkspaceSignals(detail) {
  const review = detail.review_workload || {};
  const kpi = detail.kpi_snapshot || {};
  const drift = detail.governance_drift || {};
  ui.reviewWorkload.innerHTML = `${renderMetricStrip([{ label: t("labels.pendingReviewTickets"), value: review.pending_review_tickets || 0 }, { label: t("labels.totalReviewTickets"), value: review.total_review_tickets || 0 }])}<article class="detail-section"><h4>${escapeHtml(t("labels.workloadDetails"))}</h4>${toMetricCells(review, t("workspace.emptyReview"), { keyFormatter: displayMetricKey })}</article>`;
  ui.kpiSnapshot.innerHTML = `${renderMetricStrip([{ label: t("labels.manualIntervention"), value: kpi.manual_intervention_rate || 0 }, { label: t("labels.feedbackClosure"), value: kpi.feedback_closure_rate || 0 }])}<article class="detail-section"><h4>${escapeHtml(t("labels.kpiDetails"))}</h4>${toMetricCells(kpi, t("workspace.emptyKpi"), { keyFormatter: displayMetricKey })}</article>`;
  ui.governanceDrift.innerHTML = `${renderMetricStrip([{ label: t("labels.driftCount"), value: drift.drift_count || 0 }, { label: t("labels.reasons"), value: (drift.reasons || []).length }])}<article class="detail-section"><h4>${escapeHtml(t("labels.driftReasons"))}</h4>${renderList(drift.reasons || [], t("workspace.emptyDrift"))}</article>`;
}

function renderEmptyWorkspaceSelection() {
  ui.workspaceRunTitle.textContent = t("workspace.noCardSelected");
  ui.workspaceRunMeta.textContent = t("workspace.selectCardHint");
  ui.decisionContext.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyDecision"))}</div>`;
  ui.reviewWorkload.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyReview"))}</div>`;
  ui.kpiSnapshot.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyKpi"))}</div>`;
  ui.governanceDrift.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyDrift"))}</div>`;
}

function renderWorkspaceDetail(detail) {
  state.workspaceDetail = detail;
  state.selectedWorkspaceRunId = detail.run_id;
  ui.workspaceRunTitle.textContent = detail.run_id;
  ui.workspaceRunMeta.innerHTML = `${renderPills([`${t("labels.openCards")} ${detail.operator_summary?.open_operator_cards || 0}`, `${t("labels.runtime")} ${displayStatusText(detail.operator_summary?.overall_runtime_health?.status || "unknown")}`])}<p class="panel-note">${escapeHtml(t("workspace.crossLaneHint"))}</p>`;
  renderDecisionContext(detail);
  renderWorkspaceSignals(detail);
}

async function loadRuns() {
  setLaunchFeedback("runtime.refreshingInventory");
  const payload = await fetchJson("/api/runs?limit=12");
  state.runs = payload.runs || [];
  renderRunsRail();
  setLaunchFeedback("runtime.inventoryRefreshed");
  if (!state.selectedRunId && state.runs.length) {
    await loadRunDetail(state.runs[0].run_id, { preserveMode: true });
  }
}

async function loadRunDetail(runId, options = {}) {
  const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}`);
  renderRuntimeDetail(payload.run);
  if (!options.preserveMode) {
    setMode("runtime");
    setHeroStatus(payload.run.overall_status, "hero.selectedRun", { runId: payload.run.run_id });
  }
  return payload.run;
}

async function loadArtifact(runId, artifactKey, options = {}) {
  state.selectedArtifactKey = artifactKey;
  const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactKey)}`);
  state.selectedArtifact = payload.artifact;
  renderArtifactPreview(payload.artifact);
  renderRunsRail();
  if (!options.preserveMode) {
    setMode("runtime");
  }
}

async function openRunInRuntimeLane(runId) {
  setMode("runtime");
  const run = await loadRunDetail(runId, { preserveMode: false });
  const artifactKey = preferredArtifactKey(run);
  if (artifactKey) {
    await loadArtifact(runId, artifactKey, { preserveMode: false });
  }
}

async function loadWorkspaceOverview() {
  const payload = await fetchJson("/api/workspace/overview?limit_runs=12");
  state.workspaceOverview = payload.overview || null;
  renderWorkspaceOverview();
}

async function loadWorkspaceCards() {
  const payload = await fetchJson(`/api/workspace/cards?${workspaceQueryString()}`);
  state.workspaceCards = payload.cards || [];
  renderWorkspaceCards();
  const currentCard = state.workspaceCards.find((card) => card.card_id === state.selectedCardId);
  const nextCard = currentCard || state.workspaceCards[0];
  if (nextCard) {
    await selectWorkspaceCard(nextCard.card_id, { preserveMode: true });
  } else {
    state.selectedCardId = null;
    state.selectedWorkspaceRunId = null;
    state.workspaceDetail = null;
    renderEmptyWorkspaceSelection();
  }
}

async function loadWorkspaceRunDetail(runId) {
  const payload = await fetchJson(`/api/workspace/runs/${encodeURIComponent(runId)}`);
  renderWorkspaceDetail(payload.workspace);
  return payload.workspace;
}

async function selectWorkspaceCard(cardId, options = {}) {
  const card = state.workspaceCards.find((item) => item.card_id === cardId);
  if (!card) {
    return;
  }
  state.selectedCardId = cardId;
  renderWorkspaceCards();
  await loadWorkspaceRunDetail(card.run_id);
  const run = await loadRunDetail(card.run_id, { preserveMode: true });
  const artifactKey = preferredArtifactKey(run);
  if (artifactKey) {
    await loadArtifact(card.run_id, artifactKey, { preserveMode: true });
  }
  if (!options.preserveMode) {
    setMode("workspace");
    setHeroStatus(card.status, "hero.selectedCard", { cardId: card.card_id });
  }
}

async function loadWorkspace() {
  setWorkspaceFeedback("workspace.refreshing");
  await loadWorkspaceOverview();
  await loadWorkspaceCards();
  setWorkspaceFeedback("workspace.refreshed");
}

function handleRuntimeError(error) {
  setLaunchFeedback(error.message, {}, { raw: true });
  setHeroStatus("fail", "hero.runtimeLaneFailed");
}

function handleWorkspaceError(error) {
  setWorkspaceFeedback(error.message, {}, { raw: true });
  setHeroStatus("fail", "hero.workspaceLoadFailed");
}

ui.languageZhButton.addEventListener("click", () => applyLanguage("zh"));
ui.languageEnButton.addEventListener("click", () => applyLanguage("en"));
ui.workspaceModeButton.addEventListener("click", () => setMode("workspace"));
ui.runtimeModeButton.addEventListener("click", () => setMode("runtime"));
ui.openRuntimeButton.addEventListener("click", () => {
  if (!state.selectedWorkspaceRunId) return;
  openRunInRuntimeLane(state.selectedWorkspaceRunId).catch(handleRuntimeError);
});
ui.workspaceFilters.addEventListener("change", () => {
  loadWorkspace().catch(handleWorkspaceError);
});
ui.workspaceRefreshButton.addEventListener("click", () => {
  loadWorkspace().catch(handleWorkspaceError);
});
ui.launcherForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const formData = new FormData(ui.launcherForm);
  const payload = Object.fromEntries(formData.entries());
  setLaunchFeedback("runtime.launchingRun");
  try {
    const response = await fetchJson("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    setLaunchFeedback("runtime.runLaunched", { runId: response.run.run_id });
    await loadRuns();
    await loadRunDetail(response.run.run_id);
    await loadWorkspace();
  } catch (error) {
    handleRuntimeError(error);
  }
});
ui.refreshButton.addEventListener("click", () => {
  loadRuns().catch(handleRuntimeError);
});

applyLanguage(state.language, { persist: false });
renderEmptyWorkspaceSelection();
renderEmptyRuntimeSelection();
setMode("workspace");

Promise.all([loadRuns(), loadWorkspace()])
  .then(() => {
    setMode("workspace");
    setHeroStatus("pass", "hero.workspaceReady");
  })
  .catch((error) => {
    setLaunchFeedback(error.message, {}, { raw: true });
    setWorkspaceFeedback(error.message, {}, { raw: true });
    setHeroStatus("fail", "hero.initialLoadFailed");
  });
