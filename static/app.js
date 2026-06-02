
let jobId = null;
let pollInterval = null;
let logOffset = 0;

// Drag & drop
const dz = document.getElementById('drop-zone');
const fi = document.getElementById('csv-file');
dz.addEventListener('dragover', e => { e.preventDefault(); dz.classList.add('drag'); });
dz.addEventListener('dragleave', () => dz.classList.remove('drag'));
dz.addEventListener('drop', e => {
  e.preventDefault(); dz.classList.remove('drag');
  fi.files = e.dataTransfer.files;
  updateFileName();
});
fi.addEventListener('change', updateFileName);
function updateFileName() {
  const f = fi.files[0];
  document.getElementById('file-name').textContent = f ? '📄 ' + f.name : '';
}

async function iniciarEnvio() {
  const tokenEl = document.getElementById('token');
  const token = tokenEl ? tokenEl.value.trim() : '';
  const phoneId = '1084767568053371';
  const plantilla = document.getElementById('plantilla').value;
  const csvFile = document.getElementById('csv-file').files[0];
  const pausaMsg = document.getElementById('pausa_msg').value;
  const tamTanda = document.getElementById('tam_tanda').value;
  const pausaTanda = document.getElementById('pausa_tanda').value;

  //#if (!token) { alert('Ingresa el token de acceso.'); return; } -al usar token permanente, no es obligatorio ingresarlo manualmente (descomentar si cambia la logica en backend)
  if (!csvFile) { alert('Selecciona un archivo CSV.'); return; }

  const btn = document.getElementById('btn-enviar');
  btn.disabled = true;
  btn.innerHTML = '<span class="pulse">⟳</span> Iniciando...';

  const fd = new FormData();
  fd.append('token', token);
  fd.append('phone_id', phoneId);
  fd.append('plantilla', plantilla);
  fd.append('csv', csvFile);
  fd.append('pausa_msg', pausaMsg);
  fd.append('tam_tanda', tamTanda);
  fd.append('pausa_tanda', pausaTanda);

  try {
    const res = await fetch('/api/iniciar', { method: 'POST', body: fd });
    const data = await res.json();
    if (data.error) { alert('Error: ' + data.error); btn.disabled = false; btn.innerHTML = '<span>▶</span> Iniciar Envío'; return; }

    jobId = data.job_id;
    document.getElementById('stat-total').textContent = data.total;
    if (data.invalidos.length > 0) {
      addLog('warn', `⚠ ${data.invalidos.length} números inválidos ignorados`);
    }

    document.getElementById('form-section').style.display = 'none';
    document.getElementById('progreso-section').style.display = 'block';

    pollInterval = setInterval(actualizarEstado, 1500);
  } catch(e) {
    alert('Error de conexión: ' + e.message);
    btn.disabled = false;
    btn.innerHTML = '<span>▶</span> Iniciar Envío';
  }
}

async function actualizarEstado() {
  if (!jobId) return;
  try {
    const res = await fetch('/api/estado/' + jobId + '?offset=' + logOffset);
    const d = await res.json();

    const pct = d.total > 0 ? (d.progreso / d.total * 100) : 0;
    document.getElementById('prog-bar').style.width = pct + '%';
    document.getElementById('prog-nums').textContent = d.progreso + ' / ' + d.total;
    document.getElementById('stat-ok').textContent = d.enviados;
    document.getElementById('stat-fail').textContent = d.fallidos.length;
    if (d.plantilla_label) {
      document.getElementById('plantilla-activa-label').textContent = d.plantilla_label;
    }

    // Nuevos logs
    d.log.forEach(l => {
      if (l.pausa) {
        addLog('pausa', `⏸ Pausa de ${l.minutos} min entre tandas...`);
      } else {
        const icon = l.ok ? '✅' : '❌';
        const cls = l.ok ? 'ok' : 'fail';
        const txt = l.ok
          ? `${icon} [${l.i}/${l.total}] ${l.nombre} (+57${l.numero})`
          : `${icon} [${l.i}/${l.total}] ${l.nombre} (+57${l.numero}) — ${l.error}`;
        addLog(cls, txt);
      }
    });
    logOffset = d.log_total;

    // Estado badge
    const badge = document.getElementById('estado-badge');
    badge.className = 'estado-badge estado-' + d.estado;
    badge.classList.toggle('pulse', d.estado === 'enviando' || d.estado === 'iniciando');
    const labels = { enviando: '● Enviando', completado: '✓ Completado', cancelado: '✕ Cancelado', iniciando: '⟳ Iniciando' };
    badge.textContent = labels[d.estado] || d.estado;

    if (d.estado === 'completado' || d.estado === 'cancelado') {
      clearInterval(pollInterval);
      document.getElementById('btn-cancelar').style.display = 'none';
      document.getElementById('btn-nuevo').style.display = 'inline-flex';
      if (d.estado === 'completado') {
        addLog('info', `─── Envío finalizado · ${d.enviados} enviados · ${d.fallidos.length} fallidos ───`);
      }
    }
  } catch(e) {}
}

async function cancelarEnvio() {
  if (!jobId) return;
  if (!confirm('¿Cancelar el envío en curso?')) return;
  await fetch('/api/cancelar/' + jobId, { method: 'POST' });
}

function nuevoEnvio() {
  clearInterval(pollInterval);
  jobId = null; logOffset = 0;
  document.getElementById('log-wrap').innerHTML = '';
  document.getElementById('prog-bar').style.width = '0%';
  document.getElementById('btn-enviar').disabled = false;
  document.getElementById('btn-enviar').innerHTML = '<span>▶</span> Iniciar Envío';
  document.getElementById('btn-cancelar').style.display = 'inline-flex';
  document.getElementById('btn-nuevo').style.display = 'none';
  document.getElementById('form-section').style.display = 'block';
  document.getElementById('progreso-section').style.display = 'none';
  document.getElementById('file-name').textContent = '';
  document.getElementById('csv-file').value = '';
  document.getElementById('plantilla-activa-label').textContent = '—';
}

function addLog(type, text) {
  const wrap = document.getElementById('log-wrap');
  const d = document.createElement('div');
  d.className = 'log-line log-' + type;
  d.textContent = text;
  wrap.appendChild(d);
  wrap.scrollTop = wrap.scrollHeight;
}

// Calcular días restantes para el token permanente
(function() {
  const vencimiento = new Date('2026-07-27');
  const hoy = new Date();
  const diff = Math.ceil((vencimiento - hoy) / (1000 * 60 * 60 * 24));
  const span = document.getElementById('dias-restantes');
  const warn = document.getElementById('token-warn');
  if (diff <= 0) {
    warn.style.background = 'rgba(255,71,87,0.15)';
    warn.style.borderColor = 'rgba(255,71,87,0.5)';
    warn.style.color = '#FF4757';
    span.textContent = '0 — TOKEN VENCIDO';
  } else if (diff <= 10) {
    warn.style.background = 'rgba(255,71,87,0.1)';
    warn.style.borderColor = 'rgba(255,71,87,0.3)';
    warn.style.color = '#FF4757';
    span.textContent = diff;
  } else {
    span.textContent = diff;
  }
})();

function toggleTokenAvanzado() {
  const div = document.getElementById('token-avanzado');
  const label = document.getElementById('toggle-label');
  if (div.style.display === 'none') {
    div.style.display = 'block';
    label.textContent = '▼ Usar token diferente';
  } else {
    div.style.display = 'none';
    label.textContent = '▶ Usar token diferente';
  }
}