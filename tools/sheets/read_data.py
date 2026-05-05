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

def read_clinica(target_date: str = None) -> list[dict]:
    """Lee tab CLINICA. Retorna lista de filas con fecha, citas, procedimientos."""
    try:
        sheet = _get_sheet()
        ws = sheet.worksheet("CLINICA")
        rows = ws.get_all_records()
        result = []
        for row in rows:
            fecha = str(row.get("Fecha", "")).strip()
            if not fecha:
                continue
            if target_date and fecha != target_date:
                continue
            result.append({
                "fecha": fecha,
                "citas_agendadas": _parse_int(row.get("Citas Agendadas", 0)),
                "procedimientos_vendidos": _parse_int(row.get("Procedimientos Vendidos", 0)),
            })
        logger.info(f"CLINICA: {len(result)} filas leídas")
        return result
    except Exception as e:
        logger.error(f"Error leyendo CLINICA: {e}")
        return []

def read_procedimientos(target_date: str = None) -> list[dict]:
    """Lee tab PROCEDIMIENTOS. Retorna lista de procedimientos con valor."""
    try:
        sheet = _get_sheet()
        ws = sheet.worksheet("PROCEDIMIENTOS")
        rows = ws.get_all_records()
        result = []
        for row in rows:
            fecha = str(row.get("Fecha", "")).strip()
            if not fecha:
                continue
            if target_date and fecha != target_date:
                continue
            result.append({
                "fecha": fecha,
                "tipo": str(row.get("Tipo Cirugía", "")).strip(),
                "valor": _parse_cop(row.get("Valor COP", 0)),
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
            fecha = str(row.get("Fecha", "")).strip()
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
