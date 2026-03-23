/**
 * DockView — Main Application JS
 * Vanilla JS SPA — no framework needed.
 * 2026: clean, fast, modular.
 */

// ── State ────────────────────────────────────────────────────
const state = {
  databases: [],
  activeDbId: null,
  activeSchema: null,
  activeTable: null,
  schemas: [],
  tables: [],
  preview: null,
  page: 0,
  pageSize: 50,
  schemaColumns: null,
};

// ── DOM refs ──────────────────────────────────────────────────
const $ = (sel) => document.querySelector(sel);
const $$ = (sel) => [...document.querySelectorAll(sel)];

// ── Init ──────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded', () => {
  initUI();
  checkDockerStatus();
  loadDatabases();
  startEventStream();
  registerServiceWorker();
});

function initUI() {
  // Theme toggle
  $('#theme-btn').addEventListener('click', toggleTheme);

  // Refresh button
  $('#refresh-btn').addEventListener('click', async () => {
    const btn = $('#refresh-btn');
    btn.classList.add('spinning');
    await fetch('/api/containers/refresh', { method: 'POST' });
    await loadDatabases();
    btn.classList.remove('spinning');
    toast('Containers refreshed', 'success');
  });

  // Tabs
  $$('.tab').forEach(tab => {
    tab.addEventListener('click', () => switchTab(tab.dataset.tab));
  });

  // Reconnect
  $('#panel-reconnect-btn').addEventListener('click', showCredModal);

  // Modal close
  $('#cred-modal-close').addEventListener('click', hideCredModal);
  $('#cred-cancel').addEventListener('click', hideCredModal);
  $('#cred-save').addEventListener('click', saveCredentials);

  // Pagination
  $('#pg-prev').addEventListener('click', () => changePage(-1));
  $('#pg-next').addEventListener('click', () => changePage(1));

  // CSV export
  $('#btn-copy-csv').addEventListener('click', copyTableCSV);

  // Global search
  let searchDebounce;
  $('#global-search').addEventListener('input', (e) => {
    clearTimeout(searchDebounce);
    searchDebounce = setTimeout(() => filterDatabases(e.target.value), 200);
  });

  // Keyboard shortcut
  document.addEventListener('keydown', (e) => {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
      e.preventDefault();
      $('#global-search').focus();
    }
    if (e.key === 'Escape') {
      hideCredModal();
      $('#global-search').blur();
    }
  });

  // Modal backdrop close
  $('#cred-modal').addEventListener('click', (e) => {
    if (e.target === $('#cred-modal')) hideCredModal();
  });
}

// ── Theme ─────────────────────────────────────────────────────
function toggleTheme() {
  const html = document.documentElement;
  const current = html.getAttribute('data-theme');
  const next = current === 'dark' ? 'light' : 'dark';
  html.setAttribute('data-theme', next);
  localStorage.setItem('dv-theme', next);
}

// Load saved theme
const savedTheme = localStorage.getItem('dv-theme') || 'dark';
document.documentElement.setAttribute('data-theme', savedTheme);

// ── Docker Status ─────────────────────────────────────────────
async function checkDockerStatus() {
  try {
    const res = await fetch('/api/containers/status');
    const data = await res.json();
    const pill = $('#docker-status');
    const dot = pill.querySelector('.status-dot');
    const label = pill.querySelector('.status-label');

    if (data.connected) {
      dot.className = 'status-dot connected';
      label.textContent = `Docker · ${data.db_count} DB${data.db_count !== 1 ? 's' : ''}`;
      $('#no-docker-warning')?.classList.add('hidden');
    } else {
      dot.className = 'status-dot error';
      label.textContent = 'Docker unavailable';
      $('#no-docker-warning')?.classList.remove('hidden');
    }
  } catch {
    const dot = $('#docker-status .status-dot');
    if (dot) dot.className = 'status-dot error';
  }
}

// ── Load Databases ────────────────────────────────────────────
async function loadDatabases() {
  try {
    const res = await fetch('/api/databases');
    if (!res.ok) throw new Error('API error');
    const dbs = await res.json();
    state.databases = dbs;
    renderDbList(dbs);
    $('#db-count').textContent = dbs.length;

    if (dbs.length === 0) {
      showWelcome();
    }
  } catch (err) {
    console.error('loadDatabases:', err);
    renderDbList([]);
  }
}

function renderDbList(dbs) {
  const list = $('#db-list');
  if (!dbs.length) {
    list.innerHTML = `<div class="empty-state-sidebar">
      <span style="font-size:24px">🔍</span>
      <span>No databases found</span>
    </div>`;
    return;
  }

  list.innerHTML = dbs.map(db => `
    <div class="db-item" data-id="${db.id}" style="--db-color: ${db.color}"
         role="button" tabindex="0">
      <span class="db-item-icon">${db.icon}</span>
      <div class="db-item-info">
        <div class="db-item-name">${escHtml(db.name)}</div>
        <div class="db-item-sub">${escHtml(db.display_name)} · :${db.port}</div>
      </div>
      <div class="db-item-status ${db.status}"></div>
    </div>
  `).join('');

  list.querySelectorAll('.db-item').forEach(el => {
    el.addEventListener('click', () => selectDatabase(el.dataset.id));
    el.addEventListener('keydown', (e) => {
      if (e.key === 'Enter' || e.key === ' ') selectDatabase(el.dataset.id);
    });
  });

  // Re-highlight active
  if (state.activeDbId) {
    list.querySelector(`[data-id="${state.activeDbId}"]`)?.classList.add('active');
  }
}

function filterDatabases(query) {
  const q = query.toLowerCase();
  const filtered = q
    ? state.databases.filter(d =>
        d.name.toLowerCase().includes(q) ||
        d.type.toLowerCase().includes(q) ||
        d.display_name.toLowerCase().includes(q)
      )
    : state.databases;
  renderDbList(filtered);
}

// ── Select Database ───────────────────────────────────────────
async function selectDatabase(dbId) {
  state.activeDbId = dbId;
  state.activeSchema = null;
  state.activeTable = null;

  // Highlight
  $$('.db-item').forEach(el => el.classList.toggle('active', el.dataset.id === dbId));

  const db = state.databases.find(d => d.id === dbId);
  if (!db) return;

  showDbPanel(db);
  switchTab('explorer');
  await loadSchemas(dbId, db);
}

function showWelcome() {
  $('#welcome-screen').classList.remove('hidden');
  $('#db-panel').classList.add('hidden');
}

function showDbPanel(db) {
  $('#welcome-screen').classList.add('hidden');
  $('#db-panel').classList.remove('hidden');

  // Header
  const badge = $('#panel-db-badge');
  badge.textContent = db.icon;
  badge.style.background = hexToAlpha(db.color, 0.15);

  $('#panel-db-name').textContent = db.name;
  $('#panel-db-meta').textContent = `${db.display_name} · ${db.host}:${db.port} · ${db.image}`;
}

// ── Schemas ───────────────────────────────────────────────────
async function loadSchemas(dbId, db) {
  const list = $('#schema-list');
  list.innerHTML = '<div class="mini-spinner"></div>';

  try {
    const res = await fetch(`/api/databases/${dbId}/schemas`);
    if (!res.ok) {
      if (res.status === 500) {
        const err = await res.json();
        list.innerHTML = renderConnError(err.detail, dbId);
        attachConnErrorActions(list, dbId);
        return;
      }
      throw new Error('Failed to load schemas');
    }
    const schemas = await res.json();
    state.schemas = schemas;
    renderSchemaList(schemas, dbId);

    // Auto-select first
    if (schemas.length > 0) {
      selectSchema(dbId, schemas[0]);
    }
  } catch (err) {
    list.innerHTML = renderConnError(err.message, dbId);
    attachConnErrorActions(list, dbId);
  }
}

function renderConnError(msg, dbId) {
  return `
    <div class="conn-error">
      <span class="err-icon">🔌</span>
      <strong>Connection failed</strong>
      <p>${escHtml(msg || 'Could not connect to the database.')}</p>
      <button class="btn-ghost" data-action="creds">Enter credentials</button>
    </div>
  `;
}

function attachConnErrorActions(container, dbId) {
  container.querySelector('[data-action="creds"]')?.addEventListener('click', () => {
    showCredModal();
  });
}

function renderSchemaList(schemas, dbId) {
  const list = $('#schema-list');
  if (!schemas.length) {
    list.innerHTML = '<div class="empty-hint">No schemas found</div>';
    return;
  }
  list.innerHTML = schemas.map(s => `
    <div class="schema-item" data-schema="${escHtml(s)}">${escHtml(s)}</div>
  `).join('');

  list.querySelectorAll('.schema-item').forEach(el => {
    el.addEventListener('click', () => selectSchema(dbId, el.dataset.schema));
  });
}

async function selectSchema(dbId, schema) {
  state.activeSchema = schema;
  state.activeTable = null;

  $$('.schema-item').forEach(el =>
    el.classList.toggle('active', el.dataset.schema === schema)
  );

  await loadTables(dbId, schema);
}

// ── Tables ────────────────────────────────────────────────────
async function loadTables(dbId, schema) {
  const list = $('#table-list');
  list.innerHTML = '<div class="mini-spinner"></div>';
  $('#table-panel-title').textContent = 'Tables';
  $('#table-count').textContent = '';

  try {
    const res = await fetch(`/api/databases/${dbId}/schemas/${encodeURIComponent(schema)}/tables`);
    if (!res.ok) throw new Error('Failed to load tables');
    const tables = await res.json();
    state.tables = tables;
    renderTableList(tables, dbId, schema);
    $('#table-count').textContent = tables.length;
  } catch (err) {
    list.innerHTML = `<div class="empty-hint">Error: ${escHtml(err.message)}</div>`;
  }
}

function renderTableList(tables, dbId, schema) {
  const list = $('#table-list');
  if (!tables.length) {
    list.innerHTML = '<div class="empty-hint">No tables found</div>';
    return;
  }

  const maxRows = Math.max(...tables.map(t => t.row_count || 0), 1);

  list.innerHTML = tables.map(t => {
    const pct = maxRows > 0 ? Math.round(((t.row_count || 0) / maxRows) * 100) : 0;
    const icon = t.collection_type === 'view' ? '👁' : t.collection_type === 'collection' ? '◎' : '▦';
    return `
      <div class="table-item" data-table="${escHtml(t.name)}">
        <div class="table-item-name">
          <span class="type-icon">${icon}</span>
          ${escHtml(t.name)}
        </div>
        <div class="table-item-meta">
          ${t.row_count !== null ? fmtNum(t.row_count) + ' rows' : ''}
          ${t.size_bytes ? ' · ' + fmtBytes(t.size_bytes) : ''}
        </div>
        <div class="table-size-bar">
          <div class="table-size-fill" style="width:${pct}%"></div>
        </div>
      </div>
    `;
  }).join('');

  list.querySelectorAll('.table-item').forEach(el => {
    el.addEventListener('click', () => {
      $$('.table-item').forEach(i => i.classList.remove('active'));
      el.classList.add('active');
      selectTable(dbId, schema, el.dataset.table);
    });
  });
}

// ── Preview ───────────────────────────────────────────────────
async function selectTable(dbId, schema, table) {
  state.activeTable = table;
  state.page = 0;
  await loadPreview(dbId, schema, table);
  await loadSchemaView(dbId, schema, table);
}

async function loadPreview(dbId, schema, table, page = 0) {
  const wrap = $('#data-table-wrap');
  wrap.innerHTML = '<div style="padding:20px;display:flex;justify-content:center"><div class="spinner"></div></div>';

  $('#data-panel-table-name').textContent = table;
  const offset = page * state.pageSize;

  try {
    const res = await fetch(
      `/api/databases/${dbId}/schemas/${encodeURIComponent(schema)}/tables/${encodeURIComponent(table)}/preview?limit=${state.pageSize}&offset=${offset}`
    );
    if (!res.ok) throw new Error((await res.json()).detail || 'Preview failed');
    const preview = await res.json();
    state.preview = preview;
    renderDataTable(preview, offset);
    updatePagination(preview, page);
  } catch (err) {
    wrap.innerHTML = `<div class="conn-error">
      <span class="err-icon">⚠</span>
      <strong>Preview failed</strong>
      <p>${escHtml(err.message)}</p>
    </div>`;
  }
}

function renderDataTable(preview, offset) {
  const wrap = $('#data-table-wrap');
  if (!preview.rows?.length) {
    wrap.innerHTML = '<div class="select-table-hint"><span>Table is empty</span></div>';
    return;
  }

  const cols = preview.columns;
  const rows = preview.rows;

  const thead = `<thead><tr>
    <th class="row-num">#</th>
    ${cols.map(c => `
      <th class="${c.is_primary_key ? 'pk' : ''}">
        ${escHtml(c.name)}
        <span class="col-type">${escHtml(c.data_type)}</span>
        ${c.is_primary_key ? ' 🔑' : ''}
      </th>
    `).join('')}
  </tr></thead>`;

  const tbody = `<tbody>${rows.map((row, ri) => `
    <tr>
      <td class="row-num">${offset + ri + 1}</td>
      ${row.map((cell, ci) => {
        const cls = classifyCell(cell, cols[ci]);
        const display = cell === null || cell === undefined ? 'NULL' : escHtml(String(cell));
        return `<td class="${cls}" title="${escHtml(String(cell ?? ''))}">${display}</td>`;
      }).join('')}
    </tr>
  `).join('')}</tbody>`;

  wrap.innerHTML = `<table class="data-table">${thead}${tbody}</table>`;
  $('#data-row-count').textContent = `${fmtNum(preview.total_rows)} rows`;
}

function classifyCell(val, col) {
  if (val === null || val === undefined) return 'null-val';
  if (col?.is_primary_key) return 'pk-val';
  if (typeof val === 'number' || (typeof val === 'string' && !isNaN(Number(val)) && val !== '')) return 'num-val';
  if (val === 'true' || val === 'false' || val === true || val === false) return 'bool-val';
  return '';
}

function updatePagination(preview, page) {
  const total = preview.total_rows || 0;
  const totalPages = Math.ceil(total / state.pageSize);
  const start = page * state.pageSize + 1;
  const end = Math.min((page + 1) * state.pageSize, total);

  $('#pg-info').textContent = total > 0 ? `${start}–${end} / ${fmtNum(total)}` : '0';
  $('#pg-prev').disabled = page <= 0;
  $('#pg-next').disabled = page >= totalPages - 1;
  state.page = page;
}

function changePage(delta) {
  const newPage = state.page + delta;
  if (!state.activeDbId || !state.activeSchema || !state.activeTable) return;
  loadPreview(state.activeDbId, state.activeSchema, state.activeTable, newPage);
}

// ── Schema View ───────────────────────────────────────────────
async function loadSchemaView(dbId, schema, table) {
  const wrap = $('#schema-view-wrap');
  wrap.innerHTML = '<div class="mini-spinner"></div>';

  try {
    const res = await fetch(
      `/api/databases/${dbId}/schemas/${encodeURIComponent(schema)}/tables/${encodeURIComponent(table)}/columns`
    );
    if (!res.ok) throw new Error('Failed to load columns');
    const cols = await res.json();

    wrap.innerHTML = `
      <div class="schema-table-card">
        <div class="schema-table-card-header">
          <span style="font-size:16px">▦</span>
          <strong>${escHtml(table)}</strong>
          <span class="count-badge">${cols.length} columns</span>
        </div>
        <table class="schema-cols-table">
          <thead><tr>
            <th>Column</th>
            <th>Type</th>
            <th>Nullable</th>
            <th>Default</th>
            <th>Key</th>
          </tr></thead>
          <tbody>
            ${cols.map(c => `
              <tr>
                <td class="${c.is_primary_key ? 'pk-col' : ''}">${escHtml(c.name)}</td>
                <td class="type-col">${escHtml(c.data_type)}</td>
                <td>${c.nullable ? '<span style="color:var(--text-3)">YES</span>' : 'NO'}</td>
                <td style="color:var(--text-3)">${escHtml(c.default || '—')}</td>
                <td>${c.is_primary_key ? '🔑 PK' : ''}</td>
              </tr>
            `).join('')}
          </tbody>
        </table>
      </div>
    `;
  } catch (err) {
    wrap.innerHTML = `<div class="empty-hint">Could not load schema: ${escHtml(err.message)}</div>`;
  }
}

// ── Server Info ───────────────────────────────────────────────
async function loadServerInfo(dbId) {
  const wrap = $('#server-info-wrap');
  wrap.innerHTML = '<div class="mini-spinner"></div>';

  const db = state.databases.find(d => d.id === dbId);

  try {
    const res = await fetch(`/api/databases/${dbId}/info`);
    if (!res.ok) throw new Error('Failed to load info');
    const info = await res.json();

    wrap.innerHTML = `
      <div class="info-card">
        <div class="info-card-title">CONTAINER</div>
        ${infoRow('Container name', db?.container_name || '—')}
        ${infoRow('Image', db?.image || '—')}
        ${infoRow('Host', db?.host || '—')}
        ${infoRow('Port', db?.port || '—')}
        ${infoRow('Status', db?.status || '—')}
      </div>
      <div class="info-card">
        <div class="info-card-title">SERVER</div>
        ${Object.entries(info).map(([k, v]) => infoRow(k, v)).join('')}
      </div>
    `;
  } catch (err) {
    wrap.innerHTML = `<div class="conn-error">
      <span class="err-icon">⚠</span>
      <strong>Could not load server info</strong>
      <p>${escHtml(err.message)}</p>
    </div>`;
  }
}

function infoRow(k, v) {
  return `<div class="info-row">
    <span class="info-key">${escHtml(String(k))}</span>
    <span class="info-val">${escHtml(String(v))}</span>
  </div>`;
}

// ── Tabs ──────────────────────────────────────────────────────
function switchTab(name) {
  $$('.tab').forEach(t => t.classList.toggle('active', t.dataset.tab === name));
  $$('.tab-content').forEach(c => c.classList.toggle('active', c.id === `tab-${name}`));

  if (name === 'info' && state.activeDbId) {
    loadServerInfo(state.activeDbId);
  }
}

// ── Credentials Modal ─────────────────────────────────────────
function showCredModal() {
  const db = state.databases.find(d => d.id === state.activeDbId);
  if (db) {
    $('#cred-host').value = db.host;
    $('#cred-port').value = db.port;
  }
  $('#cred-modal').classList.remove('hidden');
}

function hideCredModal() {
  $('#cred-modal').classList.add('hidden');
}

async function saveCredentials() {
  const dbId = state.activeDbId;
  if (!dbId) return;

  const creds = {
    host: $('#cred-host').value || undefined,
    port: parseInt($('#cred-port').value) || undefined,
    user: $('#cred-user').value || undefined,
    password: $('#cred-pass').value || undefined,
    database: $('#cred-db').value || undefined,
  };

  try {
    const res = await fetch(`/api/databases/${dbId}/connect`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(creds),
    });
    const data = await res.json();
    if (data.connected) {
      toast('Connected successfully', 'success');
      hideCredModal();
      const db = state.databases.find(d => d.id === dbId);
      if (db) await loadSchemas(dbId, db);
    } else {
      toast('Connection failed — check credentials', 'error');
    }
  } catch {
    toast('Network error', 'error');
  }
}

// ── CSV Export ────────────────────────────────────────────────
function copyTableCSV() {
  const preview = state.preview;
  if (!preview) return;

  const header = preview.columns.map(c => c.name).join(',');
  const rows = preview.rows.map(row =>
    row.map(cell => {
      if (cell === null) return '';
      const s = String(cell);
      return s.includes(',') || s.includes('"') || s.includes('\n')
        ? `"${s.replace(/"/g, '""')}"`
        : s;
    }).join(',')
  );
  const csv = [header, ...rows].join('\n');

  navigator.clipboard.writeText(csv).then(() => {
    toast(`Copied ${preview.rows.length} rows as CSV`, 'success');
  }).catch(() => {
    toast('Clipboard not available', 'error');
  });
}

// ── SSE: live updates ─────────────────────────────────────────
function startEventStream() {
  const es = new EventSource('/api/events');
  es.onmessage = (e) => {
    const data = JSON.parse(e.data);
    if (data.count !== state.databases.length) {
      loadDatabases();
      checkDockerStatus();
    }
    // Update statuses
    data.databases.forEach(update => {
      const db = state.databases.find(d => d.id === update.id);
      if (db && db.status !== update.status) {
        db.status = update.status;
        const dot = document.querySelector(`.db-item[data-id="${update.id}"] .db-item-status`);
        if (dot) dot.className = `db-item-status ${update.status}`;
      }
    });
  };
  es.onerror = () => {
    setTimeout(startEventStream, 5000);
  };
}

// ── PWA ───────────────────────────────────────────────────────
function registerServiceWorker() {
  if ('serviceWorker' in navigator) {
    navigator.serviceWorker.register('/static/sw.js').catch(() => {});
  }
}

// ── Toast notifications ───────────────────────────────────────
function toast(msg, type = 'info') {
  const container = $('#toasts');
  const el = document.createElement('div');
  el.className = `toast ${type}`;
  el.textContent = msg;
  container.appendChild(el);
  setTimeout(() => {
    el.classList.add('toast-out');
    setTimeout(() => el.remove(), 200);
  }, 3000);
}

// ── Utilities ─────────────────────────────────────────────────
function escHtml(str) {
  if (str === null || str === undefined) return '';
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}

function fmtNum(n) {
  if (n === null || n === undefined) return '—';
  return Number(n).toLocaleString();
}

function fmtBytes(bytes) {
  if (!bytes) return '';
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  if (bytes < 1024 * 1024 * 1024) return `${(bytes / 1024 / 1024).toFixed(1)} MB`;
  return `${(bytes / 1024 / 1024 / 1024).toFixed(2)} GB`;
}

function hexToAlpha(hex, alpha) {
  try {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    return `rgba(${r},${g},${b},${alpha})`;
  } catch {
    return `rgba(124,108,240,${alpha})`;
  }
}
