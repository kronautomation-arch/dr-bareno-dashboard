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
    try:
        insights = account.get_insights(
            fields=["spend","reach","impressions","frequency","clicks","ctr","cpm","cpp"],
            params={
                "filtering": [{"field":"campaign.id","operator":"EQUAL","value":campaign_id}],
                "time_range": {"since": date_start, "until": date_end},
                "level": "campaign",
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

def get_spend_range(campaign_id: str, date_start: str, date_end: str) -> float:
    """Retorna gasto por cada día en el rango, para la gráfica de 7 días."""
    _init_api()
    account_id = env_loader.get("META_AD_ACCOUNT_ID")
    account = AdAccount(account_id)
    insights = account.get_insights(
        fields=["date_start", "spend"],
        params={
            "filtering": [{"field": "campaign.id", "operator": "EQUAL", "value": campaign_id}],
            "time_range": {"since": date_start, "until": date_end},
            "time_increment": 1,
            "level": "campaign",
        },
    )
    daily = {}
    for row in insights:
        daily[row["date_start"]] = float(row.get("spend", 0))
    return daily
