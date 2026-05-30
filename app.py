# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template_string
from flask_cors import CORS
import csv
import time
import json
import requests
import threading
import io
import uuid
import os

app = Flask(__name__)
CORS(app)

# Estado global de envíos (en memoria)
jobs = {}

WA_API_VERSION = "v20.0"

TEMPLATES = {
    "semilleros": {"name": "mensajes_de_asistencia", "language": "es_CO"},
    "orquestas":  {"name": "mensajes_asistencia_orquestas_en_ruta", "language": "en"},
    "mensajes_gda": {"name": "mensajes_gda", "language": "es_CO"},
    "artes_al_aula": {"name": "artes_al_aula", "language": "es_CO"},
    "yawa_agenda_nueva": {
    "name": "yawa_agenda_nueva",
    "language": "es_CO",
    "header_image": "https://raw.githubusercontent.com/YanCaicedo/App_Envio_Masivo/6d2ada826e0204fc3d5981b18c9223d3561d5912/Imagenes/Agenda_Yawa_Junio.jpg"
},
}


TEMPLATE_LABELS = {
    "semilleros": "Semilleros Artísticos",
    "orquestas": "Orquestas en Ruta",
    "mensajes_gda": "Mensajes Masivos GdA",
    "artes_al_aula": "Artes al Aula",
    "yawa_agenda_nueva": "YAWA Agenda Nueva",
}

def solo_digitos(s):
    return "".join(ch for ch in str(s) if ch.isdigit())

def normalizar_numero(raw):
    d = solo_digitos(raw)
    if len(d) == 10 and d.startswith("3"):
        return d
    if len(d) == 12 and d.startswith("57") and d[2] == "3":
        return d[2:]
    return None

def cargar_contactos_csv(content):
    contactos, invalidos = [], []
    for enc in ["utf-8-sig", "utf-8", "cp1252", "latin-1"]:
        try:
            text = content.decode(enc)
            reader = csv.DictReader(io.StringIO(text))
            campos = reader.fieldnames or []
            if "numero" not in campos:
                return [], [], "El CSV debe tener columna 'numero'."
            tiene_nombre = "nombre" in campos
            for row in reader:
                n = normalizar_numero(row["numero"])
                nombre = row.get("nombre", "").strip() if tiene_nombre else ""
                if n:
                    contactos.append({"nombre": nombre, "numero": n})
                else:
                    invalidos.append(str(row["numero"]))
            break
        except UnicodeDecodeError:
            continue

    seen, out = set(), []
    for c in contactos:
        if c["numero"] not in seen:
            seen.add(c["numero"])
            out.append(c)
    return out, invalidos, None

def enviar_mensaje(token, phone_id, numero, template_name, template_lang, header_image=None):
    url = f"https://graph.facebook.com/{WA_API_VERSION}/{phone_id}/messages"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    components = []
    if header_image:
        components.append({
            "type": "header",
            "parameters": [{"type": "image", "image": {"link": header_image}}]
        })

    payload = {
        "messaging_product": "whatsapp",
        "to": f"57{numero}",
        "type": "template",
        "template": {
            "name": template_name,
            "language": {"code": template_lang},
            "components": components
        }
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        data = resp.json()
        if resp.status_code == 200 and "messages" in data:
            return True, ""
        return False, data.get("error", {}).get("message", str(data))
    except requests.exceptions.RequestException as e:
        return False, str(e)

def run_job(job_id, token, phone_id, contactos, template_name, template_lang,
            pausa_msg, tam_tanda, pausa_tanda, header_image=None):
    job = jobs[job_id]
    job["estado"] = "enviando"
    total = len(contactos)

    for i, c in enumerate(contactos, start=1):
        if job.get("cancelar"):
            job["estado"] = "cancelado"
            break

        numero = c["numero"]
        nombre = c["nombre"] or numero
        ok, error = enviar_mensaje(token, phone_id, numero, template_name, template_lang, header_image)

        entry = {"i": i, "total": total, "nombre": nombre, "numero": numero,
                 "ok": ok, "error": error}
        job["log"].append(entry)
        job["progreso"] = i

        if ok:
            job["enviados"] += 1
        else:
            job["fallidos"].append({"numero": numero, "error": error})

        time.sleep(pausa_msg)

        if i % tam_tanda == 0 and i < total:
            job["log"].append({"pausa": True, "minutos": pausa_tanda // 60})
            time.sleep(pausa_tanda)

    if job["estado"] != "cancelado":
        job["estado"] = "completado"

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/api/iniciar", methods=["POST"])
def iniciar():
    token     = request.form.get("token", "").strip() or os.environ.get("WA_TOKEN", "")
    phone_id  = "1084767568053371"
    plantilla = request.form.get("plantilla", "semilleros")
    pausa_msg = int(request.form.get("pausa_msg", 3))
    tam_tanda = int(request.form.get("tam_tanda", 15))
    pausa_tanda = int(request.form.get("pausa_tanda", 240))
    archivo   = request.files.get("csv")

    if not token:
        return jsonify({"error": "Token requerido"}), 400
    if not archivo:
        return jsonify({"error": "CSV requerido"}), 400

    content = archivo.read()
    contactos, invalidos, err = cargar_contactos_csv(content)
    if err:
        return jsonify({"error": err}), 400
    if not contactos:
        return jsonify({"error": "No hay contactos válidos en el CSV"}), 400

    tmpl = TEMPLATES.get(plantilla, TEMPLATES["semilleros"])
    header_image = tmpl.get("header_image", None)
    plantilla_label = TEMPLATE_LABELS.get(plantilla, plantilla)
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "estado": "iniciando", "progreso": 0, "total": len(contactos),
        "enviados": 0, "fallidos": [], "log": [], "invalidos": invalidos,
        "cancelar": False, "plantilla_label": plantilla_label
    }

    t = threading.Thread(target=run_job, args=(
        job_id, token, phone_id, contactos,
        tmpl["name"], tmpl["language"],
        pausa_msg, tam_tanda, pausa_tanda, header_image
    ), daemon=True)
    t.start()

    return jsonify({"job_id": job_id, "total": len(contactos), "invalidos": invalidos})

@app.route("/api/estado/<job_id>")
def estado(job_id):
    job = jobs.get(job_id)
    if not job:
        return jsonify({"error": "Job no encontrado"}), 404
    offset = int(request.args.get("offset", 0))
    return jsonify({
        "estado": job["estado"],
        "progreso": job["progreso"],
        "total": job["total"],
        "enviados": job["enviados"],
        "fallidos": job["fallidos"],
        "log": job["log"][ offset:],
        "log_total": len(job["log"]),
        "plantilla_label": job.get("plantilla_label", ""),
    })

@app.route("/api/cancelar/<job_id>", methods=["POST"])
def cancelar(job_id):
    job = jobs.get(job_id)
    if job:
        job["cancelar"] = True
    return jsonify({"ok": True})

# ===== HTML FRONTEND =====
HTML = """<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Envío Masivo WhatsApp — Gestión de las Artes</title>
<link href="https://fonts.googleapis.com/css2?family=Syne:wght@400;600;700;800&family=DM+Mono:wght@300;400;500&display=swap" rel="stylesheet">
<style>
  :root {
    --bg: #0a0a0a;
    --surface: #111111;
    --surface2: #1a1a1a;
    --border: #2a2a2a;
    --accent: #25D366;
    --accent2: #128C7E;
    --warn: #FFB347;
    --danger: #FF4757;
    --text: #f0f0f0;
    --text2: #888;
    --text3: #555;
    --mono: 'DM Mono', monospace;
    --sans: 'Syne', sans-serif;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    min-height: 100vh;
    padding: 2rem 1rem;
  }
  .noise {
    position: fixed; inset: 0; pointer-events: none; z-index: 0;
    background-image: url("data:image/svg+xml,%3Csvg viewBox='0 0 256 256' xmlns='http://www.w3.org/2000/svg'%3E%3Cfilter id='noise'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='0.9' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23noise)' opacity='0.03'/%3E%3C/svg%3E");
    opacity: 0.4;
  }
  .container { max-width: 760px; margin: 0 auto; position: relative; z-index: 1; }

  header { margin-bottom: 3rem; }
  .badge {
    display: inline-flex; align-items: center; gap: 6px;
    background: rgba(37,211,102,0.1); border: 1px solid rgba(37,211,102,0.3);
    color: var(--accent); font-family: var(--mono); font-size: 0.7rem;
    padding: 4px 10px; border-radius: 2px; letter-spacing: 0.1em;
    text-transform: uppercase; margin-bottom: 1rem;
  }
  .badge::before { content: '●'; font-size: 0.5rem; }
  h1 {
    font-size: clamp(1.8rem, 4vw, 2.8rem); font-weight: 800;
    line-height: 1.1; letter-spacing: -0.03em;
  }
  h1 span { color: var(--accent); }
  .subtitle { color: var(--text2); font-family: var(--mono); font-size: 0.8rem; margin-top: 0.5rem; }

  .card {
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 4px; padding: 1.5rem; margin-bottom: 1.5rem;
  }
  .card-title {
    font-size: 0.7rem; font-family: var(--mono); color: var(--text3);
    text-transform: uppercase; letter-spacing: 0.15em; margin-bottom: 1.2rem;
    display: flex; align-items: center; gap: 8px;
  }
  .card-title::after { content: ''; flex: 1; height: 1px; background: var(--border); }

  .field { margin-bottom: 1.2rem; }
  label { display: block; font-size: 0.75rem; font-family: var(--mono); color: var(--text2); margin-bottom: 6px; }
  input[type=text], input[type=password], select {
    width: 100%; background: var(--surface2); border: 1px solid var(--border);
    color: var(--text); font-family: var(--mono); font-size: 0.85rem;
    padding: 10px 12px; border-radius: 3px; outline: none;
    transition: border-color 0.2s;
  }
  input:focus, select:focus { border-color: var(--accent); }
  select option { background: var(--surface2); }

  .grid-2 { display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }
  @media(max-width:500px) { .grid-2 { grid-template-columns: 1fr; } }

  .drop-zone {
    border: 2px dashed var(--border); border-radius: 4px;
    padding: 2rem; text-align: center; cursor: pointer;
    transition: all 0.2s; position: relative;
  }
  .drop-zone:hover, .drop-zone.drag { border-color: var(--accent); background: rgba(37,211,102,0.04); }
  .drop-zone input { position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; }
  .drop-icon { font-size: 2rem; margin-bottom: 0.5rem; }
  .drop-text { font-family: var(--mono); font-size: 0.8rem; color: var(--text2); }
  .drop-text strong { color: var(--accent); }
  .file-name { font-family: var(--mono); font-size: 0.8rem; color: var(--accent); margin-top: 0.5rem; }

  .btn {
    display: inline-flex; align-items: center; gap: 8px;
    font-family: var(--sans); font-weight: 700; font-size: 0.9rem;
    padding: 12px 24px; border-radius: 3px; border: none;
    cursor: pointer; transition: all 0.15s; letter-spacing: 0.02em;
  }
  .btn-primary {
    background: var(--accent); color: #000; width: 100%;
    justify-content: center; font-size: 1rem; padding: 14px;
  }
  .btn-primary:hover { background: #1db954; transform: translateY(-1px); }
  .btn-primary:disabled { background: var(--text3); color: var(--surface); cursor: not-allowed; transform: none; }
  .btn-danger { background: transparent; color: var(--danger); border: 1px solid var(--danger); }
  .btn-danger:hover { background: rgba(255,71,87,0.1); }

  /* Progress */
  #progreso-section { display: none; }
  .prog-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 1rem; }
  .prog-nums { font-family: var(--mono); font-size: 0.85rem; }
  .prog-nums .big { font-size: 1.8rem; font-weight: 800; color: var(--accent); }
  .prog-bar-wrap { background: var(--surface2); border-radius: 2px; height: 6px; overflow: hidden; margin-bottom: 1rem; }
  .prog-bar { height: 100%; background: var(--accent); border-radius: 2px; transition: width 0.4s ease; width: 0%; }

  .stats { display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; margin-bottom: 1.5rem; }
  .stat { background: var(--surface2); border: 1px solid var(--border); border-radius: 3px; padding: 1rem; text-align: center; }
  .stat-val { font-size: 1.6rem; font-weight: 800; font-family: var(--mono); }
  .stat-val.ok { color: var(--accent); }
  .stat-val.fail { color: var(--danger); }
  .stat-val.total { color: var(--text); }
  .stat-label { font-size: 0.65rem; color: var(--text3); text-transform: uppercase; letter-spacing: 0.1em; margin-top: 2px; font-family: var(--mono); }

  /* Log */
  .log-wrap {
    background: var(--surface2); border: 1px solid var(--border); border-radius: 3px;
    height: 280px; overflow-y: auto; padding: 1rem; font-family: var(--mono); font-size: 0.75rem;
  }
  .log-wrap::-webkit-scrollbar { width: 4px; }
  .log-wrap::-webkit-scrollbar-track { background: transparent; }
  .log-wrap::-webkit-scrollbar-thumb { background: var(--border); border-radius: 2px; }
  .log-line { padding: 2px 0; border-bottom: 1px solid rgba(255,255,255,0.03); }
  .log-ok { color: var(--accent); }
  .log-fail { color: var(--danger); }
  .log-pausa { color: var(--warn); }
  .log-info { color: var(--text2); }

  .estado-badge {
    display: inline-flex; align-items: center; gap: 6px;
    font-family: var(--mono); font-size: 0.7rem; padding: 4px 10px;
    border-radius: 2px; text-transform: uppercase; letter-spacing: 0.1em;
  }
  .estado-enviando { background: rgba(37,211,102,0.1); color: var(--accent); border: 1px solid rgba(37,211,102,0.3); }
  .estado-completado { background: rgba(37,211,102,0.2); color: var(--accent); border: 1px solid var(--accent); }
  .estado-cancelado { background: rgba(255,71,87,0.1); color: var(--danger); border: 1px solid rgba(255,71,87,0.3); }
  .estado-iniciando { background: rgba(255,179,71,0.1); color: var(--warn); border: 1px solid rgba(255,179,71,0.3); }

  .pulse { animation: pulse 1.5s infinite; }
  @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

  .warn-box {
    background: rgba(255,179,71,0.08); border: 1px solid rgba(255,179,71,0.3);
    border-radius: 3px; padding: 0.75rem 1rem; font-family: var(--mono);
    font-size: 0.75rem; color: var(--warn); margin-bottom: 1rem;
  }
</style>
</head>
<body>
<div class="noise"></div>
<div class="container">

  <header>
    <div class="badge">Gestión de las Artes</div>
    <h1>App Envío<br><span>Masivo</span></h1>
    <p class="subtitle">// Subsecretaría de Artes · Secretaría de Cultura de Cali</p>
  </header>

  <!-- FORMULARIO -->
  <div id="form-section">
    <div class="card">
      <div class="card-title">01 · Autenticación</div>

      <div class="warn-box" id="token-warn">
        ⚠ Token permanente activo — vence en <span id="dias-restantes" style="font-weight:bold;"></span> días
      </div>

      <div style="margin-top:0.75rem;">
        <span onclick="toggleTokenAvanzado()" style="font-family:var(--mono);font-size:0.75rem;color:var(--text2);cursor:pointer;" id="toggle-label">▶ Usar token diferente</span>
      </div>
      <div id="token-avanzado" style="display:none;margin-top:1rem;">
        <div class="field">
          <label>Token de acceso</label>
          <input type="password" id="token" placeholder="Dejar vacío para usar token permanente" autocomplete="off">
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">02 · Plantilla y CSV</div>

      <div class="field">
        <label>Plantilla</label>
        <select id="plantilla">
          <option value="semilleros">Semilleros Artísticos — mesnajes_de_asistencia (es_CO)</option>
          <option value="orquestas">Orquestas en Ruta — mensajes_asistencia_orquestas_en_ruta (en)</option>
          <option value="mensajes_gda">Mensajes Masivos -GdA(es_CO)</option>
          <option value="artes_al_aula">Artes al Aula — Formularios (es_CO)</option>
          <option value="yawa_agenda_nueva">YAWA Agenda Nueva — yawa_agenda_nueva (es_CO)</option>
        </select>
      </div>

      <div class="field">
        <label>Archivo CSV (columnas: numero, nombre)</label>
        <div class="drop-zone" id="drop-zone">
          <input type="file" id="csv-file" accept=".csv">
          <div class="drop-icon">📋</div>
          <div class="drop-text">Arrastra tu CSV aquí o <strong>haz clic</strong></div>
          <div class="file-name" id="file-name"></div>
        </div>
      </div>
    </div>

    <div class="card">
      <div class="card-title">03 · Configuración de envío</div>
      <div class="grid-2">
        <div class="field">
          <label>Pausa entre mensajes (seg)</label>
          <input type="text" id="pausa_msg" value="3">
        </div>
        <div class="field">
          <label>Tamaño de tanda</label>
          <input type="text" id="tam_tanda" value="15">
        </div>
        <div class="field">
          <label>Pausa entre tandas (seg)</label>
          <input type="text" id="pausa_tanda" value="240">
        </div>
      </div>
    </div>

    <button class="btn btn-primary" id="btn-enviar" onclick="iniciarEnvio()">
      <span>▶</span> Iniciar envío masivo
    </button>
  </div>

  <!-- PROGRESO -->
  <div id="progreso-section">
    <div class="card">
      <div class="prog-header">
        <div class="card-title" style="margin:0">Estado del envío</div>
        <span class="estado-badge estado-iniciando pulse" id="estado-badge">Iniciando</span>
      </div>
      <div style="font-family:var(--mono);font-size:0.75rem;color:var(--text2);margin-bottom:1rem;">
        Plantilla: <span id="plantilla-activa-label" style="color:var(--accent);">—</span>
      </div>

      <div class="stats">
        <div class="stat">
          <div class="stat-val total" id="stat-total">0</div>
          <div class="stat-label">Total</div>
        </div>
        <div class="stat">
          <div class="stat-val ok" id="stat-ok">0</div>
          <div class="stat-label">Enviados</div>
        </div>
        <div class="stat">
          <div class="stat-val fail" id="stat-fail">0</div>
          <div class="stat-label">Fallidos</div>
        </div>
      </div>

      <div class="prog-bar-wrap">
        <div class="prog-bar" id="prog-bar"></div>
      </div>
      <div class="prog-nums" id="prog-nums">0 / 0</div>
    </div>

    <div class="card">
      <div class="card-title">Log en tiempo real</div>
      <div class="log-wrap" id="log-wrap"></div>
    </div>

    <div style="display:flex;gap:1rem;margin-top:1rem">
      <button class="btn btn-danger" id="btn-cancelar" onclick="cancelarEnvio()">✕ Cancelar envío</button>
      <button class="btn btn-primary" id="btn-nuevo" style="display:none" onclick="nuevoEnvio()">+ Nuevo envío</button>
    </div>
  </div>

</div>

<script>
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
  const token = document.getElementById('token').value.trim();
  const phoneId = document.getElementById('phone_id').value.trim();
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
    if (data.error) { alert('Error: ' + data.error); btn.disabled = false; btn.innerHTML = '<span>▶</span> Iniciar envío masivo'; return; }

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
    btn.innerHTML = '<span>▶</span> Iniciar envío masivo';
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
  document.getElementById('btn-enviar').innerHTML = '<span>▶</span> Iniciar envío masivo';
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
</script>
</body>
</html>"""

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
