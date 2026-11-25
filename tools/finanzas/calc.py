"""Estado de resultados mensual de la clínica (pestaña 💰 Finanzas).

Reglas acordadas con el Dr. Bareño (nov-2026):
  - El mes se mide por cirugías REALIZADAS en el mes (fecha de PROCEDIMIENTOS).
  - Costo de cada cirugía = "Costos Salas" (clínica, anestesiólogo, insumos,
    instrumentadora). Cirugía en el consultorio = Costos Salas en 0: solo gasta
    insumos (≈ 500.000 c/u, o el inventario real anotado en GASTOS DEL MES).
  - Comisión de Silvia por cirugías realizadas: <15 → 1M, 15–19 → 1,5M,
    20–24 → 2M, 25 o más → 2,5M (tope).
  - Comisión de tarjeta: el banco consigna neto, así que no está en el gasto
    bancario. Datáfono / crédito 3,29% + 300 + IVA; Wompi 2,65% + 700 + IVA.
    Transferencia y efectivo llegan completos.
  - Dólares: tasa del día de pago; no se usan para comisiones (son transferencias).
  - Impuestos: se muestra antes y después. Después = menos ICA (8,4 por mil de
    los ingresos, mensual) y renta del 35% sobre la utilidad.
"""
import unicodedata

IVA = 0.19
TARIFAS = {  # forma de pago → (porcentaje, fijo por transacción), antes de IVA
    "tarjeta": (0.0329, 300), "datafono": (0.0329, 300), "crédito": (0.0329, 300),
    "credito": (0.0329, 300), "wompi": (0.0265, 700),
}
ICA_POR_MIL = 8.4
RENTA = 0.35
CX_MIN = 1_000_000  # un procedimiento de este valor o más cuenta como cirugía
ESCALAS_SILVIA = [(25, 2_500_000), (20, 2_000_000), (15, 1_500_000), (0, 1_000_000)]

MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio",
         "agosto", "septiembre", "octubre", "noviembre", "diciembre"]


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s)).encode("ascii", "ignore").decode()
    return " ".join(s.lower().split())


def comision_silvia(n: int) -> float:
    if n <= 0:
        return 0.0
    return next(v for minimo, v in ESCALAS_SILVIA if n >= minimo)


def comision_pago(valor: float, forma: str) -> float:
    pct, fijo = TARIFAS.get(_norm(forma), (0, 0))
    return 0.0 if not pct else (valor * pct + fijo) * (1 + IVA)


def _vigente(item: dict, mes: str) -> bool:
    return (not item["desde"] or item["desde"] <= mes) and (not item["hasta"] or mes <= item["hasta"])


def calc_mes(mes: str, fin: dict, clinica: list, meta_daily: dict,
             precio_cita: float, hoy: str) -> dict:
    """Estado de resultados de un mes 'YYYY-MM'."""
    pendientes = []
    procs = [p for p in fin["procedimientos"] if p["fecha"].startswith(mes)]
    cirugias = [p for p in procs if p["valor"] >= CX_MIN]
    locales = [p for p in cirugias if p["tiene_sala"] and p["sala"] == 0]
    sin_sala = [p for p in cirugias if not p["tiene_sala"]]
    if not cirugias:
        pendientes.append("Aún no hay cirugías registradas este mes en PROCEDIMIENTOS: "
                          "por ahora solo se ven los gastos fijos.")
    if sin_sala:
        pendientes.append(f"{len(sin_sala)} cirugía(s) sin costo de sala en PROCEDIMIENTOS: "
                          "la utilidad sale más alta de lo real hasta que se llene.")

    # ── Ingresos ──
    ing_cx = sum(p["valor"] for p in cirugias)
    ing_otros_proc = sum(p["valor"] for p in procs if p["valor"] < CX_MIN)
    ing_consultas = sum(r["total_facturado"] if r.get("tiene_total") else r["citas_agendadas"] * precio_cita
                        for r in clinica if r["fecha"].startswith(mes))
    ing_fijos = [{"concepto": f["concepto"], "valor": f["valor"]}
                 for f in fin["fijos"] if f["tipo"] == "INGRESO" and _vigente(f, mes)]
    ingresos = [
        {"concepto": f"Cirugías ({len(cirugias)})", "valor": ing_cx},
        {"concepto": "Consultas", "valor": ing_consultas},
    ]
    if ing_otros_proc:
        ingresos.append({"concepto": "Otros procedimientos", "valor": ing_otros_proc})
    ingresos += ing_fijos
    total_ing = sum(i["valor"] for i in ingresos)

    # ── Gastos reales del mes (GASTOS DEL MES) por concepto ──
    reales: dict[str, list] = {}
    for g in fin["gastos_mes"]:
        if g["mes"] == mes:
            reales.setdefault(_norm(g["concepto"]), []).append(g)
    usados = set()

    variables = [{"concepto": "Salas de cirugía", "valor": sum(p["sala"] for p in cirugias),
                  "nota": "Clínica, anestesiólogo, insumos e instrumentadora"}]
    grupos: dict[str, list] = {}

    for f in fin["fijos"]:
        if f["tipo"] in ("INGRESO", "EVENTUAL") or not _vigente(f, mes):
            continue
        clave = _norm(f["concepto"])
        item = {"concepto": f["concepto"], "valor": f["valor"]}
        if f["tipo"] == "ANUAL":
            item["valor"] = f["valor"] / 12
            item["nota"] = "Pago anual repartido en 12"
        elif f["tipo"] in ("ESTIMADO", "POR CX LOCAL"):
            if clave in reales:
                usados.add(clave)
                item["valor"] = sum(g["valor"] for g in reales[clave])
                item["nota"] = "Factura real"
            elif f["tipo"] == "POR CX LOCAL":
                item["valor"] = f["valor"] * len(locales)
                item["estimado"] = True
                item["nota"] = f"{len(locales)} cirugía(s) en consultorio × {int(f['valor']):,}".replace(",", ".")
            else:
                item["estimado"] = True
                item["nota"] = "Estimado: falta la factura del mes"
        if f["categoria"].lower().startswith("costo variable"):
            variables.append(item)
        else:
            grupos.setdefault(f["categoria"], []).append(item)

    n_cx = len(cirugias)
    variables.append({"concepto": "Comisión Silvia", "valor": comision_silvia(n_cx),
                      "nota": f"{n_cx} cirugías realizadas"})
    pagos_mes = [p for p in fin["pagos"] if p["fecha"].startswith(mes) and p["moneda"] == "COP"]
    com_tarjeta = sum(comision_pago(p["valor"], p["forma"]) for p in pagos_mes)
    n_tarjeta = sum(1 for p in pagos_mes if comision_pago(p["valor"], p["forma"]))
    variables.append({"concepto": "Comisiones de tarjeta", "valor": com_tarjeta,
                      "nota": f"{n_tarjeta} pago(s) con tarjeta/Wompi"})
    if not pagos_mes and cirugias:
        pendientes.append("No hay pagos de este mes en la pestaña PAGOS: falta la comisión de tarjeta.")

    # Gastos del mes que no reemplazan un estimado (fumigación, software…)
    otros = [{"concepto": g["concepto"], "valor": g["valor"], "nota": g["nota"] or "Gasto del mes"}
             for clave, lista in reales.items() if clave not in usados for g in lista]
    if otros:
        grupos.setdefault("Gastos del mes", []).extend(otros)

    total_var = sum(v["valor"] for v in variables)
    fijos = [{"categoria": c, "items": items, "total": sum(i["valor"] for i in items)}
             for c, items in grupos.items()]
    total_fijos = sum(g["total"] for g in fijos)
    meta = sum(v["spend"] for d, v in meta_daily.items() if d.startswith(mes))

    antes = total_ing - total_var - total_fijos - meta
    ica = total_ing * ICA_POR_MIL / 1000
    renta = max(0.0, antes - ica) * RENTA
    despues = antes - ica - renta

    # Cirugías necesarias para cubrir los fijos + Meta con el margen promedio
    margen_cx = [p["valor"] - p["sala"] for p in cirugias if p["tiene_sala"]]
    margen_prom = sum(margen_cx) / len(margen_cx) if margen_cx else 0
    equilibrio = (total_fijos + meta) / margen_prom if margen_prom > 0 else None

    if any(v.get("estimado") for v in variables) or any(i.get("estimado") for g in fijos for i in g["items"]):
        pendientes.append("Hay valores estimados (marcados con ≈): se reemplazan solos al anotar la factura en GASTOS DEL MES.")

    a, m = mes.split("-")
    return {
        "mes": mes,
        "label": f"{MESES[int(m) - 1].capitalize()} {a}",
        "en_curso": hoy.startswith(mes),
        "ingresos": ingresos, "total_ingresos": total_ing,
        "variables": variables, "total_variables": total_var,
        "fijos": fijos, "total_fijos": total_fijos,
        "meta": meta,
        "utilidad_antes": antes, "ica": ica, "renta": renta, "utilidad_despues": despues,
        "margen": antes / total_ing if total_ing else 0,
        "n_cirugias": n_cx,
        "ticket_promedio": ing_cx / n_cx if n_cx else 0,
        "equilibrio_cx": equilibrio,
        "cirugias": [{"fecha": p["fecha"], "tipo": p["tipo"], "valor": p["valor"],
                      "sala": p["sala"] if p["tiene_sala"] else None} for p in cirugias],
        "pendientes": pendientes,
    }


def calc_finanzas(fin: dict, clinica: list, meta_daily: dict, precio_cita: float,
                  hoy: str, desde: str = "2026-10") -> dict:
    meses, a, m = [], int(desde[:4]), int(desde[5:7])
    while f"{a:04d}-{m:02d}" <= hoy[:7]:
        meses.append(f"{a:04d}-{m:02d}")
        a, m = (a + 1, 1) if m == 12 else (a, m + 1)
    return {"meses": [calc_mes(x, fin, clinica, meta_daily, precio_cita, hoy) for x in meses]}
