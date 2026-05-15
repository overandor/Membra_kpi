const DEFAULT_API = 'https://membra-kpi-api.example.com';

function configuredApiBase() {
  const url = new URL(window.location.href);
  return (
    url.searchParams.get('api') ||
    localStorage.getItem('MEMBRA_API_BASE') ||
    window.MEMBRA_API_BASE ||
    ''
  ).replace(/\/$/, '');
}

function setApiBase(value) {
  const clean = (value || '').trim().replace(/\/$/, '');
  if (clean) localStorage.setItem('MEMBRA_API_BASE', clean);
  return clean;
}

function money(value) {
  const n = Number(value || 0);
  return n.toLocaleString(undefined, { style: 'currency', currency: 'USD', maximumFractionDigits: 0 });
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

async function fetchJson(path, options = {}) {
  const api = configuredApiBase();
  if (!api) throw new Error('Backend API is not configured. Set it in the dashboard connection box.');
  const res = await fetch(`${api}${path}`, { ...options, headers: { 'Content-Type': 'application/json', ...(options.headers || {}) } });
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if (!res.ok) throw new Error(data.detail || data.message || text || `HTTP ${res.status}`);
  return data;
}

async function fetchForm(path, formData) {
  const api = configuredApiBase();
  if (!api) throw new Error('Backend API is not configured. Set it in the dashboard connection box.');
  const res = await fetch(`${api}${path}`, { method: 'POST', body: formData });
  const text = await res.text();
  let data;
  try { data = text ? JSON.parse(text) : {}; } catch { data = { raw: text }; }
  if (!res.ok) throw new Error(data.detail || data.message || text || `HTTP ${res.status}`);
  return data;
}

function qs(id) { return document.getElementById(id); }

function setText(id, value) {
  const el = qs(id);
  if (el) el.textContent = value;
}

function setHtml(id, value) {
  const el = qs(id);
  if (el) el.innerHTML = value;
}

function statusBadge(ok, label) {
  if (ok === true) return `<span class="status online">● ${label || 'online'}</span>`;
  if (ok === false) return `<span class="status offline">● ${label || 'offline'}</span>`;
  return `<span class="status warn">● ${label || 'not connected'}</span>`;
}

async function connectDashboard() {
  const input = qs('apiBaseInput');
  if (input) setApiBase(input.value);
  await loadDashboard();
}

async function loadDashboard() {
  const api = configuredApiBase();
  const input = qs('apiBaseInput');
  if (input && api) input.value = api;
  setText('apiBaseText', api || 'Not configured');
  setHtml('connectionStatus', statusBadge(null, 'checking'));

  if (!api) {
    setHtml('connectionStatus', statusBadge(false, 'backend not configured'));
    setText('healthJson', pretty({ message: 'Set MEMBRA_API_BASE or use ?api=https://your-backend.example.com' }));
    renderCounts({});
    return;
  }

  try {
    const [health, ready, dashboard] = await Promise.allSettled([
      fetchJson('/api/health'),
      fetchJson('/api/ready'),
      fetchJson('/api/dashboard')
    ]);

    if (health.status === 'fulfilled') {
      setHtml('connectionStatus', statusBadge(true, health.value.app || 'connected'));
      setText('healthJson', pretty({ health: health.value, ready: ready.status === 'fulfilled' ? ready.value : ready.reason.message }));
    } else {
      throw health.reason;
    }

    if (dashboard.status === 'fulfilled') renderCounts(dashboard.value.counts || {});
    else renderCounts({});
    await Promise.allSettled([loadProofbook(), loadListings(), loadOutbox()]);
  } catch (err) {
    setHtml('connectionStatus', statusBadge(false, 'backend unreachable'));
    setText('healthJson', pretty({ error: err.message, apiBase: api }));
    renderCounts({});
  }
}

function renderCounts(counts) {
  const defaults = ['photos','inventory','drafts','public_listings','kpis','proofs','event_outbox_pending','event_outbox_delivered'];
  setHtml('dashboardStats', defaults.map(key => `
    <div class="card stat"><span>${key.replaceAll('_',' ')}</span><b>${counts[key] ?? '—'}</b></div>
  `).join(''));
}

async function loadListings() {
  const data = await fetchJson('/api/listings/public');
  const listings = data.public_listings || [];
  if (!listings.length) {
    setHtml('listingsTable', '<div class="muted">No owner-confirmed listings returned by backend.</div>');
    return;
  }
  setHtml('listingsTable', `<div class="table-wrap"><table><thead><tr><th>SKU</th><th>Title</th><th>Price</th><th>Status</th></tr></thead><tbody>${listings.map(l => `
    <tr><td>${l.sku || ''}</td><td>${l.title || ''}</td><td>${money(l.price_low)}–${money(l.price_high)} / ${l.pricing_unit || ''}</td><td>${l.visibility_status || ''}</td></tr>
  `).join('')}</tbody></table></div>`);
}

async function loadProofbook() {
  const data = await fetchJson('/api/proofbook');
  const proofs = data.proofbook || [];
  if (!proofs.length) {
    setHtml('proofbookTable', '<div class="muted">No ProofBook records returned by backend.</div>');
    return;
  }
  setHtml('proofbookTable', `<div class="table-wrap"><table><thead><tr><th>Event</th><th>Subject</th><th>Hash</th><th>Created</th></tr></thead><tbody>${proofs.slice(0, 12).map(p => `
    <tr><td>${p.event_type || ''}</td><td>${p.subject_type || ''} / ${p.subject_id || ''}</td><td><small>${p.proof_hash || ''}</small></td><td>${p.created_at || ''}</td></tr>
  `).join('')}</tbody></table></div>`);
}

async function loadOutbox() {
  const data = await fetchJson('/api/events/outbox/stats');
  setText('outboxJson', pretty(data));
}

async function submitPhotoForm(event) {
  event.preventDefault();
  const form = event.target;
  const result = qs('photoResult');
  if (result) result.textContent = 'Uploading and analyzing...';
  try {
    const data = await fetchForm('/api/photo/analyze', new FormData(form));
    if (result) result.textContent = pretty(data);
    await loadDashboard();
  } catch (err) {
    if (result) result.textContent = pretty({ error: err.message });
  }
}

async function replayOutbox() {
  const token = qs('adminToken')?.value || '';
  const result = qs('replayResult');
  if (result) result.textContent = 'Replaying outbox...';
  try {
    const data = await fetchJson('/api/events/outbox/replay?limit=50', { method: 'POST', headers: { 'x-admin-token': token } });
    if (result) result.textContent = pretty(data);
    await loadDashboard();
  } catch (err) {
    if (result) result.textContent = pretty({ error: err.message });
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const form = qs('photoForm');
  if (form) form.addEventListener('submit', submitPhotoForm);
  if (qs('dashboardStats')) loadDashboard();
});
