/* Pestaña "💰 Finanzas" — cuánto gana la clínica en el mes.
 *
 * data.json es público, así que el estado de resultados viene cifrado
 * (DATA.finanzas_enc, AES-GCM + PBKDF2, ver tools/finanzas/cifrado.py) y se
 * descifra aquí con la clave compartida del equipo. La clave queda guardada
 * en este teléfono para no pedirla cada vez.
 */
(function () {
  const KEY = 'fin_clave';
  let datos = null, mesSel = null, cajaActual = null;

  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const getClave = () => { try { return localStorage.getItem(KEY) || ''; } catch { return ''; } };
  const setClave = v => { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch {} };
  const pesos = n => (n < 0 ? '−' : '') + '$' + Math.round(Math.abs(n)).toLocaleString('es-CO');
  const millones = n => (n < 0 ? '−' : '') + '$' + (Math.abs(n) / 1e6).toLocaleString('es-CO', { maximumFractionDigits: 1 }) + ' M';
  const pct = n => (n * 100).toLocaleString('es-CO', { maximumFractionDigits: 0 }) + '%';

  const css = `
  #fin-root{padding-bottom:calc(120px + var(--safe-bottom));color:var(--txt)}
  .fin-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:4px 0 14px}
  .fin-h1{font-size:24px;font-weight:800}
  .fin-sub{font-size:14px;color:var(--txt2);margin-top:2px}
  .fin-meses{display:flex;gap:8px;overflow-x:auto;padding-bottom:4px;margin-bottom:16px;scrollbar-width:none}
  .fin-meses::-webkit-scrollbar{display:none}
  .fin-mes{flex:none;min-height:44px;padding:0 16px;border-radius:999px;border:1px solid var(--border2);background:var(--glass);
    color:var(--txt2);font-size:15px;font-weight:700;font-family:inherit;cursor:pointer}
  .fin-mes.on{background:var(--g1);border-color:var(--g2);color:#fff}
  .fin-hero{border-radius:24px;padding:20px;margin-bottom:14px;border:1px solid var(--border2);
    background:linear-gradient(135deg,rgba(5,150,105,.22),rgba(8,145,178,.12))}
  .fin-hero.neg{background:linear-gradient(135deg,rgba(190,18,60,.25),rgba(217,119,6,.12))}
  .fin-hero-l{font-size:14px;color:var(--txt2);font-weight:600}
  .fin-hero-v{font-size:40px;font-weight:800;line-height:1.1;margin-top:4px;letter-spacing:-.5px}
  .fin-hero-row{display:flex;justify-content:space-between;gap:12px;margin-top:14px;padding-top:14px;border-top:1px solid var(--border2)}
  .fin-hero-row b{display:block;font-size:22px;font-weight:800;margin-top:2px}
  .fin-hero-row span{font-size:13px;color:var(--txt2);font-weight:600}
  .fin-delta{font-size:14px;font-weight:700;margin-top:6px}
  .fin-delta.up{color:var(--g2)} .fin-delta.down{color:var(--r2)}
  .fin-kpis{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin-bottom:14px}
  .fin-kpi{background:var(--glass2);border:1px solid var(--border);border-radius:18px;padding:14px}
  .fin-kpi-l{font-size:13px;color:var(--txt2);font-weight:600}
  .fin-kpi-v{font-size:24px;font-weight:800;margin-top:4px}
  .fin-kpi-s{font-size:12px;color:var(--txt3);margin-top:2px}
  .fin-card{background:var(--glass2);border:1px solid var(--border);border-radius:20px;padding:16px;margin-bottom:14px}
  .fin-card h3{font-size:16px;font-weight:800;margin-bottom:10px}
  .fin-row{display:flex;justify-content:space-between;align-items:baseline;gap:12px;padding:9px 0;font-size:15px;border-bottom:1px solid var(--border)}
  .fin-row:last-child{border-bottom:0}
  .fin-row .c{color:var(--txt2)} .fin-row .v{font-weight:700;white-space:nowrap;font-variant-numeric:tabular-nums}
  .fin-row.tot{font-weight:800;font-size:16px}
  .fin-row.tot .c{color:var(--txt)}
  .fin-row.res{font-size:17px;font-weight:800;border-top:2px solid var(--border2);border-bottom:0;margin-top:4px;padding-top:12px}
  .fin-row.res .c{color:var(--txt)}
  .fin-pos{color:var(--g2)} .fin-neg{color:var(--r2)}
  .fin-note{display:block;font-size:12px;color:var(--txt3);margin-top:2px}
  .fin-est{display:inline-block;font-size:11px;font-weight:800;color:var(--a2);background:rgba(217,119,6,.16);border-radius:6px;padding:1px 6px;margin-left:6px}
  details.fin-card summary{list-style:none;cursor:pointer;display:flex;justify-content:space-between;align-items:center;font-size:16px;font-weight:800;min-height:28px}
  details.fin-card summary::-webkit-details-marker{display:none}
  details.fin-card summary::after{content:'›';font-size:22px;color:var(--txt3);transition:transform .2s}
  details.fin-card[open] summary::after{transform:rotate(90deg)}
  details.fin-card summary .v{margin-left:auto;margin-right:10px;font-variant-numeric:tabular-nums}
  details.fin-card[open] summary{margin-bottom:8px}
  .fin-grp{font-size:13px;color:var(--txt3);font-weight:800;text-transform:uppercase;letter-spacing:.4px;margin:12px 0 2px}
  .fin-bar{height:10px;border-radius:6px;background:var(--glass);overflow:hidden;display:flex;margin:6px 0 4px}
  .fin-bar i{display:block;height:100%}
  .fin-leg{display:flex;flex-wrap:wrap;gap:6px 14px;font-size:12px;color:var(--txt2)}
  .fin-leg b{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px;vertical-align:-1px}
  .fin-pend{border-radius:16px;padding:12px 14px;margin-bottom:14px;font-size:14px;line-height:1.45;
    background:rgba(217,119,6,.13);border:1px solid rgba(217,119,6,.5)}
  .fin-pend div+div{margin-top:6px}
  .fin-help{font-size:12px;color:var(--txt3);line-height:1.55;margin:4px 2px 18px}
  .fin-btn{min-height:52px;border-radius:16px;border:1px solid var(--border2);background:var(--g1);color:#fff;
    font-size:17px;font-weight:700;width:100%;font-family:inherit;cursor:pointer;margin-top:12px}
  .fin-link{background:none;border:0;color:var(--txt3);font-size:13px;font-family:inherit;padding:10px 0;cursor:pointer;min-height:44px}
  .fin-in{width:100%;min-height:52px;border-radius:14px;border:1px solid var(--border2);background:var(--glass);
    color:var(--txt);font-size:17px;padding:14px;margin-top:14px;font-family:inherit;box-sizing:border-box}
  .fin-lock{text-align:center;padding:36px 8px}
  .fin-lock .ico{font-size:44px}
  .fin-err{color:var(--r2);font-size:14px;margin-top:10px;min-height:20px}
  `;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  async function descifrar(caja, clave) {
    const b = s => Uint8Array.from(atob(s), c => c.charCodeAt(0));
    const base = await crypto.subtle.importKey('raw', new TextEncoder().encode(clave), 'PBKDF2', false, ['deriveKey']);
    const llave = await crypto.subtle.deriveKey(
      { name: 'PBKDF2', salt: b(caja.salt), iterations: caja.iter, hash: 'SHA-256' },
      base, { name: 'AES-GCM', length: 256 }, false, ['decrypt']);
    const plano = await crypto.subtle.decrypt({ name: 'AES-GCM', iv: b(caja.iv) }, llave, b(caja.ct));
    return JSON.parse(new TextDecoder().decode(plano));
  }

  const root = () => $('#fin-root');

  function pantallaClave(error) {
    root().innerHTML = `
      <div class="fin-lock">
        <div class="ico">🔒</div>
        <div class="fin-h1" style="margin-top:10px">Finanzas de la clínica</div>
        <div class="fin-sub">Escribe la clave del equipo para ver cuánto se gana en el mes.</div>
        <input class="fin-in" id="fin-clave" type="password" autocomplete="current-password" placeholder="Clave" />
        <button class="fin-btn" id="fin-entrar">Entrar</button>
        <div class="fin-err">${esc(error || '')}</div>
      </div>`;
    const go = () => entrar($('#fin-clave').value.trim());
    $('#fin-entrar').onclick = go;
    $('#fin-clave').onkeydown = e => { if (e.key === 'Enter') go(); };
  }

  async function entrar(clave) {
    if (!clave) return pantallaClave('Escribe la clave.');
    try {
      datos = await descifrar(cajaActual, clave);
      setClave(clave);
      render();
    } catch {
      setClave('');
      pantallaClave('La clave no es correcta.');
    }
  }

  function filas(items) {
    return items.map(i => `
      <div class="fin-row"><div class="c">${esc(i.concepto)}${i.estimado ? '<span class="fin-est">≈ estimado</span>' : ''}
        ${i.nota ? `<span class="fin-note">${esc(i.nota)}</span>` : ''}</div>
        <div class="v">${pesos(i.valor)}</div></div>`).join('');
  }

  function render() {
    if (!datos || !datos.meses || !datos.meses.length) {
      root().innerHTML = '<div class="fin-lock"><div class="fin-sub">Todavía no hay meses con datos.</div></div>';
      return;
    }
    const meses = datos.meses;
    if (!mesSel || !meses.find(m => m.mes === mesSel)) {
      const conCx = meses.filter(m => m.n_cirugias > 0);
      mesSel = (conCx.length ? conCx[conCx.length - 1] : meses[meses.length - 1]).mes;
    }
    const idx = meses.findIndex(m => m.mes === mesSel);
    const m = meses[idx], prev = meses[idx - 1];
    const neg = m.utilidad_antes < 0;
    const delta = prev ? m.utilidad_antes - prev.utilidad_antes : null;
    const costos = m.total_variables + m.total_fijos + m.meta;
    const total = Math.max(m.total_ingresos, costos, 1);
    const seg = (v, c) => `<i style="width:${Math.max(0, v / total * 100)}%;background:${c}"></i>`;

    root().innerHTML = `
      <div class="fin-top">
        <div><div class="fin-h1">💰 Finanzas</div>
        <div class="fin-sub">Cirugías realizadas en el mes, menos todos los costos</div></div>
      </div>
      <div class="fin-meses">${meses.map(x => `<button class="fin-mes ${x.mes === mesSel ? 'on' : ''}" data-mes="${x.mes}">${esc(x.label)}${x.en_curso ? ' · en curso' : ''}</button>`).join('')}</div>

      ${m.pendientes.length || datos.meta_ok === false ? `<div class="fin-pend">
        ${m.pendientes.map(p => `<div>⚠️ ${esc(p)}</div>`).join('')}
        ${datos.meta_ok === false ? '<div>⚠️ La inversión en Meta no se pudo actualizar en la última corrida.</div>' : ''}
      </div>` : ''}

      <div class="fin-hero ${neg ? 'neg' : ''}">
        <div class="fin-hero-l">Ganancia antes de impuestos · ${esc(m.label)}</div>
        <div class="fin-hero-v ${neg ? 'fin-neg' : ''}">${millones(m.utilidad_antes)}</div>
        ${delta !== null ? `<div class="fin-delta ${delta >= 0 ? 'up' : 'down'}">${delta >= 0 ? '▲' : '▼'} ${millones(Math.abs(delta))} vs ${esc(prev.label)}</div>` : ''}
        <div class="fin-hero-row">
          <div><span>Después de ICA y renta</span><b>${millones(m.utilidad_despues)}</b></div>
          <div style="text-align:right"><span>Margen</span><b>${pct(m.margen)}</b></div>
        </div>
      </div>

      <div class="fin-kpis">
        <div class="fin-kpi"><div class="fin-kpi-l">Cirugías</div><div class="fin-kpi-v">${m.n_cirugias}</div>
          <div class="fin-kpi-s">${m.n_cirugias ? 'Ticket ' + millones(m.ticket_promedio) : 'Sin registrar aún'}</div></div>
        <div class="fin-kpi"><div class="fin-kpi-l">Para cubrir gastos fijos</div>
          <div class="fin-kpi-v">${m.equilibrio_cx ? Math.ceil(m.equilibrio_cx) + ' cx' : '—'}</div>
          <div class="fin-kpi-s">Fijos + Meta ÷ margen por cirugía</div></div>
        <div class="fin-kpi"><div class="fin-kpi-l">Ingresos</div><div class="fin-kpi-v">${millones(m.total_ingresos)}</div></div>
        <div class="fin-kpi"><div class="fin-kpi-l">Costos totales</div><div class="fin-kpi-v">${millones(costos)}</div></div>
      </div>

      <div class="fin-card">
        <h3>Cómo se llega a la ganancia</h3>
        <div class="fin-bar">${seg(m.total_variables, 'var(--a2)')}${seg(m.total_fijos, 'var(--b2)')}${seg(m.meta, 'var(--p2)')}${seg(Math.max(0, m.utilidad_antes), 'var(--g2)')}</div>
        <div class="fin-leg"><span><b style="background:var(--a2)"></b>Costos de cirugía</span><span><b style="background:var(--b2)"></b>Gastos fijos</span>
          <span><b style="background:var(--p2)"></b>Meta</span><span><b style="background:var(--g2)"></b>Ganancia</span></div>
        <div style="margin-top:8px">
          <div class="fin-row tot"><div class="c">Ingresos</div><div class="v fin-pos">${pesos(m.total_ingresos)}</div></div>
          <div class="fin-row"><div class="c">− Costos de cirugía</div><div class="v">${pesos(m.total_variables)}</div></div>
          <div class="fin-row"><div class="c">− Gastos fijos</div><div class="v">${pesos(m.total_fijos)}</div></div>
          <div class="fin-row"><div class="c">− Publicidad Meta</div><div class="v">${pesos(m.meta)}</div></div>
          <div class="fin-row res"><div class="c">= Antes de impuestos</div><div class="v ${neg ? 'fin-neg' : 'fin-pos'}">${pesos(m.utilidad_antes)}</div></div>
          <div class="fin-row"><div class="c">− ICA (8,4 por mil)</div><div class="v">${pesos(m.ica)}</div></div>
          <div class="fin-row"><div class="c">− Renta (35%)</div><div class="v">${pesos(m.renta)}</div></div>
          <div class="fin-row res"><div class="c">= Después de impuestos</div><div class="v ${m.utilidad_despues < 0 ? 'fin-neg' : 'fin-pos'}">${pesos(m.utilidad_despues)}</div></div>
        </div>
      </div>

      <details class="fin-card"><summary>Ingresos<span class="v">${pesos(m.total_ingresos)}</span></summary>${filas(m.ingresos)}</details>
      <details class="fin-card"><summary>Costos de cirugía<span class="v">${pesos(m.total_variables)}</span></summary>${filas(m.variables)}</details>
      <details class="fin-card"><summary>Gastos fijos<span class="v">${pesos(m.total_fijos)}</span></summary>
        ${m.fijos.map(g => `<div class="fin-grp">${esc(g.categoria)} · ${pesos(g.total)}</div>${filas(g.items)}`).join('')}</details>
      ${m.cirugias.length ? `<details class="fin-card"><summary>Cirugías del mes<span class="v">${m.cirugias.length}</span></summary>
        ${m.cirugias.map(c => `<div class="fin-row"><div class="c">${esc(c.fecha.slice(8))}/${esc(c.fecha.slice(5, 7))} · ${esc(c.tipo)}
          <span class="fin-note">Sala: ${c.sala === null ? '<span class="fin-est">falta</span>' : pesos(c.sala)}</span></div>
          <div class="v">${pesos(c.valor)}</div></div>`).join('')}</details>` : ''}

      <div class="fin-help">
        Se actualiza solo 3 veces al día desde el Google Sheet. Silvia anota cada cirugía con su costo de sala en
        <b>PROCEDIMIENTOS</b>, los pagos de los pacientes en <b>PAGOS</b> y las facturas que llegan tarde en
        <b>GASTOS DEL MES</b>. Lo que se paga siempre está en <b>GASTOS FIJOS</b>: solo se cambia cuando algo cambie.
        La publicidad de Meta entra automática.
        <br><button class="fin-link" id="fin-salir">Cerrar sesión de Finanzas en este teléfono</button>
      </div>`;

    root().querySelectorAll('.fin-mes').forEach(b => b.onclick = () => { mesSel = b.dataset.mes; render(); });
    $('#fin-salir').onclick = () => { setClave(''); datos = null; pantallaClave(); };
  }

  /* Se llama al abrir la pestaña y cada vez que llega un data.json nuevo. */
  window.finAbrir = async function () {
    if (!root()) return;
    const caja = (typeof DATA !== 'undefined' && DATA) ? DATA.finanzas_enc : null;
    if (!caja) {
      const listo = typeof DATA !== 'undefined' && DATA;
      root().innerHTML = `<div class="fin-lock"><div class="ico">${listo ? '📭' : '⏳'}</div><div class="fin-sub">${
        listo ? 'Las finanzas todavía no están publicadas. Se actualizan en la próxima corrida.' : 'Cargando finanzas…'}</div></div>`;
      return;
    }
    if (caja !== cajaActual) { cajaActual = caja; datos = null; }
    if (datos) return render();
    const clave = getClave();
    if (clave) return entrar(clave);
    pantallaClave();
  };
})();
