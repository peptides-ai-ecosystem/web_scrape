/**
 * Operations Dashboard
 *
 * Exposes every write/ops endpoint defined in api_server.py:
 *   - Syncing:    POST /sync/core, /sync/graph, /sync/graph-missing
 *   - Evaluation: POST /evaluation/core, /evaluation/graph
 *   - Operations: GET /operations/jobs, GET /operations/job/{id},
 *                 DELETE /operations/job/{id}, GET /operations/health
 *   - Scheduler:  GET /scheduler/status, POST /scheduler/start,
 *                 POST /scheduler/pause, POST /scheduler/resume
 *
 * Every request is logged in the raw-response panel so the operator can see
 * the literal JSON each endpoint returns.
 */
(function () {
    "use strict";

    const API = "/api/v1";
    const $ = (id) => document.getElementById(id);

    // ---------------------------------------------------------------- core helpers

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function nowTime() {
        const d = new Date();
        return d.toLocaleTimeString();
    }

    function fmtTimestamp(iso) {
        if (!iso) return "—";
        try { return new Date(iso).toLocaleTimeString(); }
        catch (_e) { return iso; }
    }

    // --------------------------------------------------------------- log state
    //
    // The log captures TWO kinds of activity:
    //   1) HTTP fetches via api()   — method/path/status/body
    //   2) Inline notes via note()  — user actions, job state transitions, etc.
    //
    // Routine background polls (`/operations/jobs`, `/operations/health`,
    // `/scheduler/status` auto-refreshes, per-job polls between status changes)
    // are sent with `silent: true` so they don't drown out the events that
    // matter. Toggle "Show polls" in the panel header to surface them anyway.

    const LOG = {
        showPolls: false,
        // Per-job last-seen status so we only log job-poll transitions
        lastJobStatus: new Map(),
        // Per-poll-key last-seen serialized payload so we only log on change
        lastPollHash: new Map(),
    };

    function ensureLogReady() {
        const stream = $("log-stream");
        if (stream.firstElementChild && stream.firstElementChild.classList.contains("empty-state")) {
            stream.innerHTML = "";
        }
        return stream;
    }

    function appendLog(entry) {
        const stream = ensureLogReady();
        const ok = entry.status >= 200 && entry.status < 300;
        const statusClass = ok ? "ok" : "err";
        const body = entry.body != null ? JSON.stringify(entry.body, null, 2) : (entry.text || "");
        const node = document.createElement("details");
        node.className = "log-entry";
        if (entry.silent) node.classList.add("log-entry--poll");
        node.innerHTML = `
            <summary>
                <span class="log-method ${entry.method}">${entry.method}</span>
                <span class="log-status ${statusClass}">${entry.status}</span>
                <span class="log-path">${escapeHtml(entry.path)}</span>
                <span class="log-time">${entry.time}</span>
            </summary>
            <pre class="json-block tight">${escapeHtml(body)}</pre>
        `;
        stream.prepend(node);
    }

    /**
     * Plain-text activity note (not an HTTP request). Useful for "user clicked
     * Run sync/core", "Job xyz transitioned pending → running", etc.
     */
    function note(level, message, body) {
        const stream = ensureLogReady();
        const node = document.createElement("details");
        node.className = `log-entry log-entry--note log-entry--${level}`;
        const bodyStr = body != null ? JSON.stringify(body, null, 2) : "";
        const hasBody = bodyStr.length > 0;
        node.innerHTML = `
            <summary>
                <span class="log-note-tag log-note-${level}">${level.toUpperCase()}</span>
                <span class="log-path">${escapeHtml(message)}</span>
                <span class="log-time">${nowTime()}</span>
            </summary>
            ${hasBody ? `<pre class="json-block tight">${escapeHtml(bodyStr)}</pre>` : ""}
        `;
        stream.prepend(node);
    }

    /**
     * api(method, path[, body][, opts])
     *
     * opts.silent  — entry is rendered as a faint "poll" row, hidden by default.
     *                Use for routine background refreshes.
     * opts.dedupeKey — if provided AND the response body hasn't changed since the
     *                last call with the same key, the entry is skipped entirely.
     */
    async function api(method, path, body, opts) {
        opts = opts || {};
        const init = { method, headers: {} };
        if (body !== undefined) {
            init.headers["Content-Type"] = "application/json";
            init.body = JSON.stringify(body);
        }
        let res, data, text;
        try {
            res = await fetch(API + path, init);
            text = await res.text();
            try { data = text ? JSON.parse(text) : null; }
            catch (_e) { data = null; }

            let shouldLog = true;
            if (opts.dedupeKey) {
                const hash = `${res.status}:${text || ""}`;
                if (LOG.lastPollHash.get(opts.dedupeKey) === hash) {
                    shouldLog = false;
                }
                LOG.lastPollHash.set(opts.dedupeKey, hash);
            }
            if (shouldLog) {
                appendLog({
                    method, path,
                    status: res.status,
                    body: data, text,
                    time: nowTime(),
                    silent: !!opts.silent,
                });
            }

            if (!res.ok) {
                const err = new Error(`${res.status} ${res.statusText}`);
                err.status = res.status;
                err.body = data;
                throw err;
            }
            return data;
        } catch (e) {
            if (!res) {
                // Network error always logged loudly
                appendLog({
                    method, path,
                    status: 0,
                    body: null, text: e.message,
                    time: nowTime(),
                    silent: false,
                });
            }
            throw e;
        }
    }

    function parseUrlsTextarea(value) {
        const lines = (value || "")
            .split(/\r?\n/)
            .map((l) => l.trim())
            .filter(Boolean);
        return lines.length ? lines : null;
    }

    function statusBadge(status) {
        return `<span class="badge badge-${status}">${status}</span>`;
    }

    // ---------------------------------------------------------------- sync + eval forms

    const SYNC_FORMS = [
        {
            id: "sync-core",
            path: "/sync/core",
            label: "Core sync",
            description: "Scrape → write CSV → sync to core tables (peptides, benefits, protocols, ...).",
        },
        {
            id: "sync-graph",
            path: "/sync/graph",
            label: "Graph sync",
            description: "Scrape → sync pharmacokinetics rows into peptide_graph (replaces existing).",
        },
        {
            id: "sync-graph-missing",
            path: "/sync/graph-missing",
            label: "Graph sync (missing only)",
            description: "Idempotent — only inserts admin-method/time-range combos that don't exist yet.",
        },
    ];

    const EVAL_FORMS = [
        {
            id: "eval-core",
            path: "/evaluation/core",
            label: "Core evaluation",
            description: "13-check comparison between CSV and DB.",
            withUrls: false,
            withOutput: true,
        },
        {
            id: "eval-graph",
            path: "/evaluation/graph",
            label: "Graph evaluation",
            description: "5-check pharmacokinetics comparison.",
            withUrls: false,
            withOutput: true,
        },
    ];

    function buildSyncForm(cfg) {
        const wrap = document.createElement("div");
        wrap.style.gridColumn = "span 1";
        wrap.innerHTML = `
            <div class="kv" style="background: transparent; border: 1px solid var(--border-color);">
                <div class="kv-row"><strong>${escapeHtml(cfg.label)}</strong> <span class="panel-card-subtle">${escapeHtml(cfg.path)}</span></div>
                <div class="kv-row panel-card-subtle">${escapeHtml(cfg.description)}</div>
                <div class="field">
                    <label for="${cfg.id}-limit">Limit (number of URLs)</label>
                    <input id="${cfg.id}-limit" type="number" min="1" placeholder="unlimited">
                </div>
                <div class="field">
                    <label for="${cfg.id}-urls">URLs (one per line, blank for auto-discover)</label>
                    <textarea id="${cfg.id}-urls" placeholder="https://pep-pedia.org/peptide/..."></textarea>
                </div>
                <div class="form-actions">
                    <button class="btn" data-action="${cfg.id}" type="button">Run</button>
                    <span class="panel-card-subtle" data-jobline="${cfg.id}"></span>
                </div>
            </div>
        `;
        wrap.querySelector(`[data-action="${cfg.id}"]`).addEventListener("click", () => {
            const limitRaw = $(cfg.id + "-limit").value.trim();
            const limit = limitRaw === "" ? null : parseInt(limitRaw, 10);
            const urls = parseUrlsTextarea($(cfg.id + "-urls").value);
            runSyncOrEval(cfg.path, { limit, urls }, wrap.querySelector(`[data-jobline="${cfg.id}"]`), "sync-result");
        });
        return wrap;
    }

    function buildEvalForm(cfg) {
        const wrap = document.createElement("div");
        wrap.style.gridColumn = "span 1";
        wrap.innerHTML = `
            <div class="kv" style="background: transparent; border: 1px solid var(--border-color);">
                <div class="kv-row"><strong>${escapeHtml(cfg.label)}</strong> <span class="panel-card-subtle">${escapeHtml(cfg.path)}</span></div>
                <div class="kv-row panel-card-subtle">${escapeHtml(cfg.description)}</div>
                <div class="field">
                    <label for="${cfg.id}-limit">Limit (peptides to evaluate)</label>
                    <input id="${cfg.id}-limit" type="number" min="1" placeholder="all">
                </div>
                <div class="field">
                    <label for="${cfg.id}-output">Output JSON (optional server path)</label>
                    <input id="${cfg.id}-output" type="text" placeholder="/tmp/${cfg.id}_report.json">
                </div>
                <div class="form-actions">
                    <button class="btn" data-action="${cfg.id}" type="button">Run</button>
                    <span class="panel-card-subtle" data-jobline="${cfg.id}"></span>
                </div>
            </div>
        `;
        wrap.querySelector(`[data-action="${cfg.id}"]`).addEventListener("click", () => {
            const limitRaw = $(cfg.id + "-limit").value.trim();
            const limit = limitRaw === "" ? null : parseInt(limitRaw, 10);
            const out = $(cfg.id + "-output").value.trim();
            const body = { limit, output_json: out || null };
            runSyncOrEval(cfg.path, body, wrap.querySelector(`[data-jobline="${cfg.id}"]`), "eval-result");
        });
        return wrap;
    }

    async function runSyncOrEval(path, body, jobLine, resultPaneId) {
        jobLine.textContent = "Submitting…";
        note("action", `User triggered POST ${path}`, body);
        let job;
        try {
            job = await api("POST", path, body);
        } catch (e) {
            jobLine.innerHTML = `<span class="diff-badge diff-csv">Failed: ${escapeHtml(e.message)}</span>`;
            note("error", `POST ${path} failed: ${e.message}`, e.body || null);
            return;
        }
        const jobId = job && job.job_id;
        if (!jobId) {
            jobLine.innerHTML = `<span class="diff-badge diff-csv">No job_id returned.</span>`;
            note("error", `POST ${path} returned no job_id`, job);
            return;
        }
        note("job", `Job ${jobId} accepted — status: ${job.status || "pending"}`);
        jobLine.innerHTML = `Job <code>${escapeHtml(jobId)}</code> ${statusBadge(job.status || "pending")}`;
        renderJobResult(resultPaneId, jobId, job);
        loadJobs();
        pollJob(jobId, (latest) => {
            jobLine.innerHTML = `Job <code>${escapeHtml(jobId)}</code> ${statusBadge(latest.status)} <span class="panel-card-subtle">progress ${latest.progress || 0}%</span>`;
            renderJobResult(resultPaneId, jobId, latest);
            loadJobs();
        });
    }

    function renderJobResult(paneId, jobId, job) {
        const el = $(paneId);
        const pretty = JSON.stringify(job, null, 2);
        el.innerHTML = `
            <div class="panel-card-subtle" style="margin-bottom: 6px;">Latest result for <code>${escapeHtml(jobId)}</code></div>
            <pre class="json-block">${escapeHtml(pretty)}</pre>
        `;
    }

    // ---------------------------------------------------------------- job polling

    const TERMINAL = new Set(["completed", "failed", "cancelled"]);
    const activePolls = new Map();

    function pollJob(jobId, onUpdate) {
        if (activePolls.has(jobId)) return;
        const interval = setInterval(async () => {
            let job;
            try {
                job = await api(
                    "GET",
                    `/operations/job/${encodeURIComponent(jobId)}`,
                    undefined,
                    { silent: true, dedupeKey: `job:${jobId}` }
                );
            } catch (e) {
                clearInterval(interval);
                activePolls.delete(jobId);
                note("error", `Polling job ${jobId} failed: ${e.message}`);
                return;
            }
            // Log a loud note whenever the job's status actually transitions
            const prev = LOG.lastJobStatus.get(jobId);
            if (job && job.status && job.status !== prev) {
                LOG.lastJobStatus.set(jobId, job.status);
                if (prev !== undefined) {
                    note("job", `Job ${jobId}: ${prev} → ${job.status}`, {
                        progress: job.progress,
                        result: job.result,
                        error: job.error,
                    });
                }
            }
            onUpdate(job);
            if (TERMINAL.has(job.status)) {
                clearInterval(interval);
                activePolls.delete(jobId);
            }
        }, 2000);
        activePolls.set(jobId, interval);
    }

    // ---------------------------------------------------------------- operations panel

    let currentJobFilter = "";
    let autoJobsTimer = null;

    function setJobFilter(status) {
        currentJobFilter = status;
        document.querySelectorAll("#job-filters .filter-pill").forEach((btn) => {
            btn.classList.toggle("active", (btn.dataset.status || "") === status);
        });
        note("action", `Filter jobs by: ${status || "all"}`);
        loadJobs({ isAuto: false });
    }

    async function loadJobs(opts) {
        opts = opts || {};
        const path = currentJobFilter
            ? `/operations/jobs?status=${encodeURIComponent(currentJobFilter)}`
            : "/operations/jobs";
        // Auto-refresh is silent + deduped; manual refresh stays loud.
        const apiOpts = opts.isAuto
            ? { silent: true, dedupeKey: `jobs:${currentJobFilter || "all"}` }
            : {};
        let res;
        try {
            res = await api("GET", path, undefined, apiOpts);
        } catch (e) {
            $("jobs-tbody").innerHTML = `<tr><td colspan="6" class="empty-state">Failed to load jobs: ${escapeHtml(e.message)}</td></tr>`;
            return;
        }
        const jobs = (res && res.jobs) || [];
        const tbody = $("jobs-tbody");
        if (!jobs.length) {
            tbody.innerHTML = `<tr><td colspan="6" class="empty-state">No jobs match this filter.</td></tr>`;
        } else {
            tbody.innerHTML = jobs.map((j) => {
                const terminal = TERMINAL.has(j.status);
                return `<tr>
                    <td>${statusBadge(j.status)}</td>
                    <td><code>${escapeHtml(j.endpoint || "")}</code></td>
                    <td class="mono">${escapeHtml(j.job_id || "")}</td>
                    <td class="mono">${escapeHtml(fmtTimestamp(j.created_at))}</td>
                    <td class="mono">${j.progress != null ? j.progress + "%" : "—"}</td>
                    <td>
                        <button class="btn btn-ghost" data-open-job="${escapeHtml(j.job_id)}" type="button">Open</button>
                        <button class="btn btn-danger" data-cancel-job="${escapeHtml(j.job_id)}" type="button" ${terminal ? "disabled" : ""}>Cancel</button>
                    </td>
                </tr>`;
            }).join("");
        }

        // Health ribbon — also silent + deduped on auto-refresh
        try {
            const h = await api("GET", "/operations/health", undefined,
                opts.isAuto ? { silent: true, dedupeKey: "health" } : {});
            const s = h.stats || {};
            $("health-ribbon").innerHTML = `
                <span><strong>Status:</strong>${escapeHtml(h.status || "?")}</span>
                <span><strong>Total:</strong>${h.total_jobs || 0}</span>
                <span><strong>Pending:</strong>${s.pending || 0}</span>
                <span><strong>Running:</strong>${s.running || 0}</span>
                <span><strong>Completed:</strong>${s.completed || 0}</span>
                <span><strong>Failed:</strong>${s.failed || 0}</span>
                <span><strong>Cancelled:</strong>${s.cancelled || 0}</span>
            `;
        } catch (_e) { /* tolerated */ }

        if (autoJobsTimer) clearTimeout(autoJobsTimer);
        const hasActive = jobs.some((j) => !TERMINAL.has(j.status));
        if (hasActive) {
            autoJobsTimer = setTimeout(() => loadJobs({ isAuto: true }), 3000);
        }
    }

    async function openJobDetail(jobId) {
        note("action", `Open job detail: ${jobId}`);
        try {
            const job = await api("GET", `/operations/job/${encodeURIComponent(jobId)}`);
            $("job-detail").textContent = JSON.stringify(job, null, 2);
        } catch (e) {
            $("job-detail").textContent = "Error: " + e.message;
        }
    }

    async function cancelJobAndRefresh(jobId) {
        if (!confirm(`Cancel job ${jobId}?`)) return;
        note("action", `Cancel job: ${jobId}`);
        try {
            await api("DELETE", `/operations/job/${encodeURIComponent(jobId)}`);
        } catch (e) {
            alert("Failed to cancel: " + e.message);
            note("error", `Cancel failed for ${jobId}: ${e.message}`);
        }
        loadJobs({ isAuto: false });
    }

    // ---------------------------------------------------------------- scheduler panel

    async function loadSchedulerStatus(opts) {
        opts = opts || {};
        const apiOpts = opts.isAuto
            ? { silent: true, dedupeKey: "scheduler-status" }
            : {};
        try {
            const s = await api("GET", "/scheduler/status", undefined, apiOpts);
            const state = s.status || "unknown"; // "running" | "paused" | "not_configured"
            const cls = state === "running" ? "diff-ok"
                      : state === "paused"  ? "diff-csv"
                      : "diff-empty";
            const nextRun = s.next_run_time || s.next_run || "—";
            $("scheduler-status").innerHTML = `
                <span><strong>State:</strong><span class="diff-badge ${cls}">${escapeHtml(state)}</span></span>
                <span><strong>Interval:</strong>${escapeHtml(s.interval_hours != null ? s.interval_hours + "h" : "?")}${s.interval_minutes ? " " + s.interval_minutes + "m" : ""}</span>
                <span><strong>Next run:</strong>${escapeHtml(nextRun)}</span>
                <span><strong>Limit:</strong>${escapeHtml(s.limit != null ? s.limit : "unlimited")}</span>
            `;
            if (s.interval_hours != null) $("sched-hours").value = s.interval_hours;
            if (s.interval_minutes != null) $("sched-minutes").value = s.interval_minutes;
            if (s.limit != null) $("sched-limit").value = s.limit;
        } catch (e) {
            $("scheduler-status").innerHTML = `<span class="diff-badge diff-csv">Failed: ${escapeHtml(e.message)}</span>`;
        }
    }

    async function schedAction(path, body) {
        note("action", `Scheduler: POST ${path}`, body || null);
        try {
            await api("POST", path, body);
        } catch (e) {
            alert("Scheduler action failed: " + e.message);
            note("error", `Scheduler ${path} failed: ${e.message}`);
        }
        loadSchedulerStatus({ isAuto: false });
    }

    // ---------------------------------------------------------------- init

    function init() {
        // Build forms
        const syncWrap = $("sync-forms");
        SYNC_FORMS.forEach((cfg) => syncWrap.appendChild(buildSyncForm(cfg)));
        const evalWrap = $("eval-forms");
        EVAL_FORMS.forEach((cfg) => evalWrap.appendChild(buildEvalForm(cfg)));

        // Filter pills
        document.querySelectorAll("#job-filters .filter-pill").forEach((btn) => {
            btn.addEventListener("click", () => setJobFilter(btn.dataset.status || ""));
        });
        $("refresh-jobs-btn").addEventListener("click", () => {
            note("action", "Manual refresh: jobs");
            loadJobs({ isAuto: false });
        });

        // Jobs table event delegation
        $("jobs-tbody").addEventListener("click", (e) => {
            const open = e.target.closest("[data-open-job]");
            if (open) {
                openJobDetail(open.getAttribute("data-open-job"));
                return;
            }
            const cancel = e.target.closest("[data-cancel-job]");
            if (cancel) {
                cancelJobAndRefresh(cancel.getAttribute("data-cancel-job"));
            }
        });

        // Scheduler
        $("sched-start").addEventListener("click", () => {
            const limitRaw = $("sched-limit").value.trim();
            schedAction("/scheduler/start", {
                interval_hours:   parseFloat($("sched-hours").value) || 0,
                interval_minutes: parseFloat($("sched-minutes").value) || 0,
                limit: limitRaw === "" ? null : parseInt(limitRaw, 10),
            });
        });
        $("sched-pause").addEventListener("click", () => schedAction("/scheduler/pause"));
        $("sched-resume").addEventListener("click", () => schedAction("/scheduler/resume"));
        $("sched-refresh").addEventListener("click", () => {
            note("action", "Manual refresh: scheduler status");
            loadSchedulerStatus({ isAuto: false });
        });

        // Log clear
        $("log-clear").addEventListener("click", () => {
            $("log-stream").innerHTML = `<div class="empty-state">No requests yet.</div>`;
            LOG.lastPollHash.clear();
            LOG.lastJobStatus.clear();
        });

        // "Show polls" toggle — when off (default) routine background polls are hidden
        const togglePolls = $("log-show-polls");
        if (togglePolls) {
            togglePolls.checked = LOG.showPolls;
            document.body.classList.toggle("show-polls", LOG.showPolls);
            togglePolls.addEventListener("change", () => {
                LOG.showPolls = togglePolls.checked;
                document.body.classList.toggle("show-polls", LOG.showPolls);
            });
        }

        note("info", "Dashboard ready. Routine polls are hidden — toggle “Show polls” to see them.");
        loadJobs({ isAuto: true });
        loadSchedulerStatus({ isAuto: true });
    }

    document.addEventListener("DOMContentLoaded", init);
})();
