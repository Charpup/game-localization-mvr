const LANG_STORAGE_KEY = "human_delivery_ui.language";
const ALL_LANES = ["act", "review", "watch", "done"];

const TEXT = {
  zh: {
    "page.title": "Loc-MVR 人类交付控制台",
    "brand.eyebrow": "Loc-MVR Human Delivery",
    "brand.title": "Loc-MVR 人类交付控制台",
    "brand.copy": "先让人完成任务，再让专家看细节。普通用户从任务向导开始，运营在 Ops Monitor 里追踪，专家保留 Pro Runtime。",
    "mode.tasks": "任务控制台",
    "mode.workspace": "Ops Monitor",
    "mode.runtime": "Pro Runtime",
    "aria.languageSwitch": "语言切换",
    "aria.modeSwitch": "视图切换",
    "aria.laneFilter": "看板泳道过滤",
    "aria.inspectorTabs": "Case Details 标签页",
    "common.refresh": "刷新",
    "common.na": "未提供",
    "common.none": "无",
    "common.yes": "是",
    "common.no": "否",
    "common.previewUnavailable": "这个结果项暂不支持直接预览。",
    "common.technicalDetails": "技术细节",
    "common.openable": "可预览",
    "common.downloadable": "可导出",
    "common.sourceRun": "关联 Run",
    "common.empty": "暂无内容",
    "hero.waiting": "正在读取任务与运行态数据",
    "hero.tasksReady": "任务控制台已就绪",
    "hero.taskSelected": "已选择任务 {title}",
    "hero.workspaceSelected": "已进入 Ops Monitor：{runId}",
    "hero.runtimeSelected": "已进入 Pro Runtime：{runId}",
    "hero.taskCreated": "已创建任务 {title}",
    "hero.loadFailed": "界面数据读取失败",
    "hero.taskActionDone": "任务动作已执行",
    "status.draft": "草稿",
    "status.queued": "排队中",
    "status.running": "运行中",
    "status.needs_user_action": "待你处理",
    "status.needs_operator_review": "待运营复核",
    "status.ready_for_download": "可领取结果",
    "status.failed": "失败",
    "status.pass": "通过",
    "status.warn": "告警",
    "status.fail": "失败",
    "status.blocked": "阻塞",
    "status.pending": "等待中",
    "status.unknown": "未知",
    "status.open": "打开",
    "status.closed": "关闭",
    "status.completed": "已完成",
    "task.loading": "正在读取任务列表...",
    "task.wizardHint": "先用现有 pipeline 跑通最小闭环，再决定是否需要更重的交互框架。",
    "task.noTaskSelected": "尚未选择任务",
    "task.selectTaskHint": "选择一个任务，查看当前阶段、为什么重要，以及接下来可执行的动作。",
    "task.emptySummary": "尚未载入任务摘要。",
    "task.emptyWhy": "尚未载入任务背景。",
    "task.emptyStep": "尚未载入阶段信息。",
    "task.emptyRequired": "尚未载入推荐动作。",
    "task.noActions": "暂无可执行动作。",
    "task.noDeliveries": "任务完成后会在这里出现可查看的结果包与报告。",
    "task.emptyPreview": "选择一个结果项后会在这里预览。",
    "task.overviewTotal": "任务总数",
    "task.overviewAttention": "需要关注",
    "task.overviewRunning": "进行中",
    "task.overviewReady": "可领取结果",
    "task.latestRun": "最新 Run",
    "task.currentState": "当前状态",
    "task.targetLocale": "目标语言",
    "task.verifyMode": "验证模式",
    "task.startSuccess": "任务已创建并触发首个 Run。",
    "task.taskListEmpty": "还没有任务。可以先从上面的 Task Wizard 开始。",
    "task.deliveryEmptyForStatus": "当前阶段还没有可交付结果。",
    "task.action.refresh_status": "刷新状态",
    "task.action.open_monitor": "去 Ops Monitor 查看",
    "task.action.open_runtime": "去 Pro Runtime 查看",
    "task.action.view_deliveries": "查看结果包",
    "task.action.rerun": "重新运行",
    "workspace.emptyOverview": "尚未载入监控概览。",
    "workspace.waiting": "正在刷新监控看板...",
    "workspace.refreshed": "Ops Monitor 已刷新。",
    "workspace.noCaseSelected": "尚未选择 case",
    "workspace.selectCaseHint": "选择一个 ops case，查看上下文、证据和运行态预览。",
    "workspace.loadingCase": "正在载入 case 详情...",
    "workspace.laneEmpty": "这一列暂时没有 case。",
    "workspace.emptyDecision": "尚未载入 case 摘要。",
    "workspace.emptySignals": "尚未载入信号摘要。",
    "workspace.emptyEvidence": "尚未载入证据摘要。",
    "workspace.emptyRuntime": "切换到 Runtime Peek 后会按需读取运行态预览。",
    "workspace.runtimePeekLoading": "正在读取运行态预览...",
    "workspace.statsOpenCases": "打开 Case",
    "workspace.statsOpenCasesCopy": "仍需跟进的 run 级 case 数量。",
    "workspace.statsOpenCards": "打开卡片",
    "workspace.statsOpenCardsCopy": "需要继续处理的运营动作。",
    "workspace.statsReview": "待复核票数",
    "workspace.statsReviewCopy": "仍等待人工判断的事项数量。",
    "workspace.statsDrift": "存在漂移的 Run",
    "workspace.statsDriftCopy": "治理或 KPI 漂移已浮现的 run 数量。",
    "workspace.statsRecent": "最近 Run",
    "workspace.statsRecentCopy": "最新进入监控面的 run。",
    "workspace.caseWhy": "为什么这个 case 会浮现",
    "workspace.caseActions": "建议动作",
    "workspace.caseCards": "关联卡片",
    "workspace.signalsReview": "复核负载",
    "workspace.signalsKpi": "KPI 快照",
    "workspace.signalsDrift": "漂移信号",
    "workspace.evidenceArtifacts": "证据与产物",
    "workspace.evidenceRefs": "证据引用",
    "workspace.adrRefs": "ADR 引用",
    "filters.targetLocalePlaceholder": "如 en-US",
    "filters.searchPlaceholder": "按 run、摘要或动作搜索",
    "runtime.verifyModeFull": "完整",
    "runtime.verifyModePreflight": "预检",
    "runtime.noRunSelected": "尚未选择 Run",
    "runtime.runHint": "选择一个 run 以检查阶段状态和证据。",
    "runtime.emptyTimeline": "尚未选择 run。",
    "runtime.emptyTimelineData": "这个 run 暂时没有时间线数据。",
    "runtime.emptyVerify": "尚未载入验证报告。",
    "runtime.emptyIssue": "尚未载入问题报告。",
    "runtime.emptyArtifactPanel": "选择一个产物后可在此预览。",
    "runtime.noRunsDiscovered": "尚未发现任何 run。",
    "runtime.noArtifacts": "这个 run 没有声明任何产物。",
    "runtime.refreshingInventory": "正在刷新运行态清单...",
    "runtime.inventoryRefreshed": "运行态清单已刷新。",
    "runtime.launchingRun": "正在启动代表性 smoke run...",
    "runtime.runLaunched": "Run {runId} 已启动。",
    "runtime.runDirectory": "Run 目录：{runDir}",
    "runtime.artifactNoTextPreview": "这个产物没有文本预览。",
    "labels.runtime": "运行态",
    "labels.target": "目标语言",
    "labels.verify": "验证",
    "labels.overall": "整体",
    "labels.issueCount": "问题数",
    "labels.qaRows": "QA 行",
    "labels.pending": "等待中",
    "labels.total": "总数",
    "labels.severities": "严重级别",
    "labels.stages": "阶段",
    "labels.topIssues": "高频问题",
    "labels.bySeverity": "按严重级别",
    "labels.byStage": "按阶段",
    "labels.cards": "卡片概览",
    "labels.startedAt": "开始时间",
    "labels.priority": "优先级",
    "labels.run": "Run",
    "labels.reviewTickets": "复核票",
    "labels.drift": "漂移",
    "labels.requiresHuman": "需要人工",
    "labels.artifacts": "产物",
  },
  en: {},
};

Object.assign(TEXT.zh, {
  "task.heroKicker": "Task Console",
  "task.heroTitle": "先从一件能完成的事开始",
  "task.heroCopy": "这里回答三个问题：我能开始什么、我手上有哪些待办、做完后去哪里拿结果。",
  "task.startCta": "开始新本地化",
  "task.continueCta": "继续处理待办",
  "task.overviewKicker": "Queue Snapshot",
  "task.overviewTitle": "任务收件箱概览",
  "task.wizardKicker": "Task Wizard",
  "task.wizardTitle": "开始一个本地化任务",
  "task.formTitle": "任务标题",
  "task.formTitlePlaceholder": "例如：April launch copy",
  "task.formInput": "输入文件",
  "task.formInputPlaceholder": "例如 fixtures/input.csv",
  "task.formTarget": "目标语言",
  "task.formVerify": "验证模式",
  "task.launchButton": "创建任务并启动",
  "task.inboxKicker": "My Tasks",
  "task.inboxTitle": "继续处理待办",
  "task.detailKicker": "Task Detail",
  "task.summaryLabel": "任务摘要",
  "task.whyLabel": "为什么值得现在处理",
  "task.stepLabel": "当前阶段",
  "task.requiredLabel": "推荐动作",
  "task.actionsLabel": "现在可以做什么",
  "task.deliveryLabel": "结果包与报告",
  "task.previewLabel": "结果预览",
  "workspace.kicker": "Ops Monitor",
  "workspace.overviewTitle": "Pipeline Monitor",
  "workspace.boardKicker": "Case Board",
  "workspace.boardTitle": "Ops Cases",
  "workspace.laneAll": "全部",
  "workspace.laneAct": "Act",
  "workspace.laneActCopy": "失败或高优先级事项。",
  "workspace.laneReview": "Review",
  "workspace.laneReviewCopy": "等待人工判断的事项。",
  "workspace.laneWatch": "Watch",
  "workspace.laneWatchCopy": "值得持续观察的信号。",
  "workspace.laneDone": "Done",
  "workspace.laneDoneCopy": "仅在查看全部时显示。",
  "workspace.inspectorKicker": "Case Details",
  "workspace.openRuntimeButton": "打开 Pro Runtime",
  "workspace.tabDecision": "Case Brief",
  "workspace.tabSignals": "Signals",
  "workspace.tabEvidence": "Evidence",
  "workspace.tabRuntime": "Runtime Peek",
  "filters.status": "状态",
  "filters.status_open": "打开",
  "filters.status_all": "全部",
  "filters.targetLocale": "目标语言区域",
  "filters.search": "搜索",
  "runtime.launcherKicker": "Pro Runtime",
  "runtime.launcherTitle": "启动 Run",
  "runtime.inputCsv": "输入 CSV",
  "runtime.inputPlaceholder": "输入 CSV 路径",
  "runtime.targetLanguage": "目标语言",
  "runtime.verifyMode": "验证模式",
  "runtime.launchButton": "启动 Run",
  "runtime.recentRunsKicker": "Recent Runs",
  "runtime.timelineTitle": "Run 时间线",
  "runtime.selectedRunKicker": "Selected Run",
  "runtime.verificationKicker": "Verification",
  "runtime.verifyTitle": "验证摘要",
  "runtime.issuesKicker": "Issues",
  "runtime.issueTitle": "问题摘要",
  "runtime.artifactsKicker": "Artifacts",
  "runtime.artifactsTitle": "产物",
  "runtime.artifactHint": "Pro Runtime 会保留工程细节，但默认把路径折叠进技术说明里。",
});

Object.assign(TEXT.en, {
  "page.title": "Loc-MVR Human Delivery Console",
  "brand.eyebrow": "Loc-MVR Human Delivery",
  "brand.title": "Loc-MVR Human Delivery Console",
  "brand.copy": "Let people finish the task first, then let experts inspect the machinery. The default path starts in Task Wizard, operators follow the Ops Monitor, and specialists keep Pro Runtime.",
  "mode.tasks": "Task Console",
  "mode.workspace": "Ops Monitor",
  "mode.runtime": "Pro Runtime",
  "aria.languageSwitch": "Language switch",
  "aria.modeSwitch": "Surface switch",
  "aria.laneFilter": "Board lane filter",
  "aria.inspectorTabs": "Case details tabs",
  "common.refresh": "Refresh",
  "common.na": "n/a",
  "common.none": "none",
  "common.yes": "yes",
  "common.no": "no",
  "common.previewUnavailable": "This delivery item cannot be previewed inline.",
  "common.technicalDetails": "Technical details",
  "common.openable": "Previewable",
  "common.downloadable": "Exportable",
  "common.sourceRun": "Linked run",
  "common.empty": "No data",
  "hero.waiting": "Loading tasks and runtime data",
  "hero.tasksReady": "Task console ready",
  "hero.taskSelected": "Selected task {title}",
  "hero.workspaceSelected": "Ops Monitor focused on {runId}",
  "hero.runtimeSelected": "Pro Runtime focused on {runId}",
  "hero.taskCreated": "Created task {title}",
  "hero.loadFailed": "Failed to load UI data",
  "hero.taskActionDone": "Task action completed",
  "status.draft": "draft",
  "status.queued": "queued",
  "status.running": "running",
  "status.needs_user_action": "needs your action",
  "status.needs_operator_review": "needs operator review",
  "status.ready_for_download": "ready for download",
  "status.failed": "failed",
  "status.pass": "pass",
  "status.warn": "warn",
  "status.fail": "fail",
  "status.blocked": "blocked",
  "status.pending": "pending",
  "status.unknown": "unknown",
  "status.open": "open",
  "status.closed": "closed",
  "status.completed": "completed",
  "task.heroKicker": "Task Console",
  "task.heroTitle": "Start with one task you can finish",
  "task.heroCopy": "This surface answers three questions: what can I start, what needs my attention, and where do I collect the result.",
  "task.startCta": "Start a localization task",
  "task.continueCta": "Continue pending tasks",
  "task.overviewKicker": "Queue Snapshot",
  "task.overviewTitle": "Task inbox overview",
  "task.wizardKicker": "Task Wizard",
  "task.wizardTitle": "Start a localization task",
  "task.wizardHint": "First prove the minimum happy path with the current pipeline, then decide whether heavier interaction is worth it.",
  "task.formTitle": "Task title",
  "task.formTitlePlaceholder": "For example: April launch copy",
  "task.formInput": "Input file",
  "task.formInputPlaceholder": "For example: fixtures/input.csv",
  "task.formTarget": "Target locale",
  "task.formVerify": "Verify mode",
  "task.launchButton": "Create task and launch",
  "task.inboxKicker": "My Tasks",
  "task.inboxTitle": "Continue what needs attention",
  "task.detailKicker": "Task Detail",
  "task.loading": "Loading tasks...",
  "task.noTaskSelected": "No task selected",
  "task.selectTaskHint": "Choose a task to see the current stage, why it matters, and the next action you can take.",
  "task.summaryLabel": "Task summary",
  "task.emptySummary": "No task summary loaded yet.",
  "task.whyLabel": "Why it matters now",
  "task.emptyWhy": "No task background loaded yet.",
  "task.stepLabel": "Current stage",
  "task.emptyStep": "No stage information loaded yet.",
  "task.requiredLabel": "Recommended action",
  "task.emptyRequired": "No recommended action loaded yet.",
  "task.actionsLabel": "What you can do now",
  "task.noActions": "No available actions.",
  "task.deliveryLabel": "Deliveries and reports",
  "task.noDeliveries": "The delivery bundle and reports will appear here when the task reaches a releasable state.",
  "task.previewLabel": "Preview",
  "task.emptyPreview": "Choose a delivery item to preview it here.",
  "task.overviewTotal": "Total tasks",
  "task.overviewAttention": "Needs attention",
  "task.overviewRunning": "In progress",
  "task.overviewReady": "Ready to collect",
  "task.latestRun": "Latest run",
  "task.currentState": "Current state",
  "task.targetLocale": "Target locale",
  "task.verifyMode": "Verify mode",
  "task.startSuccess": "The task was created and its first run has been launched.",
  "task.taskListEmpty": "No tasks yet. Start with the Task Wizard above.",
  "task.deliveryEmptyForStatus": "No delivery bundle is available at the current stage.",
  "task.action.refresh_status": "Refresh status",
  "task.action.open_monitor": "Open Ops Monitor",
  "task.action.open_runtime": "Open Pro Runtime",
  "task.action.view_deliveries": "View deliveries",
  "task.action.rerun": "Rerun task",
  "workspace.kicker": "Ops Monitor",
  "workspace.overviewTitle": "Pipeline Monitor",
  "workspace.emptyOverview": "No monitor overview loaded yet.",
  "workspace.waiting": "Refreshing the monitor board...",
  "workspace.boardKicker": "Case Board",
  "workspace.boardTitle": "Ops Cases",
  "workspace.laneAll": "All",
  "workspace.laneAct": "Act",
  "workspace.laneActCopy": "Failures or highest-priority interventions.",
  "workspace.laneReview": "Review",
  "workspace.laneReviewCopy": "Cases that need a human judgment.",
  "workspace.laneWatch": "Watch",
  "workspace.laneWatchCopy": "Signals worth monitoring over time.",
  "workspace.laneDone": "Done",
  "workspace.laneDoneCopy": "Only shown in the all view.",
  "workspace.inspectorKicker": "Case Details",
  "workspace.noCaseSelected": "No case selected",
  "workspace.selectCaseHint": "Choose an ops case to inspect its context, evidence, and runtime peek.",
  "workspace.openRuntimeButton": "Open Pro Runtime",
  "workspace.tabDecision": "Case Brief",
  "workspace.tabSignals": "Signals",
  "workspace.tabEvidence": "Evidence",
  "workspace.tabRuntime": "Runtime Peek",
  "workspace.refreshed": "Ops Monitor refreshed.",
  "workspace.loadingCase": "Loading case details...",
  "workspace.laneEmpty": "No cases in this lane right now.",
  "workspace.emptyDecision": "No case brief loaded yet.",
  "workspace.emptySignals": "No signal summary loaded yet.",
  "workspace.emptyEvidence": "No evidence summary loaded yet.",
  "workspace.emptyRuntime": "Runtime preview loads on demand when you open Runtime Peek.",
  "workspace.runtimePeekLoading": "Loading runtime peek...",
  "workspace.statsOpenCases": "Open cases",
  "workspace.statsOpenCasesCopy": "Run-level cases that still need follow-up.",
  "workspace.statsOpenCards": "Open cards",
  "workspace.statsOpenCardsCopy": "Operator actions that still need attention.",
  "workspace.statsReview": "Pending review tickets",
  "workspace.statsReviewCopy": "Items still waiting for human judgment.",
  "workspace.statsDrift": "Runs with drift",
  "workspace.statsDriftCopy": "Runs where governance or KPI drift is visible.",
  "workspace.statsRecent": "Recent runs",
  "workspace.statsRecentCopy": "The most recent runs visible in the monitor.",
  "workspace.caseWhy": "Why this case is surfaced",
  "workspace.caseActions": "Recommended actions",
  "workspace.caseCards": "Linked cards",
  "workspace.signalsReview": "Review workload",
  "workspace.signalsKpi": "KPI snapshot",
  "workspace.signalsDrift": "Drift signals",
  "workspace.evidenceArtifacts": "Evidence and artifacts",
  "workspace.evidenceRefs": "Evidence references",
  "workspace.adrRefs": "ADR references",
  "filters.status": "Status",
  "filters.status_open": "open",
  "filters.status_all": "all",
  "filters.targetLocale": "Target locale",
  "filters.targetLocalePlaceholder": "For example: en-US",
  "filters.search": "Search",
  "filters.searchPlaceholder": "Search by run, summary, or action",
  "runtime.launcherKicker": "Pro Runtime",
  "runtime.launcherTitle": "Launch Run",
  "runtime.launcherHint": "Use the current pipeline defaults behind the shell.",
  "runtime.inputCsv": "Input CSV",
  "runtime.inputPlaceholder": "Input CSV path",
  "runtime.targetLanguage": "Target locale",
  "runtime.verifyMode": "Verify mode",
  "runtime.verifyModeFull": "full",
  "runtime.verifyModePreflight": "preflight",
  "runtime.launchButton": "Launch run",
  "runtime.recentRunsKicker": "Recent Runs",
  "runtime.timelineTitle": "Run Timeline",
  "runtime.selectedRunKicker": "Selected Run",
  "runtime.noRunSelected": "No run selected",
  "runtime.runHint": "Choose a run to inspect stage status and evidence.",
  "runtime.emptyTimeline": "No run selected yet.",
  "runtime.emptyTimelineData": "This run has no timeline data yet.",
  "runtime.verificationKicker": "Verification",
  "runtime.verifyTitle": "Verification summary",
  "runtime.emptyVerify": "No verify report loaded yet.",
  "runtime.issuesKicker": "Issues",
  "runtime.issueTitle": "Issue summary",
  "runtime.emptyIssue": "No issue report loaded yet.",
  "runtime.artifactsKicker": "Artifacts",
  "runtime.artifactsTitle": "Artifacts",
  "runtime.artifactHint": "Pro Runtime keeps the engineering detail, but technical paths stay collapsed by default.",
  "runtime.emptyArtifactPanel": "Choose an artifact to preview it here.",
  "runtime.noRunsDiscovered": "No runs discovered yet.",
  "runtime.noArtifacts": "No artifacts declared for this run.",
  "runtime.refreshingInventory": "Refreshing runtime inventory...",
  "runtime.inventoryRefreshed": "Runtime inventory refreshed.",
  "runtime.launchingRun": "Launching representative smoke run...",
  "runtime.runLaunched": "Run {runId} launched.",
  "runtime.runDirectory": "Run directory: {runDir}",
  "runtime.artifactNoTextPreview": "This artifact has no text preview.",
  "labels.runtime": "Runtime",
  "labels.target": "Target",
  "labels.verify": "Verify",
  "labels.overall": "Overall",
  "labels.issueCount": "Issues",
  "labels.qaRows": "QA rows",
  "labels.pending": "Pending",
  "labels.total": "Total",
  "labels.severities": "Severities",
  "labels.stages": "Stages",
  "labels.topIssues": "Top issues",
  "labels.bySeverity": "By severity",
  "labels.byStage": "By stage",
  "labels.cards": "Card mix",
  "labels.startedAt": "Started",
  "labels.priority": "Priority",
  "labels.run": "Run",
  "labels.reviewTickets": "Review tickets",
  "labels.drift": "Drift",
  "labels.requiresHuman": "Needs human",
  "labels.artifacts": "Artifacts",
});

Object.assign(TEXT.zh, {
  "aria.wizardEntry": "任务向导入口模式",
  "aria.uploadDropzone": "上传 CSV 文件",
  "aria.taskBuckets": "任务收件箱分组",
  "task.entryUpload": "上传 CSV",
  "task.entryPath": "高级路径输入",
  "task.dropBadge": "CSV 上传",
  "task.dropTitle": "拖拽 CSV 到这里，或点击选择文件",
  "task.dropCopy": "默认入口只接受 CSV，并会先把文件暂存到本地 staged 区。",
  "task.stagedKicker": "已暂存文件",
  "task.noStagedFile": "尚未暂存文件",
  "task.stagedHint": "选择 CSV 后会在这里显示文件名和暂存状态。",
  "task.chooseFile": "选择文件",
  "task.clearUpload": "清空",
  "task.pathKicker": "高级输入",
  "task.pathTitle": "使用已有文件路径",
  "task.pathCopy": "适合已经知道本地 CSV 路径的高级用户。默认流程仍建议直接上传。",
  "task.submitNote": "任务对象会先被创建，再由底层 pipeline 触发首个 run。",
  "task.searchLabel": "搜索任务",
  "task.searchPlaceholder": "按任务标题、输入文件或 run 搜索",
  "task.primaryActionLabel": "接下来要做什么",
  "task.noteLabel": "变更说明",
  "task.notePlaceholder": "说明希望修改什么、为什么修改，以及希望怎样处理。",
  "task.noteHint": "只有在请求修改时才会提交这段说明。",
  "task.latestFeedbackLabel": "上次人工决策",
  "task.bundleLabel": "结果包",
  "task.bundleCopy": "只展示对人类有意义的结果、报告与说明，技术产物会折叠到技术细节里。",
  "task.noTechnicalDetails": "当前没有额外的技术细节。",
  "task.linkedRunsLabel": "关联 Run 历史",
  "task.noLinkedRuns": "任务还没有关联任何 run。",
  "task.historyLabel": "任务事件时间线",
  "task.noHistory": "当前还没有额外历史记录。",
  "task.backToTask": "返回任务控制台",
  "task.action.approve_delivery": "批准结果包",
  "task.action.request_changes": "请求修改",
  "task.action.archive_task": "归档任务",
  "task.action.download_delivery": "下载文件",
});

Object.assign(TEXT.en, {
  "aria.wizardEntry": "Task wizard entry mode",
  "aria.uploadDropzone": "Upload a CSV file",
  "aria.taskBuckets": "Task inbox buckets",
  "task.entryUpload": "Upload CSV",
  "task.entryPath": "Advanced path input",
  "task.dropBadge": "CSV Upload",
  "task.dropTitle": "Drop a CSV here, or click to choose a file",
  "task.dropCopy": "The default path only accepts CSV files and stages them locally before launch.",
  "task.stagedKicker": "Staged file",
  "task.noStagedFile": "No staged file yet",
  "task.stagedHint": "After you choose a CSV, the staged filename and upload status will appear here.",
  "task.chooseFile": "Choose file",
  "task.clearUpload": "Clear",
  "task.pathKicker": "Advanced input",
  "task.pathTitle": "Use an existing file path",
  "task.pathCopy": "Best for advanced users who already know the local CSV path. The default flow still recommends upload.",
  "task.submitNote": "The task record is created first, then the underlying pipeline launches the first run.",
  "task.searchLabel": "Search tasks",
  "task.searchPlaceholder": "Search by title, input file, or run",
  "task.primaryActionLabel": "What should happen next",
  "task.noteLabel": "Change request note",
  "task.notePlaceholder": "Explain what should change, why it matters, and how the package should be adjusted.",
  "task.noteHint": "This note is only sent when you request changes.",
  "task.latestFeedbackLabel": "Latest human decision",
  "task.bundleLabel": "Delivery bundle",
  "task.bundleCopy": "Show the human-facing result package first, and keep raw engineering artifacts inside technical details.",
  "task.noTechnicalDetails": "No extra technical details are available right now.",
  "task.linkedRunsLabel": "Linked run history",
  "task.noLinkedRuns": "No runs have been linked to this task yet.",
  "task.historyLabel": "Task event timeline",
  "task.noHistory": "No additional task history is available yet.",
  "task.backToTask": "Back to Task Console",
  "task.action.approve_delivery": "Approve package",
  "task.action.request_changes": "Request changes",
  "task.action.archive_task": "Archive task",
  "task.action.download_delivery": "Download file",
});

const state = { language: getStoredLanguage(), mode: "tasks", heroMessage: { status: "unknown", key: "hero.waiting", vars: {}, raw: false }, taskFeedbackMessage: { key: "task.wizardHint", vars: {}, raw: false }, workspaceFeedbackMessage: { key: "workspace.waiting", vars: {}, raw: false }, launchFeedbackMessage: { key: "runtime.launcherHint", vars: {}, raw: false }, taskOverview: null, tasks: [], selectedTaskId: null, selectedTask: null, taskDeliveries: [], selectedDeliveryId: null, selectedDeliveryPreview: null, taskLoading: false, workspaceOverview: null, workspaceCases: [], selectedCaseId: null, workspaceDetail: null, workspaceDetailLoadingRunId: null, workspaceFilters: { status: "open", targetLocale: "", query: "", lane: "all" }, inspectorTab: "decision", runtimePeekCache: {}, runtimePeekLoadingRunId: null, runs: [], selectedRunId: null, selectedRunDetail: null, selectedArtifactKey: null, selectedArtifact: null };

const ui = {
  heroStatus: document.getElementById("hero-status"), taskView: document.getElementById("task-view"), workspaceView: document.getElementById("workspace-view"), runtimeView: document.getElementById("runtime-view"), modeTasksButton: document.getElementById("mode-tasks"), modeWorkspaceButton: document.getElementById("mode-workspace"), modeRuntimeButton: document.getElementById("mode-runtime"), languageZhButton: document.getElementById("lang-zh"), languageEnButton: document.getElementById("lang-en"), heroStartTaskButton: document.getElementById("hero-start-task"), heroContinueTasksButton: document.getElementById("hero-continue-tasks"), taskRefreshButton: document.getElementById("task-refresh-button"), taskFeedback: document.getElementById("task-feedback"), taskForm: document.getElementById("task-form"), taskOverview: document.getElementById("task-overview"), taskList: document.getElementById("task-list"), taskTitle: document.getElementById("task-title"), taskMeta: document.getElementById("task-meta"), taskSummary: document.getElementById("task-summary"), taskWhy: document.getElementById("task-why"), taskStep: document.getElementById("task-step"), taskRequired: document.getElementById("task-required"), taskActionBar: document.getElementById("task-action-bar"), taskDeliveryList: document.getElementById("task-delivery-list"), taskPreview: document.getElementById("task-preview"), overviewRibbon: document.getElementById("overview-ribbon"), workspaceFeedback: document.getElementById("workspace-feedback"), workspaceRefreshButton: document.getElementById("workspace-refresh-button"), caseStatusFilter: document.getElementById("case-status-filter"), caseLocaleFilter: document.getElementById("case-locale-filter"), caseQueryFilter: document.getElementById("case-query-filter"), laneFilterButtons: Array.from(document.querySelectorAll(".lane-filter-button")), laneSections: Object.fromEntries(ALL_LANES.map((lane) => [lane, document.querySelector(`[data-lane-section="${lane}"]`)])), laneLists: Object.fromEntries(ALL_LANES.map((lane) => [lane, document.getElementById(`lane-${lane}`)])), laneCounts: Object.fromEntries(ALL_LANES.map((lane) => [lane, document.getElementById(`lane-count-${lane}`)])), workspaceRunTitle: document.getElementById("workspace-run-title"), workspaceRunMeta: document.getElementById("workspace-run-meta"), openRuntimeButton: document.getElementById("open-runtime-button"), tabButtons: Array.from(document.querySelectorAll(".tab-button")), inspectorPanels: { decision: document.getElementById("inspector-decision"), signals: document.getElementById("inspector-signals"), evidence: document.getElementById("inspector-evidence"), runtime: document.getElementById("inspector-runtime") }, launchFeedback: document.getElementById("launch-feedback"), launcherForm: document.getElementById("launcher-form"), refreshButton: document.getElementById("refresh-button"), runsList: document.getElementById("runs-list"), runTitle: document.getElementById("run-title"), runMeta: document.getElementById("run-meta"), timelinePanel: document.getElementById("timeline-panel"), verifySummary: document.getElementById("verify-summary"), issueSummary: document.getElementById("issue-summary"), artifactList: document.getElementById("artifact-list"), artifactPanel: document.getElementById("artifact-panel") };

let workspaceQueryDebounce = null;
let taskQueryDebounce = null;

Object.assign(state, {
  taskBucket: "needs_your_action",
  taskQuery: "",
  wizardMode: "upload",
  stagedUpload: null,
  returnTaskId: null,
  taskLoadingTaskId: "",
  taskListRequestSeq: 0,
  taskSelectionRequestSeq: 0,
});

Object.assign(ui, {
  taskMetricsStrip: document.getElementById("task-metrics-strip"),
  taskPrimaryAction: document.getElementById("task-primary-action"),
  taskNoteSection: document.getElementById("task-note-section"),
  taskNoteInput: document.getElementById("task-note-input"),
  taskFeedbackSection: document.getElementById("task-feedback-section"),
  taskLatestFeedback: document.getElementById("task-latest-feedback"),
  taskBundleGroups: document.getElementById("task-bundle-groups"),
  taskTechnicalDetails: document.getElementById("task-technical-details"),
  taskLinkedRuns: document.getElementById("task-linked-runs"),
  taskHistory: document.getElementById("task-history"),
  taskBucketTabs: document.getElementById("task-bucket-tabs"),
  taskQueryFilter: document.getElementById("task-query-filter"),
  taskFileInput: document.getElementById("task-file-input"),
  taskDropzone: document.getElementById("task-dropzone"),
  stagedUploadCard: document.getElementById("staged-upload-card"),
  taskStagedFilename: document.getElementById("task-staged-filename"),
  taskStagedMeta: document.getElementById("task-staged-meta"),
  taskChooseFileButton: document.getElementById("task-choose-file-button"),
  taskClearUploadButton: document.getElementById("task-clear-upload-button"),
  taskPathInput: document.getElementById("task-path-input"),
  wizardModeButtons: Array.from(document.querySelectorAll("[data-wizard-mode]")),
  wizardUploadPanel: document.getElementById("wizard-upload-panel"),
  wizardPathPanel: document.getElementById("wizard-path-panel"),
  taskSubmitButton: document.getElementById("task-submit-button"),
  taskSubmitNote: document.getElementById("task-submit-note"),
  runtimeLaunchButton: document.getElementById("runtime-launch-button"),
  workspaceReturnButton: document.getElementById("workspace-return-button"),
  runtimeReturnButton: document.getElementById("runtime-return-button"),
});

function getStoredLanguage() { try { const stored = localStorage.getItem(LANG_STORAGE_KEY); return stored === "en" || stored === "zh" ? stored : "zh"; } catch (error) { return "zh"; } }
function persistLanguage(language) { try { localStorage.setItem(LANG_STORAGE_KEY, language); } catch (error) { return; } }
function rawText(key, fallback = key) { return TEXT[state.language]?.[key] ?? TEXT.zh[key] ?? fallback; }
function t(key, vars = {}, fallback = key) { return String(rawText(key, fallback)).replace(/\{(\w+)\}/g, (_, name) => String(vars[name] ?? "")); }
function escapeHtml(value) { return String(value ?? "").replace(/[&<>"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[char])); }
function humanizeKey(value) { return String(value || "").replace(/[_-]+/g, " ").replace(/\s+/g, " ").trim().replace(/\b\w/g, (char) => char.toUpperCase()); }
function normalizeStatus(status) { const normalized = String(status || "unknown").trim().toLowerCase(); if (["pass", "passed", "success", "ok"].includes(normalized)) return "pass"; if (["warn", "warning"].includes(normalized)) return "warn"; if (["fail", "error"].includes(normalized)) return "fail"; if (["queued", "draft", "running", "pending", "needs_user_action", "needs_operator_review", "blocked", "open", "closed", "completed", "ready_for_download", "failed"].includes(normalized)) return normalized; return "unknown"; }
function displayStatusText(status) { return t(`status.${normalizeStatus(status)}`, {}, humanizeKey(status)); }
function displayVerifyMode(mode) { return String(mode || "").toLowerCase() === "preflight" ? t("runtime.verifyModePreflight") : t("runtime.verifyModeFull"); }
function displayMaybeValue(value) { return value === null || value === undefined || value === "" ? t("common.na") : String(value); }
function displayBool(value) { return value ? t("common.yes") : t("common.no"); }
function formatStartedAt(value) { if (!value) return t("common.na"); const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? String(value) : parsed.toLocaleString(state.language === "zh" ? "zh-CN" : "en-US", { year: "numeric", month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" }); }
function renderPills(items) { const rows = items.filter(Boolean); return rows.length ? `<div class="pill-row">${rows.map((item) => `<span class="pill">${escapeHtml(String(item))}</span>`).join("")}</div>` : ""; }
function renderList(items, emptyText, formatter = (item) => String(item)) { const rows = (items || []).filter(Boolean); return rows.length ? `<ul class="list-block">${rows.map((item) => `<li>${escapeHtml(formatter(item))}</li>`).join("")}</ul>` : `<div class="empty-state">${escapeHtml(emptyText)}</div>`; }
function renderKeyValueGrid(data, emptyText) { const rows = Object.entries(data || {}).filter(([, value]) => value !== null && value !== undefined && value !== ""); return rows.length ? `<div class="kv-grid">${rows.map(([key, value]) => `<article class="kv-item"><p class="panel-kicker">${escapeHtml(humanizeKey(key))}</p><strong>${escapeHtml(typeof value === "object" ? JSON.stringify(value) : String(value))}</strong></article>`).join("")}</div>` : `<div class="empty-state">${escapeHtml(emptyText)}</div>`; }
function renderMetricStrip(items) { const rows = (items || []).filter(Boolean); return rows.length ? `<div class="metric-strip">${rows.map((item) => `<article class="metric-card"><p class="panel-kicker">${escapeHtml(item.label)}</p><strong>${escapeHtml(displayMaybeValue(item.value))}</strong><p>${escapeHtml(item.copy || "")}</p></article>`).join("")}</div>` : ""; }
function statusMarkup(status) { const normalized = normalizeStatus(status); return `<span class="status-pill status-${escapeHtml(normalized)}">${escapeHtml(displayStatusText(normalized))}</span>`; }
function laneMarkup(lane) { return `<span class="lane-chip lane-${escapeHtml(String(lane || "watch"))}">${escapeHtml(humanizeKey(lane))}</span>`; }
function setHeroStatus(status, key, vars = {}, options = {}) { state.heroMessage = { status: normalizeStatus(status), key, vars, raw: Boolean(options.raw) }; renderHeroStatus(); }
function setTaskFeedback(key, vars = {}, options = {}) { state.taskFeedbackMessage = { key, vars, raw: Boolean(options.raw) }; renderTaskFeedback(); }
function setWorkspaceFeedback(key, vars = {}, options = {}) { state.workspaceFeedbackMessage = { key, vars, raw: Boolean(options.raw) }; renderWorkspaceFeedback(); }
function setLaunchFeedback(key, vars = {}, options = {}) { state.launchFeedbackMessage = { key, vars, raw: Boolean(options.raw) }; renderLaunchFeedback(); }
function renderHeroStatus() { const message = state.heroMessage.raw ? state.heroMessage.key : t(state.heroMessage.key, state.heroMessage.vars); ui.heroStatus.innerHTML = `<span class="status-dot status-${escapeHtml(state.heroMessage.status)}"></span><span>${escapeHtml(message)}</span>`; }
function renderTaskFeedback() {
  const message = state.taskFeedbackMessage.raw ? state.taskFeedbackMessage.key : t(state.taskFeedbackMessage.key, state.taskFeedbackMessage.vars);
  ui.taskFeedback.textContent = message;
}
function renderWorkspaceFeedback() { ui.workspaceFeedback.textContent = state.workspaceFeedbackMessage.raw ? state.workspaceFeedbackMessage.key : t(state.workspaceFeedbackMessage.key, state.workspaceFeedbackMessage.vars); }
function renderLaunchFeedback() {
  const message = state.launchFeedbackMessage.raw ? state.launchFeedbackMessage.key : t(state.launchFeedbackMessage.key, state.launchFeedbackMessage.vars);
  ui.launchFeedback.textContent = message;
}
function setMode(mode) { state.mode = ["tasks", "workspace", "runtime"].includes(mode) ? mode : "tasks"; ui.taskView.classList.toggle("hidden", state.mode !== "tasks"); ui.workspaceView.classList.toggle("hidden", state.mode !== "workspace"); ui.runtimeView.classList.toggle("hidden", state.mode !== "runtime"); ui.modeTasksButton.classList.toggle("active", state.mode === "tasks"); ui.modeWorkspaceButton.classList.toggle("active", state.mode === "workspace"); ui.modeRuntimeButton.classList.toggle("active", state.mode === "runtime"); }
function applyLanguage(language, options = {}) { state.language = language === "en" ? "en" : "zh"; if (options.persist !== false) persistLanguage(state.language); document.documentElement.lang = state.language === "zh" ? "zh-CN" : "en"; document.title = t("page.title"); document.querySelectorAll("[data-i18n]").forEach((element) => { element.textContent = t(element.getAttribute("data-i18n"), {}, element.textContent); }); document.querySelectorAll("[data-i18n-placeholder]").forEach((element) => { element.setAttribute("placeholder", t(element.getAttribute("data-i18n-placeholder"), {}, element.getAttribute("placeholder") || "")); }); document.querySelectorAll("[data-i18n-aria-label]").forEach((element) => { element.setAttribute("aria-label", t(element.getAttribute("data-i18n-aria-label"), {}, element.getAttribute("aria-label") || "")); }); ui.languageZhButton.classList.toggle("active", state.language === "zh"); ui.languageEnButton.classList.toggle("active", state.language === "en"); renderAll(); }
function renderAll() { renderHeroStatus(); renderTaskFeedback(); renderWorkspaceFeedback(); renderLaunchFeedback(); renderTaskOverview(); renderTaskList(); renderTaskDetail(); renderWorkspaceOverview(); renderWorkspaceBoard(); renderWorkspaceDetail(); renderRunsRail(); renderRuntimeDetail(state.selectedRunDetail); }
function summarizeStageCounts(counts) { const rows = Object.entries(counts || {}); return rows.length ? rows.map(([key, value]) => `${displayStatusText(key)} ${value}`).join(" · ") : t("common.none"); }
function preferredArtifactKey(run) { const artifacts = Array.isArray(run?.artifacts) ? run.artifacts : []; return artifacts.find((artifact) => artifact.previewable)?.key || run?.allowed_artifact_keys?.[0] || artifacts[0]?.key || null; }
function artifactMetaLabel(key) { const map = { run_manifest: { label: "Execution manifest", use: "Technical record", description: "Technical record of the run inputs, status, and generated artifacts." }, smoke_verify_report: { label: "Verification report", use: "Quality review", description: "Quality check summary for the latest run." }, smoke_issues_report: { label: "Issue summary", use: "Risk review", description: "Structured issue list collected during verification." }, smoke_verify_log: { label: "Run log", use: "Debugging", description: "Plain-text execution log for the selected run." }, smoke_governance_kpi_json: { label: "Governance snapshot", use: "Monitoring", description: "Governance and KPI signal snapshot for the run." }, smoke_review_tickets_jsonl: { label: "Review queue", use: "Review planning", description: "Queued human review tickets generated by this run." }, smoke_feedback_log_jsonl: { label: "Feedback log", use: "Review history", description: "Recorded review feedback attached to this run." }, operator_cards: { label: "Operator cards", use: "Operator evidence", description: "Operator-facing cards linked to the selected run." }, operator_summary_json: { label: "Operator summary JSON", use: "Technical summary", description: "Machine-readable operator summary exported for the run." }, operator_summary_md: { label: "Operator summary Markdown", use: "Human-readable summary", description: "Readable operator summary for sharing and inspection." } }; const base = map[key] || { label: humanizeKey(key), use: t("labels.artifacts"), description: `${humanizeKey(key)} exported from the selected run.` }; if (state.language !== "zh") return base; const zhMap = { "Execution manifest": "执行清单", "Technical record": "技术记录", "Technical record of the run inputs, status, and generated artifacts.": "记录本次运行输入、状态与产物的技术清单。", "Verification report": "验证报告", "Quality review": "质量检查", "Quality check summary for the latest run.": "汇总最新 run 的验证结果。", "Issue summary": "问题清单", "Risk review": "风险排查", "Structured issue list collected during verification.": "结构化整理验证阶段收集到的问题。", "Run log": "运行日志", "Debugging": "排障", "Plain-text execution log for the selected run.": "查看当前 run 的纯文本执行日志。", "Governance snapshot": "治理快照", "Monitoring": "监控", "Governance and KPI signal snapshot for the run.": "查看本次 run 的治理与 KPI 信号。", "Review queue": "复核队列", "Review planning": "复核计划", "Queued human review tickets generated by this run.": "查看该 run 产出的人工复核队列。", "Feedback log": "反馈日志", "Review history": "复核历史", "Recorded review feedback attached to this run.": "查看已经记录到该 run 的复核反馈。", "Operator cards": "运营卡片", "Operator evidence": "运营证据", "Operator-facing cards linked to the selected run.": "查看该 run 关联的运营卡片。", "Operator summary JSON": "运营摘要 JSON", "Technical summary": "技术摘要", "Machine-readable operator summary exported for the run.": "查看机器可读的运营摘要。", "Operator summary Markdown": "运营摘要 Markdown", "Human-readable summary": "人工阅读", "Readable operator summary for sharing and inspection.": "查看适合分享和阅读的运营摘要。" }; return { label: zhMap[base.label] || base.label, use: zhMap[base.use] || base.use, description: zhMap[base.description] || base.description }; }
function taskSummaryText(task) { const title = task.title || t("common.na"); const status = normalizeStatus(task.status); const zh = { draft: `${title} 还没有启动，配置输入后即可开始。`, queued: `${title} 已进入队列，正在等待 pipeline 启动。`, running: `${title} 正在经过翻译和验证流程。`, needs_user_action: `${title} 正在等待你完成明确的人类动作。`, needs_operator_review: `${title} 产生了需要人工判断的信号，暂时不能直接放行。`, ready_for_download: `${title} 已生成可检查、可导出的结果包。`, failed: `${title} 在生成可信结果包前失败了。` }; const en = { draft: `${title} is ready to be configured.`, queued: `${title} has been queued and is waiting for the pipeline to start.`, running: `${title} is currently moving through translation and verification.`, needs_user_action: `${title} is waiting for a specific human action before it can continue.`, needs_operator_review: `${title} produced signals that need a human review before release.`, ready_for_download: `${title} has a delivery bundle ready to inspect and export.`, failed: `${title} failed before producing a trusted delivery bundle.` }; return state.language === "zh" ? (zh[status] || task.summary || title) : (en[status] || task.summary || title); }
function taskWhyText(task) { const status = normalizeStatus(task.status); const zh = { draft: "创建任务后，系统会开始生成对应的本地化 run。", queued: "任务已被接受，当前只是在等待运行资源。", running: "目前不需要人工干预，但你可以切去监控面观察进度。", needs_user_action: "任务当前停在需要你执行的动作上，完成后才能继续。", needs_operator_review: "需要在 Ops Monitor 中判断是否重跑、复核或继续放行。", ready_for_download: "结果已经足够稳定，可以开始检查并导出。", failed: "最新 run 已经失败，建议先定位问题，再决定是否重跑。" }; const en = { draft: "Once created, the pipeline can start the first localization run.", queued: "The job has already been accepted and is waiting for runtime capacity.", running: "No human action is needed yet, but you can open the monitor to watch progress.", needs_user_action: "The task is paused on a human action and cannot continue until it is completed.", needs_operator_review: "Use the Ops Monitor to decide whether this task needs rerun, review, or release.", ready_for_download: "The result is stable enough to inspect and export.", failed: "The latest run failed and should be diagnosed before you decide to rerun." }; return state.language === "zh" ? zh[status] || task.why_it_matters || "" : en[status] || task.why_it_matters || ""; }
function taskStepText(task) { const status = normalizeStatus(task.status); const zh = { draft: "配置输入后即可启动首个 run。", queued: "任务正在等待 pipeline 开始执行。", running: "Pipeline 正在处理行数据并收集验证信号。", needs_user_action: "等待你完成指定的人类动作。", needs_operator_review: "等待运营或审核角色完成判断。", ready_for_download: "结果包已经生成，可继续检查或导出。", failed: "最新 run 失败，当前处于诊断/重跑阶段。" }; const en = { draft: "Configure the inputs and launch the first run.", queued: "The task is waiting for the pipeline to start.", running: "The pipeline is processing rows and collecting validation signals.", needs_user_action: "Waiting for the assigned human action.", needs_operator_review: "Waiting for operator review and a release decision.", ready_for_download: "The delivery bundle is ready to inspect and export.", failed: "The latest run failed and is waiting for diagnosis or rerun." }; return state.language === "zh" ? zh[status] || task.current_step || "" : en[status] || task.current_step || ""; }
function taskRequiredText(task) { const status = normalizeStatus(task.status); const zh = { draft: "检查输入后启动任务。", queued: "可以等待，也可以切去监控面查看实时进展。", running: "观察监控面进度，或者等待结果包出现。", needs_user_action: "完成界面给出的动作，然后再继续。", needs_operator_review: "打开 Ops Monitor，决定是否复核、修复或重跑。", ready_for_download: "打开结果包，检查产物与报告。", failed: "打开 Pro Runtime 诊断问题，或在修复后重跑。" }; const en = { draft: "Review the inputs, then start the task.", queued: "Wait for the run to start, or open the monitor for visibility.", running: "Check the monitor for live progress, or wait for a result bundle.", needs_user_action: "Complete the required action shown on this task before release.", needs_operator_review: "Open the Ops Monitor to review the flagged case and decide whether to rerun.", ready_for_download: "Open the delivery bundle and inspect the exported artifacts.", failed: "Open Pro Runtime for diagnostics or rerun the task after fixing the input." }; return state.language === "zh" ? zh[status] || task.required_human_action || "" : en[status] || task.required_human_action || ""; }
function renderTaskOverview() { const overview = state.taskOverview; if (!overview) { ui.taskOverview.innerHTML = `<div class="empty-state">${escapeHtml(t("task.loading"))}</div>`; return; } const counts = overview.counts_by_status || {}; const attention = (counts.needs_user_action || 0) + (counts.needs_operator_review || 0) + (counts.failed || 0); ui.taskOverview.innerHTML = [{ label: t("task.overviewTotal"), value: overview.total }, { label: t("task.overviewAttention"), value: attention }, { label: t("task.overviewRunning"), value: (counts.queued || 0) + (counts.running || 0) }, { label: t("task.overviewReady"), value: counts.ready_for_download || 0 }].map((item) => `<article class="metric-card"><p class="panel-kicker">${escapeHtml(item.label)}</p><strong>${escapeHtml(item.value)}</strong></article>`).join(""); }
function renderTaskList() { if (!state.tasks.length) { ui.taskList.innerHTML = `<div class="empty-state">${escapeHtml(t("task.taskListEmpty"))}</div>`; return; } ui.taskList.innerHTML = state.tasks.map((task) => `<button type="button" class="task-card ${task.task_id === state.selectedTaskId ? "selected" : ""} ${state.taskLoading && task.task_id === state.selectedTaskId ? "loading" : ""}" data-task-id="${escapeHtml(task.task_id)}"><div class="task-card-header"><div><h3>${escapeHtml(task.title)}</h3><small>${escapeHtml(displayStatusText(task.status))}</small></div>${statusMarkup(task.status)}</div><p class="task-summary">${escapeHtml(taskSummaryText(task))}</p>${renderPills([`${t("task.targetLocale")}: ${displayMaybeValue(task.target_locale)}`, `${t("task.verifyMode")}: ${displayVerifyMode(task.verify_mode)}`, task.latest_run_id ? `${t("task.latestRun")}: ${task.latest_run_id}` : null])}<div class="task-card-footer"><small>${escapeHtml(taskRequiredText(task))}</small><span class="lane-chip lane-${escapeHtml(normalizeStatus(task.latest_run_status))}">${escapeHtml(displayStatusText(task.latest_run_status))}</span></div></button>`).join(""); ui.taskList.querySelectorAll("[data-task-id]").forEach((button) => button.addEventListener("click", () => selectTask(button.dataset.taskId).catch(handleTaskError))); }
function renderEmptyTaskDetail() { ui.taskTitle.textContent = t("task.noTaskSelected"); ui.taskMeta.textContent = t("task.selectTaskHint"); ui.taskSummary.textContent = t("task.emptySummary"); ui.taskWhy.textContent = t("task.emptyWhy"); ui.taskStep.textContent = t("task.emptyStep"); ui.taskRequired.textContent = t("task.emptyRequired"); ui.taskActionBar.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noActions"))}</div>`; ui.taskDeliveryList.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noDeliveries"))}</div>`; ui.taskPreview.innerHTML = escapeHtml(t("task.emptyPreview")); }
function renderTaskPreview() { if (!state.selectedDeliveryPreview) { ui.taskPreview.innerHTML = escapeHtml(t("task.emptyPreview")); return; } const preview = state.selectedDeliveryPreview; const meta = artifactMetaLabel(preview.artifact_key || preview.key); const content = preview.content || (preview.json ? JSON.stringify(preview.json, null, 2) : t("common.previewUnavailable")); ui.taskPreview.innerHTML = `<div class="artifact-header"><strong>${escapeHtml(meta.label)}</strong>${renderPills([`${t("common.sourceRun")}: ${preview.source_run_id}`, `${t("common.openable")}: ${displayBool(preview.openable)}`])}</div><p class="detail-copy">${escapeHtml(meta.description)}</p><pre>${escapeHtml(content)}</pre>${preview.path ? `<details><summary>${escapeHtml(t("common.technicalDetails"))}</summary><div class="technical-note">${escapeHtml(preview.path)}</div></details>` : ""}`; }
function renderTaskDetail() { const task = state.selectedTask; if (!task) { renderEmptyTaskDetail(); return; } ui.taskTitle.textContent = task.title; ui.taskMeta.innerHTML = renderPills([`${t("task.currentState")}: ${displayStatusText(task.status)}`, task.target_locale ? `${t("task.targetLocale")}: ${task.target_locale}` : null, task.verify_mode ? `${t("task.verifyMode")}: ${displayVerifyMode(task.verify_mode)}` : null, task.started_at ? `${t("labels.startedAt")}: ${formatStartedAt(task.started_at)}` : null]); ui.taskSummary.textContent = taskSummaryText(task); ui.taskWhy.textContent = taskWhyText(task); ui.taskStep.textContent = taskStepText(task); ui.taskRequired.textContent = taskRequiredText(task); if ((task.allowed_actions || []).length) { ui.taskActionBar.innerHTML = task.allowed_actions.map((item) => `<button type="button" class="action-button ${item.primary ? "primary" : ""}" data-task-action="${escapeHtml(item.action)}">${escapeHtml(t(`task.action.${item.action}`, {}, humanizeKey(item.action)))}</button>`).join(""); ui.taskActionBar.querySelectorAll("[data-task-action]").forEach((button) => button.addEventListener("click", () => runTaskAction(button.dataset.taskAction).catch(handleTaskError))); } else { ui.taskActionBar.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noActions"))}</div>`; } const deliveries = state.taskDeliveries.length ? state.taskDeliveries : task.output_refs || []; if (deliveries.length) { ui.taskDeliveryList.innerHTML = deliveries.map((delivery) => { const meta = artifactMetaLabel(delivery.artifact_key || delivery.key); return `<button type="button" class="delivery-card ${delivery.delivery_id === state.selectedDeliveryId ? "active" : ""}" data-delivery-id="${escapeHtml(delivery.delivery_id)}"><div class="delivery-card-header"><strong>${escapeHtml(meta.label)}</strong><span class="status-pill status-${escapeHtml(delivery.openable ? "pass" : "unknown")}">${escapeHtml(meta.use)}</span></div><small>${escapeHtml(meta.description)}</small>${renderPills([`${t("common.sourceRun")}: ${delivery.source_run_id}`, `${t("common.openable")}: ${displayBool(delivery.openable)}`, `${t("common.downloadable")}: ${displayBool(delivery.downloadable)}`])}</button>`; }).join(""); ui.taskDeliveryList.querySelectorAll("[data-delivery-id]").forEach((button) => button.addEventListener("click", () => { const delivery = deliveries.find((item) => item.delivery_id === button.dataset.deliveryId); if (delivery) previewDelivery(delivery).catch(handleTaskError); })); } else { ui.taskDeliveryList.innerHTML = `<div class="empty-state">${escapeHtml(task.status === "ready_for_download" ? t("task.noDeliveries") : t("task.deliveryEmptyForStatus"))}</div>`; } renderTaskPreview(); }
function renderWorkspaceOverview() { const overview = state.workspaceOverview; if (!overview) { ui.overviewRibbon.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyOverview"))}</div>`; return; } const recentRuns = Array.isArray(overview.recent_runs) ? overview.recent_runs.slice(0, 4) : []; ui.overviewRibbon.innerHTML = `<article class="metric-card"><p class="panel-kicker">${escapeHtml(t("workspace.statsOpenCases"))}</p><strong>${escapeHtml(overview.open_case_count || 0)}</strong><p>${escapeHtml(t("workspace.statsOpenCasesCopy"))}</p></article><article class="metric-card"><p class="panel-kicker">${escapeHtml(t("workspace.statsOpenCards"))}</p><strong>${escapeHtml(overview.open_card_count || 0)}</strong><p>${escapeHtml(t("workspace.statsOpenCardsCopy"))}</p></article><article class="metric-card"><p class="panel-kicker">${escapeHtml(t("workspace.statsReview"))}</p><strong>${escapeHtml(overview.open_review_tickets || 0)}</strong><p>${escapeHtml(t("workspace.statsReviewCopy"))}</p></article><article class="metric-card"><p class="panel-kicker">${escapeHtml(t("workspace.statsDrift"))}</p><strong>${escapeHtml(overview.runs_with_drift || 0)}</strong><p>${escapeHtml(t("workspace.statsDriftCopy"))}</p></article><article class="metric-card"><p class="panel-kicker">${escapeHtml(t("workspace.statsRecent"))}</p><strong>${escapeHtml(recentRuns.length)}</strong><p>${escapeHtml(t("workspace.statsRecentCopy"))}</p>${recentRuns.length ? `<ul class="mini-list">${recentRuns.map((run) => `<li>${escapeHtml(run.run_id)}</li>`).join("")}</ul>` : ""}</article>`; }
function shouldShowLane(lane) { return !(lane === "done" && state.workspaceFilters.status !== "all") && (state.workspaceFilters.lane === "all" || state.workspaceFilters.lane === lane); }
function renderWorkspaceBoard() { ALL_LANES.forEach((lane) => { const rows = state.workspaceCases.filter((item) => item.lane === lane); ui.laneSections[lane].classList.toggle("hidden", !shouldShowLane(lane)); ui.laneCounts[lane].textContent = String(rows.length); if (!rows.length) { ui.laneLists[lane].innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.laneEmpty"))}</div>`; return; } ui.laneLists[lane].innerHTML = rows.map((caseView) => `<button type="button" class="case-card ${caseView.case_id === state.selectedCaseId ? "selected" : ""} ${state.workspaceDetailLoadingRunId === caseView.run_id && caseView.case_id === state.selectedCaseId ? "loading" : ""}" data-case-id="${escapeHtml(caseView.case_id)}"><div class="case-card-header"><div><h4>${escapeHtml(caseView.headline)}</h4><small>${escapeHtml(caseView.run_id)}</small></div>${laneMarkup(caseView.lane)}</div><p class="case-summary">${escapeHtml(caseView.summary)}</p>${renderPills([displayStatusText(caseView.runtime_status), caseView.target_locale || null, `${t("labels.cards")}: ${caseView.open_card_count}`])}<div class="case-card-footer"><small>${escapeHtml(caseView.next_action || t("workspace.selectCaseHint"))}</small>${statusMarkup(caseView.priority)}</div></button>`).join(""); ui.laneLists[lane].querySelectorAll("[data-case-id]").forEach((button) => button.addEventListener("click", () => selectWorkspaceCase(button.dataset.caseId).catch(handleWorkspaceError))); }); ui.laneFilterButtons.forEach((button) => button.classList.toggle("active", button.dataset.lane === state.workspaceFilters.lane)); }
function renderEmptyWorkspaceSelection() { ui.workspaceRunTitle.textContent = t("workspace.noCaseSelected"); ui.workspaceRunMeta.textContent = t("workspace.selectCaseHint"); ui.openRuntimeButton.disabled = true; ui.inspectorPanels.decision.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyDecision"))}</div>`; ui.inspectorPanels.signals.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptySignals"))}</div>`; ui.inspectorPanels.evidence.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyEvidence"))}</div>`; ui.inspectorPanels.runtime.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyRuntime"))}</div>`; }
function activateInspectorTab(tab) { state.inspectorTab = ["decision", "signals", "evidence", "runtime"].includes(tab) ? tab : "decision"; ui.tabButtons.forEach((button) => button.classList.toggle("active", button.dataset.tab === state.inspectorTab)); Object.entries(ui.inspectorPanels).forEach(([key, panel]) => panel.classList.toggle("hidden", key !== state.inspectorTab)); if (state.inspectorTab === "runtime" && state.workspaceDetail?.run_id) loadRuntimePeek(state.workspaceDetail.run_id).catch(handleRuntimeError); }
function renderArtifactRefs(refs) { const entries = Object.entries(refs || {}).filter(([, value]) => value); return entries.length ? entries.map(([key, value]) => { const meta = artifactMetaLabel(key); return `<details><summary>${escapeHtml(meta.label)}</summary><p class="detail-copy">${escapeHtml(meta.use)}</p><div class="technical-note">${escapeHtml(String(value))}</div></details>`; }).join("") : `<div class="empty-state">${escapeHtml(t("workspace.emptyEvidence"))}</div>`; }
function renderDecisionInspector(detail, caseView) { const decision = detail.decision_context || {}; const actions = decision.recommended_actions?.length ? decision.recommended_actions : [caseView.next_action].filter(Boolean); const cards = Array.isArray(detail.cards) ? detail.cards.slice(0, 4) : []; ui.inspectorPanels.decision.innerHTML = `${renderMetricStrip([{ label: t("labels.run"), value: caseView.run_id }, { label: t("labels.runtime"), value: displayStatusText(caseView.runtime_status) }, { label: t("labels.priority"), value: caseView.priority }, { label: t("labels.startedAt"), value: formatStartedAt(caseView.started_at) }])}<article class="detail-section"><h4>${escapeHtml(t("workspace.caseWhy"))}</h4><p class="detail-copy">${escapeHtml(decision.summary || caseView.summary || t("workspace.emptyDecision"))}</p></article><article class="detail-section"><h4>${escapeHtml(t("workspace.caseActions"))}</h4>${renderList(actions, t("task.noActions"), (item) => item)}</article><article class="detail-section"><h4>${escapeHtml(t("workspace.caseCards"))}</h4>${cards.length ? cards.map((card) => `<article class="detail-card"><p class="panel-kicker">${escapeHtml(humanizeKey(card.card_type))}</p><strong>${escapeHtml(card.summary || card.card_id)}</strong></article>`).join("") : `<div class="empty-state">${escapeHtml(t("common.empty"))}</div>`}</article>`; }
function renderSignalsInspector(detail) { ui.inspectorPanels.signals.innerHTML = `${renderMetricStrip([{ label: t("labels.reviewTickets"), value: detail.review_workload?.pending_review_tickets || 0 }, { label: t("labels.drift"), value: detail.governance_drift?.drift_count || 0 }, { label: t("labels.requiresHuman"), value: detail.operator_summary?.open_operator_cards || 0 }, { label: t("labels.runtime"), value: detail.operator_summary?.runtime_health_label || t("common.na") }])}<article class="detail-section"><h4>${escapeHtml(t("workspace.signalsReview"))}</h4>${renderKeyValueGrid(detail.review_workload || {}, t("workspace.emptySignals"))}</article><article class="detail-section"><h4>${escapeHtml(t("workspace.signalsKpi"))}</h4>${renderKeyValueGrid(detail.kpi_snapshot || {}, t("workspace.emptySignals"))}</article><article class="detail-section"><h4>${escapeHtml(t("workspace.signalsDrift"))}</h4>${renderKeyValueGrid(detail.governance_drift || {}, t("workspace.emptySignals"))}</article>`; }
function renderEvidenceInspector(detail) { const decision = detail.decision_context || {}; ui.inspectorPanels.evidence.innerHTML = `<article class="detail-section"><h4>${escapeHtml(t("workspace.evidenceArtifacts"))}</h4>${renderArtifactRefs(decision.artifact_refs || {})}</article><article class="detail-section"><h4>${escapeHtml(t("workspace.evidenceRefs"))}</h4>${renderList(decision.evidence_refs || [], t("workspace.emptyEvidence"), (item) => item)}</article><article class="detail-section"><h4>${escapeHtml(t("workspace.adrRefs"))}</h4>${renderList(decision.adr_refs || [], t("workspace.emptyEvidence"), (item) => item)}</article>`; }
function renderRuntimeInspector(runId) { if (!runId) { ui.inspectorPanels.runtime.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyRuntime"))}</div>`; return; } if (state.runtimePeekLoadingRunId === runId) { ui.inspectorPanels.runtime.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.runtimePeekLoading"))}</div>`; return; } const run = state.runtimePeekCache[runId]; if (!run) { ui.inspectorPanels.runtime.innerHTML = `<div class="empty-state">${escapeHtml(t("workspace.emptyRuntime"))}</div>`; return; } const artifacts = Array.isArray(run.artifacts) ? run.artifacts : []; ui.inspectorPanels.runtime.innerHTML = `${renderMetricStrip([{ label: t("labels.runtime"), value: displayStatusText(run.overall_status) }, { label: t("labels.verify"), value: displayStatusText(run.verify?.overall || run.verify?.status || "unknown") }, { label: t("labels.issueCount"), value: run.issue_summary?.total || 0 }, { label: t("labels.pending"), value: displayBool(run.pending) }])}<article class="detail-section"><h4>${escapeHtml(t("labels.stages"))}</h4>${renderList(run.stages || [], t("runtime.emptyTimelineData"), (stage) => `${stage.name} · ${displayStatusText(stage.status)}`)}</article><article class="detail-section"><h4>${escapeHtml(t("labels.artifacts"))}</h4>${renderList(artifacts, t("runtime.noArtifacts"), (artifact) => `${artifactMetaLabel(artifact.key).label} · ${artifact.kind}`)}</article>`; }
function renderWorkspaceDetail() { const caseView = state.workspaceCases.find((item) => item.case_id === state.selectedCaseId); if (!caseView || !state.workspaceDetail) { renderEmptyWorkspaceSelection(); activateInspectorTab(state.inspectorTab); return; } ui.workspaceRunTitle.textContent = caseView.run_id; ui.workspaceRunMeta.innerHTML = renderPills([`${t("labels.runtime")}: ${displayStatusText(caseView.runtime_status)}`, `${t("labels.target")}: ${displayMaybeValue(caseView.target_locale)}`, `${t("labels.cards")}: ${caseView.open_card_count}`]); ui.openRuntimeButton.disabled = false; renderDecisionInspector(state.workspaceDetail, caseView); renderSignalsInspector(state.workspaceDetail); renderEvidenceInspector(state.workspaceDetail); renderRuntimeInspector(caseView.run_id); activateInspectorTab(state.inspectorTab); }
function renderRunsRail() { if (!state.runs.length) { ui.runsList.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.noRunsDiscovered"))}</div>`; return; } ui.runsList.innerHTML = state.runs.map((run) => `<button type="button" class="run-card ${run.run_id === state.selectedRunId ? "selected" : ""}" data-run-id="${escapeHtml(run.run_id)}"><div class="run-header"><strong>${escapeHtml(run.run_id)}</strong>${statusMarkup(run.overall_status)}</div>${renderPills([`${t("labels.target")}: ${displayMaybeValue(run.target_lang)}`, `${t("labels.verify")}: ${displayVerifyMode(run.verify_mode)}`, `${t("labels.issueCount")}: ${run.issue_count || 0}`])}<p class="run-summary">${escapeHtml(summarizeStageCounts(run.stage_counts || {}))}</p></button>`).join(""); ui.runsList.querySelectorAll("[data-run-id]").forEach((button) => button.addEventListener("click", () => showRunInRuntime(button.dataset.runId).catch(handleRuntimeError))); }
function renderEmptyArtifactPreview() { ui.artifactPanel.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.emptyArtifactPanel"))}</div>`; }
function renderArtifactPreview(artifact) { if (!artifact) { renderEmptyArtifactPreview(); return; } const meta = artifactMetaLabel(artifact.key); const content = artifact.content || (artifact.json ? JSON.stringify(artifact.json, null, 2) : t("runtime.artifactNoTextPreview")); ui.artifactPanel.innerHTML = `<div class="artifact-header"><strong>${escapeHtml(meta.label)}</strong><p class="detail-copy">${escapeHtml(meta.use)}</p></div><pre>${escapeHtml(content)}</pre>${artifact.path ? `<details><summary>${escapeHtml(t("common.technicalDetails"))}</summary><div class="technical-note">${escapeHtml(artifact.path)}</div></details>` : ""}`; }
function renderEmptyRuntimeSelection() { ui.runTitle.textContent = t("runtime.noRunSelected"); ui.runMeta.textContent = t("runtime.runHint"); ui.timelinePanel.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.emptyTimeline"))}</div>`; ui.verifySummary.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.emptyVerify"))}</div>`; ui.issueSummary.innerHTML = `<div class="empty-state">${escapeHtml(t("runtime.emptyIssue"))}</div>`; ui.artifactList.innerHTML = ""; renderEmptyArtifactPreview(); }
function renderRuntimeDetail(run) { if (!run) { renderEmptyRuntimeSelection(); return; } state.selectedRunId = run.run_id; state.selectedRunDetail = run; ui.runTitle.textContent = run.run_id; ui.runMeta.innerHTML = `${renderPills([`${t("labels.runtime")}: ${displayStatusText(run.overall_status)}`, `${t("labels.verify")}: ${displayVerifyMode(run.verify_mode)}`, `${t("labels.target")}: ${displayMaybeValue(run.target_lang)}`, `${t("labels.pending")}: ${displayBool(run.pending)}`])}<p class="panel-note">${escapeHtml(t("runtime.runDirectory", { runDir: run.run_dir || t("common.na") }))}</p>`; const stages = run.stages || []; const verify = run.verify || {}; const issueSummary = run.issue_summary || {}; ui.timelinePanel.innerHTML = stages.length ? stages.map((stage) => `<article class="timeline-stage"><header><strong>${escapeHtml(stage.name || t("common.na"))}</strong>${statusMarkup(stage.status)}</header>${renderPills([`${t("labels.requiresHuman")}: ${displayBool(stage.required)}`, stage.missing_required_files?.length ? `${t("labels.issueCount")}: ${stage.missing_required_files.length}` : null])}</article>`).join("") : `<div class="empty-state">${escapeHtml(t("runtime.emptyTimelineData"))}</div>`; ui.verifySummary.innerHTML = `${renderMetricStrip([{ label: t("labels.verify"), value: displayStatusText(verify.overall || verify.status || "unknown") }, { label: t("labels.overall"), value: displayStatusText(verify.status || "unknown") }, { label: t("labels.issueCount"), value: verify.issue_count || 0 }, { label: t("labels.qaRows"), value: (verify.qa_rows || []).length }])}<article class="detail-section"><h4>${escapeHtml(t("labels.qaRows"))}</h4>${renderList(verify.qa_rows || [], t("runtime.emptyVerify"), (row) => row)}</article>`; ui.issueSummary.innerHTML = `${renderMetricStrip([{ label: t("labels.total"), value: issueSummary.total || 0 }, { label: t("labels.severities"), value: Object.keys(issueSummary.by_severity || {}).length }, { label: t("labels.stages"), value: Object.keys(issueSummary.by_stage || {}).length }, { label: t("labels.topIssues"), value: (issueSummary.top || []).length }])}<article class="detail-section"><h4>${escapeHtml(t("labels.bySeverity"))}</h4>${renderKeyValueGrid(issueSummary.by_severity || {}, t("runtime.emptyIssue"))}</article><article class="detail-section"><h4>${escapeHtml(t("labels.byStage"))}</h4>${renderKeyValueGrid(issueSummary.by_stage || {}, t("runtime.emptyIssue"))}</article><article class="detail-section"><h4>${escapeHtml(t("labels.topIssues"))}</h4>${renderList(issueSummary.top || [], t("runtime.emptyIssue"), (issue) => `${issue.severity || "P?"} · ${issue.stage || "stage"} · ${issue.error_code || "issue"}`)}</article>`; const artifacts = Array.isArray(run.artifacts) ? run.artifacts : []; ui.artifactList.innerHTML = artifacts.length ? artifacts.map((artifact) => `<button type="button" class="artifact-button ${artifact.key === state.selectedArtifactKey ? "active" : ""}" data-artifact-key="${escapeHtml(artifact.key)}"><strong>${escapeHtml(artifactMetaLabel(artifact.key).label)}</strong><small>${escapeHtml(artifactMetaLabel(artifact.key).use)}</small>${renderPills([artifact.kind, artifact.exists ? t("common.yes") : t("common.no")])}</button>`).join("") : `<div class="empty-state">${escapeHtml(t("runtime.noArtifacts"))}</div>`; ui.artifactList.querySelectorAll("[data-artifact-key]").forEach((button) => button.addEventListener("click", () => loadArtifact(run.run_id, button.dataset.artifactKey).catch(handleRuntimeError))); renderRunsRail(); }
async function fetchJson(url, options = {}) { const response = await fetch(url, options); const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(String(payload.detail || payload.error || response.statusText || "request_failed")); return payload; }
function syncWorkspaceFiltersFromUi() { state.workspaceFilters.status = ui.caseStatusFilter.value || "open"; state.workspaceFilters.targetLocale = ui.caseLocaleFilter.value.trim(); state.workspaceFilters.query = ui.caseQueryFilter.value.trim(); }
function workspaceQueryString() { const params = new URLSearchParams(); params.set("status", state.workspaceFilters.status); params.set("lane", state.workspaceFilters.lane); params.set("limit", "50"); if (state.workspaceFilters.targetLocale) params.set("target_locale", state.workspaceFilters.targetLocale); if (state.workspaceFilters.query) params.set("query", state.workspaceFilters.query); return params.toString(); }
function findCaseByRunId(runId) { return state.workspaceCases.find((caseView) => caseView.run_id === runId) || null; }
async function loadTaskOverviewAndList() { const payload = await fetchJson("/api/tasks?limit=50"); state.taskOverview = payload.overview || null; state.tasks = payload.tasks || []; renderTaskOverview(); renderTaskList(); }
async function loadTaskDetail(taskId, options = {}) { const payload = await fetchJson(`/api/tasks/${encodeURIComponent(taskId)}`); state.selectedTaskId = taskId; state.selectedTask = payload.task || null; if (options.loadDeliveries) await loadTaskDeliveries(taskId); else if (!state.taskDeliveries.length) state.taskDeliveries = state.selectedTask?.output_refs || []; if (options.resetPreview) { state.selectedDeliveryId = null; state.selectedDeliveryPreview = null; } renderTaskDetail(); return state.selectedTask; }
async function loadTaskDeliveries(taskId) { const payload = await fetchJson(`/api/tasks/${encodeURIComponent(taskId)}/deliveries`); state.taskDeliveries = payload.deliveries || []; renderTaskDetail(); return state.taskDeliveries; }
async function selectTask(taskId, options = {}) { state.taskLoading = true; renderTaskList(); try { const task = await loadTaskDetail(taskId, { loadDeliveries: true, resetPreview: true }); if (task && !options.preserveMode) { setMode("tasks"); setHeroStatus(task.status, "hero.taskSelected", { title: task.title }); } } finally { state.taskLoading = false; renderTaskList(); } }
async function previewDelivery(delivery) { state.selectedDeliveryId = delivery.delivery_id; if (!delivery.openable) { state.selectedDeliveryPreview = { ...delivery, content: "", json: null, path: "" }; renderTaskDetail(); return; } const payload = await fetchJson(`/api/runs/${encodeURIComponent(delivery.source_run_id)}/artifacts/${encodeURIComponent(delivery.artifact_key)}`); state.selectedDeliveryPreview = { ...delivery, ...payload.artifact }; renderTaskDetail(); }
async function runTaskAction(action) { if (!state.selectedTaskId) return; const payload = await fetchJson(`/api/tasks/${encodeURIComponent(state.selectedTaskId)}/actions/${encodeURIComponent(action)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({}) }); await loadTaskOverviewAndList(); if (payload.task?.task_id) { state.selectedTask = payload.task; state.selectedTaskId = payload.task.task_id; state.taskDeliveries = payload.deliveries || payload.task.output_refs || []; state.selectedDeliveryId = null; state.selectedDeliveryPreview = null; renderTaskDetail(); } else { await loadTaskDetail(state.selectedTaskId, { loadDeliveries: true, resetPreview: true }); } setTaskFeedback(payload.user_message || t("hero.taskActionDone")); setHeroStatus(payload.result_status || "pass", "hero.taskActionDone"); if (action === "open_monitor") { await loadWorkspace(); const nextCase = findCaseByRunId(payload.linked_run_id) || findCaseByRunId(state.selectedTask?.latest_run_id); if (nextCase) { await selectWorkspaceCase(nextCase.case_id, { preserveMode: true }); setMode("workspace"); setHeroStatus(nextCase.runtime_status || "warn", "hero.workspaceSelected", { runId: nextCase.run_id }); } return; } if (action === "open_runtime") { if (payload.linked_run_id || state.selectedTask?.latest_run_id) { await showRunInRuntime(payload.linked_run_id || state.selectedTask.latest_run_id, { preserveMode: true }); setMode("runtime"); setHeroStatus("running", "hero.runtimeSelected", { runId: payload.linked_run_id || state.selectedTask.latest_run_id }); } return; } if (action === "view_deliveries") { if (!state.taskDeliveries.length && state.selectedTaskId) await loadTaskDeliveries(state.selectedTaskId); const delivery = state.taskDeliveries[0]; if (delivery) await previewDelivery(delivery); return; } if (action === "rerun") { await Promise.all([loadRuns(), loadWorkspace()]); if (payload.linked_run_id) { await showRunInRuntime(payload.linked_run_id, { preserveMode: true }); setHeroStatus("running", "hero.runtimeSelected", { runId: payload.linked_run_id }); } } }
async function createTaskFromForm(event) { event.preventDefault(); const payload = Object.fromEntries(new FormData(ui.taskForm).entries()); const response = await fetchJson("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); await Promise.all([loadTaskOverviewAndList(), loadRuns(), loadWorkspace()]); if (response.task?.task_id) { await selectTask(response.task.task_id, { preserveMode: true }); setHeroStatus(response.task.status || "queued", "hero.taskCreated", { title: response.task.title }); setTaskFeedback("task.startSuccess"); } ui.taskForm.reset(); ui.taskForm.elements.input.value = "fixtures/input.csv"; ui.taskForm.elements.target_lang.value = "en-US"; ui.taskForm.elements.verify_mode.value = "full"; }
async function loadWorkspaceOverview() { const payload = await fetchJson("/api/workspace/overview?limit_runs=12"); state.workspaceOverview = payload.overview || null; renderWorkspaceOverview(); }
async function loadWorkspaceRunDetail(runId) { const payload = await fetchJson(`/api/workspace/runs/${encodeURIComponent(runId)}`); return payload.workspace; }
async function selectWorkspaceCase(caseId, options = {}) { const caseView = state.workspaceCases.find((item) => item.case_id === caseId); if (!caseView) return; state.selectedCaseId = caseId; state.workspaceDetail = null; state.workspaceDetailLoadingRunId = caseView.run_id; renderWorkspaceBoard(); renderEmptyWorkspaceSelection(); ui.workspaceRunTitle.textContent = caseView.run_id; ui.workspaceRunMeta.textContent = t("workspace.loadingCase"); try { const detail = await loadWorkspaceRunDetail(caseView.run_id); if (state.selectedCaseId !== caseId) return; state.workspaceDetail = detail; if (!options.preserveMode) { setMode("workspace"); setHeroStatus(caseView.runtime_status, "hero.workspaceSelected", { runId: caseView.run_id }); } renderWorkspaceDetail(); } finally { state.workspaceDetailLoadingRunId = null; renderWorkspaceBoard(); } }
async function loadWorkspaceCases() { const payload = await fetchJson(`/api/workspace/cases?${workspaceQueryString()}`); state.workspaceCases = payload.cases || []; renderWorkspaceBoard(); const current = state.workspaceCases.find((caseView) => caseView.case_id === state.selectedCaseId); const next = current || state.workspaceCases[0] || null; if (next) await selectWorkspaceCase(next.case_id, { preserveMode: true }); else { state.selectedCaseId = null; state.workspaceDetail = null; renderEmptyWorkspaceSelection(); } }
async function loadWorkspace() { syncWorkspaceFiltersFromUi(); setWorkspaceFeedback("workspace.waiting"); await Promise.all([loadWorkspaceOverview(), loadWorkspaceCases()]); setWorkspaceFeedback("workspace.refreshed"); }
async function loadRuntimePeek(runId) { if (!runId) return null; if (state.runtimePeekCache[runId]) { renderRuntimeInspector(runId); return state.runtimePeekCache[runId]; } state.runtimePeekLoadingRunId = runId; renderRuntimeInspector(runId); try { const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}`); state.runtimePeekCache[runId] = payload.run; return payload.run; } finally { state.runtimePeekLoadingRunId = null; renderRuntimeInspector(runId); } }
async function loadRuns() { setLaunchFeedback("runtime.refreshingInventory"); const payload = await fetchJson("/api/runs?limit=12"); state.runs = payload.runs || []; renderRunsRail(); setLaunchFeedback("runtime.inventoryRefreshed"); if (!state.selectedRunId && state.runs.length) await showRunInRuntime(state.runs[0].run_id, { preserveMode: true }); }
async function loadArtifact(runId, artifactKey, options = {}) { if (!artifactKey) { state.selectedArtifactKey = null; state.selectedArtifact = null; renderRuntimeDetail(state.selectedRunDetail); renderEmptyArtifactPreview(); return null; } if (!state.selectedRunDetail || state.selectedRunDetail.run_id !== runId) await showRunInRuntime(runId, { preserveMode: true }); state.selectedArtifactKey = artifactKey; const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactKey)}`); state.selectedArtifact = payload.artifact; renderRuntimeDetail(state.selectedRunDetail); renderArtifactPreview(state.selectedArtifact); if (!options.preserveMode) setMode("runtime"); return state.selectedArtifact; }
async function showRunInRuntime(runId, options = {}) { const run = await loadRuntimePeek(runId); if (!run) return; state.selectedArtifactKey = null; state.selectedArtifact = null; renderRuntimeDetail(run); const artifactKey = preferredArtifactKey(run); if (artifactKey) await loadArtifact(run.run_id, artifactKey, { preserveMode: true }); else renderEmptyArtifactPreview(); if (!options.preserveMode) { setMode("runtime"); setHeroStatus(run.overall_status, "hero.runtimeSelected", { runId: run.run_id }); } }
async function launchRunFromShell(event) { event.preventDefault(); const payload = Object.fromEntries(new FormData(ui.launcherForm).entries()); setLaunchFeedback("runtime.launchingRun"); const response = await fetchJson("/api/runs", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); setLaunchFeedback("runtime.runLaunched", { runId: response.run.run_id }); await Promise.all([loadRuns(), loadWorkspace(), loadTaskOverviewAndList()]); await showRunInRuntime(response.run.run_id); }
function localizedBucketLabel(bucket) { const zh = { needs_your_action: "待你处理", running: "运行中", waiting_on_ops: "等待运营", ready_to_collect: "可领取结果", failed: "失败", archived: "已归档" }; const en = { needs_your_action: "Needs your action", running: "Running", waiting_on_ops: "Waiting on Ops", ready_to_collect: "Ready to collect", failed: "Failed", archived: "Archived" }; return (state.language === "zh" ? zh : en)[bucket] || humanizeKey(bucket); }
function taskBucketOrder() { return ["needs_your_action", "running", "waiting_on_ops", "ready_to_collect", "failed", "archived"]; }
function clearTaskSelection() { state.selectedTaskId = ""; state.selectedTask = null; state.taskDeliveries = []; state.selectedDeliveryId = ""; state.selectedDeliveryPreview = null; state.taskLoadingTaskId = ""; }
function findVisibleTask(taskId) { return state.tasks.find((task) => task.task_id === taskId) || null; }
function renderReturnButtons() { const visible = Boolean(state.returnTaskId); ui.workspaceReturnButton?.classList.toggle("hidden", !(visible && state.mode === "workspace")); ui.runtimeReturnButton?.classList.toggle("hidden", !(visible && state.mode === "runtime")); }
function syncWizardPanels() { const upload = state.wizardMode !== "path"; ui.wizardModeButtons.forEach((button) => button.classList.toggle("active", button.dataset.wizardMode === state.wizardMode)); ui.wizardUploadPanel?.classList.toggle("hidden", !upload); ui.wizardPathPanel?.classList.toggle("hidden", upload); }
function setMode(mode) { state.mode = ["tasks", "workspace", "runtime"].includes(mode) ? mode : "tasks"; ui.taskView.classList.toggle("hidden", state.mode !== "tasks"); ui.workspaceView.classList.toggle("hidden", state.mode !== "workspace"); ui.runtimeView.classList.toggle("hidden", state.mode !== "runtime"); ui.modeTasksButton.classList.toggle("active", state.mode === "tasks"); ui.modeWorkspaceButton.classList.toggle("active", state.mode === "workspace"); ui.modeRuntimeButton.classList.toggle("active", state.mode === "runtime"); renderReturnButtons(); }
function setWizardMode(mode) { state.wizardMode = mode === "path" ? "path" : "upload"; syncWizardPanels(); }
function renderStagedUpload() { const staged = state.stagedUpload; if (!ui.stagedUploadCard) return; const hasUpload = Boolean(staged?.upload_id); ui.stagedUploadCard.classList.toggle("active", hasUpload); ui.taskStagedFilename.textContent = hasUpload ? staged.original_filename : t("task.noStagedFile"); ui.taskStagedMeta.textContent = hasUpload ? `${Math.max(1, Math.round((staged.size_bytes || 0) / 1024))} KB · ${formatStartedAt(staged.uploaded_at)}` : t("task.stagedHint"); }
function renderTaskBucketTabs(counts = {}) { if (!ui.taskBucketTabs) return; ui.taskBucketTabs.innerHTML = taskBucketOrder().map((bucket) => `<button type="button" class="wizard-mode-button ${bucket === state.taskBucket ? "active" : ""}" data-task-bucket="${escapeHtml(bucket)}">${escapeHtml(localizedBucketLabel(bucket))}<span class="bucket-count">${escapeHtml(String(counts[bucket] || 0))}</span></button>`).join(""); ui.taskBucketTabs.querySelectorAll("[data-task-bucket]").forEach((button) => button.addEventListener("click", () => { state.taskBucket = button.dataset.taskBucket || "needs_your_action"; loadTaskOverviewAndList().catch(handleTaskError); })); }
function actionLabel(action) { return t(`task.action.${action}`, {}, humanizeKey(action)); }
function actionPayload(action) { const payload = {}; if (action === "request_changes") { payload.note = ui.taskNoteInput?.value.trim() || ""; if (!payload.note) throw new Error(state.language === "zh" ? "请求修改时必须填写说明。" : "A note is required when requesting changes."); } if (action === "approve_delivery") { payload.delivery_id = state.selectedDeliveryId || state.selectedTask?.bundle_summary?.primary_delivery_id || ""; } return payload; }
function renderTaskOverview() { const overview = state.taskOverview; if (!overview) { ui.taskOverview.innerHTML = `<div class="empty-state">${escapeHtml(t("task.loading"))}</div>`; renderTaskBucketTabs({}); return; } const bucketCounts = overview.counts_by_bucket || {}; renderTaskBucketTabs(bucketCounts); ui.taskOverview.innerHTML = [{ label: t("task.overviewTotal"), value: overview.total }, { label: t("task.overviewAttention"), value: (bucketCounts.needs_your_action || 0) + (bucketCounts.waiting_on_ops || 0) + (bucketCounts.failed || 0) }, { label: t("task.overviewRunning"), value: bucketCounts.running || 0 }, { label: t("task.overviewReady"), value: bucketCounts.ready_to_collect || 0 }].map((item) => `<article class="metric-card"><p class="panel-kicker">${escapeHtml(item.label)}</p><strong>${escapeHtml(item.value)}</strong></article>`).join(""); }
function renderTaskList() { if (!state.tasks.length) { ui.taskList.innerHTML = `<div class="empty-state">${escapeHtml(t("task.taskListEmpty"))}</div>`; return; } ui.taskList.innerHTML = state.tasks.map((task) => `<button type="button" class="task-card ${task.task_id === state.selectedTaskId ? "selected" : ""} ${state.taskLoadingTaskId === task.task_id ? "loading" : ""}" data-task-id="${escapeHtml(task.task_id)}"><div class="task-card-header"><div><h3>${escapeHtml(task.title)}</h3><small>${escapeHtml(localizedBucketLabel(task.bucket || state.taskBucket))}</small></div>${statusMarkup(task.status)}</div><p class="task-summary">${escapeHtml(task.summary || taskSummaryText(task))}</p>${renderPills([`${t("task.targetLocale")}: ${displayMaybeValue(task.target_locale)}`, `${t("task.verifyMode")}: ${displayVerifyMode(task.verify_mode)}`, task.latest_run_id ? `${t("task.latestRun")}: ${task.latest_run_id}` : null])}<div class="task-card-footer"><small>${escapeHtml(task.required_human_action || taskRequiredText(task))}</small><span class="lane-chip lane-${escapeHtml(normalizeStatus(task.latest_run_status))}">${escapeHtml(displayStatusText(task.latest_run_status))}</span></div></button>`).join(""); ui.taskList.querySelectorAll("[data-task-id]").forEach((button) => button.addEventListener("click", () => selectTask(button.dataset.taskId).catch(handleTaskError))); }
function renderTaskMetrics(task) { const metrics = task?.metrics || {}; const items = [{ label: state.language === "zh" ? "创建时间" : "Created", value: metrics.created_at ? formatStartedAt(metrics.created_at) : t("common.na") }, { label: state.language === "zh" ? "首次人工动作" : "First human action", value: metrics.first_user_action_at ? formatStartedAt(metrics.first_user_action_at) : t("common.na") }, { label: state.language === "zh" ? "批准时间" : "Approved", value: metrics.approved_at ? formatStartedAt(metrics.approved_at) : t("common.na") }, { label: state.language === "zh" ? "下载时间" : "Downloaded", value: metrics.downloaded_at ? formatStartedAt(metrics.downloaded_at) : t("common.na") }]; ui.taskMetricsStrip.innerHTML = renderMetricStrip(items); }
function renderTaskPreview() { if (!state.selectedDeliveryPreview) { ui.taskPreview.innerHTML = `<div class="empty-state">${escapeHtml(t("task.emptyPreview"))}</div>`; return; } const preview = state.selectedDeliveryPreview; const meta = { label: preview.label || artifactMetaLabel(preview.artifact_key || preview.key).label, description: preview.description || artifactMetaLabel(preview.artifact_key || preview.key).description }; const content = preview.content || (preview.json ? JSON.stringify(preview.json, null, 2) : t("common.previewUnavailable")); ui.taskPreview.innerHTML = `<div class="artifact-header"><strong>${escapeHtml(meta.label)}</strong>${renderPills([preview.source_run_id ? `${t("common.sourceRun")}: ${preview.source_run_id}` : null, `${t("common.openable")}: ${displayBool(preview.openable)}`, `${t("common.downloadable")}: ${displayBool(preview.downloadable)}`])}</div><p class="detail-copy">${escapeHtml(meta.description)}</p><pre>${escapeHtml(content)}</pre>${preview.path ? `<details><summary>${escapeHtml(t("common.technicalDetails"))}</summary><div class="technical-note">${escapeHtml(preview.path)}</div></details>` : ""}`; }
function renderBundleGroups(task) { const summary = task?.bundle_summary || {}; const groups = summary.groups || []; if (!groups.length) { ui.taskBundleGroups.innerHTML = `<div class="empty-state">${escapeHtml(task?.status === "ready_for_download" || task?.status === "needs_user_action" ? t("task.noDeliveries") : t("task.deliveryEmptyForStatus"))}</div>`; return; } ui.taskBundleGroups.innerHTML = groups.map((group) => `<article class="delivery-group"><div class="delivery-group-header"><div><h5>${escapeHtml(group.label)}</h5><p class="panel-note">${escapeHtml(String((group.items || []).length))}</p></div></div><div class="delivery-tile-grid">${(group.items || []).map((delivery) => `<article class="delivery-tile ${delivery.delivery_id === state.selectedDeliveryId ? "active" : ""}" data-delivery-id="${escapeHtml(delivery.delivery_id)}"><div><strong>${escapeHtml(delivery.label)}</strong><p class="detail-copy">${escapeHtml(delivery.description)}</p></div>${renderPills([delivery.primary_use, delivery.source_run_id ? `${t("common.sourceRun")}: ${delivery.source_run_id}` : null])}<div class="delivery-tile-actions"><button type="button" class="ghost-button" data-delivery-preview="${escapeHtml(delivery.delivery_id)}">${escapeHtml(t("task.previewLabel"))}</button>${delivery.downloadable ? `<button type="button" class="ghost-button" data-delivery-download="${escapeHtml(delivery.delivery_id)}">${escapeHtml(t("task.action.download_delivery"))}</button>` : ""}</div></article>`).join("")}</div></article>`).join(""); bindDeliveryButtons(ui.taskBundleGroups); }
function renderTechnicalDetails(task) { const summary = task?.bundle_summary || {}; const technical = summary.technical_details || []; if (!technical.length) { ui.taskTechnicalDetails.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noTechnicalDetails"))}</div>`; return; } ui.taskTechnicalDetails.innerHTML = technical.map((delivery) => `<article class="technical-delivery-card"><div class="artifact-header"><div><strong>${escapeHtml(delivery.label)}</strong><p class="detail-copy">${escapeHtml(delivery.description)}</p></div><div class="delivery-tile-actions"><button type="button" class="ghost-button" data-delivery-preview="${escapeHtml(delivery.delivery_id)}">${escapeHtml(t("task.previewLabel"))}</button>${delivery.downloadable ? `<button type="button" class="ghost-button" data-delivery-download="${escapeHtml(delivery.delivery_id)}">${escapeHtml(t("task.action.download_delivery"))}</button>` : ""}</div></div><div class="technical-note">${escapeHtml(delivery.path || t("common.na"))}</div></article>`).join(""); bindDeliveryButtons(ui.taskTechnicalDetails); }
function renderLinkedRuns(task) { const linkedRuns = task?.linked_runs || []; if (!linkedRuns.length) { ui.taskLinkedRuns.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noLinkedRuns"))}</div>`; return; } ui.taskLinkedRuns.innerHTML = linkedRuns.map((run) => `<article class="linked-run-card"><div class="artifact-header"><strong>${escapeHtml(run.run_id)}</strong>${statusMarkup(run.status)}</div>${renderPills([run.target_locale ? `${t("task.targetLocale")}: ${run.target_locale}` : null, run.started_at ? `${t("labels.startedAt")}: ${formatStartedAt(run.started_at)}` : null])}<div class="delivery-tile-actions"><button type="button" class="ghost-button" data-linked-runtime="${escapeHtml(run.run_id)}">${escapeHtml(t("task.action.open_runtime"))}</button><button type="button" class="ghost-button" data-linked-monitor="${escapeHtml(run.run_id)}">${escapeHtml(t("task.action.open_monitor"))}</button></div></article>`).join(""); ui.taskLinkedRuns.querySelectorAll("[data-linked-runtime]").forEach((button) => button.addEventListener("click", () => { state.returnTaskId = state.selectedTaskId; showRunInRuntime(button.dataset.linkedRuntime, { preserveMode: true }).then(() => { setMode("runtime"); setHeroStatus("running", "hero.runtimeSelected", { runId: button.dataset.linkedRuntime }); }).catch(handleRuntimeError); })); ui.taskLinkedRuns.querySelectorAll("[data-linked-monitor]").forEach((button) => button.addEventListener("click", () => { state.returnTaskId = state.selectedTaskId; openTaskRunInMonitor(button.dataset.linkedMonitor).catch(handleWorkspaceError); })); }
function renderTaskHistory(task) { const history = task?.history || []; if (!history.length) { ui.taskHistory.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noHistory"))}</div>`; return; } ui.taskHistory.innerHTML = history.slice().reverse().map((event) => `<article class="history-item"><div class="artifact-header"><strong>${escapeHtml(event.title || humanizeKey(event.type || "event"))}</strong><span class="panel-note">${escapeHtml(formatStartedAt(event.at))}</span></div><p class="detail-copy">${escapeHtml(event.message || t("common.empty"))}</p></article>`).join(""); }
function renderTaskActions(task) { const actions = task?.allowed_actions || []; const primary = actions.find((item) => item.primary) || null; const secondary = actions.filter((item) => !item.primary); ui.taskPrimaryAction.innerHTML = primary ? `<button type="button" class="action-button primary" data-task-action="${escapeHtml(primary.action)}">${escapeHtml(actionLabel(primary.action))}</button>` : `<div class="empty-state">${escapeHtml(t("task.noActions"))}</div>`; ui.taskActionBar.innerHTML = secondary.length ? secondary.map((item) => `<button type="button" class="action-button" data-task-action="${escapeHtml(item.action)}">${escapeHtml(actionLabel(item.action))}</button>`).join("") : `<div class="empty-state">${escapeHtml(t("task.noActions"))}</div>`; [ui.taskPrimaryAction, ui.taskActionBar].forEach((root) => root.querySelectorAll("[data-task-action]").forEach((button) => button.addEventListener("click", () => runTaskAction(button.dataset.taskAction).catch(handleTaskError)))); const requiresNote = actions.some((item) => item.requires_note); ui.taskNoteSection.classList.toggle("hidden", !requiresNote); }
function bindDeliveryButtons(root) { if (!root) return; const deliveryMap = Object.fromEntries((state.taskDeliveries || []).map((delivery) => [delivery.delivery_id, delivery])); root.querySelectorAll("[data-delivery-preview]").forEach((button) => button.addEventListener("click", (event) => { event.stopPropagation(); const delivery = deliveryMap[button.dataset.deliveryPreview]; if (delivery) previewDelivery(delivery).catch(handleTaskError); })); root.querySelectorAll("[data-delivery-download]").forEach((button) => button.addEventListener("click", (event) => { event.stopPropagation(); const delivery = deliveryMap[button.dataset.deliveryDownload]; if (delivery) downloadDelivery(delivery).catch(handleTaskError); })); root.querySelectorAll("[data-delivery-id]").forEach((tile) => tile.addEventListener("click", () => { const delivery = deliveryMap[tile.dataset.deliveryId]; if (delivery) previewDelivery(delivery).catch(handleTaskError); })); }
function renderEmptyTaskDetail() { ui.taskTitle.textContent = t("task.noTaskSelected"); ui.taskMeta.textContent = t("task.selectTaskHint"); ui.taskMetricsStrip.innerHTML = ""; ui.taskSummary.textContent = t("task.emptySummary"); ui.taskWhy.textContent = t("task.emptyWhy"); ui.taskStep.textContent = t("task.emptyStep"); ui.taskRequired.textContent = t("task.emptyRequired"); ui.taskPrimaryAction.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noActions"))}</div>`; ui.taskActionBar.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noActions"))}</div>`; ui.taskNoteSection.classList.add("hidden"); ui.taskFeedbackSection.classList.add("hidden"); ui.taskBundleGroups.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noDeliveries"))}</div>`; ui.taskTechnicalDetails.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noTechnicalDetails"))}</div>`; ui.taskLinkedRuns.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noLinkedRuns"))}</div>`; ui.taskHistory.innerHTML = `<div class="empty-state">${escapeHtml(t("task.noHistory"))}</div>`; state.selectedDeliveryPreview = null; renderTaskPreview(); }
function renderTaskDetail() { const task = state.selectedTask; if (!task) { renderEmptyTaskDetail(); return; } ui.taskTitle.textContent = task.title; ui.taskMeta.innerHTML = renderPills([`${t("task.currentState")}: ${displayStatusText(task.status)}`, task.target_locale ? `${t("task.targetLocale")}: ${task.target_locale}` : null, task.verify_mode ? `${t("task.verifyMode")}: ${displayVerifyMode(task.verify_mode)}` : null, task.source_input_label ? (state.language === "zh" ? `输入: ${task.source_input_label}` : `Input: ${task.source_input_label}`) : null]); renderTaskMetrics(task); ui.taskSummary.textContent = task.summary || taskSummaryText(task); ui.taskWhy.textContent = task.why_it_matters || taskWhyText(task); ui.taskStep.textContent = task.current_step || taskStepText(task); ui.taskRequired.textContent = task.required_human_action || taskRequiredText(task); renderTaskActions(task); ui.taskFeedbackSection.classList.toggle("hidden", !task.latest_feedback_note); ui.taskLatestFeedback.textContent = task.latest_feedback_note || ""; renderBundleGroups(task); renderTechnicalDetails(task); renderLinkedRuns(task); renderTaskHistory(task); renderTaskPreview(); }
async function loadTaskOverviewAndList() { const requestSeq = ++state.taskListRequestSeq; const params = new URLSearchParams({ limit: "50" }); if (state.taskBucket) params.set("bucket", state.taskBucket); if (state.taskQuery) params.set("query", state.taskQuery); const payload = await fetchJson(`/api/tasks?${params.toString()}`); if (requestSeq !== state.taskListRequestSeq) return state.tasks; state.taskOverview = payload.overview || null; state.tasks = payload.tasks || []; const visibleSelected = findVisibleTask(state.selectedTaskId); if (visibleSelected && state.selectedTask?.task_id === visibleSelected.task_id) { state.selectedTask = { ...visibleSelected, ...state.selectedTask }; } else if (!visibleSelected) { clearTaskSelection(); } renderTaskOverview(); renderTaskList(); renderTaskDetail(); return state.tasks; }
async function loadTaskDetail(taskId, options = {}) { const payload = await fetchJson(`/api/tasks/${encodeURIComponent(taskId)}`); if (options.requestSeq && state.taskSelectionRequestSeq !== options.requestSeq) return null; state.selectedTaskId = taskId; state.selectedTask = payload.task || null; if (!state.selectedTask) { clearTaskSelection(); renderTaskDetail(); return null; } if (options.loadDeliveries) { await loadTaskDeliveries(taskId, { preserveSelection: !options.resetPreview, requestSeq: options.requestSeq }); if (options.requestSeq && state.taskSelectionRequestSeq !== options.requestSeq) return null; } else { state.taskDeliveries = state.selectedTask.output_refs || []; if (!options.preserveSelection || !state.taskDeliveries.find((delivery) => delivery.delivery_id === state.selectedDeliveryId)) state.selectedDeliveryId = state.taskDeliveries[0]?.delivery_id || ""; } if (options.resetPreview) { state.selectedDeliveryId = ""; state.selectedDeliveryPreview = null; } else if (state.selectedDeliveryPreview && state.selectedDeliveryPreview.delivery_id !== state.selectedDeliveryId) { state.selectedDeliveryPreview = null; } renderTaskDetail(); return state.selectedTask; }
async function loadTaskDeliveries(taskId, options = {}) { const payload = await fetchJson(`/api/tasks/${encodeURIComponent(taskId)}/deliveries`); if (options.requestSeq && state.taskSelectionRequestSeq !== options.requestSeq) return []; if (state.selectedTaskId !== taskId) return []; state.taskDeliveries = payload.deliveries || []; if (state.selectedTask && state.selectedTask.task_id === taskId) { state.selectedTask.bundle_summary = payload.bundle_summary || state.selectedTask.bundle_summary || {}; state.selectedTask.output_refs = state.taskDeliveries; } if (!options.preserveSelection || !state.selectedDeliveryId || !state.taskDeliveries.find((delivery) => delivery.delivery_id === state.selectedDeliveryId)) { state.selectedDeliveryId = state.taskDeliveries[0]?.delivery_id || ""; state.selectedDeliveryPreview = null; } renderTaskDetail(); return state.taskDeliveries; }
async function selectTask(taskId, options = {}) { const requestSeq = ++state.taskSelectionRequestSeq; state.taskLoading = true; state.taskLoadingTaskId = taskId; state.selectedTaskId = taskId; renderTaskList(); try { const task = await loadTaskDetail(taskId, { loadDeliveries: true, resetPreview: true, requestSeq }); if (!task) return null; state.returnTaskId = taskId; if (task && !options.preserveMode) { setMode("tasks"); setHeroStatus(task.status, "hero.taskSelected", { title: task.title }); } return task; } finally { if (state.taskSelectionRequestSeq === requestSeq) { state.taskLoading = false; state.taskLoadingTaskId = ""; renderTaskList(); } } }
async function previewDelivery(delivery) { const taskId = state.selectedTaskId; state.selectedDeliveryId = delivery.delivery_id; if (!delivery.openable) { state.selectedDeliveryPreview = { ...delivery, content: "", json: null, path: delivery.path || "" }; renderTaskDetail(); return; } const payload = await fetchJson(`/api/tasks/${encodeURIComponent(taskId)}/deliveries/${encodeURIComponent(delivery.delivery_id)}`); if (state.selectedTaskId !== taskId) return; state.selectedTask = payload.task || state.selectedTask; state.selectedDeliveryPreview = { ...delivery, ...payload.delivery, ...payload.artifact }; renderTaskDetail(); }
async function downloadDelivery(delivery) { const taskId = state.selectedTaskId; const link = document.createElement("a"); link.href = delivery.download_url; link.rel = "noopener"; document.body.appendChild(link); link.click(); document.body.removeChild(link); setTimeout(async () => { try { await loadTaskOverviewAndList(); if (taskId && findVisibleTask(taskId)) await loadTaskDetail(taskId, { loadDeliveries: true, preserveSelection: true }); } catch (error) { handleTaskError(error); } }, 250); }
async function openTaskRunInMonitor(runId) { if (!runId) throw new Error(state.language === "zh" ? "这个任务还没有可打开的 run。" : "This task does not have a linked run yet."); const previousFilters = { ...state.workspaceFilters }; await loadWorkspace(); let nextCase = findCaseByRunId(runId); if (!nextCase) { state.workspaceFilters = { status: "all", lane: "all", targetLocale: "", query: runId }; ui.caseStatusFilter.value = "all"; ui.caseLocaleFilter.value = ""; ui.caseQueryFilter.value = runId; await loadWorkspace(); nextCase = findCaseByRunId(runId); } if (!nextCase) { state.workspaceFilters = previousFilters; ui.caseStatusFilter.value = previousFilters.status; ui.caseLocaleFilter.value = previousFilters.targetLocale; ui.caseQueryFilter.value = previousFilters.query; await loadWorkspace(); await showRunInRuntime(runId, { preserveMode: true }); setMode("runtime"); setTaskFeedback(state.language === "zh" ? "这个任务还没有形成 Ops case，已改为打开 Pro Runtime。" : "This task does not have an Ops case yet, so Pro Runtime was opened instead.", {}, { raw: true }); setHeroStatus("warn", "hero.runtimeSelected", { runId }); return null; } await selectWorkspaceCase(nextCase.case_id, { preserveMode: true }); setMode("workspace"); setHeroStatus(nextCase.runtime_status || "warn", "hero.workspaceSelected", { runId: nextCase.run_id }); return nextCase; }
async function runTaskAction(action) { const actingTaskId = state.selectedTaskId; if (!actingTaskId) return; const payload = await fetchJson(`/api/tasks/${encodeURIComponent(actingTaskId)}/actions/${encodeURIComponent(action)}`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(actionPayload(action)) }); if (action === "request_changes" || action === "archive_task" || action === "approve_delivery") { ui.taskNoteInput.value = ""; } await loadTaskOverviewAndList(); const preferredTaskId = payload.task?.task_id || payload.updated_task_ids?.[0] || actingTaskId; if (findVisibleTask(preferredTaskId)) { await loadTaskDetail(preferredTaskId, { loadDeliveries: true, resetPreview: action !== "approve_delivery" && action !== "view_deliveries" }); } else if (state.tasks[0]) { await selectTask(state.tasks[0].task_id, { preserveMode: true }); } else { clearTaskSelection(); renderTaskList(); renderTaskDetail(); } setTaskFeedback(payload.user_message || t("hero.taskActionDone"), {}, { raw: true }); setHeroStatus(payload.result_status || "pass", "hero.taskActionDone"); if (action === "approve_delivery" || action === "view_deliveries") { if (!state.taskDeliveries.length && state.selectedTaskId) await loadTaskDeliveries(state.selectedTaskId); const nextDeliveryId = state.selectedTask?.bundle_summary?.primary_delivery_id || state.taskDeliveries[0]?.delivery_id || ""; const nextDelivery = state.taskDeliveries.find((delivery) => delivery.delivery_id === nextDeliveryId) || state.taskDeliveries[0]; if (nextDelivery) await previewDelivery(nextDelivery); } if (action === "open_monitor") { state.returnTaskId = actingTaskId; await openTaskRunInMonitor(payload.linked_run_id || state.selectedTask?.latest_run_id); return; } if (action === "open_runtime") { const runId = payload.linked_run_id || state.selectedTask?.latest_run_id; if (runId) { state.returnTaskId = actingTaskId; await showRunInRuntime(runId, { preserveMode: true }); setMode("runtime"); setHeroStatus("running", "hero.runtimeSelected", { runId }); } return; } if (action === "rerun" && payload.linked_run_id) { await Promise.all([loadRuns(), loadWorkspace()]); state.returnTaskId = actingTaskId; await showRunInRuntime(payload.linked_run_id, { preserveMode: true }); setMode("runtime"); setHeroStatus("running", "hero.runtimeSelected", { runId: payload.linked_run_id }); } }
async function createTaskFromForm(event) { event.preventDefault(); const form = new FormData(ui.taskForm); const payload = { title: String(form.get("title") || "").trim(), target_locale: String(form.get("target_locale") || "").trim(), verify_mode: String(form.get("verify_mode") || "").trim(), input_mode: state.wizardMode }; if (state.wizardMode === "upload") { if (!state.stagedUpload?.upload_id) throw new Error(state.language === "zh" ? "请先上传 CSV 文件。" : "Please upload a CSV file first."); payload.upload_id = state.stagedUpload.upload_id; } else { const inputPath = String(form.get("input_path") || "").trim(); if (!inputPath) throw new Error(state.language === "zh" ? "请填写本地 CSV 路径。" : "Please provide a local CSV path."); payload.input_path = inputPath; } const response = await fetchJson("/api/tasks", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }); state.stagedUpload = null; ui.taskFileInput.value = ""; ui.taskNoteInput.value = ""; ui.taskForm.reset(); ui.taskForm.elements.target_locale.value = "en-US"; ui.taskForm.elements.verify_mode.value = "full"; setWizardMode("upload"); renderStagedUpload(); await Promise.all([loadTaskOverviewAndList(), loadRuns(), loadWorkspace()]); if (response.task?.task_id) { await selectTask(response.task.task_id, { preserveMode: true }); setHeroStatus(response.task.status || "queued", "hero.taskCreated", { title: response.task.title }); setTaskFeedback("task.startSuccess"); } }
function handleTaskError(error) { setTaskFeedback(error.message, {}, { raw: true }); setHeroStatus("fail", "hero.loadFailed"); }
function handleWorkspaceError(error) { setWorkspaceFeedback(error.message, {}, { raw: true }); setHeroStatus("fail", "hero.loadFailed"); }
function handleRuntimeError(error) { setLaunchFeedback(error.message, {}, { raw: true }); setHeroStatus("fail", "hero.loadFailed"); }
ui.languageZhButton.addEventListener("click", () => applyLanguage("zh"));
ui.languageEnButton.addEventListener("click", () => applyLanguage("en"));
ui.modeTasksButton.addEventListener("click", () => setMode("tasks"));
ui.modeWorkspaceButton.addEventListener("click", () => setMode("workspace"));
ui.modeRuntimeButton.addEventListener("click", () => setMode("runtime"));
ui.heroStartTaskButton.addEventListener("click", () => document.getElementById("task-wizard-surface").scrollIntoView({ behavior: "smooth", block: "start" }));
ui.heroContinueTasksButton.addEventListener("click", () => document.getElementById("task-list").scrollIntoView({ behavior: "smooth", block: "start" }));
ui.taskRefreshButton.addEventListener("click", () => loadTaskOverviewAndList().catch(handleTaskError));
ui.taskForm.addEventListener("submit", (event) => createTaskFromForm(event).catch(handleTaskError));
ui.taskQueryFilter.addEventListener("input", () => { state.taskQuery = ui.taskQueryFilter.value.trim(); clearTimeout(taskQueryDebounce); taskQueryDebounce = setTimeout(() => loadTaskOverviewAndList().catch(handleTaskError), 220); });
ui.wizardModeButtons.forEach((button) => button.addEventListener("click", () => setWizardMode(button.dataset.wizardMode)));
ui.taskChooseFileButton.addEventListener("click", () => ui.taskFileInput.click());
ui.taskClearUploadButton.addEventListener("click", () => { state.stagedUpload = null; ui.taskFileInput.value = ""; renderStagedUpload(); });
ui.taskFileInput.addEventListener("change", (event) => { (async () => { const file = event.target.files?.[0]; if (!file) return; const form = new FormData(); form.append("file", file, file.name); const response = await fetch("/api/task_uploads", { method: "POST", body: form }); const payload = await response.json().catch(() => ({})); if (!response.ok) throw new Error(String(payload.detail || payload.error || "upload_failed")); state.stagedUpload = payload; ui.taskFileInput.value = ""; setWizardMode("upload"); renderStagedUpload(); setTaskFeedback(state.language === "zh" ? `已暂存 ${payload.original_filename}` : `Staged ${payload.original_filename}`, {}, { raw: true }); })().catch(handleTaskError); });
["dragenter", "dragover"].forEach((eventName) => ui.taskDropzone.addEventListener(eventName, (event) => { event.preventDefault(); ui.taskDropzone.classList.add("drag-active"); }));
["dragleave", "dragend", "drop"].forEach((eventName) => ui.taskDropzone.addEventListener(eventName, (event) => { event.preventDefault(); ui.taskDropzone.classList.remove("drag-active"); }));
ui.taskDropzone.addEventListener("click", () => ui.taskFileInput.click());
ui.taskDropzone.addEventListener("drop", (event) => { const file = event.dataTransfer?.files?.[0]; if (!file) return; const transfer = new DataTransfer(); transfer.items.add(file); ui.taskFileInput.files = transfer.files; ui.taskFileInput.dispatchEvent(new Event("change")); });
ui.workspaceRefreshButton.addEventListener("click", () => loadWorkspace().catch(handleWorkspaceError));
ui.caseStatusFilter.addEventListener("change", () => loadWorkspace().catch(handleWorkspaceError));
ui.caseLocaleFilter.addEventListener("input", () => { clearTimeout(workspaceQueryDebounce); workspaceQueryDebounce = setTimeout(() => loadWorkspace().catch(handleWorkspaceError), 220); });
ui.caseQueryFilter.addEventListener("input", () => { clearTimeout(workspaceQueryDebounce); workspaceQueryDebounce = setTimeout(() => loadWorkspace().catch(handleWorkspaceError), 220); });
ui.laneFilterButtons.forEach((button) => button.addEventListener("click", () => { state.workspaceFilters.lane = button.dataset.lane || "all"; loadWorkspaceCases().catch(handleWorkspaceError); }));
ui.tabButtons.forEach((button) => button.addEventListener("click", () => activateInspectorTab(button.dataset.tab)));
ui.openRuntimeButton.addEventListener("click", () => { if (state.workspaceDetail?.run_id) showRunInRuntime(state.workspaceDetail.run_id).catch(handleRuntimeError); });
ui.launcherForm.addEventListener("submit", (event) => launchRunFromShell(event).catch(handleRuntimeError));
ui.refreshButton.addEventListener("click", () => loadRuns().catch(handleRuntimeError));
ui.workspaceReturnButton.addEventListener("click", () => { const taskId = state.returnTaskId || state.selectedTaskId; setMode("tasks"); if (taskId) selectTask(taskId, { preserveMode: true }).catch(handleTaskError); });
ui.runtimeReturnButton.addEventListener("click", () => { const taskId = state.returnTaskId || state.selectedTaskId; setMode("tasks"); if (taskId) selectTask(taskId, { preserveMode: true }).catch(handleTaskError); });
ui.taskQueryFilter.value = state.taskQuery;
ui.caseStatusFilter.value = state.workspaceFilters.status;
ui.caseLocaleFilter.value = state.workspaceFilters.targetLocale;
ui.caseQueryFilter.value = state.workspaceFilters.query;
applyLanguage(state.language, { persist: false });
syncWizardPanels();
renderStagedUpload();
renderReturnButtons();
renderEmptyTaskDetail();
renderEmptyWorkspaceSelection();
renderEmptyRuntimeSelection();
setMode("tasks");
activateInspectorTab(state.inspectorTab);
Promise.all([loadTaskOverviewAndList(), loadWorkspace(), loadRuns()]).then(async () => { const firstTask = state.tasks[0]; if (firstTask) await selectTask(firstTask.task_id, { preserveMode: true }); setHeroStatus("pass", "hero.tasksReady"); }).catch((error) => { handleTaskError(error); handleWorkspaceError(error); handleRuntimeError(error); });
