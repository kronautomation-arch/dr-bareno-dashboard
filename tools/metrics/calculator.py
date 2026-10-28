def _safe_div(numerator: float, denominator: float, default=0.0) -> float:
    if denominator == 0:
        return default
    return numerator / denominator

def _ingresos_citas(clinica_rows: list, precio_cita: float) -> float:
    """Suma 'Total $$' del Sheet por fila; si esa fila no lo trae, cae a citas × precio."""
    total = 0.0
    for r in clinica_rows:
        if r.get("tiene_total"):
            total += r["total_facturado"]
        else:
            total += r["citas_agendadas"] * precio_cita
    return total

def build_desglose(procedimientos_rows: list) -> list:
    """Agrupa por tipo de cirugía los procedimientos ya facturados.

    Sólo entra valor > 0: el Sheet también registra cirugías futuras agendadas
    con la casilla Valor todavía vacía, y contarlas aquí las mostraría como $0.
    Sin nombres de pacientes: data.json se publica sin auth (ver read_procedimientos).
    """
    por_tipo: dict = {}
    for r in procedimientos_rows:
        if r["valor"] <= 0:
            continue
        t = por_tipo.setdefault(r["tipo"], {"tipo": r["tipo"], "cantidad": 0, "valor": 0.0})
        t["cantidad"] += 1
        t["valor"] += r["valor"]
    return sorted(por_tipo.values(), key=lambda t: t["valor"], reverse=True)

def calc_clinica_day(clinica_rows: list, procedimientos_rows: list, gasto_meta: float, precio_cita: float) -> dict:
    citas = sum(r["citas_agendadas"] for r in clinica_rows)
    # La columna 'Procedimientos Vendidos' de CLINICA está vacía en todo el Sheet,
    # así que el conteo real sale del tab PROCEDIMIENTOS. Se respeta la columna
    # si algún día se llena.
    procedimientos = (sum(r["procedimientos_vendidos"] for r in clinica_rows)
                      or len([r for r in procedimientos_rows if r["valor"] > 0]))
    agendados = len([r for r in procedimientos_rows if r["valor"] <= 0])
    ingresos_citas = _ingresos_citas(clinica_rows, precio_cita)
    ingresos_procedimientos = sum(r["valor"] for r in procedimientos_rows)
    ingresos_totales = ingresos_citas + ingresos_procedimientos

    return {
        "citas_agendadas": citas,
        "procedimientos_vendidos": procedimientos,
        "procedimientos_agendados": agendados,
        "tasa_conversion": round(_safe_div(procedimientos, citas) * 100, 1),
        "ingresos_citas": ingresos_citas,
        "ingresos_procedimientos": ingresos_procedimientos,
        "ingresos_totales": ingresos_totales,
        "desglose_procedimientos": build_desglose(procedimientos_rows),
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
                     dates: list[str], precio_cita: float,
                     daily_procs: list = None) -> dict:
    """Construye datos para la gráfica de 7 días."""
    daily_procs = daily_procs or []
    clinica_ingresos = []
    clinica_gasto = []
    facetech_ingresos = []
    facetech_gasto = []

    for d in dates:
        c_rows = [r for r in daily_clinica if r["fecha"] == d]
        p_procs = sum(r["valor"] for r in daily_procs if r["fecha"] == d)
        clinica_ingresos.append(_ingresos_citas(c_rows, precio_cita) + p_procs)
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

# --- Bot vs Asistente ---

def _ingresos_citas_canal(clinica_rows: list, precio_cita: float) -> dict:
    """Reparte el 'Total $$' de cada día entre canales según sus citas.

    El Sheet factura las citas por día, no por canal: si un día hubo 3 citas del
    bot y 1 de la asistente, el bot se lleva 3/4 de lo facturado ese día.
    """
    out = {"bot": 0.0, "asistente": 0.0}
    for r in clinica_rows:
        total_dia = r["total_facturado"] if r.get("tiene_total") else r["citas_agendadas"] * precio_cita
        citas_dia = r["citas_agendadas"] or (r.get("citas_bot", 0) + r.get("citas_asistente", 0))
        for canal in out:
            out[canal] += _safe_div(total_dia * r.get(f"citas_{canal}", 0), citas_dia)
    return out

def calc_canales(clinica_rows: list, procedimientos_rows: list,
                 meta_bot: dict, meta_asistente: dict, pancake_bot: dict,
                 precio_cita: float, calendar_bot: dict | None = None) -> dict:
    """KPIs lado a lado de Bot vs Asistente para un periodo.

    meta_* y pancake_bot son series diarias ya filtradas al periodo.
    Las citas y ventas salen del Sheet (la misma fuente para los dos);
    'control_pancake' es lo que el bot dice que agendó según sus etiquetas.

    Desde 2026-10-19 las citas del BOT salen del Google Calendar del Dr.
    (`calendar_bot`, ver tools/agenda/citas_bot.py) cuando está disponible: la
    columna `Citas Bot` del Sheet casi no se llenaba y el dashboard mostraba 5
    citas del bot cuando la agenda tenía 22. `calendar_bot` = None → Sheet.
    """
    ingresos_citas = _ingresos_citas_canal(clinica_rows, precio_cita)
    citas_total = sum(r["citas_agendadas"] for r in clinica_rows)
    out = {}
    for canal, meta in (("bot", meta_bot), ("asistente", meta_asistente)):
        gasto = sum(v["spend"] for v in meta.values())
        convs = sum(v["conversaciones"] for v in meta.values())
        citas = sum(r.get(f"citas_{canal}", 0) for r in clinica_rows)
        ing_citas = ingresos_citas[canal]
        if canal == "bot" and calendar_bot is not None:
            citas = sum(v["citas"] for v in calendar_bot.values())
            ing_citas = citas * precio_cita
        vendidos = [p for p in procedimientos_rows if p.get("canal") == canal and p["valor"] > 0]
        ing_procs = sum(p["valor"] for p in vendidos)
        n_vendidos = len(vendidos)
        # Cirugías de pacientes del bot vistas en el calendario: la columna
        # Canal del Sheet no se llena, así que el conteo no puede depender de
        # ella. El valor sí sale del Sheet (el calendario no lo trae limpio).
        if canal == "bot" and calendar_bot is not None:
            n_vendidos = max(n_vendidos, sum(v.get("cirugias", 0) for v in calendar_bot.values()))
        ingresos = ing_citas + ing_procs
        out[canal] = {
            "gasto_meta": gasto,
            "conversaciones": convs,
            "costo_por_conversacion": round(_safe_div(gasto, convs)),
            "citas": citas,
            "tasa_conv_cita": round(_safe_div(citas, convs) * 100, 1),
            "costo_por_cita": round(_safe_div(gasto, citas)),
            "procedimientos_vendidos": n_vendidos,
            "tasa_cita_venta": round(_safe_div(n_vendidos, citas) * 100, 1),
            "ingresos_citas": round(ing_citas),
            "ingresos_procedimientos": ing_procs,
            "ingresos": round(ingresos),
            "roas": round(_safe_div(ingresos, gasto), 2),
        }
    out["bot"]["fuente_citas"] = "calendario" if calendar_bot is not None else "sheet"
    out["bot"]["cirugias_agendadas"] = sum(v.get("cirugias", 0) for v in (calendar_bot or {}).values())
    out["bot"]["control_pancake"] = {
        "conversaciones": sum(v["conversaciones"] for v in pancake_bot.values()),
        "citas": sum(v["citas"] for v in pancake_bot.values()),
    }
    atribuidas = out["bot"]["citas"] + out["asistente"]["citas"]
    out["sin_atribuir"] = {
        "citas": max(0, citas_total - atribuidas),
        "procedimientos": len([p for p in procedimientos_rows if not p.get("canal") and p["valor"] > 0]),
    }
    return out
