/* Cyber Lab Phase 2 UI — consumes existing registry/evidence APIs. */
(() => {
  const $ = (s) => document.querySelector(s);
  const esc = (v) => String(v ?? '').replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;').replaceAll('"','&quot;');
  const api = async (url, options = {}) => {
    const r = await fetch(url, { ...options, headers: {'Content-Type':'application/json', 'X-CSRF-Token': document.querySelector('meta[name=csrf-token]')?.content || '', ...(options.headers||{})} });
    const d = await r.json().catch(() => ({}));
    if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
    return d;
  };
  const fmt = (s) => s ? new Date(s).toLocaleString('pt-BR') : '—';
  const sev = (s) => ({critical:'CRITICAL',high:'HIGH',medium:'MEDIUM',low:'LOW',info:'INFO'}[s] || s);

  async function load() {
    try {
      const [d, tools, alerts] = await Promise.all([
        api('/api/cyber/phase2/dashboard'), api('/api/cyber/phase2/tools'), api('/api/cyber/phase2/alerts?limit=12')
      ]);
      $('#p2-status').textContent = d.jarvis === 'online' ? 'ONLINE' : 'CHECK';
      $('#p2-tools').textContent = d.tools;
      $('#p2-scans').textContent = d.scans;
      $('#p2-vulns').textContent = d.vulnerabilities;
      $('#p2-projects').textContent = d.projects;
      $('#p2-challenges').textContent = d.challenges_completed;
      $('#p2-score').textContent = `${d.security_score}/100`;
      $('#p2-xp').textContent = d.xp || 0;
      $('#p2-level').textContent = d.level || 1;
      $('#p2-badges').innerHTML = (d.badges||[]).map(b => `<span class="p2-service ${b.earned?'ok':''}">${b.earned?'🏅':'○'} ${esc(b.name)}</span>`).join('');
      $('#p2-critical').textContent = d.counts.critical || 0;
      $('#p2-high').textContent = d.counts.high || 0;
      $('#p2-medium').textContent = d.counts.medium || 0;
      $('#p2-low').textContent = d.counts.low || 0;
      $('#p2-services').innerHTML = Object.entries(d.services).map(([k,v]) => `<span class="p2-service ${v?'ok':''}">● ${esc(k)} ${v?'OK':'CHECK'}</span>`).join('');
      $('#p2-tools-list').innerHTML = tools.tools.slice(0, 24).map(t => `<div class="p2-tool" data-search="${esc((t.name+' '+t.category+' '+t.description).toLowerCase())}">
        <div><strong>${esc(t.name)}</strong><small>${esc(t.category || '—')}</small></div>
        <span class="p2-badge">${t.needs_target ? 'ALVO' : 'LOCAL'} · SAFE</span>
        <button class="btn small" data-fav="${esc(t.id)}">${t.favorite?'★':'☆'}</button>
        <button class="btn small primary" data-open="${esc(t.id)}">Abrir</button>
      </div>`).join('') || '<div class="cyber-empty">Nenhuma ferramenta disponível.</div>';
      $('#p2-alerts').innerHTML = alerts.alerts.map(a => `<div class="p2-alert ${esc(a.severity)}"><div><strong>${esc(a.title)}</strong><small>${fmt(a.created_at)} · ${esc(a.target || '')}</small></div><span>${a.read_at?'LIDO':'NOVO'}</span></div>`).join('') || '<div class="cyber-empty">Nenhum alerta.</div>';
      $('#p2-history').innerHTML = d.recent_scans.map(s => `<div class="p2-history-row"><span>#${s.id}</span><strong>${esc(s.tool)}</strong><span>${esc(s.target)}</span><span>${s.score}/100</span><small>${fmt(s.ts)}</small></div>`).join('') || '<div class="cyber-empty">Nenhum scan registrado.</div>';
      $('#p2-activity').innerHTML = (d.activity||[]).map(a => `<div class="p2-history-row"><span>${fmt(a.ts)}</span><strong>${esc(a.tool||'evento')}</strong><span>${esc(a.target||'')}</span><span>${a.ok?'OK':'ERRO'}</span><small>${esc(a.error||'')}</small></div>`).join('') || '<div class="cyber-empty">Nenhuma atividade registrada.</div>';
      $('#p2-assets').innerHTML = d.assets.map(a => `<div class="p2-asset"><strong>${esc(a.name)}</strong><span>${esc(a.target)}</span><small>${esc(a.environment)} · última verificação: ${a.last_scan ? fmt(a.last_scan.ts) : 'nunca'}</small></div>`).join('') || '<div class="cyber-empty">Nenhum ativo organizado. Os scans continuam usando a lista de alvos autorizados existente.</div>';
      $('#p2-project-select').innerHTML = '<option value="">Projeto</option>' + (d.projects_data||[]).map(p => `<option value="${p.id}">${esc(p.name)}</option>`).join('');
      $('#p2-asset-select').innerHTML = '<option value="">Ativo</option>' + (d.assets||[]).map(a => `<option value="${a.id}">${esc(a.name)}</option>`).join('');
      $('#p2-project-list').innerHTML = (d.projects_data||[]).map(p => `<div style="padding:6px 0"><strong>${esc(p.name)}</strong> · ${(p.assets||[]).map(a=>esc(a.name)).join(', ') || 'sem ativos'}</div>`).join('') || 'Nenhum projeto.';
      wireTools();
      drawEvolution(d.evolution || []);
    } catch (e) {
      const box = $('#p2-error'); if (box) { box.hidden = false; box.textContent = 'Cyber Dashboard: ' + e.message; }
    }
  }

  function wireTools() {
    document.querySelectorAll('[data-fav]').forEach(b => b.onclick = async () => { try { await api(`/api/cyber/phase2/tools/${encodeURIComponent(b.dataset.fav)}/favorite`, {method:'POST',body:'{}'}); load(); } catch(e) { alert(e.message); } });
    document.querySelectorAll('[data-open]').forEach(b => b.onclick = () => {
      sessionStorage.setItem('jarvis_selected_tool', b.dataset.open);
      $('#exec-analise')?.scrollIntoView({behavior:'smooth', block:'start'});
      $('#cyber-run-tool')?.focus();
    });
  }

  function drawEvolution(items) {
    const el = $('#p2-evolution'); if (!el) return;
    if (!items.length) { el.innerHTML = '<span class="muted small">Ainda não há dados suficientes para evolução.</span>'; return; }
    const max = Math.max(...items.map(x => x.score), 1);
    el.innerHTML = items.map(x => `<div class="p2-bar" title="${esc(x.tool)} · ${esc(x.target)} · ${x.score}/100"><i style="height:${Math.max(5, Math.round((x.score/max)*100))}%"></i></div>`).join('');
  }

  const search = $('#p2-tool-search');
  search?.addEventListener('input', () => {
    const q = search.value.toLowerCase().trim();
    document.querySelectorAll('.p2-tool').forEach(x => x.hidden = q && !x.dataset.search.includes(q));
  });
  $('#p2-refresh')?.addEventListener('click', load);
  load();
})();

// Secondary controls: project/asset creation, reports and JARVIS Analyst.
document.addEventListener('DOMContentLoaded', () => {
  const byId = (id) => document.getElementById(id);
  const post = async (url, body) => { const r = await fetch(url, {method:'POST', headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=csrf-token]')?.content||''}, body:JSON.stringify(body)}); const d=await r.json().catch(()=>({})); if(!r.ok) throw new Error(d.error||'Falha'); return d; };
  byId('p2-add-asset')?.addEventListener('click', async () => {
    try { const d = await post('/api/cyber/phase2/assets', {name:byId('p2-asset-name').value, target:byId('p2-asset-target').value, environment:byId('p2-asset-env').value}); byId('p2-asset-msg').textContent='Ativo adicionado. O escopo autorizado continua sendo a fonte de verdade.'; location.reload(); } catch(e) { byId('p2-asset-msg').textContent='Erro: '+e.message; }
  });
  byId('p2-add-project')?.addEventListener('click', async () => {
    try { await post('/api/cyber/phase2/projects', {name:byId('p2-project-name').value, description:byId('p2-project-desc').value}); byId('p2-project-msg').textContent='Projeto criado.'; location.reload(); } catch(e) { byId('p2-project-msg').textContent='Erro: '+e.message; }
  });
  byId('p2-jarvis-analyze')?.addEventListener('click', async () => {
    const id = window._cyberSelectedScan?.id; const out=byId('p2-jarvis-result');
    if(!id){ out.textContent='Abra um scan no histórico primeiro.'; return; }
    out.textContent='JARVIS analisando as evidências...';
    try { const r=await post(`/api/cyber/phase2/jarvis-analyze/${id}`, {}); out.textContent=r.reply||'Sem resposta.'; } catch(e) { out.textContent='Erro: '+e.message; }
  });
  byId('p2-report-html')?.addEventListener('click', async () => {
    const t=window._cyberSelectedScan?.target; if(!t) return alert('Selecione um scan.');
    const r=await fetch('/api/cyber/phase2/report/html?target='+encodeURIComponent(t)); const b=await r.blob(); const u=URL.createObjectURL(b); const a=document.createElement('a'); a.href=u; a.download='security-report.html'; a.click(); URL.revokeObjectURL(u);
  });
  byId('p2-report-pdf')?.addEventListener('click', async () => {
    const t=window._cyberSelectedScan?.target; if(!t) return alert('Selecione um scan.');
    const r=await fetch('/api/cyber/phase2/report/pdf?target='+encodeURIComponent(t)); if(!r.ok){const d=await r.json().catch(()=>({})); return alert(d.error||'PDF indisponível.');} const b=await r.blob(); const u=URL.createObjectURL(b); const a=document.createElement('a'); a.href=u; a.download='security-report.pdf'; a.click(); URL.revokeObjectURL(u);
  });
});

document.addEventListener('click', async (ev) => {
  const b = ev.target.closest?.('[data-phase2-finding]');
  if (!b) return;
  try {
    const r = await fetch(`/api/cyber/phase2/finding/${b.dataset.phase2Scan}/${encodeURIComponent(b.dataset.phase2Finding)}`);
    const d = await r.json(); if(!r.ok) throw new Error(d.error||'Falha');
    const f=d.finding, s=f.state||{};
    const evidenceText = typeof f.scan.raw === 'object' ? JSON.stringify(f.scan.raw, null, 2) : (f.scan.raw || 'não disponível');
    const action = s.status === 'fixed' ? 'CORRIGIDO' : s.status === 'ignored' ? 'IGNORADO' : 'ABERTO';
    const box = document.createElement('div'); box.className='card p2-investigation'; box.innerHTML=`<h3>🔬 Investigação — ${esc(f.title)}</h3><p><b>Status:</b> ${action} · <b>Severidade:</b> ${esc(f.severity)}</p><p><b>Endpoint/local:</b> <code>${esc(f.where)}</code></p><p><b>Evidência:</b><br><code>${esc(f.evidence)}</code></p><p><b>Impacto:</b> ${esc(f.impact)}</p><p><b>Correção:</b> ${esc(f.fix)}</p><p><b>Raw disponível:</b></p><pre>${esc(evidenceText.slice(0,10000))}</pre><div class="card-actions"><button class="btn small" data-state="fixed">Marcar como corrigida</button><button class="btn small" data-rescan="1">Reverificar</button><button class="btn small danger" data-state="ignored">Ignorar com justificativa</button></div><div class="result" data-investigation-msg></div>`;
    box.querySelector('[data-state="fixed"]').onclick=async()=>{await setState(f, 'fixed', box);};
    box.querySelector('[data-state="ignored"]').onclick=async()=>{const j=prompt('Justificativa obrigatória:'); if(j) await setState(f,'ignored',box,j);};
    box.querySelector('[data-rescan]').onclick=async()=>{box.querySelector('[data-investigation-msg]').textContent='Reverificando...'; try{const rr=await fetch(`/api/cyber/phase2/finding/${f.scan.id}/${encodeURIComponent(f.id)}/rescan`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=csrf-token]')?.content||''},body:'{}'});const dd=await rr.json();box.querySelector('[data-investigation-msg]').textContent=rr.ok?(dd.comparison?`Reverificação concluída: ${dd.comparison.verdict}; novos ${dd.comparison.new.length}; persistentes ${dd.comparison.persistent.length}; resolvidos ${dd.comparison.resolved.length}.`:'Reverificação concluída.'):(dd.error||'Falha');}catch(e){box.querySelector('[data-investigation-msg]').textContent=e.message;}};
    const host=document.getElementById('cyber-findings-card'); host.appendChild(box); box.scrollIntoView({behavior:'smooth',block:'start'});
  } catch(e) { alert(e.message); }
});
async function setState(f, status, box, justification='') {
  try { const r=await fetch(`/api/cyber/phase2/finding/${f.scan.id}/${encodeURIComponent(f.id)}/state`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=csrf-token]')?.content||''},body:JSON.stringify({status,justification})}); const d=await r.json(); if(!r.ok) throw new Error(d.error||'Falha'); box.querySelector('[data-investigation-msg]').textContent=`Status atualizado: ${d.state.status}`; } catch(e) { box.querySelector('[data-investigation-msg]').textContent='Erro: '+e.message; }
}

document.getElementById('p2-attach')?.addEventListener('click', async()=>{ const p=document.getElementById('p2-project-select').value,a=document.getElementById('p2-asset-select').value,m=document.getElementById('p2-attach-msg'); if(!p||!a){m.textContent='Selecione projeto e ativo.';return;} try{const r=await fetch(`/api/cyber/phase2/projects/${p}/assets/${a}`,{method:'POST',headers:{'Content-Type':'application/json','X-CSRF-Token':document.querySelector('meta[name=csrf-token]')?.content||''},body:'{}'});const d=await r.json();if(!r.ok)throw new Error(d.error||'Falha');m.textContent='Ativo vinculado ao projeto.'; location.reload();}catch(e){m.textContent='Erro: '+e.message;} });

document.getElementById('p2-self-audit')?.addEventListener('click', async()=>{ const out=document.getElementById('p2-self-audit-result'); out.textContent='Executando revisão estática somente leitura...'; try{const r=await fetch('/api/cyber/phase2/self-audit');const d=await r.json();if(!r.ok)throw new Error(d.error||'Falha');const c={};(d.findings||[]).forEach(f=>c[f.severity]=(c[f.severity]||0)+1);out.textContent=d.count+' alertas estáticos encontrados · '+Object.entries(c).map(([k,v])=>k+': '+v).join(' · ')+'. Muitos resultados podem ser exemplos intencionais dos desafios; abra os arquivos antes de tratar como falha real.';}catch(e){out.textContent='Erro: '+e.message;} });
