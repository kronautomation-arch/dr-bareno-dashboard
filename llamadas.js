/* Pestaña "📞 Por llamar" — lista de pendientes de pago para YURI.
 *
 * Los datos de pacientes NO están en data.json (el dashboard es público): se
 * piden en vivo al bot en Railway con la clave compartida (header X-Clave).
 * Hecho para el dedo en iPhone: botones de 56 px con ícono + palabra.
 */
(function () {
  const LL_API = 'https://dr-bareno-bot-production.up.railway.app/llamadas';
  const KEY = 'll_clave';
  let datos = null, cargando = false, cuposCache = null, actual = null;

  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const getClave = () => { try { return localStorage.getItem(KEY) || ''; } catch { return ''; } };
  const setClave = v => { try { v ? localStorage.setItem(KEY, v) : localStorage.removeItem(KEY); } catch {} };

  /* ── estilos ─────────────────────────────────────────── */
  const css = `
  #ll-root{padding-bottom:calc(120px + var(--safe-bottom));font-size:17px;color:var(--txt)}
  .ll-top{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:4px 0 16px}
  .ll-h1{font-size:26px;font-weight:800}
  .ll-sub{font-size:15px;color:var(--txt2);margin-top:2px}
  .ll-btn{min-height:56px;border-radius:16px;border:1px solid var(--border2);background:var(--glass2);color:var(--txt);
    font-size:17px;font-weight:700;display:flex;align-items:center;justify-content:center;gap:8px;padding:0 16px;
    cursor:pointer;-webkit-tap-highlight-color:transparent;text-decoration:none;width:100%;font-family:inherit}
  .ll-btn:active{transform:scale(.97)}
  .ll-btn[disabled]{opacity:.5}
  .ll-btn.wa{background:#128c4a;border-color:#16a34a}
  .ll-btn.tel{background:var(--b1);border-color:var(--b2)}
  .ll-btn.mk{background:var(--p1);border-color:var(--p2)}
  .ll-btn.ok{background:var(--g1);border-color:var(--g2)}
  .ll-btn.danger{background:var(--r1);border-color:var(--r2)}
  .ll-btn.ghost{background:transparent}
  .ll-refresh{width:auto;min-width:56px}
  .ll-metrics{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:18px}
  .ll-m{background:var(--glass2);border:1px solid var(--border);border-radius:20px;padding:16px}
  .ll-m.wide{grid-column:1/-1}
  .ll-m-l{font-size:15px;color:var(--txt2);font-weight:600}
  .ll-m-v{font-size:34px;font-weight:800;margin-top:4px;line-height:1.1}
  .ll-m-s{font-size:15px;color:var(--txt2);margin-top:4px}
  .ll-split{display:flex;gap:40px;margin-top:4px}
  .ll-split b{font-size:34px;font-weight:800;display:block}
  .ll-banner{border-radius:16px;padding:14px 16px;margin-bottom:14px;font-size:16px;background:rgba(217,119,6,.15);
    border:1px solid var(--a1);display:flex;gap:12px;align-items:center;justify-content:space-between}
  .ll-card{background:var(--glass2);border:1px solid var(--border2);border-radius:22px;padding:18px;margin-bottom:14px}
  .ll-name{font-size:21px;font-weight:800;word-break:break-word}
  .ll-info{font-size:16px;color:var(--txt2);margin-top:6px;line-height:1.4}
  .ll-info b{color:var(--txt)}
  .ll-tag{display:inline-block;font-size:14px;font-weight:700;padding:3px 10px;border-radius:999px;background:rgba(251,113,133,.15);color:var(--r2);margin-top:8px}
  .ll-actions{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
  .ll-actions .full{grid-column:1/-1}
  .ll-chat{display:inline-block;margin-top:10px;font-size:16px;color:var(--b2);padding:8px 0;min-height:44px}
  .ll-empty{text-align:center;padding:40px 10px;color:var(--txt2)}
  .ll-spin{width:42px;height:42px;border-radius:50%;border:4px solid var(--border2);border-top-color:var(--p2);
    margin:30px auto 14px;animation:llspin 1s linear infinite}
  @keyframes llspin{to{transform:rotate(360deg)}}
  .ll-sheet-bg{position:fixed;inset:0;background:rgba(0,0,0,.6);z-index:1000;display:flex;align-items:flex-end}
  .ll-sheet{background:var(--bg2);width:100%;max-height:92vh;overflow-y:auto;border-radius:26px 26px 0 0;
    padding:20px 16px calc(24px + var(--safe-bottom));border-top:1px solid var(--border2)}
  .ll-sheet h2{font-size:22px;margin:0 0 4px}
  .ll-sheet .ll-btn{margin-top:12px}
  .ll-in{width:100%;min-height:56px;border-radius:14px;border:1px solid var(--border2);background:var(--glass);
    color:var(--txt);font-size:17px;padding:14px;margin-top:12px;font-family:inherit;box-sizing:border-box}
  textarea.ll-in{min-height:80px}
  .ll-seg{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:12px}
  .ll-seg .ll-btn.on{background:var(--p1);border-color:var(--p2)}
  .ll-day{font-size:17px;font-weight:800;margin:18px 0 8px}
  .ll-day::first-letter{text-transform:uppercase}
  .ll-slots{display:grid;grid-template-columns:1fr 1fr;gap:12px}
  .ll-slots .ll-btn{margin-top:0}
  .ll-slots .ll-btn.on{background:var(--g1);border-color:var(--g2)}
  .ll-lbl{font-size:15px;color:var(--txt2);margin-top:16px;font-weight:600}
  .ll-toast{position:fixed;left:16px;right:16px;bottom:calc(20px + var(--safe-bottom));z-index:1100;background:var(--g1);
    color:#fff;font-size:17px;font-weight:700;border-radius:16px;padding:16px;text-align:center}
  .ll-toast.err{background:var(--r1)}
  `;
  const st = document.createElement('style'); st.textContent = css; document.head.appendChild(st);

  /* ── red ─────────────────────────────────────────────── */
  async function api(ruta, opt = {}) {
    const r = await fetch(LL_API + ruta, {
      ...opt, headers: { 'X-Clave': getClave(), ...(opt.body ? { 'Content-Type': 'application/json' } : {}) },
    });
    if (r.status === 401) { setClave(''); pantallaClave('La clave no es correcta.'); throw new Error('401'); }
    let j = null; try { j = await r.json(); } catch {}
    if (!r.ok) { const e = new Error(String(r.status)); e.status = r.status; e.detail = j && j.detail; throw e; }
    return j;
  }

  function toast(msg, err) {
    const t = document.createElement('div'); t.className = 'll-toast' + (err ? ' err' : ''); t.textContent = msg;
    document.body.appendChild(t); setTimeout(() => t.remove(), 3200);
  }

  const root = () => $('#ll-root');

  /* ── pantallas ───────────────────────────────────────── */
  function pantallaClave(msg) {
    root().innerHTML = `
      <div class="ll-top"><div><div class="ll-h1">📞 Por llamar</div><div class="ll-sub">Escribe la clave del equipo</div></div></div>
      ${msg ? `<div class="ll-banner">${esc(msg)}</div>` : ''}
      <input class="ll-in" id="ll-clave" type="password" autocomplete="current-password" placeholder="Clave">
      <button class="ll-btn mk" id="ll-entrar" style="margin-top:14px">Entrar</button>`;
    const go = () => { const v = $('#ll-clave').value.trim(); if (v) { setClave(v); cargar(true); } };
    $('#ll-entrar').onclick = go;
    $('#ll-clave').onkeydown = e => { if (e.key === 'Enter') go(); };
  }

  function pantallaCargando() {
    root().innerHTML = `<div class="ll-h1">📞 Por llamar</div>
      <div class="ll-spin"></div>
      <div class="ll-empty" style="padding-top:0">Leyendo conversaciones de Pancake…<br>la primera vez puede tardar un minuto.</div>`;
  }

  function hace(iso) {
    if (!iso) return '';
    const min = Math.round((Date.now() - new Date(iso).getTime()) / 60000);
    return min < 1 ? 'recién' : min < 60 ? `hace ${min} min` : `hace ${Math.round(min / 60)} h`;
  }
  function horas(h) { return h < 24 ? `hace ${h} h` : `hace ${Math.round(h / 24)} día${h >= 48 ? 's' : ''}`; }

  function pintar() {
    const m = datos.metricas || {}, ts = datos.tarjetas || [];
    root().innerHTML = `
      <div class="ll-top">
        <div><div class="ll-h1">📞 Por llamar</div><div class="ll-sub">${ts.length} pendiente${ts.length === 1 ? '' : 's'} · ${esc(hace(datos.actualizado))}</div></div>
        <button class="ll-btn ghost ll-refresh" id="ll-ref" aria-label="Actualizar">↻</button>
      </div>
      ${datos.viejo ? `<div class="ll-banner">Pancake no respondió: mostrando datos de ${esc(hace(datos.actualizado))}.</div>` : ''}
      <div class="ll-metrics">
        <div class="ll-m wide"><div class="ll-m-l">Citas esta semana</div>
          <div class="ll-split"><div><b>${m.citas_bot ?? 0}</b><span class="ll-m-s">Bot</span></div>
          <div><b>${m.citas_yuri ?? 0}</b><span class="ll-m-s">YURI</span></div></div></div>
        <div class="ll-m"><div class="ll-m-l">Pendientes nuevos</div><div class="ll-m-v">${m.pendientes_semana ?? 0}</div><div class="ll-m-s">esta semana</div></div>
        <div class="ll-m"><div class="ll-m-l">Conversión</div><div class="ll-m-v">${m.tasa ?? 0}%</div>
          <div class="ll-m-s">${m.convertidas_semana ?? 0} de ${m.pendientes_semana ?? 0}</div></div>
      </div>
      ${ts.length ? ts.map(tarjetaHTML).join('') : '<div class="ll-empty">🎉 No hay nadie pendiente por llamar.</div>'}`;
    $('#ll-ref').onclick = () => cargar(true);
    root().querySelectorAll('[data-mk]').forEach(b => b.onclick = () => hojaMarcar(ts.find(t => t.conv_id === b.dataset.mk)));
  }

  function tarjetaHTML(t) {
    const tel = t.telefono;
    const detalle = [horas(t.enlace_hace_h) + ' le llegó el link', t.cuando ? `eligió <b>${esc(t.cuando)}</b>` : ''].filter(Boolean).join(' · ');
    const intentos = t.intentos ? `<span class="ll-tag">📵 ${t.intentos} intento${t.intentos > 1 ? 's' : ''}${t.ultimo === 'paga_despues' ? ' · paga después' : ''}</span>` :
      (t.ultimo === 'paga_despues' ? '<span class="ll-tag">⏳ dijo que paga después</span>' : '');
    return `<div class="ll-card">
      <div class="ll-name">${esc(t.nombre)}</div>
      <div class="ll-info">${tel ? '📱 ' + esc(tel.replace(/(\d{3})(\d{3})(\d{4})/, '$1 $2 $3')) + '<br>' : ''}${detalle}</div>
      ${intentos}${t.nota ? `<div class="ll-info">📝 ${esc(t.nota)}</div>` : ''}
      <div class="ll-actions">
        ${tel ? `<a class="ll-btn wa" href="https://wa.me/57${esc(tel)}" target="_blank" rel="noopener">💬 WhatsApp</a>
                 <a class="ll-btn tel" href="tel:+57${esc(tel)}">📞 Llamar</a>` : ''}
        <button class="ll-btn mk full" data-mk="${esc(t.conv_id)}">✍️ Marcar</button>
      </div>
      <a class="ll-chat" href="${esc(t.pancake_url)}" target="_blank" rel="noopener">Ver chat en Pancake ›</a>
    </div>`;
  }

  /* ── hojas inferiores ────────────────────────────────── */
  function hoja(html) {
    cerrarHoja();
    const bg = document.createElement('div'); bg.className = 'll-sheet-bg'; bg.id = 'll-sheet';
    bg.innerHTML = `<div class="ll-sheet">${html}</div>`;
    bg.onclick = e => { if (e.target === bg) cerrarHoja(); };
    document.body.appendChild(bg); document.body.style.overflow = 'hidden';
    return bg;
  }
  function cerrarHoja() { const s = $('#ll-sheet'); if (s) s.remove(); document.body.style.overflow = ''; }

  function hojaMarcar(t) {
    if (!t) return;
    actual = t;
    const h = hoja(`<h2>${esc(t.nombre)}</h2><div class="ll-sub">¿Cómo te fue con la llamada?</div>
      <button class="ll-btn ok" data-r="agendo">✅ Agendó</button>
      <button class="ll-btn" data-r="paga_despues">⏳ Va a pagar después</button>
      <button class="ll-btn" data-r="no_contesto">📵 No contestó</button>
      <button class="ll-btn" data-r="no_interesa">❌ No le interesa</button>
      <button class="ll-btn" data-r="quitado">🗑️ Quitar de la lista</button>
      <textarea class="ll-in" id="ll-nota" placeholder="Nota (opcional)"></textarea>
      <div id="ll-conf"></div>
      <button class="ll-btn ghost" id="ll-x">Cancelar</button>`);
    $('#ll-x', h).onclick = cerrarHoja;
    h.querySelectorAll('[data-r]').forEach(b => b.onclick = () => {
      const r = b.dataset.r;
      if (r === 'agendo') return hojaAgendar(t);
      if (r === 'no_interesa' || r === 'quitado') {
        const txt = r === 'quitado' ? `Sí, quitar a ${t.nombre} de la lista` : `Sí, ${t.nombre} no está interesada`;
        $('#ll-conf', h).innerHTML = `<button class="ll-btn danger" id="ll-si">${esc(txt)}</button>`;
        $('#ll-si', h).onclick = () => marcar(t, r, $('#ll-nota', h).value);
        $('#ll-si', h).scrollIntoView({ behavior: 'smooth', block: 'center' });
        return;
      }
      marcar(t, r, $('#ll-nota', h).value);
    });
  }

  async function marcar(t, resultado, nota) {
    try {
      await api(`/${encodeURIComponent(t.conv_id)}/resultado`, { method: 'POST', body: JSON.stringify({ resultado, nota }) });
      cerrarHoja();
      toast({ no_contesto: 'Anotado: no contestó', paga_despues: 'Anotado: paga después (vuelve mañana)',
              no_interesa: 'Listo, no se le vuelve a escribir', quitado: 'Quitada de la lista' }[resultado]);
      cargar(false, true);
    } catch (e) { if (e.message !== '401') toast('No se pudo guardar. Intenta de nuevo.', true); }
  }

  /* ── agendador ───────────────────────────────────────── */
  const DIAS = ['domingo', 'lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado'];
  const MESES = ['enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio', 'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre'];
  function diaLargo(f) { const [y, m, d] = f.split('-').map(Number); const dt = new Date(y, m - 1, d); return `${DIAS[dt.getDay()]} ${d} de ${MESES[m - 1]}`; }
  function hora12(h) { let [H, M] = h.split(':').map(Number); const s = H < 12 ? 'am' : 'pm'; H = H % 12 || 12; return `${H}:${String(M).padStart(2, '0')} ${s}`; }

  async function hojaAgendar(t) {
    const sel = { modalidad: 'presencial', slot: null, pago: 'pagó' };
    const h = hoja(`<h2>Agendar a ${esc(t.nombre)}</h2><div class="ll-sub">Solo salen las horas libres del Dr.</div>
      <div class="ll-seg"><button class="ll-btn on" data-mod="presencial">🏥 Presencial</button><button class="ll-btn" data-mod="virtual">💻 Virtual</button></div>
      <div id="ll-cupos"><div class="ll-spin"></div></div>
      <div class="ll-lbl">Nombre completo</div><input class="ll-in" id="ll-nom" value="${esc(t.nombre)}">
      <div class="ll-lbl">Cédula (opcional)</div><input class="ll-in" id="ll-ced" inputmode="numeric">
      <div class="ll-lbl">Pago</div>
      <div class="ll-seg"><button class="ll-btn on" data-pago="pagó">✅ Pagó</button><button class="ll-btn" data-pago="efectivo">💵 Efectivo</button></div>
      <div class="ll-lbl">Nota (opcional)</div><textarea class="ll-in" id="ll-nt"></textarea>
      <button class="ll-btn ok" id="ll-ag" disabled>Elige una hora</button>
      <button class="ll-btn ghost" id="ll-x">Cancelar</button>`);
    $('#ll-x', h).onclick = cerrarHoja;
    const btnAg = $('#ll-ag', h);
    const refrescarBoton = () => {
      btnAg.disabled = !sel.slot;
      btnAg.textContent = sel.slot ? `Agendar ${diaLargo(sel.slot.fecha)} · ${hora12(sel.slot.hora)}` : 'Elige una hora';
    };
    h.querySelectorAll('[data-mod]').forEach(b => b.onclick = () => {
      sel.modalidad = b.dataset.mod; sel.slot = null;
      h.querySelectorAll('[data-mod]').forEach(x => x.classList.toggle('on', x === b));
      pintarCupos(); refrescarBoton();
    });
    h.querySelectorAll('[data-pago]').forEach(b => b.onclick = () => {
      sel.pago = b.dataset.pago; h.querySelectorAll('[data-pago]').forEach(x => x.classList.toggle('on', x === b));
    });

    async function traerCupos(desde) {
      const c = await api('/cupos' + (desde ? `?desde=${desde}` : ''));
      if (!cuposCache || !desde) cuposCache = { presencial: [], virtual: [] };
      cuposCache.presencial.push(...c.presencial); cuposCache.virtual.push(...c.virtual);
      cuposCache.hasta = c.hasta;
    }
    function pintarCupos() {
      const box = $('#ll-cupos', h); const lista = (cuposCache && cuposCache[sel.modalidad]) || [];
      if (!lista.length) { box.innerHTML = '<div class="ll-empty">No hay horas libres en estas semanas.</div>'; }
      else {
        const porDia = {}; lista.forEach(s => (porDia[s.fecha] = porDia[s.fecha] || []).push(s));
        box.innerHTML = Object.keys(porDia).sort().map(f => `<div class="ll-day">${diaLargo(f)}</div><div class="ll-slots">${
          porDia[f].map(s => `<button class="ll-btn${sel.slot && sel.slot.fecha === s.fecha && sel.slot.hora === s.hora ? ' on' : ''}" data-f="${s.fecha}" data-h="${s.hora}">${hora12(s.hora)}</button>`).join('')}</div>`).join('');
      }
      box.insertAdjacentHTML('beforeend', '<button class="ll-btn ghost" id="ll-mas">Ver más adelante</button>');
      box.querySelectorAll('[data-f]').forEach(b => b.onclick = () => {
        sel.slot = { fecha: b.dataset.f, hora: b.dataset.h }; pintarCupos(); refrescarBoton();
      });
      $('#ll-mas', box).onclick = async () => {
        const [y, m, d] = cuposCache.hasta.split('-').map(Number);
        const sig = new Date(y, m - 1, d + 1);
        try { await traerCupos(`${sig.getFullYear()}-${String(sig.getMonth() + 1).padStart(2, '0')}-${String(sig.getDate()).padStart(2, '0')}`); pintarCupos(); }
        catch (e) { if (e.message !== '401') toast('No se pudieron traer más horas.', true); }
      };
    }
    try { await traerCupos(); pintarCupos(); }
    catch (e) { if (e.message !== '401') $('#ll-cupos', h).innerHTML = '<div class="ll-banner">No se pudo leer la agenda del Dr. Cierra e intenta de nuevo.</div>'; }

    btnAg.onclick = async () => {
      const nombre = $('#ll-nom', h).value.trim();
      if (!nombre) { toast('Falta el nombre.', true); return; }
      btnAg.disabled = true; btnAg.textContent = 'Agendando…';
      try {
        await api(`/${encodeURIComponent(t.conv_id)}/agendar`, { method: 'POST', body: JSON.stringify({
          fecha: sel.slot.fecha, hora: sel.slot.hora, modalidad: sel.modalidad, nombre,
          cedula: $('#ll-ced', h).value.trim(), pago: sel.pago, nota: $('#ll-nt', h).value.trim() }) });
        cerrarHoja(); toast(`✅ Cita agendada: ${diaLargo(sel.slot.fecha)} ${hora12(sel.slot.hora)}`);
        cuposCache = null; cargar(false, true);
      } catch (e) {
        if (e.message === '401') return;
        if (e.status === 409) {
          toast('Esa hora se acaba de ocupar. Elige otra.', true);
          sel.slot = null; cuposCache = null;
          try { await traerCupos(); } catch {}
          pintarCupos(); refrescarBoton();
        } else { toast('No se pudo agendar. ' + (e.detail || 'Intenta de nuevo.'), true); refrescarBoton(); }
      }
    };
  }

  /* ── carga ───────────────────────────────────────────── */
  async function cargar(refrescar, silencioso) {
    if (!getClave()) return pantallaClave();
    if (cargando) return;
    cargando = true;
    if (!datos && !silencioso) pantallaCargando();
    try {
      datos = await api('/pendientes' + (refrescar ? '?refrescar=1' : ''));
      pintar();
    } catch (e) {
      if (e.message !== '401') {
        root().innerHTML = `<div class="ll-h1">📞 Por llamar</div>
          <div class="ll-banner" style="margin-top:16px">No se pudo conectar con el bot.</div>
          <button class="ll-btn mk" id="ll-re">Reintentar</button>`;
        $('#ll-re').onclick = () => cargar(true);
      }
    } finally { cargando = false; }
  }

  window.llAbrir = function () { if (!datos) cargar(false); };
})();
