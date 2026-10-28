from facebook_business.api import FacebookAdsApi
from facebook_business.adobjects.adaccount import AdAccount
from datetime import date, timedelta
from tools.core import env_loader
from tools.core.logger import get_logger

logger = get_logger("meta.fetch_spend")

def _init_api():
    token = env_loader.get("META_ACCESS_TOKEN")
    app_id = env_loader.get_optional("META_APP_ID", "")
    app_secret = env_loader.get_optional("META_APP_SECRET", "")
    FacebookAdsApi.init(app_id, app_secret, token)

# META_CAMPAIGN_ID_CLINICA=* → toda la cuenta menos FaceTech. El Dr. rota
# campañas de la clínica (la del 13/04 se apagó el 2026-09-28 y entraron las
# "ASISTENTE"), así que fijar un solo ID dejaba el gasto en $0 sin avisar.
ALL_CAMPAIGNS = "*"

def _scope(campaign_id: str) -> tuple[list, str]:
    """(filtering, level) para un ID de campaña o para ALL_CAMPAIGNS."""
    if campaign_id == ALL_CAMPAIGNS:
        excluir = env_loader.get_optional("META_CAMPAIGN_ID_FACETECH", "")
        f = [{"field": "campaign.id", "operator": "NOT_IN", "value": [excluir]}] if excluir else []
        return f, "account"
    return [{"field": "campaign.id", "operator": "EQUAL", "value": campaign_id}], "campaign"

def _fetch_campaign_spend(account_id: str, campaign_id: str, date_start: str, date_end: str) -> float:
    account = AdAccount(account_id)
    campaigns = account.get_campaigns(
        fields=["id", "name", "spend"],
        params={
            "filtering": [{"field": "campaign.id", "operator": "EQUAL", "value": campaign_id}],
            "time_range": {"since": date_start, "until": date_end},
            "level": "campaign",
        },
    )
    total = 0.0
    for c in campaigns:
        total += float(c.get("spend", 0))
    return total

def get_spend_today(campaign_id: str) -> float:
    today = date.today().isoformat()
    daily = get_spend_range(campaign_id, today, today)
    spend = daily.get(today, 0.0)
    logger.info(f"Gasto hoy campaign {campaign_id}: ${spend:,.0f} COP")
    return spend

def get_spend_month(campaign_id: str, year: int, month: int) -> float:
    start = date(year, month, 1).isoformat()
    if month == 12:
        end = date(year + 1, 1, 1) - timedelta(days=1)
    else:
        end = date(year, month + 1, 1) - timedelta(days=1)
    end = min(end, date.today()).isoformat()
    daily = get_spend_range(campaign_id, start, end)
    spend = sum(daily.values())
    logger.info(f"Gasto mes campaign {campaign_id}: ${spend:,.0f} COP")
    return spend

def get_insights_totals(campaign_id: str, date_start: str, date_end: str) -> dict:
    """Retorna métricas agregadas del período: alcance, impresiones, CTR, frecuencia, etc."""
    _init_api()
    account_id = env_loader.get("META_AD_ACCOUNT_ID")
    account = AdAccount(account_id)
    filtering, level = _scope(campaign_id)
    try:
        insights = account.get_insights(
            fields=["spend","reach","impressions","frequency","clicks","ctr","cpm","cpp"],
            params={
                "filtering": filtering,
                "time_range": {"since": date_start, "until": date_end},
                "level": level,
            },
        )
        if insights:
            r = insights[0]
            return {
                "spend":       round(float(r.get("spend", 0))),
                "reach":       int(r.get("reach", 0)),
                "impressions": int(r.get("impressions", 0)),
                "frequency":   round(float(r.get("frequency", 0)), 2),
                "clicks":      int(r.get("clicks", 0)),
                "ctr":         round(float(r.get("ctr", 0)), 2),
                "cpm":         round(float(r.get("cpm", 0))),
                "cpp":         round(float(r.get("cpp", 0))),
            }
    except Exception as e:
        logger.warning(f"Error insights campaign {campaign_id}: {e}")
    return {"spend":0,"reach":0,"impressions":0,"frequency":0,"clicks":0,"ctr":0,"cpm":0,"cpp":0}

def get_insights_daily(campaign_id: str, date_start: str, date_end: str) -> dict:
    """Retorna métricas por día: {'YYYY-MM-DD': {spend, impressions, clicks}}.

    Sólo expone métricas aditivas. 'reach' y 'frequency' se omiten a propósito:
    son personas únicas deduplicadas por Meta dentro del rango consultado, así
    que sumarlas por día daría un número inflado. Para rangos con alcance real
    hay que pedirle a la API ese rango exacto (ver get_insights_totals).
    """
    _init_api()
    account = AdAccount(env_loader.get("META_AD_ACCOUNT_ID"))
    daily = {}
    filtering, level = _scope(campaign_id)
    try:
        insights = account.get_insights(
            fields=["date_start", "spend", "impressions", "clicks"],
            params={
                "filtering": filtering,
                "time_range": {"since": date_start, "until": date_end},
                "time_increment": 1,
                "level": level,
            },
        )
        for row in insights:
            daily[row["date_start"]] = {
                "spend":       round(float(row.get("spend", 0))),
                "impressions": int(row.get("impressions", 0)),
                "clicks":      int(row.get("clicks", 0)),
            }
    except Exception as e:
        logger.warning(f"Error insights diarios campaign {campaign_id}: {e}")
    return daily

def get_spend_range(campaign_id: str, date_start: str, date_end: str) -> float:
    """Retorna gasto por cada día en el rango, para la gráfica de 7 días."""
    _init_api()
    account_id = env_loader.get("META_AD_ACCOUNT_ID")
    account = AdAccount(account_id)
    filtering, level = _scope(campaign_id)
    insights = account.get_insights(
        fields=["date_start", "spend"],
        params={
            "filtering": filtering,
            "time_range": {"since": date_start, "until": date_end},
            "time_increment": 1,
            "level": level,
        },
    )
    daily = {}
    for row in insights:
        daily[row["date_start"]] = daily.get(row["date_start"], 0.0) + float(row.get("spend", 0))
    return daily

# --- Bot vs Asistente ---
# El Dr. separa los canales por el NOMBRE de la campaña: las que llevan
# "ASISTENTE" mandan al WhatsApp del bot; el resto de la clínica manda al
# WhatsApp de la asistente humana. FaceTech se excluye porque es otra línea.
CANAL_BOT_TAG = "ASISTENTE"
ACTION_CONVERSACION = "onsite_conversion.messaging_conversation_started_7d"

def _canal_filtering(canal: str, excluir_ids: list) -> list:
    op = "CONTAIN" if canal == "bot" else "NOT_CONTAIN"
    f = [{"field": "campaign.name", "operator": op, "value": CANAL_BOT_TAG}]
    ids = [i for i in excluir_ids if i]
    if ids:
        f.append({"field": "campaign.id", "operator": "NOT_IN", "value": ids})
    return f

def _conversaciones(row) -> int:
    for a in row.get("actions", []) or []:
        if a.get("action_type") == ACTION_CONVERSACION:
            return int(float(a.get("value", 0)))
    return 0

def get_channel_daily(canal: str, date_start: str, date_end: str, excluir_ids: list) -> dict:
    """Gasto y conversaciones de WhatsApp por día para un canal ('bot' | 'asistente').

    Retorna {'YYYY-MM-DD': {spend, conversaciones}}. Se pide a nivel campaña y
    se suma por día, porque cada canal puede tener varias campañas activas.
    Lanza la excepción si Meta falla: quien llama decide si conserva data vieja.
    """
    _init_api()
    account = AdAccount(env_loader.get("META_AD_ACCOUNT_ID"))
    insights = account.get_insights(
        fields=["date_start", "campaign_name", "spend", "actions"],
        params={
            "filtering": _canal_filtering(canal, excluir_ids),
            "time_range": {"since": date_start, "until": date_end},
            "time_increment": 1,
            "level": "campaign",
            "limit": 500,
        },
    )
    daily: dict = {}
    for row in insights:  # el cursor del SDK pagina solo
        d = daily.setdefault(row["date_start"], {"spend": 0, "conversaciones": 0})
        d["spend"] += round(float(row.get("spend", 0)))
        d["conversaciones"] += _conversaciones(row)
    logger.info(f"Canal {canal}: {len(daily)} días, "
                f"${sum(v['spend'] for v in daily.values()):,.0f} COP, "
                f"{sum(v['conversaciones'] for v in daily.values())} conversaciones")
    return daily

def list_campaigns() -> list:
    """Lista id/nombre/estado de las campañas de la cuenta (para diagnóstico)."""
    _init_api()
    account = AdAccount(env_loader.get("META_AD_ACCOUNT_ID"))
    return [{"id": c["id"], "name": c["name"], "status": c.get("effective_status")}
            for c in account.get_campaigns(fields=["id", "name", "effective_status"])]
