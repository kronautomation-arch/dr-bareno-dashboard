import json
import subprocess
import sys
from datetime import date, timedelta, datetime
from pathlib import Path

from tools.core import env_loader
from tools.core.logger import get_logger
from tools.meta.refresh_token import refresh_long_lived_token
from tools.meta.fetch_spend import (
    get_spend_today, get_spend_month, get_spend_range, get_insights_totals,
    get_insights_daily, get_channel_daily,
)
from tools.pancake.bot_citas import get_bot_daily
from tools.agenda.citas_bot import get_bot_calendar_daily
from tools.sheets.read_data import read_clinica, read_procedimientos, read_facetech, get_last_30_days
from tools.metrics.calculator import calc_clinica_day, calc_facetech_day, build_chart_data, calc_canales

logger = get_logger("main")

def build_data() -> dict:
    env_loader.load_env()
    today = date.today().isoformat()
    year = date.today().year
    month = date.today().month

    precio_cita = float(env_loader.get("PRECIO_CITA_COP"))
    campaign_clinica = env_loader.get("META_CAMPAIGN_ID_CLINICA")
    campaign_facetech = env_loader.get("META_CAMPAIGN_ID_FACETECH")

    first_of_month = date(year, month, 1).isoformat()
    chart_start = (date.today() - timedelta(days=6)).isoformat()
    chart_end = today

    logger.info("=== Iniciando actualización de datos ===")

    # Renovar token automáticamente (siempre 60 días frescos)
    refresh_long_lived_token()

    # --- Gasto Meta ---
    logger.info("Obteniendo gasto Meta Ads...")
    meta_ok = True
    try:
        gasto_clinica_hoy = get_spend_today(campaign_clinica)
        gasto_facetech_hoy = get_spend_today(campaign_facetech)
        gasto_clinica_mes = get_spend_month(campaign_clinica, year, month)
        gasto_facetech_mes = get_spend_month(campaign_facetech, year, month)
        meta_clinica_7d = get_spend_range(campaign_clinica, chart_start, chart_end)
        meta_facetech_7d = get_spend_range(campaign_facetech, chart_start, chart_end)
    except Exception as e:
        logger.warning(f"No se pudo obtener Meta Ads: {e}. Usando valores 0.")
        meta_ok = False
        gasto_clinica_hoy = gasto_facetech_hoy = 0.0
        gasto_clinica_mes = gasto_facetech_mes = 0.0
        meta_clinica_7d = meta_facetech_7d = {}

    # --- Insights de alcance (posicionamiento de marca) ---
    _empty_ins = {"spend":0,"reach":0,"impressions":0,"frequency":0,"clicks":0,"ctr":0,"cpm":0,"cpp":0}
    logger.info("Obteniendo métricas de alcance...")
    try:
        ins_c_hoy    = get_insights_totals(campaign_clinica, today, today)
        ins_c_semana = get_insights_totals(campaign_clinica, chart_start, chart_end)
        ins_c_mes    = get_insights_totals(campaign_clinica, first_of_month, today)
        ins_f_hoy    = get_insights_totals(campaign_facetech, today, today)
        ins_f_semana = get_insights_totals(campaign_facetech, chart_start, chart_end)
        ins_f_mes    = get_insights_totals(campaign_facetech, first_of_month, today)
    except Exception as e:
        logger.warning(f"No se pudieron obtener insights de alcance: {e}")
        ins_c_hoy = ins_c_semana = ins_c_mes = _empty_ins
        ins_f_hoy = ins_f_semana = ins_f_mes = _empty_ins

    # 'ayer' tenía su propia clave de alcance apuntando a 'hoy' en el frontend,
    # así que el bloque de marca mostraba el alcance de hoy bajo la etiqueta Ayer.
    _yesterday = (date.today() - timedelta(days=1)).isoformat()
    try:
        ins_c_ayer = get_insights_totals(campaign_clinica, _yesterday, _yesterday)
        ins_f_ayer = get_insights_totals(campaign_facetech, _yesterday, _yesterday)
    except Exception as e:
        logger.warning(f"No se pudo obtener alcance de ayer: {e}")
        ins_c_ayer = ins_f_ayer = _empty_ins

    # --- Sheets ---
    # Una sola lectura por tab; los periodos se filtran en memoria. Antes se
    # llamaba a la API 3 veces por tab (hoy / mes / ayer) leyendo lo mismo.
    logger.info("Leyendo Google Sheets...")
    clinica_all = read_clinica()
    procs_all = read_procedimientos()
    facetech_all = read_facetech()

    def _on(rows, d):      return [r for r in rows if r["fecha"] == d]
    def _between(rows, a, b): return [r for r in rows if a <= r["fecha"] <= b]

    clinica_hoy = _on(clinica_all, today)
    procs_hoy = _on(procs_all, today)
    facetech_hoy = _on(facetech_all, today)

    # Filtrar solo el mes actual
    prefix = f"{year}-{month:02d}"
    clinica_mes = [r for r in clinica_all if r["fecha"].startswith(prefix)]
    procs_mes = [r for r in procs_all if r["fecha"].startswith(prefix)]
    facetech_mes = [r for r in facetech_all if r["fecha"].startswith(prefix)]

    # Histórico: desde el primer día con datos reales hasta hoy. El tab CLINICA
    # trae la columna Fecha pre-rellenada (filas en 0 antes del primer dato y
    # hasta 2027), así que se descartan para no arrastrar días vacíos ni correr
    # first_date hacia atrás.
    def _con_datos(r):
        # OJO: desde octubre la asistente muchos días llena SOLO "Citas Bot" /
        # "Citas Asistente" y deja "Citas Agendadas" vacía. Antes esas filas se
        # descartaban y el dashboard mostraba 6 citas de la asistente en el mes
        # cuando el Sheet tenía 24 (reclamo de la clínica 2026-10-20).
        return any(r.get(k, 0) > 0 for k in (
            "citas_agendadas", "total_facturado", "citas_bot", "citas_asistente",
            "citas_virtual", "citas_presencial"))

    clinica_todo = [r for r in _between(clinica_all, "0000-00-00", today) if _con_datos(r)]
    procs_todo = _between(procs_all, "0000-00-00", today)
    facetech_todo = [r for r in _between(facetech_all, "0000-00-00", today)
                     if r.get("leads", 0) > 0 or r.get("compras", 0) > 0]

    _fechas = [r["fecha"] for r in clinica_todo + procs_todo + facetech_todo]
    first_date = min(_fechas) if _fechas else today

    # --- Serie diaria (alimenta el rango de fechas custom en el frontend) ---
    logger.info(f"Obteniendo serie diaria Meta desde {first_date}...")
    try:
        daily_meta_clinica = get_insights_daily(campaign_clinica, first_date, today)
        daily_meta_facetech = get_insights_daily(campaign_facetech, first_date, today)
    except Exception as e:
        logger.warning(f"No se pudo obtener la serie diaria de Meta: {e}")
        daily_meta_clinica = daily_meta_facetech = {}

    # Alcance del histórico: se le pide a Meta el rango exacto para que 'reach'
    # sean personas únicas reales y no una suma de días.
    try:
        ins_c_todo = get_insights_totals(campaign_clinica, first_date, today)
        ins_f_todo = get_insights_totals(campaign_facetech, first_date, today)
    except Exception as e:
        logger.warning(f"No se pudo obtener alcance histórico: {e}")
        ins_c_todo = ins_f_todo = _empty_ins

    # --- KPIs hoy, mes y todo ---
    clinica_kpis_hoy = calc_clinica_day(clinica_hoy, procs_hoy, gasto_clinica_hoy, precio_cita)
    clinica_kpis_mes = calc_clinica_day(clinica_mes, procs_mes, gasto_clinica_mes, precio_cita)
    facetech_kpis_hoy = calc_facetech_day(facetech_hoy, gasto_facetech_hoy)
    facetech_kpis_mes = calc_facetech_day(facetech_mes, gasto_facetech_mes)

    gasto_clinica_todo = sum(v["spend"] for v in daily_meta_clinica.values())
    gasto_facetech_todo = sum(v["spend"] for v in daily_meta_facetech.values())
    clinica_kpis_todo = calc_clinica_day(clinica_todo, procs_todo, gasto_clinica_todo, precio_cita)
    facetech_kpis_todo = calc_facetech_day(facetech_todo, gasto_facetech_todo)

    # --- Chart 7 días ---
    chart_dates = [(date.today() - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    chart_data = build_chart_data(
        clinica_mes, meta_clinica_7d,
        facetech_mes, meta_facetech_7d,
        chart_dates, precio_cita,
        daily_procs=procs_mes,
    )

    # --- KPIs ayer ---
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    clinica_ayer = read_clinica(yesterday)
    procs_ayer = read_procedimientos(yesterday)
    facetech_ayer = read_facetech(yesterday)
    gasto_clinica_ayer = meta_clinica_7d.get(yesterday, 0.0) if isinstance(meta_clinica_7d, dict) else 0.0
    gasto_facetech_ayer = meta_facetech_7d.get(yesterday, 0.0) if isinstance(meta_facetech_7d, dict) else 0.0
    clinica_kpis_ayer = calc_clinica_day(clinica_ayer, procs_ayer, gasto_clinica_ayer, precio_cita)
    facetech_kpis_ayer = calc_facetech_day(facetech_ayer, gasto_facetech_ayer)

    # --- KPIs semana (últimos 7 días) ---
    clinica_semana = [r for r in clinica_mes if r["fecha"] >= chart_start]
    procs_semana = [r for r in procs_mes if r["fecha"] >= chart_start]
    facetech_semana = [r for r in facetech_mes if r["fecha"] >= chart_start]
    gasto_clinica_semana = sum(meta_clinica_7d.values()) if isinstance(meta_clinica_7d, dict) else 0.0
    gasto_facetech_semana = sum(meta_facetech_7d.values()) if isinstance(meta_facetech_7d, dict) else 0.0
    clinica_kpis_semana = calc_clinica_day(clinica_semana, procs_semana, gasto_clinica_semana, precio_cita)
    facetech_kpis_semana = calc_facetech_day(facetech_semana, gasto_facetech_semana)

    # --- Bot vs Asistente ---
    # Canal por nombre de campaña (ver get_channel_daily). Si falla, la pestaña
    # sale vacía pero el resto del dashboard se actualiza igual.
    logger.info("Obteniendo Bot vs Asistente...")
    try:
        meta_bot = get_channel_daily("bot", first_date, today, [campaign_facetech])
        meta_asistente = get_channel_daily("asistente", first_date, today, [campaign_facetech])
    except Exception as e:
        logger.warning(f"No se pudo obtener Meta por canal: {e}")
        meta_bot = meta_asistente = {}
    pancake_bot = get_bot_daily(first_date)
    calendar_bot = get_bot_calendar_daily(first_date)

    def _canales(a: str, b: str) -> dict:
        def _rng(d): return {k: v for k, v in d.items() if a <= k <= b}
        return calc_canales(_between(clinica_todo, a, b), _between(procs_todo, a, b),
                            _rng(meta_bot), _rng(meta_asistente), _rng(pancake_bot),
                            precio_cita, _rng(calendar_bot) if calendar_bot else None)

    canales = {
        "hoy":    _canales(today, today),
        "ayer":   _canales(_yesterday, _yesterday),
        "semana": _canales(chart_start, today),
        "mes":    _canales(first_of_month, today),
        "todo":   _canales(first_date, today),
    }

    data = {
        "updated_at": f"{today} {datetime.now().strftime('%H:%M')}",
        "today": today,
        "precio_cita": precio_cita,
        "first_date": first_date,
        "clinica": {
            "hoy":    clinica_kpis_hoy,
            "ayer":   clinica_kpis_ayer,
            "semana": clinica_kpis_semana,
            "mes":    clinica_kpis_mes,
            "todo":   clinica_kpis_todo,
        },
        "facetech": {
            "hoy":    facetech_kpis_hoy,
            "ayer":   facetech_kpis_ayer,
            "semana": facetech_kpis_semana,
            "mes":    facetech_kpis_mes,
            "todo":   facetech_kpis_todo,
        },
        "canales": canales,
        "chart": chart_data,
        # Serie cruda por día: el frontend la usa para calcular rangos de fechas
        # arbitrarios sin backend (el dashboard es estático en GitHub Pages).
        "daily": {
            "clinica":       clinica_todo,
            "procedimientos": procs_todo,
            "facetech":      facetech_todo,
            "meta_clinica":  daily_meta_clinica,
            "meta_facetech": daily_meta_facetech,
            "meta_bot":       meta_bot,
            "meta_asistente": meta_asistente,
            "pancake_bot":    pancake_bot,
            "calendar_bot":   calendar_bot,
        },
    }

    # --- Conclusiones ---
    def _num(n): return f"{int(n):,}".replace(",", ".")

    def conclusiones_clinica(ins: dict, kpis: dict, label: str) -> list:
        out = []
        reach       = ins.get("reach", 0)
        freq        = ins.get("frequency", 0)
        ctr         = ins.get("ctr", 0)
        impressions = ins.get("impressions", 0)
        clicks      = ins.get("clicks", 0)
        cpp         = ins.get("cpp", 0)
        if reach > 0:
            out.append(f"📣 {label} tu clínica llegó a {_num(reach)} personas únicas en la región — excelente alcance de marca.")
        if impressions > 0:
            out.append(f"👁️ {_num(impressions)} impresiones generadas — tu clínica estuvo presente en la mente de los pacientes de la zona.")
        if freq > 0:
            if freq < 2:
                out.append(f"🚀 Con {freq:.1f}x de frecuencia, tu anuncio está llegando constantemente a nuevas personas — la audiencia de la clínica sigue creciendo.")
            elif freq <= 4:
                out.append(f"✅ Frecuencia {freq:.1f}x — nivel óptimo de recordación. Tu marca está perfectamente posicionada en la mente de los pacientes.")
            else:
                out.append(f"💪 Frecuencia {freq:.1f}x — tu audiencia conoce muy bien la clínica. Excelente nivel de recordación de marca logrado.")
        if ctr > 0:
            bench = 1.5
            if ctr >= bench:
                out.append(f"🎯 CTR {ctr:.2f}% — supera el promedio médico ({bench}%). Los pacientes sienten una fuerte atracción por el anuncio de la clínica.")
            else:
                out.append(f"📊 CTR {ctr:.2f}% — el {ctr:.2f}% de las personas que vieron el anuncio hicieron clic para conocer más sobre la clínica.")
        if clicks > 0:
            out.append(f"🖱️ {_num(clicks)} personas hicieron clic para conocer más sobre la clínica — interés real y concreto demostrado.")
        if cpp > 0 and reach > 0:
            out.append(f"💰 Costo por persona alcanzada: ${_num(cpp)} COP — inversión eficiente para posicionar la marca en la región.")
        return out[:5]

    def conclusiones_facetech(ins: dict, kpis: dict, label: str) -> list:
        out = []
        reach       = ins.get("reach", 0)
        freq        = ins.get("frequency", 0)
        ctr         = ins.get("ctr", 0)
        impressions = ins.get("impressions", 0)
        clicks      = ins.get("clicks", 0)
        cpp         = ins.get("cpp", 0)
        if reach > 0:
            out.append(f"📣 {label} FaceTech llegó a {_num(reach)} personas únicas — potenciales asistentes al congreso ya en el radar.")
        if impressions > 0:
            out.append(f"👁️ {_num(impressions)} impresiones generadas — el congreso FaceTech está presente en la mente de los profesionales de la región.")
        if freq > 0:
            if freq <= 4:
                out.append(f"✅ Frecuencia {freq:.1f}x — excelente nivel de recordación para el evento. Los profesionales están recordando el congreso FaceTech.")
            else:
                out.append(f"💪 Frecuencia {freq:.1f}x — el congreso FaceTech es ampliamente reconocido en la audiencia objetivo. Gran posicionamiento logrado.")
        if ctr > 0:
            bench = 1.8
            if ctr >= bench:
                out.append(f"🎯 CTR {ctr:.2f}% — por encima del promedio de eventos ({bench}%). Gran atracción e interés generados por el congreso.")
            else:
                out.append(f"📊 CTR {ctr:.2f}% — el {ctr:.2f}% de los profesionales que vieron el anuncio quisieron conocer más sobre el congreso FaceTech.")
        if clicks > 0:
            out.append(f"🖱️ {_num(clicks)} profesionales hicieron clic para conocer el congreso — interés genuino y demanda comprobada.")
        if cpp > 0 and reach > 0:
            out.append(f"💰 Costo por persona alcanzada: ${_num(cpp)} COP — excelente eficiencia para posicionar el congreso FaceTech en la región.")
        return out[:5]

    label_map = {"hoy": "Hoy", "semana": "Esta semana", "mes": "Este mes"}

    data["alcance"] = {
        "clinica": {
            "hoy":    ins_c_hoy,
            "ayer":   ins_c_ayer,
            "semana": ins_c_semana,
            "mes":    ins_c_mes,
            "todo":   ins_c_todo,
        },
        "facetech": {
            "hoy":    ins_f_hoy,
            "ayer":   ins_f_ayer,
            "semana": ins_f_semana,
            "mes":    ins_f_mes,
            "todo":   ins_f_todo,
        },
    }
    data["conclusiones"] = {
        "clinica": {
            "hoy":    conclusiones_clinica(ins_c_hoy,    data["clinica"]["hoy"],    "Hoy"),
            "ayer":   conclusiones_clinica(ins_c_ayer,   data["clinica"]["ayer"],   "Ayer"),
            "semana": conclusiones_clinica(ins_c_semana, data["clinica"]["semana"], "Esta semana"),
            "mes":    conclusiones_clinica(ins_c_mes,    data["clinica"]["mes"],    "Este mes"),
            "todo":   conclusiones_clinica(ins_c_todo,   data["clinica"]["todo"],   "Desde el inicio"),
        },
        "facetech": {
            "hoy":    conclusiones_facetech(ins_f_hoy,    data["facetech"]["hoy"],    "Hoy"),
            "ayer":   conclusiones_facetech(ins_f_ayer,   data["facetech"]["ayer"],   "Ayer"),
            "semana": conclusiones_facetech(ins_f_semana, data["facetech"]["semana"], "Esta semana"),
            "mes":    conclusiones_facetech(ins_f_mes,    data["facetech"]["mes"],    "Este mes"),
            "todo":   conclusiones_facetech(ins_f_todo,   data["facetech"]["todo"],   "Desde el inicio"),
        },
    }

    data["_meta_ok"] = meta_ok
    logger.info("Datos construidos correctamente")
    return data

def save_data(data: dict):
    out = Path(__file__).parent / "dashboard" / "data.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    logger.info(f"data.json guardado en {out}")

def deploy_github():
    """Push dashboard/ a GitHub Pages (rama gh-pages)."""
    try:
        token = env_loader.get_optional("GITHUB_TOKEN")
        repo = env_loader.get_optional("GITHUB_REPO")
        if not token or not repo:
            logger.warning("GITHUB_TOKEN o GITHUB_REPO no configurados, omitiendo deploy.")
            return

        dashboard_dir = Path(__file__).parent / "dashboard"
        user_email = "bot@dr-bareno-dashboard.com"
        user_name = "Dr Bareno Bot"

        cmds = [
            f'cd "{dashboard_dir}"',
            "git init",
            f'git config user.email "{user_email}"',
            f'git config user.name "{user_name}"',
            "git checkout -B gh-pages",
            "git add -A",
            'git commit -m "chore: actualizar data.json" --allow-empty',
            f'git push -f https://x-access-token:{token}@github.com/{repo}.git gh-pages',
        ]
        subprocess.run(" && ".join(cmds), shell=True, check=True)
        logger.info(f"Deploy a GitHub Pages exitoso: {repo}")
    except Exception as e:
        logger.error(f"Error en deploy: {e}")

if __name__ == "__main__":
    try:
        data = build_data()
        # Antes, si Meta fallaba no se escribía nada y las ventas del Sheet/Pancake
        # quedaban congeladas semanas (token muerto 2026-09-08). Ahora se publica
        # igual y el frontend avisa que gasto/ROAS no están al día.
        meta_ok = data.pop("_meta_ok", True)
        prev_path = Path(__file__).parent / "dashboard" / "data.json"
        try:
            prev = json.loads(prev_path.read_text(encoding="utf-8"))
        except Exception:
            prev = {}
        data["meta_ok"] = meta_ok
        if meta_ok:
            data["meta_last_ok"] = data["updated_at"]
        else:
            data["meta_last_ok"] = prev.get("meta_last_ok") or (
                prev.get("updated_at") if prev.get("meta_ok", True) else None)
            logger.warning(f"Meta API falló (token o rate limit). Se publican ventas igual; gasto Meta en 0. Último Meta OK: {data['meta_last_ok']}")
        save_data(data)
        deploy_github()
        logger.info("=== Actualización completada ===")
    except Exception as e:
        logger.error(f"Error fatal: {e}")
        sys.exit(1)
