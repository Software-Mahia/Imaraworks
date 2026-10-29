/* ==========================================================================
   app.js — shared shell, formatters, charts, drawer and audit timeline.
   Loaded after auth.js on every page that extends base.html.
   Server text is always rendered with textContent (never innerHTML).
   ========================================================================== */

const SHELL = (() => {
  const SVG_NS = "http://www.w3.org/2000/svg";

  const ROLE_LABEL = {
    EMPLOYEE: "Employee",
    MANAGER: "Manager",
    FINANCE: "Finance officer",
    ADMIN: "Administrator",
  };

  const STATUS = {
    DRAFT:            { label: "Draft",               tone: "muted",  note: "Not sent for approval yet" },
    SUBMITTED:        { label: "Submitted",           tone: "info",   note: "" },
    PENDING_APPROVAL: { label: "Awaiting approval",   tone: "warning",note: "" },
    APPROVED:         { label: "Approved",            tone: "accent", note: "Waiting for Finance to pay" },
    REJECTED:         { label: "Rejected",            tone: "danger", note: "" },
    PROCESSING:       { label: "Processing",          tone: "purple", note: "Payment is in flight" },
    PAID:             { label: "Paid",                tone: "success",note: "" },
    FAILED:           { label: "Failed",              tone: "danger", note: "Finance can retry" },
  };

  const STATUS_COLOR = {
    DRAFT: "#9897b4",
    SUBMITTED: "#4b4b77",
    PENDING_APPROVAL: "#a96800",
    APPROVED: "#6f68d8",
    REJECTED: "#d92d20",
    PROCESSING: "#b0a9f9",
    PAID: "#12805c",
    FAILED: "#d92d20",
  };

  const ACTIONS = {
    CREATED:         { label: "Request created",    icon: "file",         tone: "accent" },
    SUBMITTED:       { label: "Sent for approval",  icon: "send",         tone: "info" },
    APPROVED:        { label: "Approved",           icon: "check-circle", tone: "success" },
    REJECTED:        { label: "Rejected",           icon: "x",            tone: "danger" },
    AMOUNT_CHANGED:  { label: "Amount changed",     icon: "refresh",      tone: "warning" },
    PAYMENT_STARTED: { label: "Payment started",    icon: "credit-card",  tone: "warning" },
    PAID:            { label: "Payment completed",  icon: "wallet",       tone: "success" },
    PAYMENT_FAILED:  { label: "Payment failed",     icon: "alert",        tone: "danger" },
  };

  const DETAIL_LABELS = {
    amount: "Amount",
    level: "Level",
    required_levels: "Required levels",
    approved_levels: "Approved levels",
    outstanding_levels: "Outstanding",
    reason: "Reason",
    transaction: "Transaction",
    provider_reference: "Provider ref",
    fully_approved: "Fully approved",
    previous_amount: "Previous amount",
    new_amount: "New amount",
  };

  /* ---------------------------------------------------------------- icons */

  function icon(name, className) {
    const svg = document.createElementNS(SVG_NS, "svg");
    svg.setAttribute("class", "icon" + (className ? " " + className : ""));
    svg.setAttribute("aria-hidden", "true");
    const use = document.createElementNS(SVG_NS, "use");
    use.setAttribute("href", "#i-" + name);
    svg.append(use);
    return svg;
  }

  /* ------------------------------------------------------------ formatting */

  function num(value) {
    const n = Number(value);
    return Number.isFinite(n) ? n.toLocaleString("en-KE") : "—";
  }

  function money(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return "KES " + n.toLocaleString("en-KE", { minimumFractionDigits: 0, maximumFractionDigits: 2 });
  }

  function moneyExact(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    return "KES " + n.toLocaleString("en-KE", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  }

  function moneyCompact(value) {
    const n = Number(value);
    if (!Number.isFinite(n)) return "—";
    const abs = Math.abs(n);
    let out;
    if (abs >= 1e9) out = (n / 1e9).toFixed(abs >= 1e10 ? 0 : 1) + "B";
    else if (abs >= 1e6) out = (n / 1e6).toFixed(abs >= 1e7 ? 0 : 1) + "M";
    else if (abs >= 1e3) out = (n / 1e3).toFixed(abs >= 1e5 ? 0 : 1) + "K";
    else out = String(Math.round(n));
    return "KES " + out;
  }

  function dateText(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short", year: "numeric" });
  }

  function shortDate(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleDateString("en-GB", { day: "2-digit", month: "short" });
  }

  function dateTime(value) {
    if (!value) return "—";
    const d = new Date(value);
    if (Number.isNaN(d.getTime())) return String(value);
    return d.toLocaleString("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit" });
  }

  function relative(value) {
    if (!value) return "—";
    const then = new Date(value).getTime();
    if (Number.isNaN(then)) return String(value);
    const diff = Date.now() - then;
    if (diff < 45 * 1000) return "just now";
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return mins + "m ago";
    const hours = Math.floor(mins / 60);
    if (hours < 24) return hours + "h ago";
    const days = Math.floor(hours / 24);
    if (days < 30) return days + "d ago";
    return shortDate(value);
  }

  function monthLabel(isoMonth) {
    if (!isoMonth) return "";
    const [y, m] = String(isoMonth).split("-").map(Number);
    if (!y || !m) return String(isoMonth);
    return new Date(y, m - 1, 1).toLocaleDateString("en-GB", { month: "short" });
  }

  function initials(name, username) {
    const source = (name || username || "IW").trim();
    const parts = source.split(/\s+/).filter(Boolean);
    if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
    return source.slice(0, 2).toUpperCase();
  }

  function statusInfo(status) {
    return STATUS[status] || { label: status || "Unknown", tone: "muted", note: "" };
  }

  function statusPill(status, extraNote) {
    const info = statusInfo(status);
    const pill = document.createElement("span");
    pill.className = "pill pill--" + info.tone;
    const dot = document.createElement("i");
    dot.className = "pill-dot";
    pill.append(dot, document.createTextNode(info.label));
    if (extraNote) pill.title = extraNote;
    return pill;
  }

  function actionInfo(action) {
    return ACTIONS[action] || { label: action || "Event", icon: "activity", tone: "muted" };
  }

  /* --------------------------------------------------------------- alerts */

  function alert(el, message, type) {
    if (!el) return;
    const kind = type || "info";
    const iconName = kind === "error" ? "alert" : kind === "success" ? "check-circle" : kind === "warning" ? "alert" : "info";
    el.replaceChildren(icon(iconName), document.createTextNode(message));
    el.className = "alert" + (kind === "info" ? "" : " alert--" + kind);
    el.hidden = false;
  }

  function clearAlert(el) {
    if (!el) return;
    el.hidden = true;
    el.replaceChildren();
  }

  function toast(message, type) {
    const region = document.getElementById("toast-region");
    if (!region) return;
    const kind = type || "info";
    const item = document.createElement("div");
    item.className = "toast" + (kind === "info" ? "" : " toast--" + kind);
    const iconName = kind === "error" ? "alert" : kind === "success" ? "check-circle" : kind === "warning" ? "alert" : "info";
    item.append(icon(iconName), document.createTextNode(message));
    region.append(item);
    window.setTimeout(() => {
      item.classList.add("is-leaving");
      item.addEventListener("animationend", () => item.remove(), { once: true });
      window.setTimeout(() => item.remove(), 500);
    }, 4200);
  }

  async function readJson(res) {
    try { return await res.json(); } catch (err) { return {}; }
  }

  function errorText(body) {
    if (!body) return "Something went wrong.";
    if (typeof body === "string") return body;
    if (body.detail) return String(body.detail);
    const parts = Object.values(body).flat().map(String);
    return parts.length ? parts.join(" ") : "Something went wrong.";
  }

  /* --------------------------------------------------------------- charts */

  const hasCharts = () => typeof window.Chart !== "undefined";

  function cssVar(name, fallback) {
    const value = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
    return value || fallback;
  }

  function setupCharts() {
    if (!hasCharts()) return;
    const Chart = window.Chart;
    Chart.defaults.color = cssVar("--muted", "#63637d");
    Chart.defaults.font.family = "'Plus Jakarta Sans', ui-sans-serif, system-ui, sans-serif";
    Chart.defaults.font.size = 11;
    Chart.defaults.borderColor = "rgba(0, 0, 68, 0.07)";
    Chart.defaults.plugins.legend.display = false;
    Chart.defaults.plugins.tooltip.backgroundColor = "#000044";
    Chart.defaults.plugins.tooltip.borderColor = "rgba(255, 255, 255, 0.14)";
    Chart.defaults.plugins.tooltip.borderWidth = 1;
    Chart.defaults.plugins.tooltip.titleColor = "#ffffff";
    Chart.defaults.plugins.tooltip.bodyColor = "#dddafc";
    Chart.defaults.plugins.tooltip.padding = 11;
    Chart.defaults.plugins.tooltip.cornerRadius = 12;
    Chart.defaults.plugins.tooltip.displayColors = false;
    Chart.defaults.animation.duration = 650;
    Chart.defaults.animation.easing = "easeOutQuart";
  }

  function chart(id, config) {
    const canvas = typeof id === "string" ? document.getElementById(id) : id;
    if (!canvas) return null;
    if (!hasCharts()) {
      const box = canvas.parentElement;
      if (box && !box.querySelector(".chart-missing")) {
        const note = document.createElement("div");
        note.className = "empty chart-missing";
        note.append(icon("chart"), document.createTextNode("Charts could not load."));
        box.append(note);
      }
      return null;
    }
    const existing = window.Chart.getChart(canvas);
    if (existing) existing.destroy();
    return new window.Chart(canvas, config);
  }

  function axisMoney(value) {
    return moneyCompact(value).replace("KES ", "");
  }

  function areaChart(id, labels, values, options) {
    const opts = options || {};
    const color = opts.color || cssVar("--lilac", "#b0a9f9");
    const currency = !!opts.currency;
    return chart(id, {
      type: "line",
      data: {
        labels,
        datasets: [{
          label: opts.label || "Value",
          data: values,
          borderColor: color,
          borderWidth: 2.5,
          tension: 0.45,
          cubicInterpolationMode: "monotone",
          fill: true,
          pointRadius: 0,
          pointHoverRadius: 5,
          pointHoverBackgroundColor: color,
          pointHoverBorderColor: cssVar("--surface", "#ffffff"),
          pointHoverBorderWidth: 3,
          backgroundColor: hexToRgba(color, 0.16),
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        interaction: { mode: "index", intersect: false },
        plugins: {
          tooltip: {
            callbacks: {
              label: (ctx) => (currency ? money(ctx.parsed.y) : num(ctx.parsed.y) + (opts.suffix ? " " + opts.suffix : "")),
            },
          },
        },
        scales: {
          x: {
            grid: { display: false },
            border: { display: false },
            ticks: { maxRotation: 0, autoSkipPadding: 12, padding: 6 },
          },
          y: {
            beginAtZero: true,
            grid: { color: "rgba(0, 0, 68, 0.07)", drawTicks: false, borderDash: [4, 6] },
            border: { display: false },
            ticks: {
              padding: 8,
              maxTicksLimit: 5,
              callback: (value) => (currency ? axisMoney(value) : value),
            },
          },
        },
      },
    });
  }

  function barChart(id, labels, values, options) {
    const opts = options || {};
    const color = opts.color || cssVar("--lilac", "#b0a9f9");
    const currency = !!opts.currency;
    const horizontal = !!opts.horizontal;
    return chart(id, {
      type: "bar",
      data: {
        labels,
        datasets: [{
          label: opts.label || "Value",
          data: values,
          backgroundColor: color,
          hoverBackgroundColor: color,
          borderRadius: horizontal ? 999 : 10,
          borderSkipped: false,
          maxBarThickness: 24,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        indexAxis: horizontal ? "y" : "x",
        plugins: {
          tooltip: {
            callbacks: {
              label: (ctx) => {
                const raw = horizontal ? ctx.parsed.x : ctx.parsed.y;
                return currency ? money(raw) : num(raw) + (opts.suffix ? " " + opts.suffix : "");
              },
            },
          },
        },
        scales: {
          x: horizontal
            ? {
                beginAtZero: true,
                grid: { color: "rgba(0, 0, 68, 0.07)", drawTicks: false, borderDash: [4, 6] },
                border: { display: false },
                ticks: { padding: 8, maxTicksLimit: 5, callback: (value) => (currency ? axisMoney(value) : value) },
              }
            : {
                grid: { display: false },
                border: { display: false },
                ticks: { maxRotation: 0, autoSkipPadding: 10, padding: 6 },
              },
          y: horizontal
            ? {
                grid: { display: false },
                border: { display: false },
                ticks: {
                  padding: 6,
                  autoSkip: false,
                  callback: function (value) {
                    const label = this.getLabelForValue(value);
                    return label.length > 18 ? label.slice(0, 17) + "…" : label;
                  },
                },
              }
            : {
                beginAtZero: true,
                grid: { color: "rgba(0, 0, 68, 0.07)", drawTicks: false, borderDash: [4, 6] },
                border: { display: false },
                ticks: { padding: 8, maxTicksLimit: 5, callback: (value) => (currency ? axisMoney(value) : value) },
              },
        },
      },
    });
  }

  function doughnutChart(id, labels, values, colors) {
    return chart(id, {
      type: "doughnut",
      data: {
        labels,
        datasets: [{
          data: values,
          backgroundColor: colors,
          borderColor: cssVar("--surface", "#ffffff"),
          borderWidth: 2,
          hoverOffset: 5,
        }],
      },
      options: {
        responsive: true,
        maintainAspectRatio: false,
        cutout: "72%",
        plugins: {
          tooltip: { callbacks: { label: (ctx) => `${ctx.label}: ${num(ctx.parsed)}` } },
        },
      },
    });
  }

  function hexToRgba(hex, alpha) {
    let value = String(hex || "").replace("#", "");
    if (value.length === 3) value = value.split("").map((c) => c + c).join("");
    const int = parseInt(value, 16);
    if (Number.isNaN(int)) return `rgba(176,169,249,${alpha})`;
    const r = (int >> 16) & 255;
    const g = (int >> 8) & 255;
    const b = int & 255;
    return `rgba(${r},${g},${b},${alpha})`;
  }

  function sparkline(container, values, tone) {
    if (!container) return;
    container.replaceChildren();
    container.className = "spark spark--" + (tone || "accent");
    const list = (values || []).map((v) => Number(v) || 0);
    if (!list.length) return;
    const max = Math.max(...list, 1);
    list.forEach((value) => {
      const bar = document.createElement("span");
      bar.style.height = Math.max(12, Math.round((value / max) * 100)) + "%";
      bar.title = num(value);
      container.append(bar);
    });
  }

  /* ------------------------------------------------------------- progress */

  const STAGE_PROGRESS = {
    DRAFT: 0,
    SUBMITTED: 1,
    PENDING_APPROVAL: 1,
    APPROVED: 2,
    PROCESSING: 3,
    PAID: 4,
    FAILED: 3,
    REJECTED: 1,
  };

  function stageTracker(status) {
    const steps = ["Submitted", "Manager", "Finance", "Paid"];
    const done = STAGE_PROGRESS[status] == null ? 0 : STAGE_PROGRESS[status];
    const failed = status === "REJECTED" || status === "FAILED";
    const wrap = document.createElement("div");
    wrap.className = "stages";
    wrap.setAttribute("role", "img");
    wrap.setAttribute("aria-label", `${statusInfo(status).label} — ${done} of ${steps.length} stages complete`);

    steps.forEach((label, index) => {
      if (index) {
        const line = document.createElement("span");
        line.className = "stage-line";
        if (index <= done) line.classList.add("is-done");
        wrap.append(line);
      }
      const stage = document.createElement("span");
      stage.className = "stage";
      if (index < done) stage.classList.add("is-done");
      if (index === done && done < steps.length) stage.classList.add("is-current");
      if (failed && index === Math.max(done - 1, 0)) {
        stage.classList.remove("is-current");
        stage.classList.add("is-stopped");
      }
      const dot = document.createElement("i");
      dot.className = "stage-dot";
      const text = document.createElement("span");
      text.className = "stage-label";
      text.textContent = label;
      stage.append(dot, text);
      wrap.append(stage);
    });
    return wrap;
  }

  /* --------------------------------------------------------------- tabs */

  function tabs() {
    const buttons = Array.from(document.querySelectorAll('[role="tab"][data-tab]'));
    if (!buttons.length) return null;
    const names = buttons.map((button) => button.dataset.tab);
    const panels = names
      .map((name) => document.getElementById("panel-" + name))
      .filter(Boolean);

    function activate(name, updateHash) {
      const next = names.includes(name) ? name : names[0];
      buttons.forEach((button) => {
        const on = button.dataset.tab === next;
        button.setAttribute("aria-selected", String(on));
        button.tabIndex = on ? 0 : -1;
      });
      panels.forEach((panel) => { panel.hidden = panel.id !== "panel-" + next; });
      if (updateHash && window.location.hash !== "#" + next) {
        history.replaceState(null, "", "#" + next);
      }
      window.requestAnimationFrame(() => {
        window.dispatchEvent(new CustomEvent("shell:tab", { detail: { tab: next } }));
      });
      return next;
    }

    buttons.forEach((button, index) => {
      button.addEventListener("click", () => activate(button.dataset.tab, true));
      button.addEventListener("keydown", (event) => {
        if (event.key !== "ArrowRight" && event.key !== "ArrowLeft") return;
        event.preventDefault();
        const step = event.key === "ArrowRight" ? 1 : -1;
        const target = buttons[(index + step + buttons.length) % buttons.length];
        target.focus();
        activate(target.dataset.tab, true);
      });
    });

    const requested = window.location.hash.replace("#", "");
    activate(requested || names[0], false);
    window.addEventListener("hashchange", () => activate(window.location.hash.replace("#", ""), false));

    document.querySelectorAll("[data-goto-tab]").forEach((el) => {
      el.addEventListener("click", () => {
        activate(el.dataset.gotoTab, true);
      });
    });

    return activate;
  }

  /* --------------------------------------------------------------- drawer */

  let lastFocus = null;

  function openDrawer(title, subtitle) {
    const drawer = document.getElementById("detail-drawer");
    const scrim = document.getElementById("drawer-scrim");
    if (!drawer || !scrim) return;
    lastFocus = document.activeElement;
    document.getElementById("drawer-title").textContent = title || "Details";
    document.getElementById("drawer-subtitle").textContent = subtitle || "";
    drawer.hidden = false;
    scrim.hidden = false;
    document.body.style.overflow = "hidden";
    requestAnimationFrame(() => {
      drawer.classList.add("is-open");
      scrim.classList.add("is-open");
    });
    document.getElementById("drawer-close").focus();
  }

  function closeDrawer() {
    const drawer = document.getElementById("detail-drawer");
    const scrim = document.getElementById("drawer-scrim");
    if (!drawer || !scrim) return;
    drawer.classList.remove("is-open");
    scrim.classList.remove("is-open");
    document.body.style.overflow = "";
    window.setTimeout(() => {
      if (!drawer.classList.contains("is-open")) {
        drawer.hidden = true;
        scrim.hidden = true;
      }
    }, 300);
    if (lastFocus && lastFocus.focus) lastFocus.focus();
  }

  function closeGuide() {
    const modal = document.getElementById("guide-modal");
    if (modal) modal.hidden = true;
  }

  function detailValue(key, value) {
    if (value === null || value === undefined || value === "") return "—";
    if (key === "amount" || key === "previous_amount" || key === "new_amount") return money(value);
    if (Array.isArray(value)) return value.length ? value.join(", ") : "—";
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "object") return Object.entries(value).map(([k, v]) => `${k}: ${v}`).join(", ");
    return String(value);
  }

  function renderTimeline(entries) {
    const body = document.getElementById("drawer-body");
    if (!body) return;
    if (!entries.length) {
      body.replaceChildren();
      const empty = document.createElement("div");
      empty.className = "empty";
      const box = document.createElement("div");
      box.className = "empty-icon";
      box.append(icon("history"));
      const title = document.createElement("strong");
      title.textContent = "No history yet";
      const text = document.createElement("p");
      text.textContent = "Actions on this request will appear here.";
      empty.append(box, title, text);
      body.append(empty);
      return;
    }

    const timeline = document.createElement("div");
    timeline.className = "timeline";
    entries.forEach((entry) => {
      const info = actionInfo(entry.action);
      const item = document.createElement("div");
      item.className = "timeline-item";

      const dot = document.createElement("span");
      dot.className = "timeline-dot timeline-dot--" + info.tone;
      dot.append(icon(info.icon));

      const content = document.createElement("div");
      content.className = "timeline-content";

      const top = document.createElement("div");
      top.className = "timeline-top";
      const title = document.createElement("strong");
      title.textContent = info.label;
      const time = document.createElement("time");
      time.dateTime = entry.timestamp || "";
      time.textContent = relative(entry.timestamp);
      time.title = dateTime(entry.timestamp);
      top.append(title, time);

      const who = document.createElement("p");
      who.textContent = entry.actor_username ? "by " + entry.actor_username : "by the system";
      content.append(top, who);

      const details = entry.details && typeof entry.details === "object" ? Object.entries(entry.details) : [];
      const shown = details.filter(([, value]) => value !== null && value !== undefined && value !== "");
      if (shown.length) {
        const box = document.createElement("div");
        box.className = "timeline-details";
        shown.forEach(([key, value]) => {
          const span = document.createElement("span");
          const label = document.createElement("b");
          label.textContent = (DETAIL_LABELS[key] || key) + ": ";
          span.append(label, document.createTextNode(detailValue(key, value)));
          box.append(span);
        });
        content.append(box);
      }

      item.append(dot, content);
      timeline.append(item);
    });
    body.replaceChildren(timeline);
  }

  async function openHistory(requestId, subtitle) {
    openDrawer("Request history", subtitle || `Request #${requestId} · newest first`);
    const body = document.getElementById("drawer-body");
    if (body) {
      body.replaceChildren();
      const loading = document.createElement("div");
      for (let i = 0; i < 4; i += 1) {
        const line = document.createElement("div");
        line.className = "skeleton skeleton-line";
        loading.append(line);
      }
      body.append(loading);
    }
    try {
      const res = await AUTH.apiFetch(`/api/payment-requests/${requestId}/history/`);
      if (!res.ok) {
        if (body) {
          body.replaceChildren();
          const note = document.createElement("div");
          note.className = "alert alert--error";
          note.append(icon("alert"), document.createTextNode(
            res.status === 404 ? "You cannot see the history of this request." : "Could not load this request's history."
          ));
          body.append(note);
        }
        return;
      }
      const entries = await res.json();
      renderTimeline(entries.slice().reverse());
    } catch (err) {
      if (body) {
        body.replaceChildren();
        const note = document.createElement("div");
        note.className = "alert alert--error";
        note.append(icon("alert"), document.createTextNode("Could not reach the server. Please try again."));
        body.append(note);
      }
    }
  }

  /* ------------------------------------------------------------ shell init */

  const ROLE_ICONS = {
    ADMIN: "/static/frontend/icon-admin.png",
    MANAGER: "/static/frontend/icon-manager.png",
    EMPLOYEE: "/static/frontend/icon-employer.png",
    FINANCE: "/static/frontend/icon-finance-officer.png",
  };

  function init(me) {
    if (!me) return;
    setupCharts();

    const fullName = `${me.first_name || ""} ${me.last_name || ""}`.trim() || me.username;
    const role = ROLE_LABEL[me.role] || me.role || "No role";
    const badge = initials(fullName, me.username);
    const iconUrl = ROLE_ICONS[me.role] || "";

    const avatarEl = document.getElementById("topbar-avatar");
    if (avatarEl) {
      if (iconUrl) avatarEl.src = iconUrl;
      avatarEl.alt = badge;
    }
    ["topbar-name", "topbar-role"].forEach((id) => {
      const el = document.getElementById(id);
      if (el) el.textContent = id === "topbar-name" ? fullName : role;
    });

    document.querySelectorAll("[data-roles]").forEach((el) => {
      const roles = (el.dataset.roles || "").split(",").map((r) => r.trim());
      if (!roles.includes(me.role)) el.hidden = true;
    });

    document.querySelectorAll(".nav-link[data-nav]").forEach((link) => {
      const path = new URL(link.href, window.location.origin).pathname;
      if (path === window.location.pathname) link.classList.add("is-active");
    });

    const today = document.getElementById("today-label");
    if (today) {
      today.textContent = new Date().toLocaleDateString("en-GB", {
        weekday: "short", day: "numeric", month: "short", year: "numeric",
      });
    }

    const page = document.getElementById("page");
    if (page) page.hidden = false;

    tabs();

    const logout = document.getElementById("logout-btn");
    if (logout) logout.addEventListener("click", () => AUTH.logout());

    const drawerClose = document.getElementById("drawer-close");
    if (drawerClose) drawerClose.addEventListener("click", closeDrawer);
    const drawerScrim = document.getElementById("drawer-scrim");
    if (drawerScrim) drawerScrim.addEventListener("click", closeDrawer);
    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") return;
      const drawer = document.getElementById("detail-drawer");
      if (drawer && drawer.classList.contains("is-open")) closeDrawer();
      const guideModal = document.getElementById("guide-modal");
      if (guideModal && !guideModal.hidden) closeGuide();
    });

    const guideBtn = document.getElementById("guide-btn");
    const guideModal = document.getElementById("guide-modal");
    const guideClose = document.getElementById("guide-close");
    if (guideBtn && guideModal && guideClose) {
      guideBtn.addEventListener("click", () => {
        guideModal.hidden = false;
      });
      guideClose.addEventListener("click", closeGuide);
      guideModal.addEventListener("click", (event) => {
        if (event.target === guideModal) closeGuide();
      });
    }

    window.SHELL.me = me;
  }

  function navCount(value) {
    const n = Number(value) || 0;
    document.querySelectorAll("[data-queue-count]").forEach((el) => {
      el.textContent = n > 99 ? "99+" : String(n);
      el.hidden = n === 0;
    });
  }

  function debounce(fn, wait) {
    let timer = null;
    return function debounced(...args) {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn.apply(this, args), wait || 180);
    };
  }

  function sum(list, pick) {
    return list.reduce((total, item) => total + (Number(pick(item)) || 0), 0);
  }

  return {
    init,
    icon,
    num,
    money,
    moneyExact,
    moneyCompact,
    dateText,
    shortDate,
    dateTime,
    relative,
    monthLabel,
    initials,
    statusInfo,
    statusPill,
    actionInfo,
    alert,
    clearAlert,
    toast,
    readJson,
    errorText,
    areaChart,
    barChart,
    doughnutChart,
    sparkline,
    openDrawer,
    closeDrawer,
    openHistory,
    stageTracker,
    tabs,
    navCount,
    debounce,
    sum,
    hasCharts,
    STATUS,
    STATUS_COLOR,
    ACTIONS,
    ROLE_LABEL,
    ROLE_ICONS,
  };
})();

// Classic scripts keep top-level const bindings out of the window object. Expose the shell
// explicitly so page code and the console can both reach it.
window.SHELL = SHELL;
