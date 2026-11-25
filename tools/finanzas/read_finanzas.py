"""Lee del Google Sheet lo que necesita el módulo de Finanzas.

Pestañas: PROCEDIMIENTOS (valor + Costos Salas), GASTOS FIJOS, GASTOS DEL MES
y PAGOS. Ver tools/finanzas/setup_sheet.py para el formato de cada una.

Nada de esto va en claro a data.json (que es público): main.py lo cifra con
FINANZAS_CLAVE antes de publicarlo.
"""
import json
import os
from pathlib import Path

import gspread
from google.oauth2.service_account import Credentials

from tools.core import env_loader
from tools.core.logger import get_logger
from tools.sheets.read_data import _get_sheet, _norm_date, _parse_cop, _pick

logger = get_logger("finanzas.read")


def open_sheet_rw():
    """El Sheet con permiso de escritura (solo para setup_sheet.py)."""
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    content = os.getenv("GOOGLE_CREDENTIALS_JSON_CONTENT")
    if content:
        creds = Credentials.from_service_account_info(json.loads(content), scopes=scopes)
    else:
        path = env_loader.get("GOOGLE_CREDENTIALS_JSON")
        if not Path(path).is_absolute():
            path = Path(__file__).parent.parent.parent / path
        creds = Credentials.from_service_account_file(path, scopes=scopes)
    return gspread.authorize(creds).open_by_key(env_loader.get("GOOGLE_SHEET_ID"))


def _mes(value: str) -> str:
    """'15/10/2026', '10/2026', '2026-10' o '2026-10-15' → '2026-10'. Vacío → ''."""
    s = str(value or "").strip()
    if not s:
        return ""
    if len(s) >= 7 and s[4] == "-":
        return s[:7]
    partes = s.replace("-", "/").split("/")
    try:
        if len(partes) == 2:      # MM/YYYY
            return f"{int(partes[1]):04d}-{int(partes[0]):02d}"
        if len(partes) == 3:      # DD/MM/YYYY
            return f"{int(partes[2]):04d}-{int(partes[1]):02d}"
    except ValueError:
        pass
    return ""


def _valor(v) -> tuple[float, bool]:
    """(valor, tiene_dato). Distingue celda vacía de un 0 escrito a propósito."""
    s = str(v if v is not None else "").strip()
    return (_parse_cop(s), s != "")


def _records(sheet, titulo: str) -> list[dict]:
    try:
        return sheet.worksheet(titulo).get_all_records()
    except gspread.WorksheetNotFound:
        logger.warning(f"Falta la pestaña {titulo} en el Sheet")
        return []


def read_finanzas() -> dict:
    sheet = _get_sheet()

    procedimientos = []
    for r in _records(sheet, "PROCEDIMIENTOS"):
        fecha = _norm_date(str(r.get("Fecha", "")))
        tipo = _pick(r, "Que se hizo", "Tipo Cirugía")
        valor = _parse_cop(_pick(r, "Valor", "Valor COP"))
        if not fecha or (not tipo and valor == 0):
            continue
        sala, tiene_sala = _valor(r.get("Costos Salas", ""))
        procedimientos.append({"fecha": fecha, "tipo": tipo or "Sin especificar",
                               "valor": valor, "sala": sala, "tiene_sala": tiene_sala})

    fijos = []
    for r in _records(sheet, "GASTOS FIJOS"):
        concepto = str(r.get("Concepto", "")).strip()
        if not concepto:
            continue
        fijos.append({
            "concepto": concepto,
            "categoria": str(r.get("Categoría", r.get("Categoria", ""))).strip() or "Otros",
            "tipo": str(r.get("Tipo", "FIJO")).strip().upper() or "FIJO",
            "valor": _parse_cop(r.get("Valor", "")),
            "desde": _mes(r.get("Desde", "")),
            "hasta": _mes(r.get("Hasta", "")),
        })

    gastos_mes = []
    for r in _records(sheet, "GASTOS DEL MES"):
        mes = _mes(r.get("Fecha", ""))
        concepto = str(r.get("Concepto", "")).strip()
        valor = _parse_cop(r.get("Valor", ""))
        if mes and concepto and valor:
            gastos_mes.append({"mes": mes, "concepto": concepto, "valor": valor,
                               "nota": str(r.get("Nota", "")).strip()})

    pagos = []
    for r in _records(sheet, "PAGOS"):
        fecha = _norm_date(str(r.get("Fecha pago", "")))
        valor = _parse_cop(r.get("Valor", ""))
        if not fecha or not valor:
            continue
        pagos.append({"fecha": fecha, "valor": valor,
                      "forma": str(r.get("Forma de pago", "")).strip().lower(),
                      "moneda": (str(r.get("Moneda", "")).strip().upper() or "COP")})

    logger.info(f"Finanzas: {len(procedimientos)} procedimientos, {len(fijos)} gastos fijos, "
                f"{len(gastos_mes)} gastos del mes, {len(pagos)} pagos")
    return {"procedimientos": procedimientos, "fijos": fijos,
            "gastos_mes": gastos_mes, "pagos": pagos}
