# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, render_template
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
    "yawa_agenda_nueva": {"name": "yawa_agenda_nueva","language": "es_CO",
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
    return render_template('index.html')

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

if __name__ == "__main__":
    app.run(debug=False, host="0.0.0.0", port=5000)
