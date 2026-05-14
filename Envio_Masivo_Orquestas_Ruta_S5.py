# -*- coding: utf-8 -*-
"""
Envío masivo por WhatsApp Business Cloud API (Meta) usando plantilla aprobada.
Requisitos:
    pip install requests
"""

import csv
import time
import json
import requests
from pathlib import Path

# ===== CONFIGURACIÓN API =====
WA_ACCESS_TOKEN    = "EAFmEqY8nfrYBRR6ZCZCBcvp7KPljtid0e7O7eDr402Tfa9VlhIYCaYN8viGkYzmtTAh16gtMudG8eP4kv2fFRrlZBR4e4TGV8lDhwDUGPws2XEu0Ahv70NbUtGK0RBB91FYqsOQkFZB7ZBTh0NYCWTh9uyZCqPPcqe3cjU7A2owVcK0P2oltG9QiTGYZAc5ZAJ0ZCehKhuHVJPU8Yh8sGMgCpls6YGnYvInl8ov08PWFt8ZBAr7zDVt1ZAF7W43dHORZA0kNMUOxk73YbZBj7UB5nEaudE0iej564a88WMQLrPgZDZD"
WA_PHONE_NUMBER_ID = "1084767568053371"
WA_API_VERSION     = "v20.0"

# ===== PLANTILLA =====
TEMPLATE_NAME     = "mensajes_asistencia_orquestas_en_ruta"
TEMPLATE_LANGUAGE = "en"


# ===== ARCHIVO CSV =====
CSV_FILE          = "Orquestas_Ruta_Sesion5.csv"

# ===== CONFIGURACIÓN DE ENVÍO =====
PAUSA_ENTRE_MSG = 3    # Segundos entre mensajes
TAM_TANDA       = 15   # Mensajes por tanda
PAUSA_TANDA     = 240  # Segundos entre tandas (4 min)


def solo_digitos(s: str) -> str:
    return "".join(ch for ch in str(s) if ch.isdigit())


def normalizar_numero(raw: str):
    d = solo_digitos(raw)
    if len(d) == 10 and d.startswith("3"):
        return d
    if len(d) == 12 and d.startswith("57") and d[2] == "3":
        return d[2:]
    return None


def cargar_contactos(csv_path: Path):
    contactos, invalidos = [], []
    encodings = ["utf-8-sig", "utf-8", "cp1252", "latin-1"]

    for enc in encodings:
        try:
            with csv_path.open("r", encoding=enc, newline="") as f:
                reader = csv.DictReader(f)
                campos = reader.fieldnames or []
                if "numero" not in campos:
                    raise ValueError("El CSV debe tener columna 'numero'.")
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
    return out, invalidos


def enviar_mensaje_api(numero: str) -> tuple[bool, str]:
    """Envía mensaje usando la plantilla aprobada."""
    url = f"https://graph.facebook.com/{WA_API_VERSION}/{WA_PHONE_NUMBER_ID}/messages"
    headers = {
        "Authorization": f"Bearer {WA_ACCESS_TOKEN}",
        "Content-Type": "application/json",
    }
    payload = {
        "messaging_product": "whatsapp",
        "to": f"57{numero}",
        "type": "template",
        "template": {
            "name": TEMPLATE_NAME,
            "language": {
                "code": TEMPLATE_LANGUAGE
            }
        }
    }

    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=15)
        data = resp.json()
        if resp.status_code == 200 and "messages" in data:
            return True, ""
        else:
            error = data.get("error", {}).get("message", str(data))
            return False, error
    except requests.exceptions.RequestException as e:
        return False, str(e)


def guardar_reporte(enviados, fallidos):
    reporte = {
        "enviados": enviados,
        "fallidos": [{"numero": n, "error": e} for n, e in fallidos],
    }
    Path("reporte_envio.json").write_text(
        json.dumps(reporte, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print("📄 Reporte guardado en: reporte_envio.json")


def main():
    csv_path = Path(CSV_FILE)

    if not csv_path.exists():
        raise FileNotFoundError(
            f"No encuentro '{CSV_FILE}'.\n"
            "Asegúrate de que esté en la misma carpeta que este script."
        )

    contactos, invalidos = cargar_contactos(csv_path)

    if invalidos:
        print(f"⚠️  Números inválidos ignorados: {', '.join(invalidos)}")

    if not contactos:
        print("❌ No hay contactos válidos.")
        return

    total = len(contactos)
    print(f"\n📋 {total} contactos cargados.")
    print(f"📤 Iniciando envío por WhatsApp Business API...\n")

    enviados = []
    fallidos = []

    try:
        for i, contacto in enumerate(contactos, start=1):
            numero = contacto["numero"]
            nombre = contacto["nombre"] or numero

            print(f"  [{i}/{total}] {nombre} (+57{numero})", end=" ... ", flush=True)

            ok, error = enviar_mensaje_api(numero)

            if ok:
                print("✅")
                enviados.append(numero)
            else:
                print(f"❌ {error}")
                fallidos.append((numero, error))

            time.sleep(PAUSA_ENTRE_MSG)

            if i % TAM_TANDA == 0 and i < total:
                print(f"\n⏸  Pausa de {PAUSA_TANDA//60} min entre tandas...\n")
                time.sleep(PAUSA_TANDA)

    finally:
        guardar_reporte(enviados, fallidos)

    print(f"\n{'='*55}")
    print(f"✅ Enviados : {len(enviados)}")
    print(f"❌ Fallidos : {len(fallidos)}")
    print("="*55)


if __name__ == "__main__":
    main()