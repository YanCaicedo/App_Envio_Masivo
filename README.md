# Envío Masivo WhatsApp — Gestión de las Artes

App web para envío masivo de mensajes WhatsApp usando Meta Business Cloud API.

## Características
- Interfaz visual sin código
- Carga de CSV con drag & drop
- Log en tiempo real
- Soporte para 2 plantillas aprobadas
- Cancelación de envío en curso

## Plantillas configuradas
| Clave | Nombre | Idioma |
|-------|--------|--------|
| semilleros | mesnajes_de_asistencia | es_CO |
| orquestas | mensajes_asistencia_orquestas_en_ruta | en |

## Formato CSV requerido
```
numero,nombre
3001234567,Juan Pérez
3109876543,María García
```

## Deploy en Railway

1. Sube este repositorio a GitHub
2. En Railway → New Project → Deploy from GitHub
3. Selecciona el repo
4. Railway detecta automáticamente Python y usa el Procfile
5. ¡Listo!

## Uso local
```bash
pip install -r requirements.txt
python app.py
# Abre http://localhost:5000
```

## Notas
- El token de acceso vence cada 24h — generarlo en developers.facebook.com
- Phone Number ID por defecto: 1084767568053371
- Los envíos corren en background, puedes cerrar y reabrir la pestaña
