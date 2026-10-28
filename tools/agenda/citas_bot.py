"""Citas que vinieron del bot, leídas del Google Calendar del Dr.

Por qué el calendario y no el Sheet: la columna `Citas Bot` del Sheet la llena
la asistente a mano y casi nunca se llenaba. El 2026-10-19 el Dr. vio que el
dashboard decía 5 citas del bot desde mayo cuando en su agenda había 22. El
calendario es donde de verdad queda cada cita, así que es la fuente.

Cuenta como cita del bot:
- los eventos que creó el bot (extendedProperties.private.origen =
  "asistente-virtual"), y
- los que la secretaria creó a mano con "BOT" en el título (leads del bot que
  ella cerró por teléfono).

Solo primeras veces: se excluyen segundas citas, controles y cirugías, para
que se compare igual que las "Citas Agendadas" del Sheet. Las cirugías de
pacientes del bot se cuentan aparte.

La fecha es la de CREACIÓN del evento (el día en que se agendó), igual que el
Sheet, que anota el día en que se cerró la cita y no el de la consulta.
"""
import json
import re
from datetime import datetime, timedelta, timezone

import requests

from tools.core import env_loader
from tools.core.logger import get_logger

logger = get_logger("agenda.citas_bot")

API = "https://www.googleapis.com/calendar/v3"
COLOMBIA = timezone(timedelta(hours=-5))
ORIGEN_BOT = "asistente-virtual"

_BOT = re.compile(r"\bbot\b", re.I)
_NO_PRIMERA = re.compile(r"segunda|control|revisi[oó]n", re.I)
_CIRUGIA = re.compile(r"\bcx\b|cirug|pre ?cx", re.I)
COLOR_CIRUGIA = "9"


def _token() -> str | None:
    from google.auth.transport.requests import Request
    from google.oauth2 import service_account

    # Cloud-friendly: en Railway el JSON va como contenido, no como archivo.
    contenido = env_loader.get_optional("GOOGLE_CALENDAR_CREDENTIALS_CONTENT")
    ruta = env_loader.get_optional("GOOGLE_CALENDAR_CREDENTIALS")
    if contenido:
        info = json.loads(contenido)
    elif ruta:
        with open(ruta, encoding="utf-8") as f:
            info = json.load(f)
    else:
        return None
    creds = service_account.Credentials.from_service_account_info(
        # La delegación del dominio solo autoriza este scope; acá solo se lee.
        info, scopes=["https://www.googleapis.com/auth/calendar"])
    sujeto = env_loader.get_optional("GOOGLE_IMPERSONAR")
    if sujeto:
        creds = creds.with_subject(sujeto)
    creds.refresh(Request())
    return creds.token


def _eventos(token: str, calendario: str, desde: str) -> list:
    items, pagina = [], None
    while True:
        params = {"timeMin": f"{desde}T00:00:00-05:00", "singleEvents": "true",
                  "maxResults": "2500", "showDeleted": "false"}
        if pagina:
            params["pageToken"] = pagina
        r = requests.get(f"{API}/calendars/{calendario}/events",
                         headers={"Authorization": f"Bearer {token}"},
                         params=params, timeout=30)
        r.raise_for_status()
        data = r.json()
        items += data.get("items", [])
        pagina = data.get("nextPageToken")
        if not pagina:
            return items


def clasificar(ev: dict) -> str | None:
    """'cita', 'cirugia' o None si el evento no es del bot."""
    titulo = ev.get("summary") or ""
    privadas = (ev.get("extendedProperties") or {}).get("private") or {}
    if not (privadas.get("origen") == ORIGEN_BOT or _BOT.search(titulo)):
        return None
    if ev.get("colorId") == COLOR_CIRUGIA or _CIRUGIA.search(titulo):
        return "cirugia"
    if _NO_PRIMERA.search(titulo):
        return None
    return "cita"


def get_bot_calendar_daily(date_start: str) -> dict:
    """{'YYYY-MM-DD': {'citas': n, 'cirugias': n}} por fecha de creación.

    Devuelve {} si no hay credenciales o falla: no debe tumbar el dashboard.
    """
    calendario = env_loader.get_optional("GOOGLE_CALENDAR_ID")
    try:
        token = _token()
        if not token or not calendario:
            logger.info("Calendar sin configurar: se omiten las citas del bot")
            return {}
        # El evento puede ser de una fecha posterior a su creación, pero no
        # anterior: con pedir desde date_start alcanza.
        eventos = _eventos(token, calendario, date_start)
    except Exception as e:
        logger.warning(f"No se pudo leer el calendario: {e}")
        return {}

    daily: dict = {}
    for ev in eventos:
        if ev.get("status") == "cancelled":
            continue
        tipo = clasificar(ev)
        if not tipo or not ev.get("created"):
            continue
        creado = datetime.fromisoformat(ev["created"].replace("Z", "+00:00"))
        fecha = creado.astimezone(COLOMBIA).date().isoformat()
        if fecha < date_start:
            continue
        dia = daily.setdefault(fecha, {"citas": 0, "cirugias": 0})
        dia["citas" if tipo == "cita" else "cirugias"] += 1

    logger.info(f"Calendar bot: {sum(d['citas'] for d in daily.values())} citas y "
                f"{sum(d['cirugias'] for d in daily.values())} cirugías desde {date_start}")
    return dict(sorted(daily.items()))
