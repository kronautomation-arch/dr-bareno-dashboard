"""Conteo automático de lo que hizo el bot de WhatsApp, leído de Pancake.

Sirve de CONTROL frente al Sheet: la comparación Bot vs Asistente se hace con
las citas que la asistente registra en el Sheet (así las dos se miden igual),
y esto muestra al lado cuántas citas dejó agendadas el bot según sus propias
etiquetas. Si el bot marca 10 y el Sheet dice 4, alguien no está registrando.

Detalles de la API (ver dr-bareno-bot/tools/pancake/client.py):
- Token como query param `page_access_token`, base `/public_api/v2`.
- 60 conversaciones por llamada; sólo pagina el cursor `last_conversation_id`.
- Vienen ordenadas por `updated_at` descendente: poner una etiqueta actualiza
  la conversación, así que cortar cuando `updated_at` < desde no pierde nada.
- Las fechas vienen en UTC; la clínica opera en hora Colombia (UTC-5).
"""
from datetime import datetime, timedelta, timezone

import requests

from tools.core import env_loader
from tools.core.logger import get_logger

logger = get_logger("pancake.bot_citas")

BASE_V2 = "https://pages.fm/api/public_api/v2"
ETIQUETA_CITA = "CITA AGENDADA"
COLOMBIA = timezone(timedelta(hours=-5))
MAX_PAGINAS = 150  # ~9.000 conversaciones; con ~45/día alcanza para meses


def _dt(s: str):
    if not s:
        return None
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except ValueError:
        return None
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _fecha_local(d: datetime) -> str:
    return d.astimezone(COLOMBIA).date().isoformat()


def _listar(api_key: str, page_id: str, desde: datetime) -> list:
    todas, vistos, cursor = [], set(), None
    for _ in range(MAX_PAGINAS):
        params = {"page_access_token": api_key}
        if cursor:
            params["last_conversation_id"] = cursor
        r = requests.get(f"{BASE_V2}/pages/{page_id}/conversations",
                         params=params, timeout=20)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("success") is False:
            raise RuntimeError(f"Pancake: {data.get('message')}")
        nuevas = [v for v in data.get("conversations", [])
                  if isinstance(v, dict) and v.get("id") not in vistos]
        if not nuevas:
            break
        todas.extend(nuevas)
        vistos.update(v["id"] for v in nuevas)
        cursor = nuevas[-1]["id"]
        ultima = _dt(nuevas[-1].get("updated_at"))
        if ultima and ultima < desde:
            break
    return todas


def get_bot_daily(date_start: str) -> dict:
    """{'YYYY-MM-DD': {conversaciones, citas}} del número del bot desde date_start.

    - conversaciones: chats nuevos ese día (inserted_at).
    - citas: la PRIMERA vez que el bot le puso CITA AGENDADA a cada chat.
    Devuelve {} si Pancake no está configurado o falla: es un dato de control,
    no debe tumbar la actualización del dashboard.
    """
    api_key = env_loader.get_optional("PANCAKE_API_KEY")
    page_id = env_loader.get_optional("PANCAKE_PAGE_ID")
    if not api_key or not page_id:
        logger.info("PANCAKE_API_KEY/PAGE_ID no configurados: se omite el control del bot")
        return {}

    desde = datetime.fromisoformat(date_start).replace(tzinfo=COLOMBIA)
    try:
        convs = _listar(api_key, page_id, desde)
    except Exception as e:
        logger.warning(f"No se pudo leer Pancake: {e}")
        return {}

    daily: dict = {}

    def _dia(f):
        return daily.setdefault(f, {"conversaciones": 0, "citas": 0})

    for v in convs:
        creada = _dt(v.get("inserted_at"))
        if creada and creada >= desde:
            _dia(_fecha_local(creada))["conversaciones"] += 1

        adds = [_dt(h.get("inserted_at")) for h in v.get("tag_histories") or []
                if (h.get("payload") or {}).get("action") == "add"
                and ((h.get("payload") or {}).get("tag") or {}).get("text") == ETIQUETA_CITA]
        adds = [d for d in adds if d]
        if adds and min(adds) >= desde:
            _dia(_fecha_local(min(adds)))["citas"] += 1

    logger.info(f"Pancake bot: {len(convs)} chats leídos, "
                f"{sum(d['citas'] for d in daily.values())} citas desde {date_start}")
    return dict(sorted(daily.items()))
