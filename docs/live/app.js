/* ============================================================
   AutoTarefas — Live System  (app.js)
   Consome ./assets/runs.json e monta o console de execucoes.
   Sem dependencias externas. Saida do terminal e 100% real.
   ============================================================ */

(() => {
  "use strict";

  const RM = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const $ = (id) => document.getElementById(id);

  /* ---------- refs ---------- */
  const shellEl = $("shell");
  const errorEl = $("error");
  const railEl = $("rail");
  const cardsEl = $("cards");
  const catHeadEl = $("catalog-head");
  const catSubEl = $("catalog-sub");

  const drawer = $("drawer");
  const backdrop = $("drawer-backdrop");
  const btnRun = $("btn-run");
  const btnRunLabel = $("btn-run-label");
  const btnSkip = $("btn-skip");
  const termBody = $("terminal-body");
  const termName = $("terminal-name");

  /* ---------- estado ---------- */
  let DATA = null;
  let activeCat = "all";
  let activeRun = null;
  let lastFocus = null;
  let runSeq = 0;
  let skipFlag = false;

  /* ---------- icones (inline) ---------- */
  const ICONS = {
    all: '<path d="M4 5h7v7H4zM13 5h7v4h-7zM13 12h7v7h-7zM4 15h7v4H4z"/>',
    validacao:
      '<path d="M12 3l7 3v5c0 4.2-2.9 7.3-7 8.5C7.9 18.3 5 15.2 5 11V6z"/><path d="M9 11.5l2 2 4-4.5"/>',
    arquivos:
      '<path d="M3 7h18M5 7l1-2.5h12L19 7M5 7v12h14V7"/><path d="M9.5 11.5h5"/>',
    integracao: '<path d="M4 8h13M14 5l3 3-3 3M20 16H7M10 13l-3 3 3 3"/>',
    notificacoes: '<path d="M4 12l16-7-5 16-3.5-6.5L4 12z"/>',
    scraping:
      '<circle cx="12" cy="12" r="8.5"/><path d="M3.5 12h17M12 3.5c2.4 2.3 3.6 5.3 3.6 8.5S14.4 18.2 12 20.5C9.6 18.2 8.4 15.2 8.4 12S9.6 5.8 12 3.5z"/>',
    rpa: '<path d="M5 4l11 5.5-4.6 1.7L9.7 16 5 4z"/><path d="M13 13l5 5"/>',
    auditoria:
      '<path d="M8 4h8v3H8zM6 6h12v14H6z"/><path d="M9.5 12l1.7 1.7L15 10"/>',
    file: '<path d="M13 3H7a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2V9z"/><path d="M13 3v6h6"/>',
  };
  const iconSvg = (key, size) =>
    '<svg viewBox="0 0 24 24" width="' +
    (size || 18) +
    '" height="' +
    (size || 18) +
    '" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">' +
    (ICONS[key] || ICONS.all) +
    "</svg>";

  /* ---------- status ---------- */
  const STATUS = {
    ok: { label: "Concluido", cls: "badge--ok" },
    caught_issue: { label: "Dados barrados", cls: "badge--caught" },
    requires_browser: { label: "Roda local", cls: "badge--local" },
    error: { label: "Falha", cls: "badge--error" },
  };
  const statusOf = (run) => STATUS[run.outcome] || STATUS.error;

  /* ---------- helpers ---------- */
  const esc = (s) =>
    String(s == null ? "" : s).replace(
      /[&<>"']/g,
      (c) =>
        ({
          "&": "&amp;",
          "<": "&lt;",
          ">": "&gt;",
          '"': "&quot;",
          "'": "&#39;",
        })[c],
    );

  const humanBytes = (n) => {
    if (n == null) return "—";
    const u = ["B", "KB", "MB", "GB"];
    let v = n;
    let i = 0;
    while (v >= 1024 && i < u.length - 1) {
      v /= 1024;
      i += 1;
    }
    return (i === 0 ? v : v.toFixed(1)) + " " + u[i];
  };

  const fmtDate = (iso) => {
    if (!iso) return "—";
    try {
      return new Date(iso).toLocaleString("pt-BR", {
        day: "2-digit",
        month: "2-digit",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      });
    } catch (_e) {
      return iso;
    }
  };

  const wait = (ms) => new Promise((r) => setTimeout(r, ms));

  /* ============================ INIT ============================ */
  init();

  async function init() {
    try {
      const res = await fetch("./assets/runs.json", { cache: "no-store" });
      if (!res.ok) throw new Error("HTTP " + res.status);
      DATA = await res.json();
    } catch (_e) {
      errorEl.hidden = false;
      return;
    }
    hydrate();
  }

  function hydrate() {
    (DATA.runs || []).forEach((r, i) => {
      r.__order = i + 1;
    });
    shellEl.hidden = false;
    renderTelemetry();
    renderSummary();
    renderNotes();
    renderRail();
    setCategory("all");
    wireDrawer();
  }

  /* ============================ TELEMETRIA ============================ */
  function renderTelemetry() {
    const env = DATA.environment || {};
    const tool = DATA.tool || {};
    $("tel-env").textContent = env.mode || "—";
    $("tel-version").textContent = "v" + (tool.version || "—");
    $("tel-python").textContent = "py " + (env.python || "—");
    const br = env.browser_available;
    const telBr = $("tel-browser");
    telBr.textContent = "navegador " + (br ? "on" : "local");
    telBr.style.color = br ? "var(--green)" : "var(--info)";
    $("tel-generated").textContent = fmtDate(DATA.generated_at);
  }

  function renderSummary() {
    const s = DATA.summary || {};
    const o = s.by_outcome || {};
    $("sum-total").textContent = s.total != null ? s.total : "—";
    $("sum-ok").textContent = o.ok || 0;
    $("sum-caught").textContent = o.caught_issue || 0;
    $("sum-local").textContent = o.requires_browser || 0;
  }

  function renderNotes() {
    const n = DATA.notes || {};
    $("note-hash").textContent = n.input_hash || "—";
    $("note-sanit").textContent = n.sanitization || "—";
    $("note-repro").textContent = n.reproducibility || "—";
  }

  /* ============================ RAIL ============================ */
  function renderRail() {
    const cats = DATA.categories || [];
    const total = (DATA.runs || []).length;
    let html = '<span class="rail__group-label">Categorias</span>';
    html += railItem("all", "Todos", total);
    cats.forEach((c) => {
      const count = (DATA.runs || []).filter(
        (r) => r.category === c.key,
      ).length;
      html += railItem(c.key, c.title, count);
    });
    railEl.innerHTML = html;
    railEl.querySelectorAll(".railitem").forEach((btn) => {
      btn.addEventListener("click", () => setCategory(btn.dataset.key));
    });
  }

  function railItem(key, label, count) {
    return (
      '<button class="railitem" data-key="' +
      esc(key) +
      '" type="button">' +
      '<span class="railitem__icon">' +
      iconSvg(key, 17) +
      "</span>" +
      "<span>" +
      esc(label) +
      "</span>" +
      '<span class="railitem__count">' +
      count +
      "</span>" +
      "</button>"
    );
  }

  function setCategory(key) {
    activeCat = key;
    railEl.querySelectorAll(".railitem").forEach((btn) => {
      btn.classList.toggle("is-active", btn.dataset.key === key);
    });
    const cat = (DATA.categories || []).find((c) => c.key === key);
    catHeadEl.textContent = cat ? cat.title : "Todas as automacoes";
    catSubEl.textContent = cat
      ? cat.summary
      : "Cada cartao roda uma automacao real do robo e mostra a saida capturada.";
    renderCards();
  }

  /* ============================ CARDS ============================ */
  function renderCards() {
    const list =
      activeCat === "all"
        ? DATA.runs || []
        : (DATA.runs || []).filter((r) => r.category === activeCat);
    cardsEl.innerHTML = "";
    list.forEach((run) => cardsEl.appendChild(makeCard(run)));
  }

  function makeCard(run) {
    const st = statusOf(run);
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "card";
    btn.innerHTML =
      '<span class="badge ' +
      st.cls +
      '">' +
      esc(st.label) +
      "</span>" +
      '<div class="card__top">' +
      '<span class="card__icon">' +
      iconSvg(run.category, 20) +
      "</span>" +
      '<span class="card__titles">' +
      '<h3 class="card__title">' +
      esc(run.title) +
      "</h3>" +
      '<p class="card__subtitle">' +
      esc(run.subtitle) +
      "</p>" +
      "</span></div>" +
      '<p class="card__headline">' +
      esc(run.headline || run.expected_outcome || "") +
      "</p>" +
      '<div class="card__foot">' +
      '<span class="card__index">run ' +
      String(run.__order).padStart(2, "0") +
      "</span>" +
      '<span class="card__go">abrir &rsaquo;</span>' +
      "</div>";
    btn.addEventListener("click", () => openDrawer(run, btn));
    return btn;
  }

  /* ============================ DRAWER ============================ */
  function wireDrawer() {
    $("drawer-close").addEventListener("click", closeDrawer);
    backdrop.addEventListener("click", closeDrawer);
    btnRun.addEventListener("click", () => {
      if (!activeRun) return;
      playTerminal(activeRun, !RM);
    });
    btnSkip.addEventListener("click", () => {
      skipFlag = true;
    });
    $("drawer-copy").addEventListener("click", copyCommand);

    document.querySelectorAll(".tab").forEach((tab) => {
      tab.addEventListener("click", () =>
        switchTab(tab.id.replace("tabbtn-", "")),
      );
    });

    document.addEventListener("keydown", (e) => {
      if (drawer.hidden) return;
      if (e.key === "Escape") {
        e.preventDefault();
        closeDrawer();
      } else if (e.key === "Tab") {
        trapTab(e);
      }
    });
  }

  function openDrawer(run, trigger) {
    activeRun = run;
    lastFocus = trigger || null;
    fillDrawer(run);
    switchTab("output");

    backdrop.hidden = false;
    drawer.hidden = false;
    // permite a transicao de entrada
    requestAnimationFrame(() => {
      backdrop.classList.add("is-open");
      drawer.classList.add("is-open");
    });
    document.body.style.overflow = "hidden";
    $("drawer-close").focus();

    playTerminal(run, !RM);
  }

  function closeDrawer() {
    cancelRun();
    drawer.classList.remove("is-open");
    backdrop.classList.remove("is-open");
    document.body.style.overflow = "";
    const finish = () => {
      drawer.hidden = true;
      backdrop.hidden = true;
      drawer.removeEventListener("transitionend", finish);
    };
    if (RM) finish();
    else drawer.addEventListener("transitionend", finish);
    if (lastFocus) lastFocus.focus();
    activeRun = null;
  }

  function fillDrawer(run) {
    const st = statusOf(run);
    const cat = (DATA.categories || []).find((c) => c.key === run.category);
    $("drawer-cat").textContent = cat ? cat.title : run.category;
    $("drawer-title").textContent = run.title;
    $("drawer-subtitle").textContent = run.subtitle;

    const badge = $("drawer-status");
    badge.className = "badge " + st.cls;
    badge.textContent = st.label;

    const inp = run.input || {};
    $("drawer-hash-text").textContent = (inp.hmac_short || "—") + "…";
    $("drawer-cmd").textContent = run.command || "";
    termName.textContent = run.id || "console";

    renderInputTab(run);
    renderAuditTab(run);
    renderOutputTab(run);
  }

  /* ---------- tabs ---------- */
  function switchTab(name) {
    ["output", "input", "audit"].forEach((n) => {
      const btn = $("tabbtn-" + n);
      const panel = $("tab-" + n);
      const on = n === name;
      btn.classList.toggle("is-active", on);
      btn.setAttribute("aria-selected", on ? "true" : "false");
      panel.hidden = !on;
    });
  }

  function renderOutputTab(run) {
    const panel = $("tab-output");
    const outs = run.outputs || [];
    let html = '<p class="panel-title">Artefatos gerados</p>';
    if (outs.length === 0) {
      html +=
        '<p class="empty-line">Esta automacao entrega o resultado em tela — nao grava arquivos.</p>';
    } else {
      html += '<div class="files">';
      outs.forEach((o) => {
        const sub =
          (o.kind === "dir" ? o.files + " arquivo(s) · " : "") +
          humanBytes(o.bytes) +
          (o.sha256 ? " · sha256 " + esc(o.sha256.slice(0, 12)) + "…" : "");
        html +=
          '<div class="file">' +
          '<span class="file__icon">' +
          iconSvg("file", 18) +
          "</span>" +
          '<span class="file__meta">' +
          '<span class="file__path">' +
          esc(o.path) +
          "</span>" +
          '<span class="file__sub">' +
          sub +
          "</span>" +
          "</span></div>";
      });
      html += "</div>";
    }
    panel.innerHTML = html;
  }

  function renderInputTab(run) {
    const panel = $("tab-input");
    const inp = run.input || {};
    let html =
      '<p class="panel-note">' +
      esc(inp.descriptor || "Entrada da automacao.") +
      "</p>";

    const id = inp.identity || {};
    const keys = Object.keys(id);
    if (keys.length) {
      html +=
        '<p class="panel-title">Identidade do input (canonica)</p><dl class="kv">';
      keys.forEach((k) => {
        html += "<dt>" + esc(k) + "</dt><dd>" + esc(String(id[k])) + "</dd>";
      });
      html += "</dl>";
    }

    const prev = inp.preview;
    if (Array.isArray(prev) && prev.length) {
      const cols = Object.keys(prev[0]);
      html += '<p class="panel-title">Amostra (CPF mascarado)</p>';
      html += '<table class="ptable"><thead><tr>';
      cols.forEach((c) => {
        html += "<th>" + esc(c) + "</th>";
      });
      html += "</tr></thead><tbody>";
      prev.forEach((row) => {
        html += "<tr>";
        cols.forEach((c) => {
          html += "<td>" + esc(String(row[c])) + "</td>";
        });
        html += "</tr>";
      });
      html += "</tbody></table>";
    }
    panel.innerHTML = html;
  }

  function renderAuditTab(run) {
    const panel = $("tab-audit");
    const a = run.audit || {};
    const inp = run.input || {};
    let html = "";

    if (a.recorded) {
      html += '<p class="panel-title">Registro no trilho</p><dl class="kv">';
      html += "<dt>Tarefa</dt><dd>" + esc(a.task_name) + "</dd>";
      html += "<dt>Status</dt><dd>" + esc(a.status) + "</dd>";
      html +=
        "<dt>Linhas afetadas</dt><dd>" +
        (a.rows_affected != null ? a.rows_affected : "—") +
        "</dd>";
      html +=
        "<dt>Linhas falhas</dt><dd>" +
        (a.rows_failed != null ? a.rows_failed : "—") +
        "</dd>";
      html +=
        "<dt>Duracao</dt><dd>" +
        (a.duration_ms != null ? a.duration_ms + " ms" : "—") +
        "</dd>";
      html += "<dt>Ambiente</dt><dd>" + esc(a.environment) + "</dd>";
      html += "<dt>Carimbo</dt><dd>" + esc(fmtDate(a.timestamp)) + "</dd>";
      html += "</dl>";
    } else {
      html +=
        '<p class="panel-note">' +
        esc(a.note || "Esta etapa nao gravou auditoria neste ambiente.") +
        "</p>";
    }

    html += '<p class="panel-title">Integridade do input</p>';
    html += '<p class="hash-line">' + esc(inp.hmac_sha256 || "—") + "</p>";
    html +=
      '<p class="panel-note">HMAC-SHA256 do input sanitizado, recalculado pelo capturador (' +
      esc(inp.hmac_algo || "core.security.hash_string") +
      ").</p>";

    if (a.recorded) {
      html += '<p class="panel-title">Hash armazenado no banco</p>';
      const stored = a.stored_input_hash;
      if (stored) {
        html += '<p class="hash-line">' + esc(stored) + "</p>";
      } else {
        html += '<p class="hash-line hash-empty">vazio</p>';
        html +=
          '<p class="panel-note">O nucleo grava a execucao sem o <code>input_data</code>, ' +
          "entao o hash no banco fica vazio de proposito. Por isso a verificacao contra o " +
          "valor armazenado (<code>verify_input_hash_against_stored</code>) e <strong>false</strong> — " +
          "o HMAC acima e a recomputacao honesta a partir do input.</p>";
      }
    }
    panel.innerHTML = html;
  }

  /* ---------- copiar comando ---------- */
  async function copyCommand() {
    const btn = $("drawer-copy");
    try {
      await navigator.clipboard.writeText(
        ($("drawer-cmd").textContent || "").trim(),
      );
      btn.textContent = "copiado";
      btn.classList.add("is-done");
      setTimeout(() => {
        btn.textContent = "copiar";
        btn.classList.remove("is-done");
      }, 1600);
    } catch (_e) {
      btn.textContent = "selecione";
    }
  }

  /* ============================ TERMINAL ============================ */
  function setRunning(on) {
    btnRun.disabled = on;
    btnRunLabel.textContent = on
      ? "Executando…"
      : activeRun
        ? "Reexecutar"
        : "Executar simulacao";
    btnSkip.hidden = !on;
  }

  function cancelRun() {
    runSeq += 1;
  }

  function statusLine(run) {
    if (run.outcome === "requires_browser")
      return "\u21b3 execucao local necessaria (Chromium)";
    if (run.outcome === "caught_issue") {
      return (
        "\u21b3 exit " +
        run.exit_code +
        " \u00b7 barrou dados invalidos (esperado) \u00b7 " +
        run.duration_ms +
        " ms"
      );
    }
    if (run.outcome === "ok") {
      return (
        "\u21b3 exit " + run.exit_code + " \u00b7 " + run.duration_ms + " ms"
      );
    }
    return "\u21b3 exit " + run.exit_code + " \u00b7 falha";
  }

  function classifyLine(text) {
    const t = text.trim();
    if (t.startsWith("[OK]")) return "t-ok";
    if (
      t.startsWith("[execucao local") ||
      t.startsWith("Para reproduzir") ||
      t.startsWith("Resultado esperado")
    ) {
      return "t-info";
    }
    if (/^=+$/.test(t) || /^-+$/.test(t)) return "t-dim";
    return "";
  }

  function buildLines(run) {
    const lines = [
      { text: "$ " + (run.command || ""), cls: "t-prompt" },
      { text: "", cls: "" },
    ];
    const out = (run.stdout || "").replace(/\s+$/, "");
    if (out) {
      out
        .split("\n")
        .forEach((l) => lines.push({ text: l, cls: classifyLine(l) }));
    } else {
      lines.push({ text: "(sem saida em tela)", cls: "t-dim" });
    }
    lines.push({ text: "", cls: "" });
    lines.push({ text: statusLine(run), cls: "t-status" });
    return lines;
  }

  function makeLine(line) {
    const frag = document.createDocumentFragment();
    const span = document.createElement("span");
    if (line.cls) span.className = line.cls;
    span.textContent = line.text;
    frag.appendChild(span);
    frag.appendChild(document.createTextNode("\n"));
    return frag;
  }

  async function playTerminal(run, animate) {
    const lines = buildLines(run);
    const mySeq = ++runSeq;
    skipFlag = false;
    termBody.textContent = "";
    setRunning(true);

    if (!animate) {
      lines.forEach((ln) => termBody.appendChild(makeLine(ln)));
      termBody.scrollTop = termBody.scrollHeight;
      setRunning(false);
      return;
    }

    const cursor = document.createElement("span");
    cursor.className = "t-cursor";
    termBody.appendChild(cursor);

    for (let i = 0; i < lines.length; i += 1) {
      if (mySeq !== runSeq) return; // cancelado por nova execucao/fechamento
      if (skipFlag) {
        for (let j = i; j < lines.length; j += 1) {
          termBody.insertBefore(makeLine(lines[j]), cursor);
        }
        break;
      }
      termBody.insertBefore(makeLine(lines[i]), cursor);
      termBody.scrollTop = termBody.scrollHeight;
      await wait(lines[i].text === "" ? 16 : i === 0 ? 70 : 34);
    }

    if (mySeq !== runSeq) return;
    cursor.remove();
    termBody.scrollTop = termBody.scrollHeight;
    setRunning(false);
  }

  /* ---------- foco preso no drawer ---------- */
  function trapTab(e) {
    const f = drawer.querySelectorAll(
      'button, a[href], iframe, [tabindex]:not([tabindex="-1"])',
    );
    const items = Array.prototype.filter.call(
      f,
      (el) => !el.disabled && el.offsetParent !== null,
    );
    if (!items.length) return;
    const first = items[0];
    const last = items[items.length - 1];
    if (e.shiftKey && document.activeElement === first) {
      e.preventDefault();
      last.focus();
    } else if (!e.shiftKey && document.activeElement === last) {
      e.preventDefault();
      first.focus();
    }
  }
})();
