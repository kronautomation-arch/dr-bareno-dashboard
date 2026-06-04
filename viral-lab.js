/* ═══════════════════════════════════════════════════════════
   Viral Lab — Sistema de contenido para Dr. John Bareño
   Depende de: auth.js (_sb, SUPABASE_URL, SUPABASE_ANON_KEY)
   ═══════════════════════════════════════════════════════════ */

const VL = (() => {
  /* ── Constantes ── */
  const SUPABASE_FN_URL      = `${SUPABASE_URL}/functions/v1/generate-script`;
  const SUPABASE_SCRAPE_URL  = `${SUPABASE_URL}/functions/v1/scrape-instagram`;
  // Legacy Apify (kept for website scraping)
  const APIFY_BASE       = 'https://api.apify.com/v2';
  const APIFY_WEB_ACTOR  = 'apify~website-content-crawler';

  const SURGERY_TYPES = [
    'Lifting Endoscópico',
    'Blefaroplastia Inferior',
    'Blefaroplastia Superior',
    'Quadfecta',
    'Lifting de Cuello',
    'Lifting de Tercio Medio',
    'Lifting de Tercio Superior',
    'Frontoplastia',
    'Liplift',
  ];

  /* ── Estado ── */
  let apifyToken = localStorage.getItem('vl_apify_token') || '';
  let igCookie   = localStorage.getItem('vl_ig_cookie')   || '';
  let drHandle   = localStorage.getItem('vl_dr_handle')   || 'drjohnbareno';
  let drWebsite  = localStorage.getItem('vl_dr_website')  || 'https://www.johnbareno.com';

  let currentSubTab    = 'competidores';
  let selectedCompetitorId = null;
  let selectedPostId   = null;
  let competitors      = [];
  let viralPosts       = [];
  let scripts          = [];
  let dnaData          = null;

  /* ─────────────────────────────────────────────────
     HELPERS
  ───────────────────────────────────────────────── */
  const $ = id => document.getElementById(id);
  const fmt = n => n >= 1e6 ? (n/1e6).toFixed(1)+'M' : n >= 1e3 ? (n/1e3).toFixed(1)+'K' : String(n||0);
  const engScore = p => (p.likes||0) + (p.views||0)*0.1 + (p.comments||0)*2;
  const dateStr  = iso => iso ? new Date(iso).toLocaleDateString('es-CO', {day:'2-digit', month:'2-digit', year:'numeric', hour:'2-digit', minute:'2-digit'}) : '—';

  function toast(msg, isError = false) {
    const el = document.createElement('div');
    el.className = 'vl-toast' + (isError ? ' vl-toast-err' : '');
    el.textContent = msg;
    document.body.appendChild(el);
    setTimeout(() => el.remove(), 3200);
  }

  function copyText(text) {
    navigator.clipboard.writeText(text).then(
      () => toast('Copiado al portapapeles ✓'),
      () => {
        const ta = document.createElement('textarea');
        ta.value = text; document.body.appendChild(ta); ta.select();
        document.execCommand('copy'); ta.remove();
        toast('Copiado ✓');
      }
    );
  }

  /* ─────────────────────────────────────────────────
     APIFY — scraping
  ───────────────────────────────────────────────── */
  function buildApifyInput(base) {
    if (!igCookie) return base;
    const cookieVal = igCookie.replace(/^sessionid=/, '');
    return {
      ...base,
      loginCookies: [{ name: 'sessionid', value: cookieVal, domain: '.instagram.com', path: '/' }],
    };
  }

  async function apifyRun(actorId, input) {
    if (!apifyToken) throw new Error('Falta el Apify API token. Configura en ⚙️');

    const finalInput = actorId.includes('instagram') ? buildApifyInput(input) : input;

    const res = await fetch(`${APIFY_BASE}/acts/${actorId}/runs`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${apifyToken}`, 'Content-Type': 'application/json' },
      body: JSON.stringify(finalInput),
    });
    if (!res.ok) throw new Error(`Apify error ${res.status}: ${await res.text()}`);
    const { data } = await res.json();
    return data.id;
  }

  async function apifyPoll(runId, onProgress) {
    const maxWait = 180000; // 3 min max
    const start = Date.now();
    while (Date.now() - start < maxWait) {
      await new Promise(r => setTimeout(r, 4000));
      const res = await fetch(`${APIFY_BASE}/actor-runs/${runId}`, {
        headers: { Authorization: `Bearer ${apifyToken}` },
      });
      const { data } = await res.json();
      if (onProgress) onProgress(data.status);
      if (data.status === 'SUCCEEDED') return data.defaultDatasetId;
      if (['FAILED','ABORTED','TIMED-OUT'].includes(data.status))
        throw new Error(`Apify run ${data.status}`);
    }
    throw new Error('Tiempo de espera agotado (3 min)');
  }

  async function apifyItems(datasetId) {
    const res = await fetch(`${APIFY_BASE}/datasets/${datasetId}/items?clean=true`, {
      headers: { Authorization: `Bearer ${apifyToken}` },
    });
    return res.json();
  }

  /* ─────────────────────────────────────────────────
     SUPABASE — CRUD
  ───────────────────────────────────────────────── */
  async function dbGetCompetitors() {
    const { data, error } = await _sb.from('bareno_competitors').select('*').order('created_at', { ascending: false });
    if (error) throw error;
    return data || [];
  }

  async function dbUpsertCompetitor(handle) {
    const { data, error } = await _sb.from('bareno_competitors')
      .upsert({ handle: handle.replace(/^@/, '') }, { onConflict: 'handle' })
      .select().single();
    if (error) throw error;
    return data;
  }

  async function dbDeleteCompetitor(id) {
    const { error } = await _sb.from('bareno_competitors').delete().eq('id', id);
    if (error) throw error;
  }

  async function dbSavePosts(competitorId, handle, posts) {
    if (!posts.length) return;
    const rows = posts.map(p => ({
      competitor_id: competitorId,
      apify_post_id: p.shortCode || p.id || p.postId,
      post_url:      p.url || p.postUrl || `https://instagram.com/p/${p.shortCode || p.id}`,
      thumbnail_url: p.displayUrl || p.thumbnailUrl || p.imageUrl || p.previewImageUrl || null,
      caption:       (p.caption || p.text || p.description || '').slice(0, 2000),
      likes:         p.likesCount || p.likes || p.likeCount || 0,
      views:         p.videoViewCount || p.videoPlayCount || p.playsCount || p.views || 0,
      comments:      p.commentsCount || p.comments || p.commentCount || 0,
      posted_at:     p.timestamp ? new Date(p.timestamp).toISOString() : p.takenAt ? new Date(p.takenAt * 1000).toISOString() : null,
    }));
    const { error } = await _sb.from('bareno_viral_posts').upsert(rows, { onConflict: 'apify_post_id' });
    if (error) throw error;

    await _sb.from('bareno_competitors').update({ last_scraped_at: new Date().toISOString() }).eq('id', competitorId);
  }

  async function dbGetPosts(competitorId) {
    const { data, error } = await _sb.from('bareno_viral_posts')
      .select('*')
      .eq('competitor_id', competitorId)
      .order('scraped_at', { ascending: false })
      .limit(50);
    if (error) throw error;
    return (data || []).sort((a, b) => engScore(b) - engScore(a));
  }

  async function dbSaveScript(postId, competitorHandle, surgeryType, caption, script) {
    const { error } = await _sb.from('bareno_scripts').insert({
      source_post_id:   postId,
      competitor_handle: competitorHandle,
      surgery_type:     surgeryType,
      original_caption: caption,
      generated_script: script,
    });
    if (error) throw error;
  }

  async function dbGetScripts(filterSurgery = null) {
    let q = _sb.from('bareno_scripts').select('*').order('created_at', { ascending: false }).limit(50);
    if (filterSurgery) q = q.eq('surgery_type', filterSurgery);
    const { data, error } = await q;
    if (error) throw error;
    return data || [];
  }

  async function dbDeleteScript(id) {
    const { error } = await _sb.from('bareno_scripts').delete().eq('id', id);
    if (error) throw error;
  }

  async function dbGetDNA() {
    const { data } = await _sb.from('bareno_dna').select('*').order('updated_at', { ascending: false }).limit(1).single();
    return data || null;
  }

  async function dbSaveDNA(payload) {
    const existing = await dbGetDNA();
    if (existing) {
      const { error } = await _sb.from('bareno_dna').update({ ...payload, updated_at: new Date().toISOString() }).eq('id', existing.id);
      if (error) throw error;
    } else {
      const { error } = await _sb.from('bareno_dna').insert(payload);
      if (error) throw error;
    }
  }

  /* ─────────────────────────────────────────────────
     GENERAR GUIÓN — Edge Function
  ───────────────────────────────────────────────── */
  async function callGenerateScript(dna, viralCaption, surgeryType) {
    const session = await _sb.auth.getSession();
    const token = session.data?.session?.access_token || SUPABASE_ANON_KEY;

    const res = await fetch(SUPABASE_FN_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        apikey: SUPABASE_ANON_KEY,
      },
      body: JSON.stringify({
        dna: dna?.structured_dna || null,
        viral_caption: viralCaption,
        surgery_type: surgeryType,
      }),
    });

    if (!res.ok) {
      const errText = await res.text();
      throw new Error(`Edge Function error ${res.status}: ${errText}`);
    }

    const { script, error } = await res.json();
    if (error) throw new Error(error);
    return script;
  }

  /* ─────────────────────────────────────────────────
     SUB-TAB ROUTING
  ───────────────────────────────────────────────── */
  function switchSubTab(name) {
    currentSubTab = name;
    ['competidores','adn','guiones'].forEach(t => {
      $(`vl-btn-${t}`)?.classList.toggle('active', t === name);
      $(`vl-sub-${t}`)?.classList.toggle('active', t === name);
    });
  }

  /* ═══════════════════════════════════════════════
     MODO MANUAL
  ═══════════════════════════════════════════════ */
  let lastManualScript = '';

  async function generateFromManual() {
    const caption = ($('vl-manual-caption')?.value || '').trim();
    const surgeryType = $('vl-manual-surgery')?.value;
    if (!caption) return toast('Pega el caption del video viral primero', true);
    if (!surgeryType) return toast('Elige el tipo de cirugía', true);

    const btn = document.querySelector('[onclick="VL.generateFromManual()"]');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Generando...'; }
    $('vl-manual-result').style.display = 'none';

    try {
      dnaData = dnaData || await dbGetDNA();
      const script = await callGenerateScript(dnaData, caption, surgeryType);
      lastManualScript = script;
      $('vl-manual-script').textContent = script;
      $('vl-manual-result').style.display = 'block';
    } catch(e) {
      toast(e.message, true);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '🤖 Generar guión'; }
    }
  }

  async function saveManualScript() {
    if (!lastManualScript) return;
    const surgeryType = $('vl-manual-surgery')?.value || 'General';
    const caption = ($('vl-manual-caption')?.value || '').trim();
    try {
      await dbSaveScript(null, 'manual', surgeryType, caption, lastManualScript);
      toast('Guión guardado ✓');
    } catch(e) { toast(e.message, true); }
  }

  /* ═══════════════════════════════════════════════
     COMPETIDORES
  ═══════════════════════════════════════════════ */
  async function loadCompetitors() {
    competitors = await dbGetCompetitors();
    renderCompetitorList();
    if (competitors.length > 0 && !selectedCompetitorId) {
      selectedCompetitorId = competitors[0].id;
    }
    if (selectedCompetitorId) await loadPosts(selectedCompetitorId);
  }

  function renderCompetitorList() {
    const el = $('vl-competitor-list');
    if (!el) return;
    if (!competitors.length) {
      el.innerHTML = '<div class="vl-empty">Sin competidores todavía. Añade uno arriba.</div>';
      return;
    }
    el.innerHTML = competitors.map(c => `
      <div class="vl-comp-item ${c.id === selectedCompetitorId ? 'selected' : ''}" data-id="${c.id}">
        <div class="vl-comp-info">
          <span class="vl-comp-handle">@${c.handle}</span>
          ${c.last_scraped_at ? `<span class="vl-comp-meta">Actualizado ${dateStr(c.last_scraped_at)}</span>` : '<span class="vl-comp-meta">Sin datos aún</span>'}
        </div>
        <div class="vl-comp-actions">
          <button class="vl-btn-sm vl-btn-refresh" onclick="VL.scrapeCompetitor(${c.id},'${c.handle}')" title="Actualizar posts">🔄</button>
          <button class="vl-btn-sm vl-btn-del" onclick="VL.deleteCompetitor(${c.id})" title="Eliminar">✕</button>
        </div>
      </div>
    `).join('');

    el.querySelectorAll('.vl-comp-item').forEach(item => {
      item.addEventListener('click', e => {
        if (e.target.closest('button')) return;
        const id = parseInt(item.dataset.id);
        selectedCompetitorId = id;
        renderCompetitorList();
        loadPosts(id);
      });
    });
  }

  async function addCompetitor() {
    const input = $('vl-new-handle');
    const handle = (input?.value || '').replace(/^@/, '').trim();
    if (!handle) return toast('Escribe un @handle', true);

    try {
      const comp = await dbUpsertCompetitor(handle);
      input.value = '';
      competitors = await dbGetCompetitors();
      selectedCompetitorId = comp.id;
      renderCompetitorList();
      toast(`@${handle} añadido`);
      await scrapeCompetitor(comp.id, comp.handle);
    } catch (e) {
      toast(e.message, true);
    }
  }

  async function deleteCompetitor(id) {
    if (!confirm('¿Eliminar este competidor y todos sus posts?')) return;
    try {
      await dbDeleteCompetitor(id);
      if (selectedCompetitorId === id) selectedCompetitorId = null;
      competitors = await dbGetCompetitors();
      renderCompetitorList();
      $('vl-posts-container').innerHTML = '';
      $('vl-posts-title').textContent = 'Videos virales';
      toast('Competidor eliminado');
    } catch(e) { toast(e.message, true); }
  }

  async function scrapeCompetitor(competitorId, handle) {
    const progress = $('vl-scrape-progress');
    const label    = $('vl-scrape-label');
    if (progress) progress.style.display = 'flex';
    if (label)    label.textContent = `Scrapeando @${handle}...`;

    try {
      const session = await _sb.auth.getSession();
      const tok = session.data?.session?.access_token || SUPABASE_ANON_KEY;

      const res = await fetch(SUPABASE_SCRAPE_URL, {
        method: 'POST',
        headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json', apikey: SUPABASE_ANON_KEY },
        body: JSON.stringify({ username: handle, sessionid: igCookie || undefined }),
      });

      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        throw new Error(err.error || `Error ${res.status}`);
      }

      const data = await res.json();
      if (data.error) throw new Error(data.error);

      const posts = data.posts || [];
      if (!posts.length) { toast(`@${handle}: sin posts encontrados`, true); return; }

      await dbSavePosts(competitorId, handle, posts);

      // Update follower count
      if (data.followers) {
        await _sb.from('bareno_competitors').update({ follower_count: data.followers, last_scraped_at: new Date().toISOString() }).eq('id', competitorId);
      }

      competitors = await dbGetCompetitors();
      selectedCompetitorId = competitorId;
      renderCompetitorList();
      await loadPosts(competitorId);
      toast(`@${handle}: ${posts.length} posts actualizados ✓`);
    } catch(e) {
      toast(e.message, true);
    } finally {
      if (progress) progress.style.display = 'none';
    }
  }

  async function loadPosts(competitorId) {
    viralPosts = await dbGetPosts(competitorId);
    const comp = competitors.find(c => c.id === competitorId);
    renderPosts(comp?.handle || '');
  }

  function renderPosts(handle) {
    const container = $('vl-posts-container');
    const title     = $('vl-posts-title');
    if (!container) return;
    if (title) title.textContent = handle ? `Videos virales de @${handle}` : 'Videos virales';

    if (!viralPosts.length) {
      container.innerHTML = '<div class="vl-empty">Sin posts. Haz clic en 🔄 para scrapear.</div>';
      return;
    }

    container.innerHTML = viralPosts.map((p, i) => `
      <div class="vl-post-card" onclick="VL.openProcessModal(${p.id},'${(p.caption||'').replace(/'/g,"\\'").slice(0,60)}')">
        <div class="vl-post-rank">#${i+1}</div>
        ${p.thumbnail_url ? `<img class="vl-post-thumb" src="${p.thumbnail_url}" alt="" loading="lazy" onerror="this.style.display='none'">` : '<div class="vl-post-thumb-placeholder">📷</div>'}
        <div class="vl-post-meta">
          <div class="vl-post-stats">
            <span>👁 ${fmt(p.views)}</span>
            <span>❤️ ${fmt(p.likes)}</span>
            <span>💬 ${fmt(p.comments)}</span>
          </div>
          <div class="vl-post-caption">${(p.caption||'Sin caption').slice(0,90)}${(p.caption||'').length > 90 ? '…' : ''}</div>
          ${p.posted_at ? `<div class="vl-post-date">${dateStr(p.posted_at)}</div>` : ''}
        </div>
        <div class="vl-post-arrow">›</div>
      </div>
    `).join('');
  }

  /* ═══════════════════════════════════════════════
     MODAL: PROCESAR POST
  ═══════════════════════════════════════════════ */
  function openProcessModal(postId, captionPreview) {
    selectedPostId = postId;
    const post = viralPosts.find(p => p.id === postId);
    if (!post) return;

    const comp = competitors.find(c => c.id === post.competitor_id);

    $('modal-post-handle').textContent = comp ? `@${comp.handle}` : '';
    $('modal-post-stats').textContent  = `👁 ${fmt(post.views)}  ❤️ ${fmt(post.likes)}  💬 ${fmt(post.comments)}`;
    $('modal-post-caption').textContent = post.caption || '(sin caption)';
    $('modal-surgery-select').innerHTML = SURGERY_TYPES.map(t => `<option value="${t}">${t}</option>`).join('');
    $('modal-script-output').textContent = '';
    $('modal-script-section').style.display = 'none';
    $('modal-save-btn').style.display = 'none';
    $('modal-generate-btn').disabled = false;
    $('modal-generate-btn').textContent = '🤖 Procesar con IA';

    $('vl-process-modal').classList.add('open');
  }

  function closeProcessModal() {
    $('vl-process-modal').classList.remove('open');
    selectedPostId = null;
  }

  async function generateScript() {
    if (!selectedPostId) return;
    const post = viralPosts.find(p => p.id === selectedPostId);
    if (!post) return;

    const surgeryType = $('modal-surgery-select').value;
    const btn = $('modal-generate-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Generando...';
    $('modal-script-section').style.display = 'none';
    $('modal-save-btn').style.display = 'none';

    try {
      dnaData = dnaData || await dbGetDNA();
      const script = await callGenerateScript(dnaData, post.caption, surgeryType);
      $('modal-script-output').textContent = script;
      $('modal-script-section').style.display = 'block';
      $('modal-save-btn').style.display = 'inline-flex';
      $('modal-copy-btn').style.display = 'inline-flex';
      btn.textContent = '🔄 Regenerar';
    } catch(e) {
      toast(e.message, true);
      btn.textContent = '🤖 Procesar con IA';
    } finally {
      btn.disabled = false;
    }
  }

  async function saveScript() {
    if (!selectedPostId) return;
    const post = viralPosts.find(p => p.id === selectedPostId);
    if (!post) return;

    const surgeryType = $('modal-surgery-select').value;
    const script = $('modal-script-output').textContent;
    if (!script) return;

    const comp = competitors.find(c => c.id === post.competitor_id);

    try {
      await dbSaveScript(post.id, comp?.handle || '', surgeryType, post.caption, script);
      toast('Guión guardado ✓');
      $('modal-save-btn').textContent = '✓ Guardado';
      setTimeout(() => { $('modal-save-btn').textContent = '💾 Guardar guión'; }, 2000);
    } catch(e) { toast(e.message, true); }
  }

  /* ═══════════════════════════════════════════════
     ADN
  ═══════════════════════════════════════════════ */
  async function loadDNA() {
    dnaData = await dbGetDNA();
    renderDNA();
  }

  function renderDNA() {
    const el = $('vl-dna-display');
    if (!el) return;

    if (!dnaData?.structured_dna) {
      el.innerHTML = `<div class="vl-empty">ADN no construido aún. Haz clic en "Escanear" para empezar.</div>`;
      return;
    }

    const d = dnaData.structured_dna;
    el.innerHTML = `
      <div class="vl-dna-updated">Última actualización: ${dateStr(dnaData.updated_at)}</div>
      <div class="vl-dna-field">
        <label>TONO</label>
        <div class="vl-dna-value" id="dna-tone" contenteditable="${$('vl-dna-edit-btn')?.dataset.editing === '1' ? 'true' : 'false'}">${d.tone || '—'}</div>
      </div>
      <div class="vl-dna-field">
        <label>PALABRAS CLAVE</label>
        <div class="vl-dna-value" id="dna-keywords" contenteditable="false">${(d.keywords || []).join(', ') || '—'}</div>
      </div>
      <div class="vl-dna-field">
        <label>MENSAJES CLAVE</label>
        <div class="vl-dna-value" id="dna-messages" contenteditable="false">${(d.key_messages || []).map(m => `• ${m}`).join('<br>') || '—'}</div>
      </div>
      <div class="vl-dna-field">
        <label>ESTILO</label>
        <div class="vl-dna-value" id="dna-style" contenteditable="false">${d.style_notes || '—'}</div>
      </div>
    `;
  }

  function toggleDNAEdit() {
    const btn = $('vl-dna-edit-btn');
    const editing = btn?.dataset.editing === '1';
    const newState = !editing;
    if (btn) btn.dataset.editing = newState ? '1' : '0';
    if (btn) btn.textContent = newState ? '💾 Guardar cambios' : '✏️ Editar ADN';

    ['tone','keywords','messages','style'].forEach(field => {
      const el = $(`dna-${field}`);
      if (el) el.contentEditable = newState ? 'true' : 'false';
    });

    if (!newState) saveDNAEdits();
  }

  async function saveDNAEdits() {
    if (!dnaData) return;
    const keywordsText = $('dna-keywords')?.textContent || '';
    const messagesText = $('dna-messages')?.textContent || '';

    const updated = {
      ...dnaData.structured_dna,
      tone:         $('dna-tone')?.textContent?.trim() || dnaData.structured_dna?.tone,
      keywords:     keywordsText.split(',').map(k => k.trim()).filter(Boolean),
      key_messages: messagesText.replace(/^• /gm, '').split('\n').map(m => m.trim()).filter(Boolean),
      style_notes:  $('dna-style')?.textContent?.trim() || dnaData.structured_dna?.style_notes,
    };

    try {
      await dbSaveDNA({ structured_dna: updated });
      dnaData = await dbGetDNA();
      toast('ADN guardado ✓');
    } catch(e) { toast(e.message, true); }
  }

  async function scanInstagram() {
    if (!apifyToken) { openConfigModal(); return; }
    const btn = $('vl-scan-ig-btn');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Escaneando...'; }

    try {
      const runId = await apifyRun(APIFY_IG_ACTOR, {
        directUrls: [`https://www.instagram.com/${drHandle}/reels/`],
        resultsLimit: 20,
      });
      const datasetId = await apifyPoll(runId);
      const items = await apifyItems(datasetId);

      const bio = items[0]?.ownerBio || items[0]?.biography || '';
      const captions = items.map(p => p.caption || p.text || '').filter(Boolean).slice(0, 15).join('\n\n---\n\n');

      const dna = await extractDNAWithClaude(bio, captions, '');
      await dbSaveDNA({
        instagram_bio: bio,
        instagram_top_captions: captions,
        structured_dna: dna,
      });
      dnaData = await dbGetDNA();
      renderDNA();
      toast('ADN de Instagram construido ✓');
    } catch(e) {
      toast(e.message, true);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '📱 Escanear Instagram'; }
    }
  }

  async function scanWebsite() {
    if (!apifyToken) { openConfigModal(); return; }
    const btn = $('vl-scan-web-btn');
    if (btn) { btn.disabled = true; btn.textContent = '⏳ Escaneando web...'; }

    try {
      const runId = await apifyRun(APIFY_WEB_ACTOR, {
        startUrls: [{ url: drWebsite }],
        maxCrawlPages: 5,
        maxCrawlDepth: 2,
      });
      const datasetId = await apifyPoll(runId);
      const items = await apifyItems(datasetId);
      const webContent = items.map(p => p.text || p.content || '').join('\n\n').slice(0, 4000);

      const existingDna = await dbGetDNA();
      const igCaptions = existingDna?.instagram_top_captions || '';
      const igBio      = existingDna?.instagram_bio || '';

      const dna = await extractDNAWithClaude(igBio, igCaptions, webContent);
      await dbSaveDNA({
        website_content: webContent,
        structured_dna: dna,
      });
      dnaData = await dbGetDNA();
      renderDNA();
      toast('ADN de sitio web integrado ✓');
    } catch(e) {
      toast(e.message, true);
    } finally {
      if (btn) { btn.disabled = false; btn.textContent = '🌐 Escanear Sitio Web'; }
    }
  }

  async function extractDNAWithClaude(bio, captions, webContent) {
    const session = await _sb.auth.getSession();
    const token = session.data?.session?.access_token || SUPABASE_ANON_KEY;

    const prompt = `Analiza el siguiente contenido del Dr. John Bareño, cirujano estético facial de Colombia.

BIO INSTAGRAM: ${bio || '(no disponible)'}
CAPTIONS INSTAGRAM: ${captions || '(no disponibles)'}
CONTENIDO SITIO WEB: ${webContent || '(no disponible)'}

Extrae y estructura el ADN de comunicación del Dr. Bareño en formato JSON estricto:
{
  "tone": "descripción del tono en 1 oración",
  "keywords": ["palabra1", "palabra2", ...hasta 10],
  "key_messages": ["mensaje1", "mensaje2", ...hasta 5],
  "style_notes": "descripción del estilo narrativo en 2-3 oraciones"
}

Responde SOLO con el JSON, sin texto adicional.`;

    const res = await fetch(SUPABASE_FN_URL, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${token}`,
        'Content-Type': 'application/json',
        apikey: SUPABASE_ANON_KEY,
      },
      body: JSON.stringify({ dna: null, viral_caption: prompt, surgery_type: '__DNA_EXTRACTION__' }),
    });

    if (!res.ok) throw new Error(`Error extrayendo ADN: ${res.status}`);
    const { script } = await res.json();

    const jsonMatch = script.match(/\{[\s\S]*\}/);
    if (!jsonMatch) throw new Error('No se pudo parsear el JSON del ADN');
    return JSON.parse(jsonMatch[0]);
  }

  /* ═══════════════════════════════════════════════
     GUIONES
  ═══════════════════════════════════════════════ */
  async function loadScripts(filterSurgery = null) {
    scripts = await dbGetScripts(filterSurgery);
    renderScripts();
  }

  function renderScripts() {
    const el = $('vl-scripts-list');
    if (!el) return;

    if (!scripts.length) {
      el.innerHTML = '<div class="vl-empty">Sin guiones guardados aún.</div>';
      return;
    }

    el.innerHTML = scripts.map(s => `
      <div class="vl-script-card">
        <div class="vl-script-header">
          <span class="vl-script-surgery">${s.surgery_type}</span>
          <span class="vl-script-date">${dateStr(s.created_at)}</span>
        </div>
        ${s.competitor_handle ? `<div class="vl-script-source">Inspirado en @${s.competitor_handle}</div>` : ''}
        <div class="vl-script-preview">${(s.generated_script||'').slice(0,120)}…</div>
        <div class="vl-script-actions">
          <button class="vl-btn-sm" onclick="VL.expandScript(${s.id})">👁 Ver</button>
          <button class="vl-btn-sm" onclick="VL.copyScript(${s.id})">📋 Copiar</button>
          <button class="vl-btn-sm vl-btn-del" onclick="VL.deleteScript(${s.id})">🗑</button>
        </div>
        <div class="vl-script-full" id="script-full-${s.id}" style="display:none">
          <pre class="vl-script-text">${s.generated_script}</pre>
        </div>
      </div>
    `).join('');
  }

  function expandScript(id) {
    const el = $(`script-full-${id}`);
    if (el) el.style.display = el.style.display === 'none' ? 'block' : 'none';
  }

  function copyScript(id) {
    const s = scripts.find(x => x.id === id);
    if (s) copyText(s.generated_script);
  }

  async function deleteScript(id) {
    if (!confirm('¿Eliminar este guión?')) return;
    try {
      await dbDeleteScript(id);
      scripts = scripts.filter(s => s.id !== id);
      renderScripts();
      toast('Guión eliminado');
    } catch(e) { toast(e.message, true); }
  }

  function filterScripts() {
    const val = $('vl-surgery-filter')?.value || '';
    loadScripts(val || null);
  }

  /* ═══════════════════════════════════════════════
     CONFIGURACIÓN
  ═══════════════════════════════════════════════ */
  function openConfigModal() {
    $('config-apify-token').value = apifyToken;
    $('config-dr-handle').value   = drHandle;
    $('config-dr-website').value  = drWebsite;
    if ($('config-ig-cookie')) $('config-ig-cookie').value = igCookie;
    $('vl-config-modal').classList.add('open');
  }

  function closeConfigModal() {
    $('vl-config-modal').classList.remove('open');
  }

  function saveConfig() {
    apifyToken = ($('config-apify-token').value || '').trim();
    drHandle   = ($('config-dr-handle').value || 'drjohnbareno').replace(/^@/, '').trim();
    drWebsite  = ($('config-dr-website').value || '').trim();
    igCookie   = ($('config-ig-cookie')?.value || '').trim();
    localStorage.setItem('vl_apify_token', apifyToken);
    localStorage.setItem('vl_dr_handle',   drHandle);
    localStorage.setItem('vl_dr_website',  drWebsite);
    localStorage.setItem('vl_ig_cookie',   igCookie);
    closeConfigModal();
    toast('Configuración guardada ✓');
  }

  /* ─────────────────────────────────────────────────
     CONFIG — carga token Apify desde Supabase secret
  ───────────────────────────────────────────────── */
  async function fetchConfig() {
    if (apifyToken) return;
    try {
      const session = await _sb.auth.getSession();
      const tok = session.data?.session?.access_token || SUPABASE_ANON_KEY;
      const res = await fetch(SUPABASE_FN_URL, {
        method: 'POST',
        headers: { Authorization: `Bearer ${tok}`, 'Content-Type': 'application/json', apikey: SUPABASE_ANON_KEY },
        body: JSON.stringify({ action: 'get_config' }),
      });
      if (res.ok) {
        const { apify_token } = await res.json();
        if (apify_token) { apifyToken = apify_token; localStorage.setItem('vl_apify_token', apify_token); }
      }
    } catch (e) { console.warn('[VL] fetchConfig:', e); }
  }

  /* ═══════════════════════════════════════════════
     INIT
  ═══════════════════════════════════════════════ */
  async function init() {
    await fetchConfig();
    if (!apifyToken) {
      const notice = $('vl-config-notice');
      if (notice) notice.style.display = 'flex';
    }

    // Init manual mode surgery selector
    const manualSel = $('vl-manual-surgery');
    if (manualSel) {
      manualSel.innerHTML = SURGERY_TYPES.map(t => `<option value="${t}">${t}</option>`).join('');
    }

    switchSubTab('competidores');

    $('vl-btn-competidores')?.addEventListener('click', async () => {
      switchSubTab('competidores');
      await loadCompetitors();
    });
    $('vl-btn-adn')?.addEventListener('click', async () => {
      switchSubTab('adn');
      await loadDNA();
    });
    $('vl-btn-guiones')?.addEventListener('click', async () => {
      switchSubTab('guiones');
      const sel = $('vl-surgery-filter');
      if (sel) {
        sel.innerHTML = `<option value="">Todos</option>` +
          SURGERY_TYPES.map(t => `<option value="${t}">${t}</option>`).join('');
      }
      await loadScripts();
    });

    await loadCompetitors();
  }

  /* ── API pública ── */
  return {
    init,
    switchSubTab,
    generateFromManual,
    saveManualScript,
    addCompetitor,
    deleteCompetitor,
    scrapeCompetitor,
    openProcessModal,
    closeProcessModal,
    generateScript,
    saveScript,
    scanInstagram,
    scanWebsite,
    toggleDNAEdit,
    expandScript,
    copyScript,
    deleteScript,
    filterScripts,
    openConfigModal,
    closeConfigModal,
    saveConfig,
  };
})();

document.addEventListener('DOMContentLoaded', () => {
  if (document.getElementById('page-viral-lab')) {
    VL.init().catch(console.error);
  }
});
