# Envío Masivo WhatsApp — Gestión de las Artes

App web para envío masivo de mensajes WhatsApp usando Meta Business Cloud API.

## Características
- Interfaz visual sin código
- Carga de CSV con drag & drop
- Log en tiempo real
- Soporte para múltiples plantillas aprobadas (con y sin imagen)
- Cancelación de envío en curso
- Configuración de tandas y pausas entre envíos

## Plantillas configuradas

| Clave | Nombre en Meta | Idioma | Imagen |
|-------|---------------|--------|--------|
| semilleros | mesnajes_de_asistencia | es_CO | No |
| orquestas | mensajes_asistencia_orquestas_en_ruta | en | No |
| mensajes_gda | mensajes_gda | es_CO | No |
| artes_al_aula | artes_al_aula | es_CO | No |
| yawa_agenda_nueva | yawa_agenda_nueva | es_CO | Si |

### Para agregar una plantilla nueva
En `app.py`, busca el diccionario `TEMPLATES` (~línea 21) y agrega:

```python
# Sin imagen
"clave": {"name": "nombre_en_meta", "language": "es_CO"},

# Con imagen
"clave": {"name": "nombre_en_meta", "language": "es_CO", "header_image": "https://url_directa_imagen.jpg"},
```

Luego agrega la opción en el `<select id="plantilla">` del HTML.

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
| respond.io | Conectado via WhatsApp Cloud API + webhook |

## Deploy en Railway

1. Sube cambios al repo en GitHub
2. Railway redespliega automáticamente en ~1 minuto

Para nuevo proyecto:
1. Railway → New Project → Deploy from GitHub
2. Selecciona el repo
3. Railway detecta automáticamente Python y usa el Procfile

## Uso local

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python app.py
# Abre http://localhost:5000
```

## Token de acceso

El token vence cada 24h. Para regenerarlo:
1. Ve a `developers.facebook.com/tools/explorer/`
2. Selecciona app **Envio_Masivo**
3. Activa permisos: `whatsapp_business_messaging`, `whatsapp_business_management`, `business_management`
4. Clic en **Generate Access Token**
5. Pégalo en el campo de la app

## Notas
- Los envíos corren en background — puedes cerrar y reabrir la pestaña
- Configuración recomendada: 1-2 seg entre mensajes, tandas de 30, pausas de 2 min
- Las respuestas entrantes se gestionan desde respond.io
- Imágenes para plantillas se almacenan en la carpeta `Imagenes/` del repo
