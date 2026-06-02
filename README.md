# App Envío Masivo WhatsApp — Gestión de las Artes
**Subsecretaría de Artes · Secretaría de Cultura de Cali**

App web para envío masivo de mensajes WhatsApp usando Meta Business Cloud API.

## Características
- Interfaz visual sin código
- Carga de CSV con drag & drop
- Log en tiempo real con historial completo
- Soporte para múltiples plantillas aprobadas (con y sin imagen)
- Token permanente configurado — no requiere renovación diaria
- Cancelación de envío en curso
- Configuración de tandas y pausas entre envíos

## Estructura del proyecto
```
App_Envio_Masivo/
├── app.py                          # Backend Flask
├── requirements.txt                # Dependencias Python
├── Procfile                        # Comando de arranque Railway
├── railway.toml                    # Configuración Railway
├── .gitignore
├── README.md
├── Imagenes/                       # Imágenes para plantillas con header
│   └── Agenda_Yawa_Junio.jpg
├── templates/
│   └── index.html                  # Frontend HTML
└── static/
    ├── styles.css                  # Estilos
    └── app.js                      # Lógica JavaScript
```

## Plantillas configuradas

| Clave | Nombre en Meta | Idioma | Imagen |
|-------|---------------|--------|--------|
| semilleros | mesnajes_de_asistencia | es_CO | No |
| orquestas | mensajes_asistencia_orquestas_en_ruta | en | No |
| mensajes_gda | mensajes_gda | es_CO | No |
| artes_al_aula | artes_al_aula | es_CO | No |
| yawa_agenda_nueva | yawa_agenda_nueva | es_CO | Si |

### Para agregar una plantilla nueva

**1 — En `app.py`**, busca el diccionario `TEMPLATES` (~línea 21) y agrega:

```python
# Sin imagen
"clave": {"name": "nombre_en_meta", "language": "es_CO"},

# Con imagen
"clave": {"name": "nombre_en_meta", "language": "es_CO", "header_image": "https://url_imagen.jpg"},
```

**2 — En `app.py`**, agrega el nombre visible en `TEMPLATE_LABELS`:

```python
"clave": "Nombre visible en la app",
```

**3 — En `templates/index.html`**, agrega la opción en el `<select id="plantilla">`:

```html
<option value="clave">Nombre visible — nombre_en_meta (es_CO)</option>
```

### Para agregar imágenes
Sube la imagen a la carpeta `Imagenes/` del repo y usa la URL raw:
```
https://raw.githubusercontent.com/YanCaicedo/App_Envio_Masivo/main/Imagenes/nombre_imagen.jpg
```

## Formato CSV requerido
El archivo debe usar **comas** como separador (no punto y coma).

```
numero,nombre
3001234567,Juan Pérez
3109876543,María García
```

Si el CSV viene de Excel en español, al guardar selecciona **"CSV UTF-8 (delimitado por comas)"**.

## Infraestructura

| Dato | Valor |
|------|-------|
| App desplegada | https://web-production-d8c886.up.railway.app/ |
| Repo app web | https://github.com/YanCaicedo/App_Envio_Masivo |
| Phone Number ID | 1084767568053371 |
| WABA | Gestion de las Artes (ID: 2139631270146701) |
| Numero WhatsApp | +57 321 5620968 |
| Respuestas entrantes | Meta Business Suite (business.facebook.com) |

## Deploy en Railway
1. Sube cambios al repo en GitHub
2. Railway redespliega automáticamente en ~1 minuto

Para nuevo proyecto:
1. Railway → New Project → Deploy from GitHub
2. Selecciona el repo
3. Agrega la variable de entorno `WA_TOKEN` en la pestaña Variables
4. Railway detecta automáticamente Python y usa el Procfile

## Uso local

```bash
# Crear y activar entorno virtual (Windows)
python -m venv .venv
(Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned)
.venv\Scripts\Activate.ps1

# Instalar dependencias
pip install -r requirements.txt

# Correr la app
python app.py
# Abre http://localhost:5000
```

## Token de acceso
El token es **permanente** (válido 60 días) y está configurado como variable de entorno `WA_TOKEN` en Railway.

Para renovarlo cuando venza:
1. Ve a `business.facebook.com` → Configuración → Usuarios del sistema
2. Selecciona `app_envio_masivo`
3. Clic en **Generar token**
4. Selecciona la app `Envio_Masivo` y activa permisos de WhatsApp
5. Copia el token y actualízalo en Railway → Variables → `WA_TOKEN`

## Notas
- Los envíos corren en background — puedes cerrar y reabrir la pestaña
- Configuración recomendada: 1-2 seg entre mensajes, tandas de 30, pausas de 2 min
- Las respuestas entrantes se monitorean desde Meta Business Suite
- Imágenes para plantillas se almacenan en la carpeta `Imagenes/` del repo
