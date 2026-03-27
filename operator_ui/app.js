const state = {
  runs: [],
  selectedRunId: null,
  selectedArtifactKey: null,
};

const ui = {
  heroStatus: document.getElementById("hero-status"),
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

function statusMarkup(status, label) {
  const normalized = (status || "unknown").toLowerCase();
  return `<span class="status-${normalized}"><span class="status-dot status-${normalized}"></span>${label || normalized}</span>`;
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
        <button type="button" class="run-card ${selected}" data-run-id="${run.run_id}">
          <strong>${run.run_id}</strong>
          <div class="run-meta">
            <span>${statusMarkup(run.overall_status, run.overall_status)}</span>
            <span>${run.target_lang || "n/a"}</span>
            <span>${run.verify_mode || "n/a"}</span>
          </div>
          <p>${stageSummary}</p>
        </button>
      `;
    })
    .join("");

  ui.runsList.querySelectorAll("[data-run-id]").forEach((element) => {
    element.addEventListener("click", () => {
      loadRunDetail(element.dataset.runId);
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
      <span class="pill">verify: ${run.verify_mode || "n/a"}</span>
      <span class="pill">target: ${run.target_lang || "n/a"}</span>
      <span class="pill">pending: ${run.pending ? "yes" : "no"}</span>
      <span class="pill">dir: ${run.run_dir || "n/a"}</span>
    </div>
  `;
  setHeroStatus(run.overall_status, `Selected ${run.run_id}`);

  ui.timelinePanel.innerHTML = stages.length
    ? stages
        .map((stage) => `
          <article class="timeline-stage">
            <header>
              <strong>${stage.name}</strong>
              ${statusMarkup(stage.status, stage.status)}
            </header>
            <p>required: ${stage.required ? "yes" : "no"}</p>
            <p>missing required: ${stage.missing_required_files?.length || 0}</p>
          </article>
        `)
        .join("")
    : '<div class="empty-state">No timeline data yet for this run.</div>';

  ui.verifySummary.innerHTML = `
    <p><strong>Status:</strong> ${verify.status || "n/a"}</p>
    <p><strong>Overall:</strong> ${verify.overall || "n/a"}</p>
    <p><strong>Issue Count:</strong> ${verify.issue_count || 0}</p>
    <p><strong>QA Rows:</strong></p>
    <pre>${(verify.qa_rows || []).join("\n") || "No QA rows."}</pre>
  `;

  ui.issueSummary.innerHTML = `
    <p><strong>Total:</strong> ${run.issue_summary?.total || 0}</p>
    <p><strong>By Severity:</strong> ${JSON.stringify(run.issue_summary?.by_severity || {})}</p>
    <p><strong>By Stage:</strong> ${JSON.stringify(run.issue_summary?.by_stage || {})}</p>
  `;

  const artifacts = run.artifacts || [];
  ui.artifactList.innerHTML = artifacts.length
    ? artifacts
        .map((artifact) => `
          <button type="button" class="artifact-button ${artifact.key === state.selectedArtifactKey ? "active" : ""}" data-artifact-key="${artifact.key}">
            <strong>${artifact.key}</strong>
            <div>${artifact.kind} · ${artifact.exists ? "present" : "missing"}</div>
          </button>
        `)
        .join("")
    : '<div class="empty-state">No artifacts declared for this run.</div>';

  ui.artifactList.querySelectorAll("[data-artifact-key]").forEach((element) => {
    element.addEventListener("click", () => {
      loadArtifact(run.run_id, element.dataset.artifactKey);
    });
  });

  renderRuns();
}

async function loadRuns() {
  ui.launchFeedback.textContent = "Refreshing runtime inventory...";
  const payload = await fetchJson("/api/runs?limit=12");
  state.runs = payload.runs || [];
  renderRuns();
  ui.launchFeedback.textContent = "Runtime inventory refreshed.";
  if (!state.selectedRunId && state.runs.length) {
    await loadRunDetail(state.runs[0].run_id);
  }
}

async function loadRunDetail(runId) {
  const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}`);
  renderDetail(payload.run);
}

async function loadArtifact(runId, artifactKey) {
  state.selectedArtifactKey = artifactKey;
  const payload = await fetchJson(`/api/runs/${encodeURIComponent(runId)}/artifacts/${encodeURIComponent(artifactKey)}`);
  const artifact = payload.artifact;
  const body =
    artifact.content ||
    (artifact.json ? JSON.stringify(artifact.json, null, 2) : "Artifact has no text preview.");
  ui.artifactPanel.innerHTML = `
    <div class="artifact-header">
      <strong>${artifact.key}</strong>
      <div>${artifact.path}</div>
    </div>
    <pre>${body.replace(/[&<>]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;" }[char]))}</pre>
  `;
  renderRuns();
}

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
  } catch (error) {
    ui.launchFeedback.textContent = error.message;
    setHeroStatus("fail", "Launch failed");
  }
});

ui.refreshButton.addEventListener("click", () => {
  loadRuns().catch((error) => {
    ui.launchFeedback.textContent = error.message;
    setHeroStatus("fail", "Refresh failed");
  });
});

loadRuns().catch((error) => {
  ui.launchFeedback.textContent = error.message;
  setHeroStatus("fail", "Initial load failed");
});
