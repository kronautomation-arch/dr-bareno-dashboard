def _safe_div(numerator: float, denominator: float, default=0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator

def calc_clinica_day(clinica_rows: list, procedimientos_rows: list, gasto_meta: float, precio_cita: float) -> dict:
    citas = sum(r["citas_agendadas"] for r in clinica_rows)
    procedimientos = sum(r["procedimientos_vendidos"] for r in clinica_rows)
    ingresos_citas = citas * precio_cita
    ingresos_procedimientos = sum(r["valor"] for r in procedimientos_rows)
    ingresos_totales = ingresos_citas + ingresos_procedimientos

    return {
        "citas_agendadas": citas,
        "procedimientos_vendidos": procedimientos,
        "tasa_conversion": round(_safe_div(procedimientos, citas) * 100, 1),
        "ingresos_citas": ingresos_citas,
        "ingresos_procedimientos": ingresos_procedimientos,
        "ingresos_totales": ingresos_totales,
        "gasto_meta": gasto_meta,
        "costo_por_cita": round(_safe_div(gasto_meta, citas)),
        "porcentaje_publicidad": round(_safe_div(gasto_meta, ingresos_totales) * 100, 1),
        "utilidad_bruta": ingresos_totales - gasto_meta,
        "roas": round(_safe_div(ingresos_totales, gasto_meta), 2),
    }

def calc_facetech_day(facetech_rows: list, gasto_meta: float) -> dict:
    leads = sum(r["leads"] for r in facetech_rows)
    compras = sum(r["compras"] for r in facetech_rows)
    # Promedio del valor ticket si hay múltiples filas
    tickets = [r["valor_ticket"] for r in facetech_rows if r["valor_ticket"] > 0]
    valor_ticket = tickets[0] if tickets else 0
    ingresos = compras * valor_ticket

    return {
        "leads": leads,
        "compras": compras,
        "valor_ticket": valor_ticket,
        "tasa_conversion": round(_safe_div(compras, leads) * 100, 1),
        "ingresos": ingresos,
        "gasto_meta": gasto_meta,
        "costo_por_lead": round(_safe_div(gasto_meta, leads)),
        "costo_por_compra": round(_safe_div(gasto_meta, compras)),
        "utilidad_bruta": ingresos - gasto_meta,
        "roas": round(_safe_div(ingresos, gasto_meta), 2),
    }

def build_chart_data(daily_clinica: list, daily_meta_clinica: dict,
                     daily_facetech: list, daily_meta_facetech: dict,
                     dates: list[str], precio_cita: float) -> dict:
    """Construye datos para la gráfica de 7 días."""
    clinica_ingresos = []
    clinica_gasto = []
    facetech_ingresos = []
    facetech_gasto = []

    for d in dates:
        c_rows = [r for r in daily_clinica if r["fecha"] == d]
        p_citas = sum(r["citas_agendadas"] for r in c_rows)
        p_procs = sum(r.get("ingresos_procedimientos", 0) for r in c_rows)
        clinica_ingresos.append(p_citas * precio_cita + p_procs)
        clinica_gasto.append(daily_meta_clinica.get(d, 0))

        f_rows = [r for r in daily_facetech if r["fecha"] == d]
        f_compras = sum(r["compras"] for r in f_rows)
        f_ticket = next((r["valor_ticket"] for r in f_rows if r["valor_ticket"] > 0), 0)
        facetech_ingresos.append(f_compras * f_ticket)
        facetech_gasto.append(daily_meta_facetech.get(d, 0))

    return {
        "labels": [d[5:] for d in dates],  # MM-DD
        "clinica_ingresos": clinica_ingresos,
        "clinica_gasto": clinica_gasto,
        "facetech_ingresos": facetech_ingresos,
        "facetech_gasto": facetech_gasto,
    }
