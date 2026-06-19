let state = null;
let config = null;
let entities = [];

const $ = (selector) => document.querySelector(selector);
const views = ["setup", "rules", "live", "log", "manual"];

document.querySelectorAll(".tabs button").forEach((button) => {
  button.addEventListener("click", () => {
    document.querySelectorAll(".tabs button").forEach((item) => item.classList.remove("active"));
    document.querySelectorAll(".view").forEach((item) => item.classList.remove("active"));
    button.classList.add("active");
    $(`#${button.dataset.tab}`).classList.add("active");
  });
});

async function api(path, options = {}) {
  const response = await fetch(`./api${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

function entityInput(label, path, domain, selected = "") {
  const listId = `entities-${path.replace(/\./g, "-")}`;
  const matching = entities.filter((entity) => entity.entity_id.startsWith(`${domain}.`));
  return `
    <label>${label}
      <input data-path="${path}" value="${escapeHtml(selected)}" list="${listId}" placeholder="${domain}.">
      <datalist id="${listId}">
        ${matching.map((entity) => `<option value="${escapeHtml(entity.entity_id)}">${escapeHtml(entity.attributes?.friendly_name || entity.entity_id)}</option>`).join("")}
      </datalist>
    </label>
  `;
}

function setpointInput(label, path, selected = "") {
  const listId = `entities-${path.replace(/\./g, "-")}`;
  const matching = entities.filter((entity) => entity.entity_id.startsWith("number.") || entity.entity_id.startsWith("input_number."));
  return `
    <label>${label}
      <input data-path="${path}" value="${escapeHtml(selected)}" list="${listId}" placeholder="number. oder input_number.">
      <datalist id="${listId}">
        ${matching.map((entity) => `<option value="${escapeHtml(entity.entity_id)}">${escapeHtml(entity.attributes?.friendly_name || entity.entity_id)}</option>`).join("")}
      </datalist>
    </label>
  `;
}

function setByPath(target, path, value) {
  const parts = path.split(".");
  let cursor = target;
  while (parts.length > 1) {
    cursor = cursor[parts.shift()];
  }
  const key = parts[0];
  const old = cursor[key];
  if (typeof old === "number") cursor[key] = Number(value);
  else if (typeof old === "boolean") cursor[key] = value === "true" || value === true;
  else cursor[key] = value;
}

async function saveConfig() {
  document.querySelectorAll("[data-path]").forEach((input) => setByPath(config, input.dataset.path, input.value));
  document.querySelectorAll("[data-bool]").forEach((input) => setByPath(config, input.dataset.bool, input.checked));
  config = await api("/config", { method: "PUT", body: JSON.stringify(config) });
  render();
}

function renderBadges() {
  const decision = state?.latest_decision;
  const control = config?.control;
  $("#subtitle").textContent = control?.dry_run ? "Dry Run aktiv" : "Schreibzugriffe aktiv";
  $("#statusStrip").innerHTML = [
    `<span class="badge ${control?.dry_run ? "warn" : "ok"}">${control?.dry_run ? "Dry Run" : "Live"}</span>`,
    `<span class="badge ${decision?.failsafe ? "danger" : "ok"}">${decision?.failsafe ? "Failsafe" : "Bereit"}</span>`,
    `<span class="badge ${control?.manual_override ? "warn" : "ok"}">${control?.manual_override ? "Manuell" : "Automatik"}</span>`,
  ].join("");
}

function renderSetup() {
  $("#setup").innerHTML = `
    <div class="grid">
      <section class="panel">
        <h2>Smart Meter</h2>
        <div class="form-grid">
          ${entityInput("Netzbezug", "smart_meter.import_power_entity", "sensor", config.smart_meter.import_power_entity)}
          ${entityInput("Netzeinspeisung", "smart_meter.export_power_entity", "sensor", config.smart_meter.export_power_entity)}
        </div>
      </section>
      ${config.banks.map((bank, index) => `
        <section class="panel">
          <h2>${bank.name}</h2>
          <div class="form-grid">
            <label>Name <input data-path="banks.${index}.name" value="${bank.name}"></label>
            <label>Kapazitaet Wh <input type="number" data-path="banks.${index}.capacity_wh" value="${bank.capacity_wh}"></label>
            ${entityInput("SOC", `banks.${index}.soc_entity`, "sensor", bank.soc_entity)}
            ${entityInput("PV-Leistung", `banks.${index}.pv_power_entity`, "sensor", bank.pv_power_entity)}
            ${entityInput("AC-Ist-Leistung", `banks.${index}.ac_output_entity`, "sensor", bank.ac_output_entity)}
            ${setpointInput("Einspeisevorgabe", `banks.${index}.setpoint_entity`, bank.setpoint_entity)}
            <label>Stellwert-Domain
              <select data-path="banks.${index}.setpoint_domain">
                <option value="number" ${bank.setpoint_domain === "number" ? "selected" : ""}>number</option>
                <option value="input_number" ${bank.setpoint_domain === "input_number" ? "selected" : ""}>input_number</option>
              </select>
            </label>
            <label>Max. Leistung W <input type="number" data-path="banks.${index}.max_output_w" value="${bank.max_output_w}"></label>
            <label><span>Smart-Meter-Steuerung</span><input type="checkbox" data-bool="banks.${index}.smart_meter_control" ${bank.smart_meter_control ? "checked" : ""}></label>
          </div>
        </section>
      `).join("")}
      <section class="panel actions">
        <button class="primary" id="saveSetup">Speichern</button>
        <button class="secondary" id="loadEntities">Entities neu laden</button>
      </section>
    </div>
  `;
  $("#saveSetup").addEventListener("click", saveConfig);
  $("#loadEntities").addEventListener("click", loadEntities);
}

function renderRules() {
  const c = config.control;
  const rows = [
    ["Modus", "mode", c.mode, "select"],
    ["Durchschnittsfenster min", "window_minutes", c.window_minutes, "number"],
    ["Kurzzeitfenster min", "short_window_minutes", c.short_window_minutes, "number"],
    ["Regelintervall s", "regulation_interval_seconds", c.regulation_interval_seconds, "number"],
    ["Sicherheitsreserve W", "safety_grid_import_reserve_w", c.safety_grid_import_reserve_w, "number"],
    ["Globales Limit W", "global_output_limit_w", c.global_output_limit_w, "number"],
    ["Totband W", "deadband_w", c.deadband_w, "number"],
    ["Max. Schritt W", "max_step_w", c.max_step_w, "number"],
    ["Min-SOC %", "min_soc_percent", c.min_soc_percent, "number"],
    ["Ziel-Max-SOC %", "target_max_soc_percent", c.target_max_soc_percent, "number"],
  ];
  $("#rules").innerHTML = `
    <section class="panel">
      <h2>Regelparameter</h2>
      <div class="form-grid">
        ${rows.map(([label, key, value, type]) => type === "select"
          ? `<label>${label}<select data-path="control.${key}">
              <option value="b14_leader_b16_follower" ${value === "b14_leader_b16_follower" ? "selected" : ""}>B14 Fuehrung, B16 Rest</option>
              <option value="central" ${value === "central" ? "selected" : ""}>Zentrale Steuerung</option>
            </select></label>`
          : `<label>${label}<input type="number" data-path="control.${key}" value="${value}"></label>`
        ).join("")}
        <label><span>Dry Run</span><input type="checkbox" data-bool="control.dry_run" ${c.dry_run ? "checked" : ""}></label>
      </div>
      <div class="actions"><button class="primary" id="saveRules">Speichern</button></div>
    </section>
  `;
  $("#saveRules").addEventListener("click", saveConfig);
}

function metric(label, value, suffix = "W") {
  return `<article class="card"><h3>${label}</h3><div class="metric">${Math.round(value ?? 0)} ${suffix}</div></article>`;
}

function renderLive() {
  const measurement = state?.latest_measurement;
  const decision = state?.latest_decision;
  $("#live").innerHTML = `
    <div class="grid">
      ${metric("Hausverbrauch", measurement?.house_consumption_w)}
      ${metric("Netzbezug", measurement?.grid_import_w)}
      ${metric("Netzeinspeisung", measurement?.grid_export_w)}
      ${metric("Ziel gesamt", decision?.calculated?.target_total_w)}
      ${(decision?.banks ?? []).map((bank) => `
        <article class="card third">
          <h3>${bank.name}</h3>
          <p>Ziel</p><div class="metric">${Math.round(bank.final_target_w)} W</div>
          <p>${bank.discharge_allowed ? "Entladung erlaubt" : bank.reason || "gesperrt"}</p>
        </article>
      `).join("")}
    </div>
  `;
}

function renderLog() {
  $("#log").innerHTML = `
    <div class="list">
      ${(state?.decisions ?? []).map((decision) => `
        <section class="panel decision ${decision.failsafe ? "failsafe" : ""}">
          <h2>${new Date(decision.time).toLocaleString()}</h2>
          <p>${decision.rules.join(" · ")}</p>
          <pre>${JSON.stringify(decision, null, 2)}</pre>
        </section>
      `).join("") || `<section class="panel"><h2>Noch keine Entscheidungen</h2></section>`}
    </div>
  `;
}

function renderManual() {
  $("#manual").innerHTML = `
    <div class="grid">
      <section class="panel half">
        <h2>Automatik</h2>
        <div class="actions">
          <button class="secondary" id="toggleOverride">${config.control.manual_override ? "Automatik fortsetzen" : "Automatik pausieren"}</button>
          <button class="secondary" id="toggleDryRun">${config.control.dry_run ? "Schreiben aktivieren" : "Dry Run aktivieren"}</button>
          <button class="danger" id="stop">Not-Aus</button>
        </div>
      </section>
      <section class="panel half">
        <h2>Manueller Stellwert</h2>
        <div class="form-grid">
          <label>Bank <select id="manualBank">${config.banks.map((bank) => `<option>${bank.name}</option>`).join("")}</select></label>
          <label>Wert W <input id="manualValue" type="number" value="0"></label>
        </div>
        <div class="actions"><button class="primary" id="setManual">Setzen</button></div>
      </section>
      <section class="panel">
        <h2>Import / Export</h2>
        <textarea id="configJson">${JSON.stringify(config, null, 2)}</textarea>
        <div class="actions"><button class="primary" id="importConfig">Importieren</button></div>
      </section>
    </div>
  `;
  $("#toggleOverride").addEventListener("click", async () => {
    await api(`/override?enabled=${!config.control.manual_override}`, { method: "POST" });
    await load();
  });
  $("#toggleDryRun").addEventListener("click", async () => {
    await api(`/dry-run?enabled=${!config.control.dry_run}`, { method: "POST" });
    await load();
  });
  $("#stop").addEventListener("click", async () => {
    await api("/emergency-stop", { method: "POST" });
    await load();
  });
  $("#setManual").addEventListener("click", async () => {
    await api("/manual-setpoint", {
      method: "POST",
      body: JSON.stringify({ bank: $("#manualBank").value, value_w: Number($("#manualValue").value) }),
    });
    await load();
  });
  $("#importConfig").addEventListener("click", async () => {
    config = JSON.parse($("#configJson").value);
    await api("/config", { method: "PUT", body: JSON.stringify(config) });
    await load();
  });
}

function render() {
  if (!config) return;
  renderBadges();
  renderSetup();
  renderRules();
  renderLive();
  renderLog();
  renderManual();
}

async function loadEntities() {
  try {
    entities = await api("/entities");
  } catch {
    entities = [];
  }
  render();
}

async function load() {
  state = await api("/state");
  config = state.config;
  render();
}

function connectWs() {
  const protocol = location.protocol === "https:" ? "wss" : "ws";
  const wsUrl = new URL("./api/ws", window.location.href);
  wsUrl.protocol = protocol;
  const ws = new WebSocket(wsUrl);
  ws.onmessage = (event) => {
    state = JSON.parse(event.data);
    config = state.config;
    render();
  };
  ws.onclose = () => setTimeout(connectWs, 3000);
}

await load();
await loadEntities();
connectWs();
