(() => {
 const $=s=>document.querySelector(s), esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
 const api=async(u,o={})=>{const r=await fetch(u,o);const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error||`Erro ${r.status}`);return d};
 async function load(){
  const [ov,rank]=await Promise.all([api('/api/community/overview'),api('/api/community/rankings?limit=6')]);
  $('#communityStats').innerHTML=[['🌐','Comunidades',ov.stats?.communities||0],['⚔️','Clãs',ov.stats?.clans||0],['🧩','Espaços',ov.stats?.spaces||0],['📰','Publicações',ov.stats?.posts||0]].map(x=>`<div class="social-stat"><span>${x[0]} ${x[1]}</span><b>${x[2]}</b></div>`).join('');
  $('#mySpaces').innerHTML=[...(ov.communities||[]),...(ov.clans||[])].slice(0,8).map(s=>`<a class="mini-row" href="/comunidade/espacos/${encodeURIComponent(s.id)}/sala"><span>${esc(s.icon)}</span><div><strong>${esc(s.name)}</strong><small>${s.members_count||0} membros · ${s.kind==='clan'?'Clã':'Comunidade'}</small></div><b>›</b></a>`).join('')||'<p class="muted">Crie seu primeiro espaço.</p>';
  const ev=[]; for(const s of [...(ov.communities||[]),...(ov.clans||[])].slice(0,8)){try{const d=await api('/api/community/events/'+encodeURIComponent(s.id));d.events?.slice(0,2).forEach(e=>ev.push({...e,space:s.name}))}catch{}}
  $('#events').innerHTML=ev.slice(0,6).map(e=>`<a class="event-row" href="/comunidade/espacos/${encodeURIComponent(e.space_id)}/sala"><span class="event-icon">${e.kind==='video'?'📹':e.kind==='workshop'?'🎓':'💬'}</span><div><strong>${esc(e.title)}</strong><small>${esc(e.space)} · ${esc(e.starts_at||'agora')} · ${e.attendees?.length||0} participantes</small></div></a>`).join('')||'<p class="muted">Nenhum evento ainda.</p>';
  $('#topRank').innerHTML=(rank.global||[]).map(r=>`<div class="rank-row"><span class="rank-num">#${r.rank}</span><span class="avatar">${esc(r.avatar)}</span><div><strong>${esc(r.display_name)}</strong><small>${r.games||0} jogos · ${r.posts||0} posts</small></div><b>${r.community_score||0} pts</b></div>`).join('')||'<p class="muted">Ainda não há dados suficientes.</p>';
 }
 load().catch(e=>{$('#mySpaces').textContent=e.message});
})();
