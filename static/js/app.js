/* ==========================================================================
   RHPTPS — client application
   Sections: utils · toasts · session · api · router+nav · views
   ========================================================================== */

// ---- utils ------------------------------------------------------------

const $ = (sel, root = document) => root.querySelector(sel);
const el = (tag, attrs = {}, children = []) => {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "html") node.innerHTML = v;
    else if (k.startsWith("on") && typeof v === "function") node.addEventListener(k.slice(2), v);
    else node.setAttribute(k, v);
  }
  for (const c of [].concat(children)) {
    if (c == null) continue;
    node.appendChild(typeof c === "string" ? document.createTextNode(c) : c);
  }
  return node;
};

function formatNaira(amount) {
  const n = Number(amount);
  const [whole, cents] = n.toFixed(2).split(".");
  return { whole: Number(whole).toLocaleString("en-NG"), cents };
}

function formatDate(iso) {
  if (!iso) return "—";
  const d = new Date(iso);
  return d.toLocaleString("en-NG", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

function shortId(id) {
  if (!id) return "—";
  return id.length > 12 ? `${id.slice(0, 8)}…` : id;
}

async function copyToClipboard(text, button) {
  try {
    await navigator.clipboard.writeText(text);
    const original = button.textContent;
    button.textContent = "Copied";
    setTimeout(() => { button.textContent = original; }, 1200);
  } catch {
    toast("Couldn't copy — select and copy manually", "error");
  }
}

function idempotencyKey() {
  return crypto.randomUUID ? crypto.randomUUID() : `${Date.now()}-${Math.random()}`;
}

// Animates a number counting up — the one deliberate motion moment,
// used only for the fare reveal.
function animateCount(node, to, { prefix = "\u20a6", duration = 700 } = {}) {
  const start = performance.now();
  const from = 0;
  function frame(now) {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 3);
    const value = from + (to - from) * eased;
    const { whole, cents } = formatNaira(value);
    node.innerHTML = `${prefix}${whole}<span class="cents">.${cents}</span>`;
    if (t < 1) requestAnimationFrame(frame);
  }
  requestAnimationFrame(frame);
}

// ---- toasts -------------------------------------------------------------

function toast(message, kind = "default") {
  const stack = $("#toast-stack");
  const node = el("div", { class: `toast ${kind === "error" ? "toast-error" : kind === "success" ? "toast-success" : ""}` }, message);
  stack.appendChild(node);
  setTimeout(() => {
    node.classList.add("leaving");
    setTimeout(() => node.remove(), 180);
  }, 3200);
}

// ---- session --------------------------------------------------------------

const Session = {
  get token() { return localStorage.getItem("rhptps_token"); },
  get role() { return localStorage.getItem("rhptps_role"); },
  get id() { return localStorage.getItem("rhptps_id"); },
  get name() { return localStorage.getItem("rhptps_name"); },
  get isAuthed() { return Boolean(this.token); },
  set({ access, role, id, full_name }) {
    localStorage.setItem("rhptps_token", access);
    localStorage.setItem("rhptps_role", role);
    localStorage.setItem("rhptps_id", id);
    localStorage.setItem("rhptps_name", full_name || "");
  },
  clear() {
    ["rhptps_token", "rhptps_role", "rhptps_id", "rhptps_name"].forEach(k => localStorage.removeItem(k));
  },
};

// ---- api client -----------------------------------------------------------

async function api(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  if (auth && Session.token) headers["Authorization"] = `Bearer ${Session.token}`;

  const res = await fetch(path, { method, headers, body: body ? JSON.stringify(body) : undefined });
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }

  if (!res.ok) {
    if (res.status === 401 && auth) {
      Session.clear();
      location.hash = "#/login";
    }
    const message = (data && (data.errors ? data.errors.join("; ") : data.detail)) || `Request failed (${res.status})`;
    throw Object.assign(new Error(message), { status: res.status, data });
  }
  return data;
}

// ---- navigation chrome -----------------------------------------------------

const NAV_ITEMS = {
  rider: [
    { href: "#/ride", label: "Ride", icon: "car" },
    { href: "#/receipt", label: "Receipt", icon: "receipt" },
  ],
  driver: [
    { href: "#/driver", label: "Profile", icon: "user" },
  ],
  admin: [
    { href: "#/admin", label: "Admin", icon: "shield" },
  ],
};

const ICONS = {
  car: '<path d="M3 12l1.5-4.5A2 2 0 0 1 6.4 6h11.2a2 2 0 0 1 1.9 1.5L21 12M4 12h16v5a1 1 0 0 1-1 1h-1a1 1 0 0 1-1-1v-1H7v1a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1v-5z"/><circle cx="7.5" cy="15.5" r="0" /><circle cx="7.5" cy="12.5" r="1"/><circle cx="16.5" cy="12.5" r="1"/>',
  receipt: '<path d="M6 3h12v18l-2.5-1.5L13 21l-2.5-1.5L8 21l-2-1.5V3z"/><path d="M9 8h6M9 12h6M9 16h3"/>',
  user: '<circle cx="12" cy="8" r="3.5"/><path d="M5 20c0-3.5 3-6 7-6s7 2.5 7 6"/>',
  shield: '<path d="M12 3l7 3v6c0 4.5-3 7.5-7 9-4-1.5-7-4.5-7-9V6l7-3z"/>',
};

function iconSvg(name) {
  return `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round">${ICONS[name] || ""}</svg>`;
}

function renderNav(activeHash) {
  const topnav = $("#topnav");
  const bottomnav = $("#bottomnav");
  const sessionSlot = $("#session-slot");
  const items = Session.role ? (NAV_ITEMS[Session.role] || []) : [];

  topnav.innerHTML = "";
  items.forEach(item => {
    topnav.appendChild(el("a", { href: item.href, class: item.href === activeHash ? "active" : "" }, item.label));
  });

  if (Session.isAuthed) {
    sessionSlot.innerHTML = "";
    sessionSlot.appendChild(el("span", {}, [el("strong", {}, Session.name || Session.id), ` · ${Session.role}`]));
    sessionSlot.appendChild(el("button", { class: "btn btn-ghost btn-sm", onclick: logout }, "Log out"));
  } else {
    sessionSlot.innerHTML = "";
  }

  bottomnav.innerHTML = "";
  if (items.length) {
    const inner = el("div", { class: "bottombar__inner" });
    items.forEach(item => {
      inner.appendChild(el("a", { href: item.href, class: item.href === activeHash ? "active" : "" }, [
        el("span", { html: iconSvg(item.icon) }),
        el("span", {}, item.label),
        el("span", { class: "bottombar__dot" }),
      ]));
    });
    bottomnav.appendChild(inner);
  }
}

function logout() {
  Session.clear();
  toast("Logged out");
  location.hash = "#/login";
}

// ---- router -----------------------------------------------------------------

const ROUTES = {
  "#/login": { render: renderLoginView, public: true },
  "#/ride": { render: renderRideView, role: "rider" },
  "#/receipt": { render: renderReceiptView, role: "rider" },
  "#/driver": { render: renderDriverView, role: "driver" },
  "#/admin": { render: renderAdminView, role: "admin" },
};

const HOME_BY_ROLE = { rider: "#/ride", driver: "#/driver", admin: "#/admin" };

// A hard refresh or direct link hits a path like /receipt with no hash
// yet; translate that path into its hash route once, on first load.
const PATH_TO_HASH = { "/ride": "#/ride", "/receipt": "#/receipt", "/driver": "#/driver", "/admin": "#/admin" };
if (!location.hash && PATH_TO_HASH[location.pathname]) {
  location.hash = PATH_TO_HASH[location.pathname];
}

function router() {
  let hash = location.hash || "#/";
  if (hash === "#/") hash = Session.role ? HOME_BY_ROLE[Session.role] : "#/login";

  const route = ROUTES[hash] || ROUTES["#/login"];

  if (!route.public && !Session.isAuthed) {
    location.hash = "#/login";
    return;
  }
  if (route.role && Session.role !== route.role) {
    location.hash = HOME_BY_ROLE[Session.role] || "#/login";
    return;
  }
  if (hash === "#/login" && Session.isAuthed) {
    location.hash = HOME_BY_ROLE[Session.role] || "#/login";
    return;
  }

  renderNav(hash);
  const view = $("#view");
  view.classList.remove("view-enter");
  void view.offsetWidth; // restart animation
  view.classList.add("view-enter");
  route.render(view);
}

window.addEventListener("hashchange", router);
document.addEventListener("DOMContentLoaded", router);

// ==========================================================================
// Views
// ==========================================================================

// ---- Login / register ------------------------------------------------------

function renderLoginView(view) {
  view.innerHTML = "";

  const thumb = el("div", { class: "segmented__thumb" });
  const loginTab = el("button", { class: "active" }, "Log in");
  const registerTab = el("button", {}, "Register");
  const segmented = el("div", { class: "segmented", "data-active": "0" }, [thumb, loginTab, registerTab]);

  const panels = el("div");
  const loginPanel = buildLoginPanel();
  const registerPanel = buildRegisterPanel();
  registerPanel.style.display = "none";
  panels.append(loginPanel, registerPanel);

  function activate(index) {
    segmented.dataset.active = String(index);
    [loginTab, registerTab].forEach((t, i) => t.classList.toggle("active", i === index));
    loginPanel.style.display = index === 0 ? "" : "none";
    registerPanel.style.display = index === 1 ? "" : "none";
  }
  loginTab.onclick = () => activate(0);
  registerTab.onclick = () => activate(1);

  view.append(
    el("div", { class: "page-head" }, [
      el("h1", {}, "Welcome back"),
      el("p", {}, "Sign in to request a ride, review a receipt, or manage the platform."),
    ]),
    segmented,
    panels
  );
}

function buildLoginPanel() {
  const email = el("input", { type: "email", required: "" });
  const password = el("input", { type: "password", required: "" });
  const errorBox = el("div", { class: "banner banner-error mt-6", style: "display:none" });
  const submitBtn = el("button", { class: "btn btn-primary btn-block", type: "submit" }, "Log in");

  const form = el("form", { class: "card stack", onsubmit: onSubmit }, [
    el("div", { class: "field" }, [el("label", {}, "Email"), email]),
    el("div", { class: "field" }, [el("label", {}, "Password"), password]),
    submitBtn,
    errorBox,
  ]);

  async function onSubmit(e) {
    e.preventDefault();
    errorBox.style.display = "none";
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Logging in…';
    try {
      const data = await api("/api/auth/login", { method: "POST", auth: false, body: { email: email.value, password: password.value } });
      Session.set(data);
      toast(`Welcome, ${data.full_name || data.role}`, "success");
      location.hash = HOME_BY_ROLE[data.role] || "#/";
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.style.display = "";
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Log in";
    }
  }

  return form;
}

function buildRegisterPanel() {
  const role = el("select", {}, [el("option", { value: "rider" }, "Rider"), el("option", { value: "driver" }, "Driver")]);
  const fullName = el("input", { required: "" });
  const email = el("input", { type: "email", required: "" });
  const phone = el("input", { placeholder: "0801xxxxxxx", required: "" });
  const password = el("input", { type: "password", minlength: "8", required: "" });
  const resultBox = el("div", { style: "display:none" });
  const submitBtn = el("button", { class: "btn btn-amber btn-block", type: "submit" }, "Create account");

  const form = el("form", { class: "card stack", onsubmit: onSubmit }, [
    el("div", { class: "field" }, [el("label", {}, "I am a"), role]),
    el("div", { class: "field" }, [el("label", {}, "Full name"), fullName]),
    el("div", { class: "field" }, [el("label", {}, "Email"), email]),
    el("div", { class: "field" }, [el("label", {}, "Phone number"), phone]),
    el("div", { class: "field" }, [el("label", {}, "Password"), password, el("div", { class: "field-hint" }, "At least 8 characters")]),
    submitBtn,
    resultBox,
  ]);

  async function onSubmit(e) {
    e.preventDefault();
    resultBox.style.display = "none";
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Creating…';
    try {
      const data = await api("/api/auth/register", {
        method: "POST", auth: false,
        body: { role: role.value, full_name: fullName.value, email: email.value, phone_number: phone.value, password: password.value },
      });
      resultBox.className = "banner banner-success mt-6";
      resultBox.innerHTML = "";
      resultBox.append(
        el("p", {}, `Account created. Save your ID if you're a driver — you'll need it when riders request you.`),
        el("div", { class: "copy-field mt-6" }, [
          el("code", {}, data.id),
          el("button", { type: "button", class: "btn btn-sm", onclick: (e2) => copyToClipboard(data.id, e2.target) }, "Copy"),
        ])
      );
      resultBox.style.display = "";
      form.reset();
      toast("Account created — you can log in now", "success");
    } catch (err) {
      resultBox.className = "banner banner-error mt-6";
      resultBox.textContent = err.message;
      resultBox.style.display = "";
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Create account";
    }
  }

  return form;
}

// ---- Ride & payment ---------------------------------------------------------

function renderRideView(view) {
  view.innerHTML = "";

  const driverId = el("input", { id: "driver-id-input", required: "", placeholder: "paste the driver's ID" });
  const method = el("select", {}, [
    el("option", { value: "card" }, "Card"),
    el("option", { value: "transfer" }, "Bank transfer"),
    el("option", { value: "wallet" }, "Mobile wallet"),
  ]);
  const distance = el("input", { type: "number", step: "0.1", value: "7.4", required: "" });
  const duration = el("input", { type: "number", value: "18", required: "" });
  const pickup = el("input", { value: "Wurukum" });
  const dropoff = el("input", { value: "North Bank" });
  const submitBtn = el("button", { class: "btn btn-primary btn-block", type: "submit" }, "Complete trip");

  const form = el("form", { class: "card stack", onsubmit: onCreateRide }, [
    el("div", { class: "field" }, [el("label", {}, "Driver ID"), driverId]),
    el("div", { class: "field-row" }, [
      el("div", { class: "field" }, [el("label", {}, "Distance (km)"), distance]),
      el("div", { class: "field" }, [el("label", {}, "Duration (minutes)"), duration]),
    ]),
    el("div", { class: "field-row" }, [
      el("div", { class: "field" }, [el("label", {}, "Pickup"), pickup]),
      el("div", { class: "field" }, [el("label", {}, "Dropoff"), dropoff]),
    ]),
    el("div", { class: "field" }, [el("label", {}, "Payment method"), method]),
    submitBtn,
  ]);

  const resultArea = el("div", { class: "mt-6" });

  view.append(
    el("div", { class: "page-head" }, [
      el("h1", {}, "Complete a trip"),
      el("p", {}, "Enter the trip details to compute the fare, then capture payment against the sandbox gateway."),
    ]),
    form,
    resultArea
  );

  async function onCreateRide(e) {
    e.preventDefault();
    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span class="spinner"></span> Computing fare…';
    try {
      const ride = await api("/api/rides", {
        method: "POST",
        body: {
          driver_id: driverId.value.trim(),
          distance_km: parseFloat(distance.value),
          duration_minutes: parseInt(duration.value, 10),
          pickup_location: pickup.value,
          dropoff_location: dropoff.value,
          payment_method: method.value,
        },
      });
      renderFareAndPay(resultArea, ride);
    } catch (err) {
      toast(err.message, "error");
    } finally {
      submitBtn.disabled = false;
      submitBtn.textContent = "Complete trip";
    }
  }
}

function renderFareAndPay(container, ride) {
  container.innerHTML = "";

  const amountNode = el("div", { class: "fare-hero__amount num" }, "\u20a60");
  const hero = el("div", { class: "fare-hero" }, [
    el("div", { class: "fare-hero__label" }, "Fare due"),
    amountNode,
  ]);

  const steps = [
    { key: "requested", label: "Requested" },
    { key: "authorized", label: "Authorising" },
    { key: "captured", label: "Captured" },
  ];
  const stepEls = steps.map((s, i) => el("div", { class: `stepper__step ${i === 0 ? "done" : ""}` }, [
    el("div", { class: "stepper__dot" }, String(i + 1)),
    el("div", { class: "stepper__label" }, s.label),
  ]));
  const stepper = el("div", { class: "stepper" }, stepEls);

  const payBtn = el("button", { class: "btn btn-amber btn-block", onclick: onPay }, "Pay now");
  const statusArea = el("div", { class: "mt-6" });

  const card = el("div", { class: "card" }, [hero, stepper, payBtn, statusArea]);
  container.appendChild(card);
  animateCount(amountNode, parseFloat(ride.fare_amount));

  async function onPay() {
    payBtn.disabled = true;
    payBtn.innerHTML = '<span class="spinner"></span> Authorising…';
    stepEls[1].classList.add("active");

    try {
      const txn = await api(`/api/payments/${ride.ride_id}/capture`, {
        method: "POST",
        body: { idempotency_key: idempotencyKey() },
      });

      stepEls[1].classList.remove("active");

      if (txn.status === "success") {
        stepEls[1].classList.add("done");
        stepEls[2].classList.add("done", "active");
        setTimeout(() => stepEls[2].classList.remove("active"), 900);
        statusArea.innerHTML = "";
        statusArea.appendChild(el("div", { class: "banner banner-success" }, [
          el("p", {}, `Payment captured. Transaction ${shortId(txn.transaction_id)} is ready to view.`),
          el("div", { class: "copy-field mt-6" }, [
            el("code", {}, txn.transaction_id),
            el("button", { class: "btn btn-sm", onclick: (e) => copyToClipboard(txn.transaction_id, e.target) }, "Copy"),
          ]),
          el("a", { href: "#/receipt", class: "btn btn-primary mt-6", style: "display:inline-flex" }, "View receipt"),
        ]));
        toast("Payment captured", "success");
        payBtn.style.display = "none";
      } else {
        stepEls[1].classList.add("error");
        statusArea.innerHTML = "";
        statusArea.appendChild(el("div", { class: "banner banner-error" }, "Payment declined by the sandbox gateway — try again or choose a different method."));
        toast("Payment declined", "error");
        payBtn.disabled = false;
        payBtn.textContent = "Try again";
      }
    } catch (err) {
      stepEls[1].classList.add("error");
      toast(err.message, "error");
      payBtn.disabled = false;
      payBtn.textContent = "Try again";
    }
  }
}

// ---- Receipt ------------------------------------------------------------------

function renderReceiptView(view) {
  view.innerHTML = "";

  const input = el("input", { placeholder: "paste a transaction ID" });
  const lookupBtn = el("button", { class: "btn btn-primary", type: "submit" }, "Look up");
  const form = el("form", { class: "card cluster", onsubmit: onLookup }, [
    el("div", { class: "field", style: "flex:1;margin:0" }, [el("label", {}, "Transaction ID"), input]),
    lookupBtn,
  ]);

  const resultArea = el("div", { class: "mt-6" });

  view.append(
    el("div", { class: "page-head" }, [
      el("h1", {}, "Digital receipt"),
      el("p", {}, "Look up any of your captured payments by transaction ID."),
    ]),
    form,
    resultArea
  );

  async function onLookup(e) {
    e.preventDefault();
    const id = input.value.trim();
    if (!id) return;
    lookupBtn.disabled = true;
    resultArea.innerHTML = '<div class="skeleton" style="height:180px"></div>';
    try {
      const r = await api(`/api/receipts/${id}`);
      resultArea.innerHTML = "";
      resultArea.appendChild(el("div", { class: "card stack" }, [
        el("div", { class: "row-item", style: "border:none;padding:0" }, [
          el("div", { class: "row-item__main" }, [el("div", { class: "row-item__title" }, "Fare"), el("div", { class: "row-item__meta" }, r.payment_method)]),
          el("div", { class: "fare-hero__amount num", style: "font-size:32px" }, `\u20a6${formatNaira(r.fare_amount).whole}`),
        ]),
        receiptRow("Ride", shortId(r.ride_id)),
        receiptRow("Status", r.status, r.status === "success" ? "badge-success" : "badge-danger"),
        receiptRow("Reference", r.reference),
        receiptRow("Timestamp", formatDate(r.timestamp)),
      ]));
    } catch (err) {
      resultArea.innerHTML = "";
      resultArea.appendChild(el("div", { class: "banner banner-error" }, err.message));
    } finally {
      lookupBtn.disabled = false;
    }
  }
}

function receiptRow(label, value, badgeClass) {
  return el("div", { class: "row-item", style: "border:none;padding:8px 0" }, [
    el("span", { class: "text-slate text-sm" }, label),
    badgeClass ? el("span", { class: `badge ${badgeClass}` }, value) : el("span", { class: "num", style: "font-weight:600" }, value),
  ]);
}

// ---- Driver profile ------------------------------------------------------------

function renderDriverView(view) {
  view.innerHTML = "";

  view.append(
    el("div", { class: "page-head" }, [
      el("h1", {}, `Hi, ${Session.name || "driver"}`),
      el("p", {}, "Share your driver ID with riders so they can request you. Riders create and pay for trips — this account reviews activity."),
    ]),
    el("div", { class: "card" }, [
      el("div", { class: "field-hint" }, "Your driver ID"),
      el("div", { class: "copy-field mt-6" }, [
        el("code", {}, Session.id),
        el("button", { class: "btn btn-sm", onclick: (e) => copyToClipboard(Session.id, e.target) }, "Copy"),
      ]),
    ])
  );

  const txnSection = el("div", { class: "mt-6" }, [el("div", { class: "skeleton", style: "height:120px" })]);
  view.appendChild(txnSection);

  api("/api/transactions").then(txns => {
    txnSection.innerHTML = "";
    txnSection.appendChild(el("h3", { class: "mt-6", style: "margin-bottom:12px" }, "Recent transactions"));
    if (!txns.length) {
      txnSection.appendChild(el("div", { class: "empty" }, "No trips completed yet — once a rider pays for a trip with you, it shows up here."));
      return;
    }
    const list = el("div", { class: "row-list" });
    txns.slice(0, 10).forEach(t => {
      list.appendChild(el("div", { class: "row-item" }, [
        el("div", { class: "row-item__main" }, [
          el("div", { class: "row-item__title" }, t.transaction_type),
          el("div", { class: "row-item__meta" }, formatDate(t.created_at)),
        ]),
        el("span", { class: `badge ${t.status === "success" ? "badge-success" : "badge-danger"}` }, t.status),
      ]));
    });
    txnSection.appendChild(list);
  }).catch(err => { txnSection.innerHTML = ""; toast(err.message, "error"); });
}

// ---- Admin dashboard --------------------------------------------------------------

function renderAdminView(view) {
  view.innerHTML = "";

  const kpiRow = el("div", { class: "kpi-row" }, [
    kpiSkeleton("Open alerts"), kpiSkeleton("Transactions"), kpiSkeleton("Failed rate"),
  ]);

  const chartCard = el("div", { class: "card chart-card" }, [
    el("h3", {}, "Transaction status (recent)"),
    el("div", { class: "chart-wrap" }, [el("canvas", { id: "txn-chart" })]),
  ]);

  const alertsHead = el("h3", { class: "mt-6", style: "margin-bottom:12px" }, "Open fraud alerts");
  const alertsList = el("div", { class: "row-list" }, [el("div", { class: "skeleton", style: "height:80px" })]);

  const payoutsHead = el("h3", { class: "mt-6", style: "margin-bottom:12px" }, "Driver payouts");
  const payoutsList = el("div", { class: "row-list" }, [el("div", { class: "skeleton", style: "height:80px" })]);

  view.append(
    el("div", { class: "page-head" }, [el("h1", {}, "Admin dashboard"), el("p", {}, "Transaction volume, open fraud alerts, and driver payouts.")]),
    kpiRow, chartCard, alertsHead, alertsList, payoutsHead, payoutsList
  );

  loadAdminData();

  async function loadAdminData() {
    try {
      const [alerts, txns, payouts] = await Promise.all([
        api("/api/admin/fraud-alerts"),
        api("/api/transactions"),
        api("/api/admin/payouts"),
      ]);

      const failed = txns.filter(t => t.status === "failed").length;
      const failedRate = txns.length ? `${Math.round((100 * failed) / txns.length)}%` : "0%";
      kpiRow.innerHTML = "";
      kpiRow.append(kpi(alerts.length, "Open alerts"), kpi(txns.length, "Transactions"), kpi(failedRate, "Failed rate"));

      drawTxnChart(txns);

      alertsList.innerHTML = "";
      if (!alerts.length) {
        alertsList.appendChild(el("div", { class: "empty" }, "No open fraud alerts right now."));
      } else {
        alerts.forEach(a => alertsList.appendChild(alertRow(a)));
      }

      payoutsList.innerHTML = "";
      if (!payouts.length) {
        payoutsList.appendChild(el("div", { class: "empty" }, "No captured payments yet."));
      } else {
        payouts.forEach(p => payoutsList.appendChild(el("div", { class: "row-item" }, [
          el("div", { class: "row-item__main" }, [el("div", { class: "row-item__title" }, p.driver_name)]),
          el("div", { class: "cluster" }, [
            el("span", { class: "text-sm text-slate" }, `Pending \u20a6${p.pending_amount.toLocaleString("en-NG")}`),
            el("span", { class: "badge badge-neutral" }, `Settled \u20a6${p.settled_amount.toLocaleString("en-NG")}`),
          ]),
        ])));
      }
    } catch (err) {
      toast(err.message, "error");
    }
  }

  function alertRow(a) {
    const row = el("div", { class: "row-item" }, [
      el("div", { class: "row-item__main" }, [
        el("div", { class: "row-item__title" }, a.rule_triggered.split(",").join(" + ")),
        el("div", { class: "row-item__meta" }, `risk ${a.risk_score}`),
      ]),
      el("div", { class: "row-item__actions" }, [
        el("button", { class: "btn btn-sm", onclick: () => review(a.alert_id, "cleared", row) }, "Clear"),
        el("button", { class: "btn btn-sm", onclick: () => review(a.alert_id, "confirmed_fraud", row) }, "Confirm fraud"),
      ]),
    ]);
    return row;
  }

  async function review(alertId, status, row) {
    row.style.opacity = "0.5";
    try {
      await api(`/api/admin/fraud-alerts/${alertId}`, { method: "PATCH", body: { review_status: status } });
      toast(status === "cleared" ? "Alert cleared" : "Marked as fraud", "success");
      row.remove();
    } catch (err) {
      row.style.opacity = "1";
      toast(err.message, "error");
    }
  }
}

function kpi(value, label) {
  return el("div", {}, [el("div", { class: "kpi__value num" }, String(value)), el("div", { class: "kpi__label" }, label)]);
}
function kpiSkeleton(label) {
  return el("div", {}, [el("div", { class: "skeleton", style: "height:34px;width:60px;margin-bottom:6px" }), el("div", { class: "kpi__label" }, label)]);
}

let txnChartInstance = null;
function drawTxnChart(txns) {
  const ctx = $("#txn-chart");
  if (!ctx || typeof Chart === "undefined") return;
  const counts = { success: 0, failed: 0, pending: 0 };
  txns.forEach(t => { counts[t.status] = (counts[t.status] || 0) + 1; });

  if (txnChartInstance) txnChartInstance.destroy();
  txnChartInstance = new Chart(ctx, {
    type: "bar",
    data: {
      labels: ["Success", "Failed", "Pending"],
      datasets: [{
        data: [counts.success, counts.failed, counts.pending],
        backgroundColor: ["#1e8e5a", "#d64545", "#f0a202"],
        borderRadius: 6,
        maxBarThickness: 48,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      plugins: { legend: { display: false } },
      scales: {
        y: { beginAtZero: true, ticks: { precision: 0 }, grid: { color: "#e1e4ea" } },
        x: { grid: { display: false } },
      },
    },
  });
}
