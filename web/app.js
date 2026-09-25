// Веб-клієнт TabDB: працює з тим самим REST API (/api/v1), що й десктоп-клієнт.
"use strict";

const API = "/api/v1";

const state = {
  types: {},          // назва типу → підказка формату
  databases: [],      // [{id, name, modified, tables}]
  dbId: null,
  summary: null,      // стан відкритої бази
  tableName: null,
  table: null,        // {name, columns, rows, display}
  selected: null,     // індекс виділеного рядка
};

const $ = (selector, root = document) => root.querySelector(selector);

// --- HTTP ---

class ApiError extends Error {
  constructor(status, body) {
    super(body && body.message ? body.message : `Помилка HTTP ${status}`);
    this.status = status;
    this.kind = body && body.error;
    this.errors = (body && body.errors) || {};
  }
}

async function api(method, path, body) {
  const options = { method, headers: { Accept: "application/json" } };
  if (body !== undefined) {
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  let response;
  try {
    response = await fetch(API + path, options);
  } catch (err) {
    throw new ApiError(0, { message: "Сервер недоступний" });
  }
  const text = await response.text();
  const data = text ? JSON.parse(text) : null;
  if (!response.ok) throw new ApiError(response.status, data);
  return data;
}

const enc = encodeURIComponent;
const dbPath = (...parts) => `/databases/${enc(state.dbId)}` + parts.map((p) => "/" + enc(p)).join("");

// --- рядок стану ---

function status(message, isError = false) {
  const bar = $("#status");
  bar.textContent = message;
  bar.classList.toggle("error", isError);
}

// Обгортка для обробників: помилку показує в рядку стану.
function guarded(fn) {
  return async (...args) => {
    try {
      await fn(...args);
    } catch (err) {
      status(err.message, true);
      if (err.status === 404 && err.kind === "NotFoundError") await reloadAll();
    }
  };
}

// --- завантаження стану ---

async function loadDatabases() {
  state.databases = await api("GET", "/databases");
}

async function openDatabase(id, tableName = null) {
  state.dbId = id;
  state.summary = await api("GET", dbPath());
  const tables = state.summary.tables;
  await openTable(tables.includes(tableName) ? tableName : tables[0] || null);
}

async function refreshSummary() {
  state.summary = await api("GET", dbPath());
  const entry = state.databases.find((db) => db.id === state.dbId);
  if (entry) Object.assign(entry, state.summary);
}

async function openTable(name, selected = null) {
  state.tableName = name;
  state.table = name ? await api("GET", dbPath("tables", name)) : null;
  state.selected = state.table && selected !== null && selected < state.table.rows.length
    ? selected : null;
  render();
}

async function reloadAll() {
  await loadDatabases();
  if (state.dbId && !state.databases.some((db) => db.id === state.dbId)) {
    state.dbId = null;
    state.summary = null;
  }
  if (state.dbId) await openDatabase(state.dbId, state.tableName);
  else await openTable(null);
}

// --- відмальовування ---

function render() {
  renderHeader();
  renderTableList();
  renderTable();
  saveLocation();
}

function renderHeader() {
  const select = $("#db-select");
  select.replaceChildren(new Option(
    state.databases.length ? "— оберіть базу —" : "— баз немає —", ""));
  for (const db of state.databases) select.add(new Option(db.name, db.id));
  select.value = state.dbId || "";

  const badge = $("#db-state");
  badge.hidden = !state.summary;
  if (state.summary) {
    const modified = state.summary.modified;
    badge.textContent = modified ? "● незбережені зміни" : "✓ збережено";
    badge.className = "badge " + (modified ? "modified" : "saved");
    document.title = `${modified ? "* " : ""}${state.summary.name} — TabDB`;
  } else {
    document.title = "TabDB";
  }

  const link = $("#export-link");
  if (state.dbId) link.href = API + dbPath("export");
  else link.removeAttribute("href");

  for (const el of document.querySelectorAll("[data-needs]")) {
    const ok = el.dataset.needs === "db" ? Boolean(state.dbId) : state.selected !== null;
    if (el.tagName === "A") el.setAttribute("aria-disabled", String(!ok));
    else el.disabled = !ok;
  }
}

function renderTableList() {
  const list = $("#table-list");
  list.replaceChildren();
  if (!state.summary) return;
  if (!state.summary.tables.length) {
    const li = document.createElement("li");
    li.className = "none";
    li.textContent = "Таблиць ще немає";
    list.append(li);
    return;
  }
  for (const name of state.summary.tables) {
    const li = document.createElement("li");
    li.textContent = name;
    li.title = name;
    li.classList.toggle("active", name === state.tableName);
    li.addEventListener("click", guarded(() => openTable(name)));
    list.append(li);
  }
}

function renderTable() {
  const panel = $("#table-panel");
  const empty = $("#empty");
  if (!state.table) {
    panel.hidden = true;
    empty.hidden = false;
    empty.textContent = !state.dbId
      ? "Оберіть базу даних угорі, створіть нову або імпортуйте файл *.tdb.json."
      : "Створіть таблицю кнопкою «+ Таблиця».";
    return;
  }
  panel.hidden = false;
  empty.hidden = true;

  const t = state.table;
  $("#table-title").textContent = t.name;
  $("#table-schema").textContent =
    `${t.columns.map((c) => `${c.name}: ${c.type}`).join(", ")} · рядків: ${t.rows.length}`;

  fillGrid($("#grid"), t, (tr, index) => {
    tr.classList.toggle("selected", index === state.selected);
    tr.addEventListener("click", () => selectRow(index));
    tr.addEventListener("dblclick", guarded(() => editRow(index)));
  });
}

// Малює таблицю t у елементі <table>; decorate(tr, index) налаштовує рядок.
function fillGrid(grid, t, decorate) {
  const head = document.createElement("tr");
  head.append(cell("th", "№", "num"));
  for (const col of t.columns) {
    const th = cell("th", col.name);
    const type = document.createElement("span");
    type.className = "type";
    type.textContent = col.type;
    th.append(type);
    head.append(th);
  }

  const body = document.createElement("tbody");
  t.display.forEach((values, index) => {
    const tr = document.createElement("tr");
    tr.append(cell("td", String(index + 1), "num"));
    for (const value of values) tr.append(cell("td", value));
    if (decorate) decorate(tr, index);
    body.append(tr);
  });
  if (!t.display.length) {
    const tr = document.createElement("tr");
    tr.className = "no-rows";
    const td = cell("td", "Рядків немає");
    td.colSpan = t.columns.length + 1;
    tr.append(td);
    body.append(tr);
  }

  const thead = document.createElement("thead");
  thead.append(head);
  grid.replaceChildren(thead, body);
}

function cell(tag, text, className) {
  const el = document.createElement(tag);
  el.textContent = text;
  if (className) el.className = className;
  return el;
}

function selectRow(index) {
  state.selected = index;
  const rows = $("#grid tbody").children;
  for (let i = 0; i < rows.length; i++) rows[i].classList.toggle("selected", i === state.selected);
  renderHeader();
}

// Поточна база й таблиця зберігаються в адресі, щоб оновлення сторінки їх не губило.
function saveLocation() {
  const params = new URLSearchParams();
  if (state.dbId) params.set("db", state.dbId);
  if (state.tableName) params.set("table", state.tableName);
  const hash = params.toString();
  history.replaceState(null, "", hash ? "#" + hash : location.pathname);
}

// --- діалоги ---

// Показує діалог; onOk виконується на «ОК» (кнопкою чи Enter у полі) і закриває
// діалог, якщо не кинув помилку. «Скасувати» має type="button", тож Enter її
// не натискає.
function runDialog(dialog, onOk) {
  const form = $("form", dialog);
  const error = $("[data-error]", dialog);
  const cancel = $("button[value=cancel]", dialog);
  error.textContent = "";

  return new Promise((resolve) => {
    const finish = (value) => {
      form.removeEventListener("submit", onSubmit);
      dialog.removeEventListener("cancel", onCancel);
      cancel.removeEventListener("click", onCancel);
      dialog.close();
      resolve(value);
    };
    const onCancel = (event) => { event.preventDefault(); finish(null); };
    const onSubmit = async (event) => {
      event.preventDefault();
      error.textContent = "";
      try {
        const result = await onOk(form);
        if (result !== undefined) finish(result);
      } catch (err) {
        error.textContent = err.message;
        if (Object.keys(err.errors || {}).length && dialog.onFieldErrors) dialog.onFieldErrors(err.errors);
      }
    };
    form.addEventListener("submit", onSubmit);
    dialog.addEventListener("cancel", onCancel);
    cancel.addEventListener("click", onCancel);
    dialog.showModal();
  });
}

function confirmAction(title, text, okLabel) {
  const dialog = $("#dlg-confirm");
  $("[data-title]", dialog).textContent = title;
  $("[data-text]", dialog).textContent = text;
  $("[data-ok]", dialog).textContent = okLabel;
  return new Promise((resolve) => {
    dialog.returnValue = "";
    dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok"), { once: true });
    dialog.showModal();
  });
}

// --- бази даних ---

async function createDatabase() {
  const dialog = $("#dlg-db");
  const form = $("form", dialog);
  form.reset();
  const summary = await runDialog(dialog, (f) =>
    api("POST", "/databases", { name: f.elements.name.value }));
  if (!summary) return;
  await loadDatabases();
  await openDatabase(summary.id);
  status(`Створено базу «${summary.name}»`);
}

async function importDatabase(file) {
  let data;
  try {
    data = JSON.parse(await file.text());
  } catch {
    throw new Error(`Файл «${file.name}» не є коректним JSON`);
  }
  const summary = await api("POST", "/databases/import", data);
  await loadDatabases();
  await openDatabase(summary.id);
  status(`Базу «${summary.name}» імпортовано з «${file.name}»`);
}

async function saveDatabase() {
  state.summary = await api("POST", dbPath("save"));
  render();
  status(`Базу «${state.summary.name}» збережено на сервері`);
}

async function discardChanges() {
  if (state.summary.modified && !await confirmAction(
    "Скасування змін", "Повернути базу до останнього збереженого стану?", "Скасувати зміни")) return;
  state.summary = await api("POST", dbPath("discard"));
  await loadDatabases();
  await openDatabase(state.dbId, state.tableName);
  status("Незбережені зміни скасовано");
}

async function deleteDatabase() {
  const name = state.summary.name;
  if (!await confirmAction("Видалення бази",
    `Видалити базу «${name}» із сервера разом з усіма таблицями?`, "Видалити")) return;
  await api("DELETE", dbPath());
  state.dbId = null;
  state.summary = null;
  await reloadAll();
  status(`Базу «${name}» видалено`);
}

// --- таблиці ---

function addFieldRow(list, name = "", type = Object.keys(state.types)[0]) {
  const li = document.createElement("li");
  const wrap = document.createElement("div");
  const input = document.createElement("input");
  input.placeholder = "назва поля";
  input.value = name;
  input.required = true;
  const select = document.createElement("select");
  for (const t of Object.keys(state.types)) select.add(new Option(t, t));
  select.value = type;
  const remove = document.createElement("button");
  remove.type = "button";
  remove.textContent = "✕";
  remove.title = "Прибрати поле";
  remove.addEventListener("click", () => {
    if (list.children.length > 1) li.remove();
  });
  wrap.append(input, select, remove);
  li.append(wrap);
  list.append(li);
  return input;
}

async function createTable() {
  const dialog = $("#dlg-table");
  const form = $("form", dialog);
  const list = $("[data-fields]", dialog);
  form.reset();
  list.replaceChildren();
  addFieldRow(list);
  $("[data-add-field]", dialog).onclick = () => addFieldRow(list).focus();

  const table = await runDialog(dialog, (f) => {
    const columns = [...list.children].map((li) => ({
      name: $("input", li).value.trim(),
      type: $("select", li).value,
    }));
    return api("POST", dbPath("tables"), { name: f.elements.name.value, columns });
  });
  if (!table) return;
  await refreshSummary();
  await openTable(table.name);
  status(`Створено таблицю «${table.name}»`);
}

async function dropTable() {
  const name = state.tableName;
  if (!await confirmAction("Видалення таблиці",
    `Видалити таблицю «${name}» разом з усіма рядками?`, "Видалити")) return;
  await api("DELETE", dbPath("tables", name));
  await refreshSummary();
  await openTable(state.summary.tables[0] || null);
  status(`Таблицю «${name}» видалено`);
}

// --- рядки ---

async function editRow(index = null) {
  const t = state.table;
  const dialog = $("#dlg-row");
  const box = $("[data-fields]", dialog);
  $("[data-title]", dialog).textContent =
    index === null ? `Новий рядок · ${t.name}` : `Рядок №${index + 1} · ${t.name}`;

  const inputs = [];
  const hints = [];
  box.replaceChildren();
  t.columns.forEach((col, i) => {
    const label = document.createElement("label");
    const title = document.createElement("span");
    title.className = "field-label";
    title.append(col.name, cell("span", col.type, "type"));
    const input = document.createElement("input");
    input.autocomplete = "off";
    input.value = index === null ? "" : t.display[index][i];
    const hint = cell("span", state.types[col.type] || "", "hint");
    input.addEventListener("input", () => {
      input.classList.remove("invalid");
      hint.textContent = state.types[col.type] || "";
      hint.classList.remove("error");
    });
    label.append(title, input, hint);
    box.append(label);
    inputs.push(input);
    hints.push(hint);
  });

  // Помилки валідації з сервера підсвічуються біля відповідних полів.
  dialog.onFieldErrors = (errors) => {
    for (const [i, message] of Object.entries(errors)) {
      inputs[i].classList.add("invalid");
      hints[i].textContent = message;
      hints[i].classList.add("error");
    }
    inputs[Math.min(...Object.keys(errors).map(Number))].focus();
    $("[data-error]", dialog).textContent = "Виправте виділені поля";
  };

  setTimeout(() => inputs[0] && inputs[0].focus());
  const row = await runDialog(dialog, () => {
    const body = { values: inputs.map((input) => input.value) };
    return index === null
      ? api("POST", dbPath("tables", t.name, "rows"), body)
      : api("PUT", dbPath("tables", t.name, "rows", index), body);
  });
  if (!row) return;
  await refreshSummary();
  await openTable(t.name, row.index);
  status(index === null ? `До таблиці «${t.name}» додано рядок` : `Рядок №${index + 1} оновлено`);
}

async function deleteRow() {
  const index = state.selected;
  if (!await confirmAction("Видалення рядка", `Видалити рядок №${index + 1}?`, "Видалити")) return;
  await api("DELETE", dbPath("tables", state.tableName, "rows", index));
  await refreshSummary();
  await openTable(state.tableName);
  status(`Рядок №${index + 1} видалено`);
}

// --- перетин ---

async function intersect() {
  const tables = state.summary.tables;
  if (tables.length < 2) throw new Error("Для перетину потрібні щонайменше дві таблиці в базі");

  const dialog = $("#dlg-intersect");
  const form = $("form", dialog);
  const { left, right, result, save } = form.elements;
  for (const select of [left, right]) {
    select.replaceChildren(...tables.map((name) => new Option(name, name)));
  }
  left.value = tables.includes(state.tableName) ? state.tableName : tables[0];
  right.value = tables.find((name) => name !== left.value);
  save.checked = true;
  $("[data-preview]", dialog).hidden = true;

  // Назва «A_x_B» підставляється, доки користувач не ввів власну.
  let suggested = "";
  const suggest = () => {
    const name = `${left.value}_x_${right.value}`;
    if (!result.value || result.value === suggested) result.value = name;
    suggested = name;
  };
  result.value = "";
  suggest();
  left.onchange = right.onchange = suggest;

  let changed = false;
  await runDialog(dialog, async () => {
    const outcome = await api("POST", dbPath("intersection"), {
      left: left.value, right: right.value, result: result.value, save: save.checked,
    });
    const t = outcome.table;
    $("[data-preview-title]", dialog).textContent =
      `Результат «${t.name}»: рядків ${t.rows.length}` +
      (outcome.saved ? " — збережено в базі" : " — без збереження");
    fillGrid($("[data-preview-grid]", dialog), t);
    $("[data-preview]", dialog).hidden = false;
    if (outcome.saved) {
      changed = true;
      await refreshSummary();
      renderTableList();
      renderHeader();
    }
    status(`Перетин «${left.value}» ∩ «${right.value}»: ${t.rows.length} рядків`);
    // Діалог лишається відкритим, щоб показати результат.
  });
  if (changed) await openTable(state.tableName);
}

// --- ініціалізація ---

const actions = {
  "create-db": createDatabase,
  "import-db": () => $("#import-file").click(),
  "save-db": saveDatabase,
  "discard-db": discardChanges,
  "delete-db": deleteDatabase,
  "create-table": createTable,
  "drop-table": dropTable,
  "add-row": () => editRow(null),
  "edit-row": () => editRow(state.selected),
  "delete-row": deleteRow,
  "intersect": intersect,
};

function bindEvents() {
  for (const button of document.querySelectorAll("[data-action]")) {
    button.addEventListener("click", guarded(actions[button.dataset.action]));
  }
  $("#import-file").addEventListener("change", guarded(async (event) => {
    const file = event.target.files[0];
    event.target.value = "";
    if (file) await importDatabase(file);
  }));
  $("#db-select").addEventListener("change", guarded(async (event) => {
    const id = event.target.value;
    if (id) {
      await openDatabase(id);
      status(`Відкрито базу «${state.summary.name}»`);
    } else {
      state.dbId = null;
      state.summary = null;
      await openTable(null);
    }
  }));
  document.addEventListener("keydown", (event) => {
    if (document.querySelector("dialog[open]") || state.selected === null) return;
    if (event.target.matches("input, select, button, a")) return;
    const action = { Enter: "edit-row", Delete: "delete-row" }[event.key];
    if (!action) return;
    // Інакше те саме натискання Enter потрапить у щойно відкриту форму.
    event.preventDefault();
    guarded(actions[action])();
  });
}

async function init() {
  bindEvents();
  const types = await api("GET", "/types");
  for (const t of types) state.types[t.name] = t.hint;
  await loadDatabases();

  const params = new URLSearchParams(location.hash.slice(1));
  const id = params.get("db");
  if (id && state.databases.some((db) => db.id === id)) {
    await openDatabase(id, params.get("table"));
  } else {
    render();
  }
  status(`Підключено до сервера · баз: ${state.databases.length}`);
}

guarded(init)();
