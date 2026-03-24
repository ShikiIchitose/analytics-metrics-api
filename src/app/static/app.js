"use strict";

const metricForm = document.getElementById("metric-form");
const metricRequest = document.getElementById("metric-request");
const metricStatus = document.getElementById("metric-status");
const metricWarnings = document.getElementById("metric-warnings");
const metricResult = document.getElementById("metric-result");
const metricRaw = document.getElementById("metric-raw");

const userForm = document.getElementById("user-form");
const userRequest = document.getElementById("user-request");
const userStatus = document.getElementById("user-status");
const userResult = document.getElementById("user-result");
const userRaw = document.getElementById("user-raw");

const jobRunsForm = document.getElementById("job-runs-form");
const jobRunsRequest = document.getElementById("job-runs-request");
const jobRunsStatus = document.getElementById("job-runs-status");
const jobRunsResult = document.getElementById("job-runs-result");
const jobRunsRaw = document.getElementById("job-runs-raw");

const jobSummaryForm = document.getElementById("job-summary-form");
const jobSummaryRequest = document.getElementById("job-summary-request");
const jobSummaryStatus = document.getElementById("job-summary-status");
const jobSummaryResult = document.getElementById("job-summary-result");
const jobSummaryRaw = document.getElementById("job-summary-raw");

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatValue(value) {
  if (value === null || value === undefined) {
    return "";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

function prettyResponse(body, rawText) {
  if (body !== null) {
    return JSON.stringify(body, null, 2);
  }
  return rawText || "";
}

async function fetchJson(url) {
  const response = await fetch(url, {
    headers: {
      Accept: "application/json",
    },
  });

  const rawText = await response.text();

  let body = null;
  try {
    body = rawText ? JSON.parse(rawText) : null;
  } catch {
    body = null;
  }

  return { response, body, rawText };
}

function renderRowsTable(rows) {
  if (!Array.isArray(rows) || rows.length === 0) {
    return '<div class="muted">No rows returned.</div>';
  }

  const columns = Array.from(
    rows.reduce((acc, row) => {
      Object.keys(row).forEach((key) => acc.add(key));
      return acc;
    }, new Set()),
  );

  const colCountClass = `cols-${columns.length}`;

  const headHtml = columns
    .map((column) => `<th>${escapeHtml(column)}</th>`)
    .join("");

  const bodyHtml = rows
    .map((row) => {
      const cells = columns
        .map((column) => {
          const value = formatValue(row[column]);
          return `<td>${escapeHtml(value)}</td>`;
        })
        .join("");

      return `<tr>${cells}</tr>`;
    })
    .join("");

  return `
    <div class="table-wrap">
      <table class="${colCountClass}">
        <thead>
          <tr>${headHtml}</tr>
        </thead>
        <tbody>
          ${bodyHtml}
        </tbody>
      </table>
    </div>
  `;
}

function renderWarnings(warnings) {
  if (!Array.isArray(warnings) || warnings.length === 0) {
    metricWarnings.textContent = "None";
    metricWarnings.className = "messages muted";
    return;
  }

  const items = warnings
    .map((warning) => `<li>${escapeHtml(formatValue(warning))}</li>`)
    .join("");

  metricWarnings.innerHTML = `<ul>${items}</ul>`;
  metricWarnings.className = "messages";
}

function renderUser(user) {
  userResult.innerHTML = `
    <dl class="user-grid">
      <dt>user_id</dt>
      <dd>${escapeHtml(formatValue(user.user_id))}</dd>

      <dt>signup_time</dt>
      <dd>${escapeHtml(formatValue(user.signup_time))}</dd>

      <dt>country</dt>
      <dd>${escapeHtml(formatValue(user.country))}</dd>

      <dt>plan</dt>
      <dd>${escapeHtml(formatValue(user.plan))}</dd>
    </dl>
  `;
  userResult.className = "panel";
}

function renderKeyValueTable(obj) {
  if (!obj || typeof obj !== "object") {
    return '<div class="muted">No data returned.</div>';
  }

  const rowsHtml = Object.entries(obj)
    .map(([key, value]) => {
      return `
        <tr>
          <th>${escapeHtml(key)}</th>
          <td>${escapeHtml(formatValue(value))}</td>
        </tr>
      `;
    })
    .join("");

  return `
    <div class="table-wrap">
      <table class="summary-table">
        <tbody>
          ${rowsHtml}
        </tbody>
      </table>
    </div>
  `;
}

function setJobRunsIdleState(message) {
  jobRunsStatus.textContent = message;
  jobRunsStatus.className = "status muted";
}

function setJobSummaryIdleState(message) {
  jobSummaryStatus.textContent = message;
  jobSummaryStatus.className = "status muted";
}

function setMetricIdleState(message) {
  metricStatus.textContent = message;
  metricStatus.className = "status muted";
}

function setUserIdleState(message) {
  userStatus.textContent = message;
  userStatus.className = "status muted";
}

metricForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  setMetricIdleState("Loading...");
  metricWarnings.textContent = "Loading...";
  metricWarnings.className = "messages muted";
  metricResult.textContent = "";
  metricResult.className = "panel";
  metricRaw.textContent = "";

  const formData = new FormData(metricForm);

  const metric = String(formData.get("metric") ?? "").trim();
  const start = String(formData.get("start") ?? "").trim();
  const end = String(formData.get("end") ?? "").trim();
  const groupBy = String(formData.get("group_by") ?? "").trim();
  const limit = String(formData.get("limit") ?? "").trim();

  const params = new URLSearchParams();
  params.set("start", start);
  params.set("end", end);
  if (groupBy !== "") {
    params.set("group_by", groupBy);
  }
  params.set("limit", limit);

  const url = `/metrics/${encodeURIComponent(metric)}?${params.toString()}`;
  metricRequest.textContent = url;

  try {
    const { response, body, rawText } = await fetchJson(url);

    metricStatus.textContent = `HTTP ${response.status}`;
    metricStatus.className = response.ok
      ? "status ok-text"
      : "status error-text";

    metricRaw.textContent = prettyResponse(body, rawText);

    if (!response.ok) {
      metricWarnings.textContent = "None";
      metricWarnings.className = "messages muted";
      metricResult.innerHTML = `
        <pre class="mono error-text">${escapeHtml(prettyResponse(body, rawText))}</pre>
      `;
      metricResult.className = "panel";
      return;
    }

    const rows = body?.data?.rows ?? [];
    const warnings = body?.meta?.warnings ?? [];

    renderWarnings(warnings);
    metricResult.innerHTML = renderRowsTable(rows);
    metricResult.className = "panel";
  } catch (error) {
    metricStatus.textContent = "Request failed";
    metricStatus.className = "status error-text";
    metricWarnings.textContent = "None";
    metricWarnings.className = "messages muted";
    metricResult.innerHTML = `
      <pre class="mono error-text">${escapeHtml(String(error))}</pre>
    `;
    metricResult.className = "panel";
    metricRaw.textContent = String(error);
  }
});

userForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  setUserIdleState("Loading...");
  userResult.textContent = "";
  userResult.className = "panel";
  userRaw.textContent = "";

  const formData = new FormData(userForm);
  const userId = String(formData.get("user_id") ?? "").trim();

  const url = `/users/${encodeURIComponent(userId)}`;
  userRequest.textContent = url;

  try {
    const { response, body, rawText } = await fetchJson(url);

    userStatus.textContent = `HTTP ${response.status}`;
    userStatus.className = response.ok ? "status ok-text" : "status error-text";

    userRaw.textContent = prettyResponse(body, rawText);

    if (!response.ok) {
      userResult.innerHTML = `
        <pre class="mono error-text">${escapeHtml(prettyResponse(body, rawText))}</pre>
      `;
      userResult.className = "panel";
      return;
    }

    renderUser(body.data);
  } catch (error) {
    userStatus.textContent = "Request failed";
    userStatus.className = "status error-text";
    userResult.innerHTML = `
      <pre class="mono error-text">${escapeHtml(String(error))}</pre>
    `;
    userResult.className = "panel";
    userRaw.textContent = String(error);
  }
});

jobRunsForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  setJobRunsIdleState("Loading...");
  jobRunsResult.textContent = "";
  jobRunsResult.className = "panel";
  jobRunsRaw.textContent = "";

  const formData = new FormData(jobRunsForm);

  const start = String(formData.get("start") ?? "").trim();
  const end = String(formData.get("end") ?? "").trim();
  const limit = String(formData.get("limit") ?? "").trim();
  const jobName = String(formData.get("job_name") ?? "").trim();
  const status = String(formData.get("status") ?? "").trim();

  const params = new URLSearchParams();
  params.set("start", start);
  params.set("end", end);
  params.set("limit", limit);

  if (jobName !== "") {
    params.set("job_name", jobName);
  }
  if (status !== "") {
    params.set("status", status);
  }

  const url = `/jobs/runs?${params.toString()}`;
  jobRunsRequest.textContent = url;

  try {
    const { response, body, rawText } = await fetchJson(url);

    jobRunsStatus.textContent = `HTTP ${response.status}`;
    jobRunsStatus.className = response.ok
      ? "status ok-text"
      : "status error-text";

    jobRunsRaw.textContent = prettyResponse(body, rawText);

    if (!response.ok) {
      jobRunsResult.innerHTML = `
        <pre class="mono error-text">${escapeHtml(prettyResponse(body, rawText))}</pre>
      `;
      jobRunsResult.className = "panel";
      return;
    }

    const rows = body?.data?.rows ?? [];
    jobRunsResult.innerHTML = renderRowsTable(rows);
    jobRunsResult.className = "panel";
  } catch (error) {
    jobRunsStatus.textContent = "Request failed";
    jobRunsStatus.className = "status error-text";
    jobRunsResult.innerHTML = `
      <pre class="mono error-text">${escapeHtml(String(error))}</pre>
    `;
    jobRunsResult.className = "panel";
    jobRunsRaw.textContent = String(error);
  }
});

jobSummaryForm.addEventListener("submit", async (event) => {
  event.preventDefault();

  setJobSummaryIdleState("Loading...");
  jobSummaryResult.textContent = "";
  jobSummaryResult.className = "panel";
  jobSummaryRaw.textContent = "";

  const formData = new FormData(jobSummaryForm);

  const jobName = String(formData.get("job_name") ?? "").trim();
  const start = String(formData.get("start") ?? "").trim();
  const end = String(formData.get("end") ?? "").trim();

  const params = new URLSearchParams();
  params.set("start", start);
  params.set("end", end);

  const url = `/jobs/${encodeURIComponent(jobName)}/summary?${params.toString()}`;
  jobSummaryRequest.textContent = url;

  try {
    const { response, body, rawText } = await fetchJson(url);

    jobSummaryStatus.textContent = `HTTP ${response.status}`;
    jobSummaryStatus.className = response.ok
      ? "status ok-text"
      : "status error-text";

    jobSummaryRaw.textContent = prettyResponse(body, rawText);

    if (!response.ok) {
      jobSummaryResult.innerHTML = `
        <pre class="mono error-text">${escapeHtml(prettyResponse(body, rawText))}</pre>
      `;
      jobSummaryResult.className = "panel";
      return;
    }

    const summary = body?.data ?? null;
    jobSummaryResult.innerHTML = renderKeyValueTable(summary);
    jobSummaryResult.className = "panel";
  } catch (error) {
    jobSummaryStatus.textContent = "Request failed";
    jobSummaryStatus.className = "status error-text";
    jobSummaryResult.innerHTML = `
      <pre class="mono error-text">${escapeHtml(String(error))}</pre>
    `;
    jobSummaryResult.className = "panel";
    jobSummaryRaw.textContent = String(error);
  }
});
