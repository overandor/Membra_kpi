async function loadVercelConfig() {
  try {
    const res = await fetch('/api/config');
    if (!res.ok) return;
    const data = await res.json();
    if (data.apiBase && !localStorage.getItem('MEMBRA_API_BASE') && !window.MEMBRA_API_BASE) {
      window.MEMBRA_API_BASE = data.apiBase.replace(/\/$/, '');
    }
  } catch (_) {
    // Static hosting without Vercel functions is still supported through ?api= or localStorage.
  }
}

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

function escapeHtml(value) {
  return String(value ?? '')
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
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
  if (ok === true) return `<span class="status online">● ${escapeHtml(label || 'online')}</span>`;
  if (ok === false) return `<span class="status offline">● ${escapeHtml(label || 'offline')}</span>`;
  return `<span class="status warn">● ${escapeHtml(label || 'not connected')}</span>`;
}

function emptyState(title, detail) {
  return `<div class="empty"><strong>${escapeHtml(title)}</strong><br><span>${escapeHtml(detail)}</span></div>`;
}

function loadingSkeleton(label = 'Loading live backend data') {
  return `<div class="skeleton" aria-label="${escapeHtml(label)}"></div>`;
}

async function connectDashboard() {
  const input = qs('apiBaseInput');
  if (input) setApiBase(input.value);
  await loadDashboard();
}

async function clearConnection() {
  localStorage.removeItem('MEMBRA_API_BASE');
  window.MEMBRA_API_BASE = '';
  const input = qs('apiBaseInput');
  if (input) input.value = '';
  await loadDashboard();
}

async function loadDashboard() {
  const api = configuredApiBase();
  const input = qs('apiBaseInput');
  if (input && api) input.value = api;
  setText('apiBaseText', api || 'Not configured');
  setHtml('connectionStatus', statusBadge(null, 'checking'));
  setHtml('dashboardStats', Array.from({ length: 8 }).map(() => loadingSkeleton()).join(''));
  setHtml('listingsTable', loadingSkeleton('Loading listings'));
  setHtml('proofbookTable', loadingSkeleton('Loading ProofBook'));

  if (!api) {
    setHtml('connectionStatus', statusBadge(false, 'backend not configured'));
    setText('healthJson', pretty({ message: 'Set MEMBRA_API_BASE in Vercel env or use ?api=https://your-backend.example.com' }));
    renderCounts({});
    setHtml('listingsTable', emptyState('Backend disconnected', 'Connect a FastAPI backend to show owner-confirmed marketplace records.'));
    setHtml('proofbookTable', emptyState('Backend disconnected', 'Connect a backend to show ProofBook records.'));
    setText('outboxJson', pretty({ status: 'backend_disconnected' }));
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
    setHtml('listingsTable', emptyState('Backend unreachable', 'The dashboard could not load marketplace listings from the configured backend.'));
    setHtml('proofbookTable', emptyState('Backend unreachable', 'The dashboard could not load ProofBook records from the configured backend.'));
    setText('outboxJson', pretty({ error: err.message }));
  }
}

function renderCounts(counts) {
  const labels = [
    ['photos', 'Photo proofs'],
    ['inventory', 'Inventory items'],
    ['drafts', 'Private drafts'],
    ['public_listings', 'Live listings'],
    ['kpis', 'KPI cards'],
    ['proofs', 'ProofBook rows'],
    ['event_outbox_pending', 'Outbox pending'],
    ['event_outbox_delivered', 'Outbox delivered']
  ];
  setHtml('dashboardStats', labels.map(([key, label]) => `
    <div class="card stat"><span>${escapeHtml(label)}</span><b>${counts[key] ?? '—'}</b></div>
  `).join(''));
}

async function loadListings() {
  const data = await fetchJson('/api/listings/public');
  const listings = data.public_listings || [];
  if (!listings.length) {
    setHtml('listingsTable', emptyState('No public listings yet', 'Owner-confirmed listings will appear here after visibility confirmation.'));
    return;
  }
  setHtml('listingsTable', `<div class="table-wrap"><table><thead><tr><th>SKU</th><th>Title</th><th>Price</th><th>Status</th></tr></thead><tbody>${listings.map(l => `
    <tr><td>${escapeHtml(l.sku || '')}</td><td>${escapeHtml(l.title || '')}</td><td>${escapeHtml(money(l.price_low))}–${escapeHtml(money(l.price_high))} / ${escapeHtml(l.pricing_unit || '')}</td><td>${escapeHtml(l.visibility_status || '')}</td></tr>
  `).join('')}</tbody></table></div>`);
}

async function loadProofbook() {
  const data = await fetchJson('/api/proofbook');
  const proofs = data.proofbook || [];
  if (!proofs.length) {
    setHtml('proofbookTable', emptyState('No ProofBook records yet', 'Proof hashes will appear after photo analysis, KPI upload, visibility events, or outbox replay.'));
    return;
  }
  setHtml('proofbookTable', `<div class="table-wrap"><table><thead><tr><th>Event</th><th>Subject</th><th>Hash</th><th>Created</th></tr></thead><tbody>${proofs.slice(0, 12).map(p => `
    <tr><td>${escapeHtml(p.event_type || '')}</td><td>${escapeHtml(p.subject_type || '')} / ${escapeHtml(p.subject_id || '')}</td><td><small>${escapeHtml(p.proof_hash || '')}</small></td><td>${escapeHtml(p.created_at || '')}</td></tr>
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
  if (result) result.textContent = 'Uploading and analyzing real image proof...';
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

document.addEventListener('DOMContentLoaded', async () => {
  await loadVercelConfig();
  const form = qs('photoForm');
  if (form) form.addEventListener('submit', submitPhotoForm);
  if (qs('dashboardStats')) loadDashboard();
});
