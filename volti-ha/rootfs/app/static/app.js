/**
 * app.js - Frontend logic per Volti HA
 * Gestisce l'interfaccia web Ingress dell'add-on.
 */

// ============================
// CONFIGURAZIONE
// ============================

// Il path base Ingress viene iniettato dal template
const INGRESS_PATH = window.INGRESS_PATH || '';
const API_BASE = `${INGRESS_PATH}/api`;

// Stato dell'applicazione
const state = {
  cameras: [],
  haCameras: [],
  modelInfo: null,
  status: null,
  logs: [],
  activeTab: 'cameras',
  addCameraSourceType: 'ha_entity',
};

// ============================
// UTILITÀ
// ============================

async function apiCall(endpoint, options = {}) {
  try {
    const url = `${API_BASE}${endpoint}`;
    const response = await fetch(url, {
      headers: { 'Content-Type': 'application/json', ...options.headers },
      ...options,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || `Errore HTTP ${response.status}`);
    }
    return data;
  } catch (error) {
    console.error(`API Error [${endpoint}]:`, error);
    throw error;
  }
}

function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;

  const icons = { success: '✅', error: '❌', info: 'ℹ️' };
  toast.innerHTML = `<span>${icons[type] || ''}</span> ${message}`;

  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(40px)';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ============================
// TABS
// ============================

function switchTab(tabName) {
  state.activeTab = tabName;

  document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  document.querySelector(`[data-tab="${tabName}"]`).classList.add('active');
  document.getElementById(`tab-${tabName}`).classList.add('active');

  // Refresh dei dati per la tab corrente
  if (tabName === 'cameras') loadCameras();
  if (tabName === 'model') loadModelInfo();
  if (tabName === 'settings') loadLogs();
}

// ============================
// TELECAMERE
// ============================

async function loadCameras() {
  try {
    const data = await apiCall('/cameras');
    state.cameras = data.cameras || [];
    renderCameras();
  } catch (e) {
    showToast('Errore nel caricamento telecamere', 'error');
  }
}

function renderCameras() {
  const container = document.getElementById('camerasList');

  if (state.cameras.length === 0) {
    container.innerHTML = `
      <div class="empty-state">
        <span class="empty-icon">📹</span>
        <p>Nessuna telecamera configurata</p>
        <button class="btn btn-primary" onclick="openAddCameraModal()">
          ➕ Aggiungi Telecamera
        </button>
      </div>
    `;
    return;
  }

  container.innerHTML = state.cameras.map(cam => {
    const lastResult = cam.last_result;
    const running = cam.running;
    const facesInfo = lastResult && lastResult.faces_count > 0
      ? lastResult.faces.map(f => `${f.name} (${Math.round(f.confidence * 100)}%)`).join(', ')
      : 'Nessun volto';
    const sourceLabel = cam.config?.source_type === 'ha_entity' ? '🏠 Entità HA' : '🌐 URL Diretto';

    return `
      <div class="card camera-card" id="cam-${cam.id}">
        <div class="card-header">
          <div class="card-title">
            <span class="cam-icon">${running ? '🟢' : '⚪'}</span>
            ${cam.name}
          </div>
          <div class="toggle-container">
            <span class="toggle-label">${running ? 'Attiva' : 'Ferma'}</span>
            <label class="toggle">
              <input type="checkbox" ${running ? 'checked' : ''} onchange="toggleCamera('${cam.id}', this.checked)">
              <span class="toggle-slider"></span>
            </label>
          </div>
        </div>
        <div class="camera-info">
          <div class="camera-info-item">
            <span class="info-label">Sorgente</span>
            <span class="info-value">${sourceLabel}</span>
          </div>
          <div class="camera-info-item">
            <span class="info-label">Frame Analizzati</span>
            <span class="info-value highlight">${cam.frames_analyzed || 0}</span>
          </div>
          <div class="camera-info-item">
            <span class="info-label">Ultimo Rilevamento</span>
            <span class="info-value">${facesInfo}</span>
          </div>
          <div class="camera-info-item">
            <span class="info-label">Intervallo</span>
            <span class="info-value">${cam.config?.interval === 0 ? '<span class="text-success">Continuo</span>' : (cam.config?.interval || 2) + 's'}</span>
          </div>
        </div>
        ${cam.last_error ? `<div style="color: var(--danger); font-size: 0.8rem; margin-bottom: 12px;">⚠️ ${cam.last_error}</div>` : ''}
        <div class="camera-actions">
          <button class="btn btn-ghost btn-sm" onclick="openEditCameraModal('${cam.id}')">
            ⚙️ Modifica
          </button>
          <button class="btn btn-danger btn-sm" onclick="deleteCamera('${cam.id}', '${cam.name}')">
            🗑️ Rimuovi
          </button>
        </div>
      </div>
    `;
  }).join('');
}

async function toggleCamera(cameraId, enabled) {
  try {
    await apiCall(`/cameras/${cameraId}/toggle`, {
      method: 'PUT',
      body: JSON.stringify({ enabled }),
    });
    showToast(`Telecamera ${enabled ? 'attivata' : 'disattivata'}`, 'success');
    setTimeout(loadCameras, 500);
  } catch (e) {
    showToast('Errore nel toggle della telecamera', 'error');
    loadCameras(); // Ricarica per sincronizzare lo stato
  }
}

async function deleteCamera(cameraId, name) {
  if (!confirm(`Rimuovere la telecamera "${name}"?\nLe entità MQTT verranno eliminate.`)) return;

  try {
    await apiCall(`/cameras/${cameraId}`, { method: 'DELETE' });
    showToast(`Telecamera "${name}" rimossa`, 'success');
    loadCameras();
  } catch (e) {
    showToast('Errore nella rimozione', 'error');
  }
}

// ============================
// MODAL AGGIUNGI TELECAMERA
// ============================

async function openAddCameraModal() {
  document.getElementById('modalTitle').textContent = '📹 Aggiungi Telecamera';
  document.getElementById('editCameraId').value = '';
  document.getElementById('saveCameraButton').textContent = '➕ Aggiungi';
  
  // Reset form
  document.getElementById('cameraName').value = '';
  document.getElementById('cameraUrl').value = '';
  document.getElementById('cameraInterval').value = '2';
  updateIntervalLabel(2);

  const modal = document.getElementById('addCameraModal');
  modal.classList.add('visible');

  // Carica lista telecamere HA
  try {
    const data = await apiCall('/ha-cameras');
    state.haCameras = data.cameras || [];
    renderHaCameraSelect();
  } catch (e) {
    state.haCameras = [];
    renderHaCameraSelect();
  }

  switchSourceType('ha_entity');
}

async function openEditCameraModal(cameraId) {
  const cam = state.cameras.find(c => c.id === cameraId);
  if (!cam) return;

  document.getElementById('modalTitle').textContent = `⚙️ Modifica ${cam.name}`;
  document.getElementById('editCameraId').value = cameraId;
  document.getElementById('saveCameraButton').textContent = '💾 Salva Modifiche';

  document.getElementById('cameraName').value = cam.name;
  document.getElementById('cameraInterval').value = cam.config?.interval || 0;
  updateIntervalLabel(cam.config?.interval || 0);

  if (cam.config?.source_type === 'ha_entity') {
    switchSourceType('ha_entity');
    // Carica telecamere HA se non presenti
    if (state.haCameras.length === 0) {
      try {
        const data = await apiCall('/ha-cameras');
        state.haCameras = data.cameras || [];
        renderHaCameraSelect();
      } catch (e) {}
    }
    document.getElementById('haCameraSelect').value = cam.config?.source || '';
  } else {
    switchSourceType('url');
    document.getElementById('cameraUrl').value = cam.config?.source || '';
  }

  document.getElementById('addCameraModal').classList.add('visible');
}

function closeAddCameraModal() {
  document.getElementById('addCameraModal').classList.remove('visible');
}

function updateIntervalLabel(value) {
  const val = parseInt(value);
  const label = document.getElementById('intervalValue');
  const hint = document.getElementById('continuousHint');
  
  if (val === 0) {
    label.textContent = 'Continuo';
    hint.style.display = 'block';
  } else {
    label.textContent = val + 's';
    hint.style.display = 'none';
  }
}

function switchSourceType(type) {
  state.addCameraSourceType = type;
  document.querySelectorAll('.source-toggle button').forEach(b => b.classList.remove('active'));
  document.querySelector(`[data-source="${type}"]`).classList.add('active');

  document.getElementById('sourceHaEntity').style.display = type === 'ha_entity' ? 'block' : 'none';
  document.getElementById('sourceUrl').style.display = type === 'url' ? 'block' : 'none';
}

function renderHaCameraSelect() {
  const select = document.getElementById('haCameraSelect');
  if (state.haCameras.length === 0) {
    select.innerHTML = '<option value="">Nessuna telecamera trovata in HA</option>';
    return;
  }
  select.innerHTML = '<option value="">Seleziona una telecamera...</option>' +
    state.haCameras.map(c =>
      `<option value="${c.entity_id}">${c.friendly_name} (${c.entity_id})</option>`
    ).join('');
}

async function saveCamera() {
  const editId = document.getElementById('editCameraId').value;
  const name = document.getElementById('cameraName').value.trim();
  const interval = parseInt(document.getElementById('cameraInterval').value);
  let source, source_type;

  if (state.addCameraSourceType === 'ha_entity') {
    source = document.getElementById('haCameraSelect').value;
    source_type = 'ha_entity';
  } else {
    source = document.getElementById('cameraUrl').value.trim();
    source_type = 'url';
  }

  if (!name) {
    showToast('Inserisci un nome per la telecamera', 'error');
    return;
  }
  if (!source) {
    showToast('Seleziona una telecamera o inserisci un URL', 'error');
    return;
  }

  try {
    if (editId) {
      // UPDATE
      await apiCall(`/cameras/${editId}`, {
        method: 'PUT',
        body: JSON.stringify({ name, source_type, source, interval }),
      });
      showToast(`Telecamera "${name}" aggiornata!`, 'success');
    } else {
      // CREATE
      await apiCall('/cameras', {
        method: 'POST',
        body: JSON.stringify({ name, source_type, source, interval }),
      });
      showToast(`Telecamera "${name}" aggiunta!`, 'success');
    }
    
    closeAddCameraModal();
    loadCameras();
  } catch (e) {
    showToast(`Errore: ${e.message}`, 'error');
  }
}

// ============================
// MODELLO
// ============================

async function loadModelInfo() {
  try {
    const data = await apiCall('/model/info');
    state.modelInfo = data;
    renderModelInfo();
  } catch (e) {
    showToast('Errore nel caricamento info modello', 'error');
  }
}

function renderModelInfo() {
  const container = document.getElementById('modelInfoContainer');
  const info = state.modelInfo;

  if (!info || !info.loaded) {
    container.innerHTML = `
      <div class="empty-state" style="padding: 24px;">
        <span class="empty-icon">🧠</span>
        <p>Nessun modello caricato.<br>Carica il file <code>classificatore_volti_HA.pkl</code></p>
      </div>
    `;
    return;
  }

  container.innerHTML = `
    <div class="model-info-grid">
      <div class="model-stat">
        <div class="stat-value">${info.known_names.length}</div>
        <div class="stat-label">Persone Note</div>
      </div>
      <div class="model-stat">
        <div class="stat-value">${info.detection_model.toUpperCase()}</div>
        <div class="stat-label">Modello Detection</div>
      </div>
      <div class="model-stat">
        <div class="stat-value">${Math.round(info.min_confidence * 100)}%</div>
        <div class="stat-label">Soglia Confidenza</div>
      </div>
      <div class="model-stat">
        <div class="stat-value">✅</div>
        <div class="stat-label">Stato</div>
      </div>
    </div>
    ${info.known_names.length > 0 ? `
      <h3 style="margin-top:20px; margin-bottom:8px; font-size:0.9rem; color:var(--text-secondary)">
        Persone Riconoscibili
      </h3>
      <div class="known-names">
        ${info.known_names.map(n => `<span class="name-chip">${n}</span>`).join('')}
      </div>
    ` : ''}
    ${info.load_time ? `
      <p style="margin-top:14px; font-size:0.78rem; color:var(--text-muted)">
        Ultimo caricamento: ${new Date(info.load_time).toLocaleString('it-IT')}
      </p>
    ` : ''}
  `;
}

// Upload modello
function setupModelUpload() {
  const zone = document.getElementById('uploadZone');
  const input = document.getElementById('modelFileInput');

  zone.addEventListener('click', () => input.click());
  zone.addEventListener('dragover', (e) => {
    e.preventDefault();
    zone.classList.add('dragover');
  });
  zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
  zone.addEventListener('drop', (e) => {
    e.preventDefault();
    zone.classList.remove('dragover');
    if (e.dataTransfer.files.length > 0) {
      uploadModel(e.dataTransfer.files[0]);
    }
  });
  input.addEventListener('change', () => {
    if (input.files.length > 0) {
      uploadModel(input.files[0]);
    }
  });
}

async function uploadModel(file) {
  if (!file.name.endsWith('.pkl')) {
    showToast('Il file deve essere un .pkl', 'error');
    return;
  }

  showToast('Caricamento modello in corso...', 'info');

  const formData = new FormData();
  formData.append('model', file);

  try {
    const response = await fetch(`${API_BASE}/model/upload`, {
      method: 'POST',
      body: formData,
    });
    const data = await response.json();

    if (response.ok) {
      showToast('Modello caricato con successo!', 'success');
      loadModelInfo();
    } else {
      showToast(`Errore: ${data.error}`, 'error');
    }
  } catch (e) {
    showToast('Errore nel caricamento del modello', 'error');
  }
}

// ============================
// STATUS & LOGS
// ============================

async function loadStatus() {
  try {
    const data = await apiCall('/status');
    state.status = data;
    renderStatusBadges();
  } catch (e) {
    // Silenzioso - non spammare errori per lo status check
  }
}

function renderStatusBadges() {
  const s = state.status;
  if (!s) return;

  const mqttBadge = document.getElementById('mqttBadge');
  const modelBadge = document.getElementById('modelBadge');

  if (mqttBadge) {
    mqttBadge.className = `badge ${s.mqtt_connected ? 'badge-success' : 'badge-danger'}`;
    mqttBadge.innerHTML = `<span>●</span> MQTT ${s.mqtt_connected ? 'Connesso' : 'Disconnesso'}`;
  }
  if (modelBadge) {
    modelBadge.className = `badge ${s.model_loaded ? 'badge-success' : 'badge-warning'}`;
    modelBadge.innerHTML = `<span>●</span> Modello ${s.model_loaded ? 'OK' : 'Non Caricato'}`;
  }
}

async function loadLogs() {
  try {
    const data = await apiCall('/logs');
    state.logs = data.logs || [];
    renderLogs();
  } catch (e) {
    // Silenzioso
  }
}

function renderLogs() {
  const container = document.getElementById('logsContainer');
  if (state.logs.length === 0) {
    container.innerHTML = '<div class="log-line" style="color:var(--text-muted)">Nessun log disponibile.</div>';
    return;
  }
  container.innerHTML = state.logs.map(l => `<div class="log-line">${escapeHtml(l)}</div>`).join('');
  container.scrollTop = container.scrollHeight;
}

function escapeHtml(str) {
  const div = document.createElement('div');
  div.textContent = str;
  return div.innerHTML;
}

// ============================
// INIZIALIZZAZIONE
// ============================

document.addEventListener('DOMContentLoaded', () => {
  setupModelUpload();
  loadStatus();
  loadCameras();
  loadModelInfo();

  // Refresh periodico
  setInterval(() => {
    loadStatus();
    if (state.activeTab === 'cameras') loadCameras();
    if (state.activeTab === 'settings') loadLogs();
  }, 5000);
});
