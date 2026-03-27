const state = {
  mode: "workspace",
  runs: [],
  selectedRunId: null,
  selectedArtifactKey: null,
  workspaceOverview: null,
  workspaceCards: [],
  selectedCardId: null,
  selectedWorkspaceRunId: null,
  workspaceDetail: null,
};

const ui = {
  heroStatus: document.getElementById("hero-status"),
  workspaceModeButton: document.getElementById("mode-workspace"),
  runtimeModeButton: document.getElementById("mode-runtime"),
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

function escapeHtml(value) {
  return String(value || "").replace(/[&<>]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[char]));
}

function statusMarkup(status, label) {
  const normalized = (status || "unknown").toLowerCase();
  return `<span class="status-${normalized}"><span class="status-dot status-${normalized}"></span>${escapeHtml(label || normalized)}</span>`;
}

async function fetchJson(url, options = {}) {
  const response = await fetch(url, options);
  if (!response.ok) {
    const payload = await response.json().catch(() => ({}));
    throw new Error(payload.detail || payload.error || `Request failed: ${response.status}`);
  }
  return response.json();
}

function setHeroStatus(status, label) {
  ui.heroStatus.innerHTML = statusMarkup(status, label);
}

function setMode(mode) {
  state.mode = mode;
  const workspaceActive = mode === "workspace";
  ui.workspaceModeButton.classList.toggle("active", workspaceActive);
  ui.runtimeModeButton.classList.toggle("active", !workspaceActive);
  ui.workspaceView.classList.toggle("hidden", !workspaceActive);
  ui.runtimeView.classList.toggle("hidden", workspaceActive);
}

function renderList(values, emptyLabel) {
  if (!values || !values.length) {
    return `<div class="empty-state">${escapeHtml(emptyLabel)}</div>`;
  }
  return `<ul class="list-block">${values.map((value) => `<li>${escapeHtml(value)}</li>`).join("")}</ul>`;
}

function renderObjectEntries(payload, emptyLabel) {
  const entries = Object.entries(payload || {});
  if (!entries.length) {
    return `<div class="empty-state">${escapeHtml(emptyLabel)}</div>`;
  }
  return `<ul class="list-block">${entries.map(([key, value]) => `<li><strong>${escapeHtml(key)}:</strong> ${escapeHtml(value)}</li>`).join("")}</ul>`;
}

function workspaceQueryString() {
  const params = new URLSearchParams();
  params.set("status", ui.cardStatusFilter.value || "open");
  if (ui.cardTypeFilter.value) {
    params.set("card_type", ui.cardTypeFilter.value);
  }
  if (ui.cardPriorityFilter.value) {
    params.set("priority", ui.cardPriorityFilter.value);
  }
  if (ui.cardLocaleFilter.value.trim()) {
    params.set("target_locale", ui.cardLocaleFilter.value.trim());
  }
  params.set("limit", "25");
  return params.toString();
}

function renderRuns() {
  if (!state.runs.length) {
    ui.runsList.innerHTML = '<div class="empty-state">No runs discovered yet.</div>';
    return;
  }

  ui.runsList.innerHTML = state.runs
    .map((run) => {
      const selected = run.run_id === state.selectedRunId ? "selected" : "";
      const stageSummary = Object.entries(run.stage_counts || {})
        .map(([key, value]) => `${key}:${value}`)
        .join(" · ") || "no timeline yet";
      return `
        <button type="button" class="run-card ${selected}" data-run-id="${escapeHtml(run.run_id)}">
          <strong>${escapeHtml(run.run_id)}</strong>
          <div class="run-meta">
            <span>${statusMarkup(run.overall_status, run.overall_status)}</span>
            <span>${escapeHtml(run.target_lang || "n/a")}</span>
            <span>${escapeHtml(run.verify_mode || "n/a")}</span>
          </div>
          <p>${escapeHtml(stageSummary)}</p>
        </button>
      `;
    })
    .join("");

  ui.runsList.querySelectorAll("[data-run-id]").forEach((element) => {
    element.addEventListener("click", () => {
      loadRunDetail(element.dataset.runId).catch(handleRuntimeError);
      setMode("runtime");
    });
  });
}

function renderDetail(run) {
  state.selectedRunId = run.run_id;
  const stages = run.stages || [];
  const verify = run.verify || {};
  ui.runTitle.textContent = run.run_id;
  ui.runMeta.innerHTML = `
    ${statusMarkup(run.overall_status, `${run.overall_status} overall`)}
    <div class="pill-row">
      <span class="pill">verify: ${escapeHtml(run.verify_mode || "n/a")}</span>
      <span class="pill">target: ${escapeHtml(run.target_lang || "n/a")}</span>
      <span class="pill">pending: ${run.pending ? "yes" : "no"}</span>
      <span class="pill">dir: ${escapeHtml(run.run_dir || "n/a")}</span>
    </div>
  `;

  ui.timelinePanel.innerHTML = stages.length
    ? stages
        .map((stage) => `
          <article class="timeline-stage">
            <header>
              <strong>${escapeHtml(stage.name)}</strong>
              ${statusMarkup(stage.status, stage.status)}
            </header>
            <p>required: ${stage.required ? "yes" : "no"}</p>
            <p>missing required: ${stage.missing_required_files?.length || 0}</p>
          </article>
        `)
        .join("")
    : '<div class="empty-state">No timeline data yet for this run.</div>';

  ui.verifySummary.innerHTML = `
    <p><strong>Status:</strong> ${escapeHtml(verify.status || "n/a")}</p>
    <p><strong>Overall:</strong> ${escapeHtml(verify.overall || "n/a")}</p>
    <p><strong>Issue Count:</strong> ${escapeHtml(verify.issue_count || 0)}</p>
    <p><strong>QA Rows:</strong></p>
    <pre>${escapeHtml((verify.qa_rows || []).join("\n") || "No QA rows.")}</pre>
  `;

  ui.issueSummary.innerHTML = `
    <p><strong>Total:</strong> ${escapeHtml(run.issue_summary?.total || 0)}</p>
    <p><strong>By Severity:</strong> ${escapeHtml(JSON.stringify(run.issue_summary?.by_severity || {}))}</p>
    <p><strong>By Stage:</strong> ${escapeHtml(JSON.stringify(run.issue_summary?.by_stage || {}))}</p>
  `;

  const artifacts = run.artifacts || [];
  ui.artifactList.innerHTML = artifacts.length
    ? artifacts
        .map((artifact) => `
          <button type="button" class="artifact-button ${artifact.key === state.selectedArtifactKey ? "active" : ""}" data-artifact-key="${escapeHtml(artifact.key)}">
            <strong>${escapeHtml(artifact.key)}</strong>
            <div>${escapeHtml(artifact.kind)} · ${artifact.exists ? "present" : "missing"}</div>
          </button>
        `)
        .join("")
    : '<div class="empty-state">No artifacts declared for this run.</div>';

  ui.artifactList.querySelectorAll("[data-artifact-key]").forEach((element) => {
    element.addEventListener("click", () => {
      loadArtifact(run.run_id, element.dataset.artifactKey).catch(handleRuntimeError);
    });
  });

  renderRuns();
}

function renderWorkspaceOverview() {
  const overview = state.workspaceOverview;
  if (!overview) {
    ui.overviewRibbon.innerHTML = '<div class="empty-state">No workspace overview loaded yet.</div>';
    return;
  }

  const recentRuns = (overview.recent_runs || [])
    .slice(0, 4)
    .map((run) => `
      <button type="button" class="recent-run-chip" data-run-id="${escapeHtml(run.run_id)}">
        <strong>${escapeHtml(run.run_id)}</strong>
        <div class="run-meta">
          <span>${statusMarkup(run.overall_status, run.overall_status)}</span>
          <span>${escapeHtml(run.target_lang || "n/a")}</span>
        </div>
      </button>
    `)
    .join("");

  ui.overviewRibbon.innerHTML = `
    <article class="ribbon-card">
      <p class="panel-kicker">Open Cards</p>
      <span class="ribbon-value">${escapeHtml(overview.open_card_count || 0)}</span>
    </article>
    <article class="ribbon-card">
      <p class="panel-kicker">Runs With Open Cards</p>
      <span class="ribbon-value">${escapeHtml(overview.runs_with_open_cards || 0)}</span>
    </article>
    <article class="ribbon-card">
      <p class="panel-kicker">Pending Review Tickets</p>
      <span class="ribbon-value">${escapeHtml(overview.open_review_tickets || 0)}</span>
    </article>
    <article class="ribbon-card">
      <p class="panel-kicker">Runs With Drift</p>
      <span class="ribbon-value">${escapeHtml(overview.runs_with_drift || 0)}</span>
    </article>
    <article class="ribbon-card">
      <p class="panel-kicker">Runtime Health</p>
      <div>${escapeHtml(JSON.stringify(overview.runtime_health_counts || {}))}</div>
    </article>
    <article class="ribbon-card">
      <p class="panel-kicker">Recent Runs</p>
      <div class="recent-run-stack">${recentRuns || '<div class="empty-state">No recent runs.</div>'}</div>
    </article>
  `;

  ui.overviewRibbon.querySelectorAll("[data-run-id]").forEach((element) => {
    element.addEventListener("click", () => {
      openRunInRuntimeLane(element.dataset.runId).catch(handleRuntimeError);
    });
  });
}

function renderWorkspaceCards() {
  if (!state.workspaceCards.length) {
    ui.workspaceCards.innerHTML = '<div class="empty-state">No operator cards match the current filters.</div>';
    return;
  }

  ui.workspaceCards.innerHTML = state.workspaceCards
    .map((card) => {
      const selected = card.card_id === state.selectedCardId ? "selected" : "";
      return `
        <button type="button" class="workspace-card ${selected}" data-card-id="${escapeHtml(card.card_id)}">
          <strong>${escapeHtml(card.title)}</strong>
          <div class="workspace-card-meta">
            <span>${statusMarkup(card.status, card.status)}</span>
            <span>${escapeHtml(card.priority)}</span>
            <span>${escapeHtml(card.card_type)}</span>
            <span>${escapeHtml(card.target_locale || "n/a")}</span>
          </div>
          <p>${escapeHtml(card.summary)}</p>
        </button>
      `;
    })
    .join("");

  ui.workspaceCards.querySelectorAll("[data-card-id]").forEach((element) => {
    element.addEventListener("click", () => {
      selectWorkspaceCard(element.dataset.cardId).catch(handleWorkspaceError);
    });
  });
}

function renderWorkspaceDetail(detail) {
  state.workspaceDetail = detail;
  state.selectedWorkspaceRunId = detail.run_id;
  ui.workspaceRunTitle.textContent = detail.run_id;
  ui.workspaceRunMeta.innerHTML = `
    <div class="pill-row">
      <span class="pill">open cards: ${escapeHtml(detail.operator_summary?.open_operator_cards || 0)}</span>
      <span class="pill">runtime: ${escapeHtml(detail.operator_summary?.overall_runtime_health?.status || "unknown")}</span>
    </div>
  `;

  const context = detail.decision_context || {};
  ui.decisionContext.innerHTML = `
    <p><strong>${escapeHtml(context.title || "No selected card")}</strong></p>
    <p>${escapeHtml(context.summary || "No decision summary loaded.")}</p>
    <h4>Recommended Actions</h4>
    ${renderList(context.recommended_actions || [], "No recommended actions.")}
    <h4>Artifact Refs</h4>
    ${renderObjectEntries(context.artifact_refs || {}, "No artifact refs.")}
    <h4>Evidence Refs</h4>
    ${renderList(context.evidence_refs || [], "No evidence refs.")}
    <h4>ADR Refs</h4>
    ${renderList(context.adr_refs || [], "No ADR refs.")}
  `;

  ui.reviewWorkload.innerHTML = renderObjectEntries(detail.review_workload || {}, "No review workload loaded.");
  ui.kpiSnapshot.innerHTML = renderObjectEntries(detail.kpi_snapshot || {}, "No KPI snapshot loaded.");
  const drift = detail.governance_drift || {};
  ui.governanceDrift.innerHTML = `
    <p><strong>Drift Count:</strong> ${escapeHtml(drift.drift_count || 0)}</p>
    <h4>Reasons</h4>
    ${renderList(drift.reasons || [], "No governance drift detected.")}
  `;
}

function preferredArtifactKey(run) {
  const allowed = new Set(run.allowed_artifact_keys || []);
  const preferred = ["run_manifest", "smoke_verify_report", "smoke_issues_report", "smoke_verify_log"];
  for (const key of preferred) {
    if (allowed.has(key)) {
      return key;
    }
  }
  const artifacts = run.artifacts || [];
  const previewable = artifacts.find((artifact) => artifact.previewable && allowed.has(artifact.key));
  return previewable ? previewable.key : "";
}

async function loadRuns() {
  ui.launchFeedback.textContent = "Refreshing runtime inventory...";
  const payload = await fetchJson("/api/runs?limit=12");
  state.runs = payload.runs || [];
  renderRuns();
  ui.launchFeedback.textContent = "Runtime inventory refreshed.";
  if (!state.selectedRunId && state.runs.length) {
    await loadRunDetail(state.runs[0].run_id, { preserveMode: true });
  }
}

async function loadRunDetail(runId, options = {}) {
  const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}`);
  renderDetail(payload.run);
  if (!options.preserveMode) {
    setMode("runtime");
    setHeroStatus(payload.run.overall_status, `Selected ${payload.run.run_id}`);
  }
  return payload.run;
}

async function loadArtifact(runId, artifactKey, options = {}) {
  state.selectedArtifactKey = artifactKey;
  const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactKey)}`);
  const artifact = payload.artifact;
  const body = artifact.content || (artifact.json ? JSON.stringify(artifact.json, null, 2) : "Artifact has no text preview.");
  ui.artifactPanel.innerHTML = `
    <div class="artifact-header">
      <strong>${escapeHtml(artifact.key)}</strong>
      <div>${escapeHtml(artifact.path)}</div>
    </div>
    <pre>${escapeHtml(body)}</pre>
  `;
  renderRuns();
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
    setHeroStatus(card.status, `Operator card ${card.card_id}`);
  }
}

async function loadWorkspace() {
  ui.workspaceFeedback.textContent = "Refreshing operator workspace...";
  await loadWorkspaceOverview();
  await loadWorkspaceCards();
  ui.workspaceFeedback.textContent = "Operator workspace refreshed.";
}

function handleRuntimeError(error) {
  ui.launchFeedback.textContent = error.message;
  setHeroStatus("fail", "Runtime lane failed");
}

function handleWorkspaceError(error) {
  ui.workspaceFeedback.textContent = error.message;
  setHeroStatus("fail", "Workspace load failed");
}

ui.workspaceModeButton.addEventListener("click", () => setMode("workspace"));
ui.runtimeModeButton.addEventListener("click", () => setMode("runtime"));
ui.openRuntimeButton.addEventListener("click", () => {
  if (!state.selectedWorkspaceRunId) {
    return;
  }
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
  ui.launchFeedback.textContent = "Launching representative smoke run...";
  try {
    const response = await fetchJson("/api/runs", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    ui.launchFeedback.textContent = `Run ${response.run.run_id} launched.`;
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

Promise.all([loadRuns(), loadWorkspace()])
  .then(() => {
    setMode("workspace");
    setHeroStatus("pass", "Workspace ready");
  })
  .catch((error) => {
    ui.launchFeedback.textContent = error.message;
    ui.workspaceFeedback.textContent = error.message;
    setHeroStatus("fail", "Initial load failed");
  });
