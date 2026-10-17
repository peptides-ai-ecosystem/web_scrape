/**
 * Core Data Inspector
 *
 * Two side-by-side columns:
 *   Left  = CSV (scraped)  — calls /api/v1/csv/peptide?name=...&method=...
 *   Right = DB  (injected) — calls /api/v1/core/peptide/by-slug/{slug}
 *
 * Picker is the union of CSV peptides + DB peptides so the operator can
 * inspect a peptide that exists on only one side.
 *
 * URL deep-linking:
 *   /visualization/core.html?name=BPC-157&method=Injectable
 */
(function () {
    "use strict";

    const API = "/api/v1";

    const $ = (id) => document.getElementById(id);

    const els = {
        search:    $("search-input"),
        peptide:   $("peptide-select"),
        method:    $("method-select"),
        reload:    $("reload-btn"),
        status:    $("picker-status"),
        title:     $("inspector-title"),
        links:     $("inspector-links"),
        csvPane:   $("csv-pane"),
        dbPane:    $("db-pane"),
    };

    /** Union list of peptides, keyed by slug. */
    let peptides = [];
    let csvByKey = new Map(); // key = slug -> [{name, method, url, full_name}]
    let dbBySlug = new Map(); // slug -> {id, name, slug, category_id}

    // ---------------------------------------------------------------- fetch

    function slugify(s) {
        return (s || "").toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "");
    }

    async function jget(path) {
        const r = await fetch(API + path);
        if (!r.ok) {
            const t = await r.text();
            throw new Error(`${r.status} ${r.statusText}: ${t.slice(0, 240)}`);
        }
        return r.json();
    }

    async function loadPeptideLists() {
        els.status.textContent = "Loading peptides from CSV + DB…";
        let csvRows = [];
        let dbRows = [];
        const errors = [];

        try {
            csvRows = await jget("/csv/peptides");
        } catch (e) {
            errors.push(`CSV: ${e.message}`);
        }
        try {
            dbRows = await jget("/core/peptides");
        } catch (e) {
            errors.push(`DB: ${e.message}`);
        }

        csvByKey = new Map();
        for (const r of csvRows) {
            const key = r.slug || slugify(r.name);
            if (!csvByKey.has(key)) csvByKey.set(key, []);
            csvByKey.get(key).push(r);
        }

        dbBySlug = new Map();
        for (const r of dbRows) {
            const key = r.slug || slugify(r.name);
            dbBySlug.set(key, r);
        }

        const unionKeys = new Set([...csvByKey.keys(), ...dbBySlug.keys()]);
        peptides = [...unionKeys].map((slug) => {
            const csv = (csvByKey.get(slug) || [])[0];
            const db  = dbBySlug.get(slug);
            const name = (db && db.name) || (csv && csv.name) || slug;
            return {
                slug,
                name,
                in_csv: !!csv,
                in_db:  !!db,
                csv_methods: (csvByKey.get(slug) || []).map((c) => c.method).filter(Boolean),
            };
        }).sort((a, b) => a.name.localeCompare(b.name));

        renderPicker();

        const csvCount = csvByKey.size;
        const dbCount = dbBySlug.size;
        const both = peptides.filter((p) => p.in_csv && p.in_db).length;
        els.status.innerHTML = errors.length
            ? `<span class="diff-badge diff-csv">${errors.join(" — ")}</span>`
            : `<strong>${peptides.length}</strong> peptides total · `
              + `<span class="diff-badge diff-csv">CSV: ${csvCount}</span> `
              + `<span class="diff-badge diff-db">DB: ${dbCount}</span> `
              + `<span class="diff-badge diff-ok">Both: ${both}</span>`;
    }

    function renderPicker() {
        const needle = (els.search.value || "").toLowerCase().trim();
        const filtered = needle
            ? peptides.filter((p) => p.name.toLowerCase().includes(needle) || p.slug.includes(needle))
            : peptides;
        const current = els.peptide.value;
        els.peptide.innerHTML = '<option value="">— Select a peptide —</option>'
            + filtered.map((p) => {
                const tag = p.in_csv && p.in_db ? "•" : p.in_csv ? "CSV" : "DB";
                return `<option value="${p.slug}">${escapeHtml(p.name)} (${tag})</option>`;
            }).join("");
        if (current && filtered.some((p) => p.slug === current)) {
            els.peptide.value = current;
        }
    }

    function refreshMethodSelect() {
        const slug = els.peptide.value;
        if (!slug) {
            els.method.innerHTML = '<option value="">— Any —</option>';
            return;
        }
        const methods = (csvByKey.get(slug) || []).map((r) => r.method).filter(Boolean);
        const unique = [...new Set(methods)];
        els.method.innerHTML = '<option value="">— Any —</option>'
            + unique.map((m) => `<option value="${escapeHtml(m)}">${escapeHtml(m)}</option>`).join("");
    }

    // ---------------------------------------------------------------- load + render

    async function loadAndRender() {
        const slug = els.peptide.value;
        if (!slug) {
            els.title.textContent = "Pick a peptide to begin";
            els.links.textContent = "";
            els.csvPane.innerHTML = '<div class="empty-state">No peptide selected.</div>';
            els.dbPane.innerHTML  = '<div class="empty-state">No peptide selected.</div>';
            return;
        }

        const meta = peptides.find((p) => p.slug === slug) || { name: slug };
        const csvMethod = els.method.value;

        els.title.innerHTML = escapeHtml(meta.name)
            + ` <span class="panel-card-subtle">(${escapeHtml(slug)})</span>`;

        const csvUrl = `${API}/csv/peptide?name=${encodeURIComponent(meta.name)}`
                    + (csvMethod ? `&method=${encodeURIComponent(csvMethod)}` : "");
        const dbUrl  = `${API}/core/peptide/by-slug/${encodeURIComponent(slug)}`;

        els.links.innerHTML = `
            <a href="${csvUrl}" target="_blank" rel="noopener" class="app-nav-link app-nav-link--secondary">CSV JSON ↗</a>
            <a href="${dbUrl}"  target="_blank" rel="noopener" class="app-nav-link app-nav-link--secondary">DB JSON ↗</a>
        `;

        els.csvPane.innerHTML = '<div class="empty-state">Loading CSV…</div>';
        els.dbPane.innerHTML  = '<div class="empty-state">Loading DB…</div>';

        const [csv, db] = await Promise.all([
            jget(csvUrl.slice(API.length)).catch((e) => ({ __error: e.message })),
            jget(dbUrl.slice(API.length)).catch((e) => ({ __error: e.message })),
        ]);

        renderCsvPane(csv);
        renderDbPane(db);

        const url = new URL(window.location.href);
        url.searchParams.set("name", meta.name);
        if (csvMethod) url.searchParams.set("method", csvMethod);
        else url.searchParams.delete("method");
        history.replaceState(null, "", url.toString());
    }

    // ---------------------------------------------------------------- renderers

    /** Decide a diff badge given CSV vs DB counts. */
    function diffBadge(csvCount, dbCount) {
        if (csvCount > 0 && dbCount > 0) return `<span class="diff-badge diff-ok">CSV ${csvCount} · DB ${dbCount}</span>`;
        if (csvCount > 0) return `<span class="diff-badge diff-csv">CSV ${csvCount} · DB 0</span>`;
        if (dbCount > 0)  return `<span class="diff-badge diff-db">CSV 0 · DB ${dbCount}</span>`;
        return `<span class="diff-badge diff-empty">empty</span>`;
    }

    // Mapping between CSV groups and DB groups for the diff badges.
    // Some DB entities don't have a 1:1 CSV mapping; in those cases we only
    // surface a DB count and skip the CSV side.
    const SECTION_LAYOUT = [
        { key: "identity",          dbKey: "peptide",       label: "Identity" },
        { key: "quick_guide",       dbKey: null,            label: "Quick guide" },
        { key: "overview",          dbKey: null,            label: "Overview" },
        { key: "indications",       dbKey: "indications",   label: "Research indications" },
        { key: "protocols",         dbKey: "protocols",     label: "Protocols" },
        { key: "interactions",      dbKey: "interactions",  label: "Interactions" },
        { key: "side_effects",      dbKey: "side_effects",  label: "Side effects" },
        { key: null,                dbKey: "benefits",      label: "Benefits" },
        { key: "quality_indicators",dbKey: null,            label: "Quality indicators" },
        { key: "references_studies",dbKey: "references",    label: "Research studies / citations", dbFilter: (r) => true },
        { key: "graph",             dbKey: "graph",         label: "Pharmacokinetics graph" },
    ];

    function renderCsvPane(csv) {
        if (csv && csv.__error) {
            els.csvPane.innerHTML = `<div class="empty-state">CSV: ${escapeHtml(csv.__error)}</div>`;
            return;
        }
        if (!csv || !csv.groups) {
            els.csvPane.innerHTML = '<div class="empty-state">No CSV row for this peptide.</div>';
            return;
        }

        const groups = csv.groups || {};
        const html = [];
        html.push(`<div class="kv">
            <div class="kv-row"><strong>Name</strong> ${escapeHtml(csv.name || "")}</div>
            <div class="kv-row"><strong>Full name</strong> ${escapeHtml(csv.full_name || "—")}</div>
            <div class="kv-row"><strong>Method</strong> ${escapeHtml(csv.method || "—")}</div>
            <div class="kv-row"><strong>URL</strong> ${csv.url ? `<a href="${csv.url}" target="_blank" rel="noopener">${escapeHtml(csv.url)}</a>` : "—"}</div>
        </div>`);

        for (const section of SECTION_LAYOUT) {
            if (!section.key) continue;
            html.push(renderCsvSection(section.label, groups[section.key]));
        }
        if (groups.references_citations) {
            html.push(renderCsvSection("Citations", groups.references_citations));
        }
        if (groups.other) {
            html.push(renderCsvSection("Other", groups.other));
        }
        els.csvPane.innerHTML = html.join("");
    }

    function renderCsvSection(title, group) {
        const entries = group ? Object.entries(group) : [];
        const count = entries.length;
        const badge = count
            ? `<span class="diff-badge diff-csv">${count}</span>`
            : `<span class="diff-badge diff-empty">empty</span>`;
        if (!count) {
            return `<details class="inspector-section">
                <summary>${escapeHtml(title)} ${badge}</summary>
                <div class="inspector-section-body"><div class="inspector-empty">No CSV cells in this group.</div></div>
            </details>`;
        }
        const rows = entries.map(([key, value]) => {
            const val = typeof value === "object" ? jsonPretty(value) : escapeHtml(String(value));
            return `<div class="inspector-entry">
                <span class="inspector-key">${escapeHtml(key)}</span>
                <span class="inspector-value">${val}</span>
            </div>`;
        }).join("");
        return `<details class="inspector-section">
            <summary>${escapeHtml(title)} ${badge}</summary>
            <div class="inspector-section-body">${rows}</div>
        </details>`;
    }

    function renderDbPane(db) {
        if (db && db.__error) {
            const msg = db.__error.includes("404") ? "Peptide not in database yet." : db.__error;
            els.dbPane.innerHTML = `<div class="empty-state">${escapeHtml(msg)}</div>`;
            return;
        }
        if (!db || !db.peptide) {
            els.dbPane.innerHTML = '<div class="empty-state">No DB record for this peptide.</div>';
            return;
        }

        const p = db.peptide;
        const html = [];
        html.push(`<div class="kv">
            <div class="kv-row"><strong>ID</strong> ${p.id}</div>
            <div class="kv-row"><strong>Name</strong> ${escapeHtml(p.name || "")}</div>
            <div class="kv-row"><strong>Slug</strong> ${escapeHtml(p.slug || "")}</div>
            <div class="kv-row"><strong>Category ID</strong> ${p.category_id == null ? "—" : p.category_id}</div>
            ${p.sequence ? `<div class="kv-row"><strong>Sequence</strong> ${escapeHtml(p.sequence)}</div>` : ""}
            ${p.half_life_value != null ? `<div class="kv-row"><strong>Half-life</strong> ${escapeHtml(p.half_life_value)} ${escapeHtml(p.half_life_unit || "")}</div>` : ""}
        </div>`);

        html.push(renderDbList("Benefits", db.benefits, (b) => `
            <div class="kv">
                <div class="kv-row"><strong>${escapeHtml(b.name)}</strong> <span class="diff-badge diff-empty">${escapeHtml(b.category || "—")}</span></div>
                ${b.description ? `<div class="kv-row">${escapeHtml(b.description)}</div>` : ""}
                ${b.evidence_level ? `<div class="kv-row">Evidence: ${escapeHtml(b.evidence_level)}</div>` : ""}
            </div>
        `));

        html.push(renderDbList("Side effects", db.side_effects, (se) => `
            <div class="kv">
                <div class="kv-row"><strong>${escapeHtml(se.name)}</strong> <span class="diff-badge diff-empty">${escapeHtml(se.severity_level || "—")}</span></div>
                ${se.frequency ? `<div class="kv-row">Frequency: ${escapeHtml(se.frequency)}</div>` : ""}
                ${se.description ? `<div class="kv-row">${escapeHtml(se.description)}</div>` : ""}
            </div>
        `));

        html.push(renderDbList("Interactions", db.interactions, (i) => `
            <div class="kv">
                <div class="kv-row"><strong>${escapeHtml(i.other_peptide_name || "—")}</strong> <span class="diff-badge diff-empty">${escapeHtml(i.interaction_type || "—")}</span></div>
                ${i.severity ? `<div class="kv-row">Severity: ${escapeHtml(i.severity)}</div>` : ""}
                ${i.description ? `<div class="kv-row">${escapeHtml(i.description)}</div>` : ""}
                ${i.recommendation ? `<div class="kv-row">Recommendation: ${escapeHtml(i.recommendation)}</div>` : ""}
            </div>
        `));

        html.push(renderDbList("Research indications", db.indications, (ind) => `
            <div class="kv">
                <div class="kv-row"><strong>${escapeHtml(ind.indication_title)}</strong> <span class="diff-badge diff-empty">${escapeHtml(ind.effectiveness_tag || "—")}</span></div>
                ${ind.description ? `<div class="kv-row">${escapeHtml(ind.description)}</div>` : ""}
                ${ind.studies && ind.studies.length ? `<div class="kv-row"><em>${ind.studies.length} study link(s)</em></div>` : ""}
            </div>
        `));

        html.push(renderDbList("Protocols", db.protocols, renderProtocol));

        html.push(renderDbList("References", db.references, (r) => {
            const isStudy = r.reference_type === "study";
            const title = isStudy ? (r.study_title || "—") : (r.citation_title || "—");
            const meta = isStudy
                ? `${r.study_authors || ""} ${r.study_journal ? "· " + r.study_journal : ""} ${r.study_year ? "(" + r.study_year + ")" : ""}`
                : `${r.citation_authors || ""} ${r.citation_journal ? "· " + r.citation_journal : ""} ${r.citation_year ? "(" + r.citation_year + ")" : ""}`;
            const url = isStudy ? r.study_url : r.citation_url;
            return `<div class="kv">
                <div class="kv-row"><strong>${escapeHtml(title)}</strong> <span class="diff-badge diff-empty">${r.reference_type}</span></div>
                ${meta.trim() ? `<div class="kv-row">${escapeHtml(meta)}</div>` : ""}
                ${url ? `<div class="kv-row"><a href="${escapeHtml(url)}" target="_blank" rel="noopener">${escapeHtml(url)}</a></div>` : ""}
                ${r.context ? `<div class="kv-row">${escapeHtml(r.context)}</div>` : ""}
            </div>`;
        }));

        html.push(renderDbList("Pharmacokinetics graph rows", db.graph, (g) => `
            <div class="kv">
                <div class="kv-row"><strong>${escapeHtml(g.administration_method || "—")}</strong> <span class="diff-badge diff-empty">${escapeHtml(g.time_range || "—")}</span></div>
                ${g.peak_concentration ? `<div class="kv-row">Peak: ${escapeHtml(g.peak_concentration)}</div>` : ""}
                ${g.half_life ? `<div class="kv-row">Half-life: ${escapeHtml(g.half_life)}</div>` : ""}
                ${g.cleared_percentage ? `<div class="kv-row">Cleared: ${escapeHtml(g.cleared_percentage)}</div>` : ""}
                <div class="kv-row">Path: ${g.has_path_data ? "✓" : "—"} · Points: ${g.point_count} · Markers: ${g.marker_count}</div>
            </div>
        `));

        els.dbPane.innerHTML = html.join("");
    }

    function renderProtocol(proto) {
        const dosages = (proto.dosages || []).map((d) => `
            <div class="kv-row">
                <strong>${escapeHtml(d.dosage_name || d.dosage_amount || "—")}</strong>
                ${d.dosage_unit ? escapeHtml(d.dosage_unit) : ""}
                ${d.schedule_name ? `· schedule: ${escapeHtml(d.schedule_name)}` : ""}
                ${d.schedule_frequency ? `· ${escapeHtml(d.schedule_frequency)}` : ""}
                ${d.is_default ? '<span class="diff-badge diff-ok">default</span>' : ""}
            </div>
        `).join("");
        const places = (proto.application_places || []).map((p) => `
            <div class="kv-row">${escapeHtml(p.name)}${p.anatomical_region ? " · " + escapeHtml(p.anatomical_region) : ""}${p.absorption_rate ? " · " + escapeHtml(p.absorption_rate) : ""}</div>
        `).join("");
        const steps = (proto.reconstitution_steps || []).map((s) => `
            <div class="kv-row"><strong>Step ${s.step_number}</strong> ${escapeHtml(s.description || "")}</div>
        `).join("");
        const qi = (proto.quality_indicators || []).map((q) => `
            <div class="kv-row"><strong>${escapeHtml(q.indicator_title || "")}</strong> ${escapeHtml(q.indicator_description || "")}</div>
        `).join("");
        return `
            <div class="kv">
                <div class="kv-row"><strong>${escapeHtml(proto.administration_method || proto.name || "Protocol")}</strong> <span class="diff-badge diff-empty">id ${proto.id}</span></div>
                ${proto.name ? `<div class="kv-row">Name: ${escapeHtml(proto.name)}</div>` : ""}
                ${proto.description ? `<div class="kv-row">${escapeHtml(proto.description)}</div>` : ""}
                ${proto.best_timing ? `<div class="kv-row">Timing: ${escapeHtml(proto.best_timing)}</div>` : ""}
                ${dosages ? `<div class="kv-row"><em>Dosages (${proto.dosages.length})</em></div>${dosages}` : ""}
                ${places  ? `<div class="kv-row"><em>Application places (${proto.application_places.length})</em></div>${places}` : ""}
                ${steps   ? `<div class="kv-row"><em>Reconstitution steps (${proto.reconstitution_steps.length})</em></div>${steps}` : ""}
                ${qi      ? `<div class="kv-row"><em>Quality indicators (${proto.quality_indicators.length})</em></div>${qi}` : ""}
            </div>
        `;
    }

    function renderDbList(title, list, renderItem) {
        const count = (list && list.length) || 0;
        const badge = count
            ? `<span class="diff-badge diff-db">${count}</span>`
            : `<span class="diff-badge diff-empty">empty</span>`;
        if (!count) {
            return `<details class="inspector-section">
                <summary>${escapeHtml(title)} ${badge}</summary>
                <div class="inspector-section-body"><div class="inspector-empty">No DB rows.</div></div>
            </details>`;
        }
        const body = list.map(renderItem).join("");
        return `<details class="inspector-section">
            <summary>${escapeHtml(title)} ${badge}</summary>
            <div class="inspector-section-body">${body}</div>
        </details>`;
    }

    // ---------------------------------------------------------------- utilities

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    }

    function jsonPretty(value) {
        try {
            return `<pre class="json-block tight">${escapeHtml(JSON.stringify(value, null, 2))}</pre>`;
        } catch (_e) {
            return escapeHtml(String(value));
        }
    }

    // ---------------------------------------------------------------- init

    function debounce(fn, ms) {
        let t = null;
        return function () {
            const args = arguments;
            clearTimeout(t);
            t = setTimeout(() => fn.apply(null, args), ms);
        };
    }

    els.search.addEventListener("input", debounce(renderPicker, 80));
    els.peptide.addEventListener("change", () => {
        refreshMethodSelect();
        loadAndRender().catch((e) => {
            els.dbPane.innerHTML = `<div class="empty-state">${escapeHtml(e.message)}</div>`;
        });
    });
    els.method.addEventListener("change", () => loadAndRender());
    els.reload.addEventListener("click", () => loadPeptideLists().catch((e) => {
        els.status.textContent = "Failed to reload: " + e.message;
    }));

    function applyDeepLink() {
        const params = new URLSearchParams(window.location.search);
        const name = params.get("name");
        const method = params.get("method");
        if (!name) return;
        const slug = slugify(name);
        const opt = [...els.peptide.options].find((o) => o.value === slug);
        if (opt) {
            els.peptide.value = slug;
            refreshMethodSelect();
            if (method) {
                const mopt = [...els.method.options].find((o) => o.value === method);
                if (mopt) els.method.value = method;
            }
            loadAndRender();
        }
    }

    loadPeptideLists()
        .then(applyDeepLink)
        .catch((e) => {
            els.status.textContent = "Failed to load picker: " + e.message;
        });
})();
