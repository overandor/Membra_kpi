async function postJson(url, payload, headers = {}) {
  const res = await fetch(url, {
    method: 'POST',
    headers: {'Content-Type': 'application/json', ...headers},
    body: JSON.stringify(payload || {})
  });
  const data = await res.json().catch(() => ({error: 'Invalid JSON response'}));
  if (!res.ok) throw data;
  return data;
}

function pretty(obj) {
  return JSON.stringify(obj, null, 2);
}

async function sendChat() {
  const input = document.getElementById('chatInput');
  const log = document.getElementById('chatLog');
  const report = document.getElementById('opportunityReport');
  if (!input || !input.value.trim()) return;
  const message = input.value.trim();
  log.insertAdjacentHTML('beforeend', `<div class="bubble user"></div>`);
  log.lastElementChild.textContent = message;
  input.value = '';
  try {
    const data = await postJson('/api/ai/chat', {messages: [{role: 'user', content: message}], owner_id: 'owner_default'});
    log.insertAdjacentHTML('beforeend', `<div class="bubble ai"></div>`);
    log.lastElementChild.textContent = data.message || 'No response';
    if (report) report.textContent = pretty(data.opportunity_report || data);
  } catch (err) {
    log.insertAdjacentHTML('beforeend', `<div class="bubble ai">Error: ${JSON.stringify(err)}</div>`);
  }
}

const photoForm = document.getElementById('photoForm');
if (photoForm) {
  photoForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const result = document.getElementById('photoResult');
    result.textContent = 'Analyzing real upload...';
    try {
      const res = await fetch('/api/photo/analyze', {method: 'POST', body: new FormData(photoForm)});
      const data = await res.json();
      if (!res.ok) throw data;
      result.textContent = pretty(data);
    } catch (err) {
      result.textContent = pretty(err);
    }
  });
}

const kpiForm = document.getElementById('kpiForm');
if (kpiForm) {
  kpiForm.addEventListener('submit', async (event) => {
    event.preventDefault();
    const result = document.getElementById('kpiResult');
    result.textContent = 'Parsing dataset...';
    try {
      const res = await fetch('/api/kpi/upload', {method: 'POST', body: new FormData(kpiForm)});
      const data = await res.json();
      if (!res.ok) throw data;
      result.textContent = pretty(data);
    } catch (err) {
      result.textContent = pretty(err);
    }
  });
}

async function requestVisibility(listingId) {
  try {
    const data = await postJson(`/api/listings/${listingId}/request-visibility`, {});
    alert(`Visibility requested: ${data.listing.status}`);
    window.location.reload();
  } catch (err) {
    alert(`Error: ${JSON.stringify(err)}`);
  }
}

async function confirmVisibility(listingId) {
  try {
    const data = await postJson(`/api/listings/${listingId}/confirm-visibility`, {});
    alert(`Published: ${data.public_listing.public_listing_id}`);
    window.location.reload();
  } catch (err) {
    alert(`Error: ${JSON.stringify(err)}`);
  }
}

async function createQrArtifact(subjectId, title) {
  const out = document.getElementById('qrResult');
  try {
    const data = await postJson('/api/qr/artifacts', {
      subject_type: 'listing',
      subject_id: subjectId,
      artifact_title: title,
      destination_url: window.location.href
    });
    if (out) out.textContent = pretty(data);
  } catch (err) {
    if (out) out.textContent = pretty(err);
  }
}

async function recordAdminDecision() {
  const token = document.getElementById('adminToken').value;
  const payload = {
    subject_type: document.getElementById('subjectType').value,
    subject_id: document.getElementById('subjectId').value,
    decision: document.getElementById('decision').value,
    risk_level: document.getElementById('riskLevel').value,
    notes: document.getElementById('adminNotes').value,
    operator: 'admin'
  };
  const out = document.getElementById('adminResult');
  try {
    const data = await postJson('/api/admin/decisions', payload, {'x-admin-token': token});
    if (out) out.textContent = pretty(data);
  } catch (err) {
    if (out) out.textContent = pretty(err);
  }
}
