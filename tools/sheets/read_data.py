import gspread
from google.oauth2.service_account import Credentials
from datetime import date, timedelta
from tools.core import env_loader
from tools.core.logger import get_logger

logger = get_logger("sheets.read_data")

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets.readonly",
    "https://www.googleapis.com/auth/drive.readonly",
]

def _get_sheet():
    import os, json
    from pathlib import Path
    sheet_id = env_loader.get("GOOGLE_SHEET_ID")

    # Cloud-friendly: si GOOGLE_CREDENTIALS_JSON_CONTENT existe (Railway/CI), úsala
    creds_content = os.getenv("GOOGLE_CREDENTIALS_JSON_CONTENT")
    if creds_content:
        info = json.loads(creds_content)
        creds = Credentials.from_service_account_info(info, scopes=SCOPES)
    else:
        creds_path = env_loader.get("GOOGLE_CREDENTIALS_JSON")
        if not Path(creds_path).is_absolute():
            creds_path = Path(__file__).parent.parent.parent / creds_path
        creds = Credentials.from_service_account_file(creds_path, scopes=SCOPES)

    client = gspread.authorize(creds)
    return client.open_by_key(sheet_id)

def _parse_cop(value: str) -> float:
    """Convierte strings como '4.500.000' o '4500000' a float."""
    if not value:
        return 0.0
    cleaned = str(value).replace(".", "").replace(",", "").replace("$", "").strip()
    try:
        return float(cleaned)
    except ValueError:
        return 0.0

def _parse_int(value) -> int:
    try:
        return int(str(value).strip())
    except (ValueError, AttributeError):
        return 0

def _norm_date(value: str) -> str:
    """Normaliza fechas a YYYY-MM-DD.

    El Google Sheet usa DD/MM/YYYY (ej '10/07/2026'), pero el pipeline compara
    contra date.today().isoformat() = YYYY-MM-DD. Sin normalizar, ninguna fila
    matchea y todas las métricas por fecha (hoy/semana/mes/chart) salen en 0.
    Acepta DD/MM/YYYY, D/M/YYYY, DD-MM-YYYY y YYYY-MM-DD (ya normalizado).
    Si no puede parsear, devuelve el string original.
    """
    s = str(value).strip()
    if not s:
        return ""
    # Ya viene en ISO (YYYY-MM-DD)
    if len(s) >= 10 and s[4] == "-" and s[7] == "-":
        return s[:10]
    # DD/MM/YYYY o D/M/YYYY (separador / o -)
    for sep in ("/", "-"):
        if sep in s:
            parts = s.split(sep)
            if len(parts) == 3:
                d, m, y = parts
                try:
                    return f"{int(y):04d}-{int(m):02d}-{int(d):02d}"
                except ValueError:
                    return s
    return s

def _pick(row: dict, *keys) -> str:
    """Primer valor no vacío entre varios nombres de columna posibles.

    El Google Sheet lo edita el cliente y los encabezados cambian sin aviso
    (ej. 'Tipo Cirugía' → 'Que se hizo', 'Valor COP' → 'Valor'). Aceptar
    alias evita que un rename silencioso vuelva a poner las métricas en 0.
    """
    for k in keys:
        v = str(row.get(k, "") or "").strip()
        if v:
            return v
    return ""

def _norm_canal(value: str) -> str:
    """'Bot' / 'bot ' / 'BOT' → 'bot'; 'Asistente' / 'Humana' → 'asistente'; resto → ''."""
    v = value.strip().lower()
    if v.startswith("bot"):
        return "bot"
    if v.startswith("asis") or v.startswith("human"):
        return "asistente"
    return ""

def read_clinica(target_date: str = None) -> list[dict]:
    """Lee tab CLINICA. Retorna filas con fecha, citas, procedimientos y total facturado."""
    try:
        sheet = _get_sheet()
        ws = sheet.worksheet("CLINICA")
        rows = ws.get_all_records()
        result = []
        for row in rows:
            fecha = _norm_date(str(row.get("Fecha", "")).strip())
            if not fecha:
                continue
            if target_date and fecha != target_date:
                continue
            total_facturado = _parse_cop(_pick(row, "Total $$", "Total"))
            # La asistente no llena siempre las mismas columnas: un día pone
            # "Citas Agendadas", otro solo "Presencial", otro solo "Citas Bot /
            # Citas Asistente". Las citas del día son lo más alto de esas tres
            # formas de contarlas, para que ningún día quede en 0 por la columna.
            citas = max(
                _parse_int(row.get("Citas Agendadas", 0)),
                _parse_int(row.get("Virtual", 0)) + _parse_int(row.get("Presencial", 0)),
                _parse_int(row.get("Citas Bot", 0)) + _parse_int(row.get("Citas Asistente", 0)),
            )
            result.append({
                "fecha": fecha,
                "citas_agendadas": citas,
                "procedimientos_vendidos": _parse_int(row.get("Procedimientos Vendidos", 0)),
                "citas_virtual": _parse_int(row.get("Virtual", 0)),
                "citas_presencial": _parse_int(row.get("Presencial", 0)),
                # Atribución Bot vs Asistente. Columnas opcionales: si no existen
                # o están vacías, esas citas quedan "sin atribuir" en el dashboard.
                "citas_bot": _parse_int(row.get("Citas Bot", 0)),
                "citas_asistente": _parse_int(row.get("Citas Asistente", 0)),
                "total_facturado": total_facturado,
                # False cuando la columna 'Total $$' está vacía → el calculator
                # cae de vuelta a citas × precio_cita para esa fila.
                "tiene_total": total_facturado > 0,
            })
        logger.info(f"CLINICA: {len(result)} filas leídas")
        return result
    except Exception as e:
        logger.error(f"Error leyendo CLINICA: {e}")
        return []

def read_procedimientos(target_date: str = None) -> list[dict]:
    """Lee tab PROCEDIMIENTOS. Retorna lista de procedimientos con valor.

    La columna 'Paciente' NO se lee a propósito: dashboard/data.json se publica
    en GitHub Pages y es legible sin autenticación, así que un nombre de paciente
    junto a su cirugía sería dato sensible de salud expuesto públicamente.
    """
    try:
        sheet = _get_sheet()
        ws = sheet.worksheet("PROCEDIMIENTOS")
        rows = ws.get_all_records()
        result = []
        for row in rows:
            fecha = _norm_date(str(row.get("Fecha", "")).strip())
            if not fecha:
                continue
            if target_date and fecha != target_date:
                continue
            tipo = _pick(row, "Que se hizo", "Tipo Cirugía")
            valor = _parse_cop(_pick(row, "Valor", "Valor COP"))
            # El Sheet trae la columna Fecha pre-rellenada hasta 2027 con el resto
            # vacío. Sin este filtro esas ~450 filas entran como procedimientos $0.
            if not tipo and valor == 0:
                continue
            result.append({
                "fecha": fecha,
                "tipo": tipo or "Sin especificar",
                "valor": valor,
                "canal": _norm_canal(_pick(row, "Canal")),
            })
        logger.info(f"PROCEDIMIENTOS: {len(result)} filas leídas")
        return result
    except Exception as e:
        logger.error(f"Error leyendo PROCEDIMIENTOS: {e}")
        return []

def read_facetech(target_date: str = None) -> list[dict]:
    """Lee tab FACETECH. Retorna lista de filas con fecha, leads, compras, valor ticket."""
    try:
        sheet = _get_sheet()
        ws = sheet.worksheet("FACETECH")
        rows = ws.get_all_records()
        result = []
        for row in rows:
            fecha = _norm_date(str(row.get("Fecha", "")).strip())
            if not fecha:
                continue
            if target_date and fecha != target_date:
                continue
            result.append({
                "fecha": fecha,
                "leads": _parse_int(row.get("Leads", 0)),
                "compras": _parse_int(row.get("Compras", 0)),
                "valor_ticket": _parse_cop(row.get("Valor Ticket COP", 0)),
            })
        logger.info(f"FACETECH: {len(result)} filas leídas")
        return result
    except Exception as e:
        logger.error(f"Error leyendo FACETECH: {e}")
        return []

def get_last_30_days() -> list[str]:
    """Retorna lista de los últimos 30 días en formato YYYY-MM-DD."""
    today = date.today()
    return [(today - timedelta(days=i)).isoformat() for i in range(29, -1, -1)]
