(() => {
  const root=document.querySelector('.room-shell'); if(!root)return;
  const sid=root.dataset.spaceId; const $=s=>document.querySelector(s);
  const esc=v=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  const csrf=()=>document.querySelector('meta[name="csrf-token"]')?.content||'';
  const api=async(u,o={})=>{o.headers=Object.assign({'Content-Type':'application/json','X-CSRFToken':csrf()},o.headers||{});const r=await fetch(u,o);const d=await r.json().catch(()=>({}));if(!r.ok)throw Error(d.error||`Erro ${r.status}`);return d};
  let currentChannel='';let currentKind='text';let timer=null;
  let voice={peerId:'',roomId:'',stream:null,pcs:new Map(),pending:new Map(),pollTimer:null,muted:false};

  async function loadSpace(){
    const d=await api('/api/community/spaces/'+encodeURIComponent(sid)); const s=d.space||d;
    $('#roomTitle').textContent=(s.icon||'🌐')+' '+(s.name||'Comunidade'); $('#roomDesc').textContent=s.description||'Espaço da comunidade';
    const members=(s.members||[]); $('#memberList').innerHTML=members.map(m=>`<div class="member"><span>${esc(m.avatar||'🤖')}</span><div><strong>${esc(m.display_name||m.user_id)}</strong><small>membro</small></div></div>`).join('')||'<p class="muted">Membros aparecerão aqui.</p>';
    await loadChannels(); await loadEvents();
  }
  async function loadChannels(){
    const d=await api('/api/community/channels/'+encodeURIComponent(sid)); const rows=d.channels||[];
    $('#channelList').innerHTML=rows.map((c,i)=>`<button class="channel ${c.id===currentChannel||(!currentChannel&&i===0)?'active':''}" data-id="${esc(c.id)}" data-kind="${esc(c.kind)}">${esc(c.label)}</button>`).join('');
    if(!currentChannel&&rows[0])currentChannel=rows[0].id; const selected=rows.find(x=>x.id===currentChannel)||rows[0];
    if(selected){currentChannel=selected.id;currentKind=selected.kind;selectChannel(selected.id,selected.kind)}
  }
  function selectChannel(id,kind){
    if(voice.peerId && currentChannel!==id) leaveVoice().catch(()=>{});
    currentChannel=id;currentKind=kind||'text'; document.querySelectorAll('.channel').forEach(x=>x.classList.toggle('active',x.dataset.id===id));
    const label=document.querySelector(`.channel[data-id="${CSS.escape(id)}"]`)?.textContent||'# geral'; $('#channelTitle').textContent=label;
    $('#channelKind').textContent=currentKind==='voice'?'Sala de voz':currentKind==='stage'?'Palco / workshop':'Canal de texto';
    loadMessages();
    if(currentKind==='voice'||currentKind==='stage') showVoicePanel(); else $('#livePanel').classList.add('hidden');
  }
  async function loadMessages(){
    if(!currentChannel)return; const d=await api('/api/community/chat/'+encodeURIComponent(sid)+'/'+encodeURIComponent(currentChannel)); const rows=d.messages||[];
    $('#messageList').innerHTML=rows.map(m=>`<article class="message"><span class="message-avatar">${esc(m.author?.avatar||'🤖')}</span><div class="message-body"><div class="message-meta"><strong>${esc(m.author?.display_name||m.author?.user_id||'Membro')}</strong><small>${new Date(m.created_at).toLocaleString('pt-BR')}</small></div><div class="message-content">${esc(m.content)}</div></div></article>`).join('')||'<p class="muted">Seja a primeira pessoa a falar neste canal.</p>';
    const box=$('#messageList');box.scrollTop=box.scrollHeight;
  }
  async function loadEvents(){
    const d=await api('/api/community/events/'+encodeURIComponent(sid)); const ev=d.events||[];
    $('#eventList').innerHTML=ev.map(e=>`<button class="event-row" data-event="${esc(e.id)}"><span class="event-icon">${e.kind==='video'?'📹':e.kind==='workshop'?'🎓':'💬'}</span><div><strong>${esc(e.title)}</strong><small>${esc(e.starts_at||'agora')} · ${e.attendees?.length||0} pessoas</small></div></button>`).join('')||'<p class="muted">Nenhum evento criado.</p>';
  }
  function showVoicePanel(){
    $('#livePanel').classList.remove('hidden');
    $('#livePanel').innerHTML=`<div class="voice-panel"><div class="live-title-row"><strong>🔊 Live / Call da comunidade</strong><span id="voiceStatus" class="voice-status">Pronto para entrar</span></div><p class="muted">Entre na sala para usar o microfone. O áudio é enviado diretamente entre os participantes pelo navegador.</p><div class="voice-actions"><button class="btn primary" id="voiceJoin">🎙️ Entrar na call</button><button class="btn ghost hidden" id="voiceMute">🔇 Mutar</button><button class="btn ghost hidden" id="voiceLeave">🚪 Sair da call</button></div><div id="remoteAudios" class="remote-audios"></div></div>`;
    $('#voiceJoin').onclick=()=>joinVoice().catch(showVoiceError);
  }
  function showVoiceError(e){const s=$('#voiceStatus');if(s)s.textContent=e?.message||'Não foi possível iniciar a call.';alert(e?.message||'Não foi possível iniciar a call.');}
  async function joinVoice(){
    if(voice.peerId)return;
    if(!navigator.mediaDevices?.getUserMedia) throw Error('Seu navegador não disponibiliza microfone seguro para esta página.');
    const stream=await navigator.mediaDevices.getUserMedia({audio:{echoCancellation:true,noiseSuppression:true,autoGainControl:true},video:false});
    voice.stream=stream;
    const d=await api('/api/community/voice/'+encodeURIComponent(sid)+'/'+encodeURIComponent(currentChannel)+'/join',{method:'POST',body:'{}'});
    voice.peerId=d.peer_id;voice.roomId=d.room_id;voice.muted=false;
    $('#voiceStatus').textContent='🟢 Conectado · '+(d.peers?.length||0)+' participante(s)';
    $('#voiceJoin').classList.add('hidden');$('#voiceMute').classList.remove('hidden');$('#voiceLeave').classList.remove('hidden');
    $('#voiceMute').onclick=toggleMute;$('#voiceLeave').onclick=()=>leaveVoice();
    for(const p of (d.peers||[])) await makeOffer(p.peer_id);
    startVoicePolling();
  }
  function pcFor(peerId){
    if(voice.pcs.has(peerId))return voice.pcs.get(peerId);
    const pc=new RTCPeerConnection({iceServers:[{urls:'stun:stun.l.google.com:19302'}]});
    voice.pcs.set(peerId,pc); voice.pending.set(peerId,[]);
    voice.stream?.getTracks().forEach(t=>pc.addTrack(t,voice.stream));
    pc.onicecandidate=e=>{if(e.candidate)sendSignal(peerId,{type:'ice',data:e.candidate}).catch(()=>{})};
    pc.ontrack=e=>attachRemote(peerId,e.streams[0]);
    pc.onconnectionstatechange=()=>{if(['failed','closed','disconnected'].includes(pc.connectionState)){removePeer(peerId)}};
    return pc;
  }
  async function makeOffer(peerId){
    const pc=pcFor(peerId); const offer=await pc.createOffer(); await pc.setLocalDescription(offer); await sendSignal(peerId,{type:'offer',data:offer});
  }
  async function sendSignal(target,signal){
    if(!voice.peerId)return; return api('/api/community/voice/'+encodeURIComponent(sid)+'/'+encodeURIComponent(currentChannel)+'/signal',{method:'POST',body:JSON.stringify({peer_id:voice.peerId,target,signal})});
  }
  async function handleSignal(sig){
    const peer=sig.from; if(!peer)return; const pc=pcFor(peer);
    if(sig.type==='offer'){
      await pc.setRemoteDescription(sig.payload); for(const c of (voice.pending.get(peer)||[]))await pc.addIceCandidate(c); voice.pending.set(peer,[]);
      const answer=await pc.createAnswer(); await pc.setLocalDescription(answer); await sendSignal(peer,{type:'answer',data:answer});
    } else if(sig.type==='answer'){
      await pc.setRemoteDescription(sig.payload); for(const c of (voice.pending.get(peer)||[]))await pc.addIceCandidate(c); voice.pending.set(peer,[]);
    } else if(sig.type==='ice'){
      if(pc.remoteDescription) await pc.addIceCandidate(sig.payload); else voice.pending.get(peer).push(sig.payload);
    } else if(sig.type==='bye') removePeer(peer);
  }
  function startVoicePolling(){
    clearInterval(voice.pollTimer); voice.pollTimer=setInterval(async()=>{
      if(!voice.peerId)return; try{const d=await api('/api/community/voice/'+encodeURIComponent(sid)+'/'+encodeURIComponent(currentChannel)+'/poll?peer_id='+encodeURIComponent(voice.peerId));for(const s of(d.signals||[]))await handleSignal(s);$('#voiceStatus').textContent='🟢 Conectado · '+(d.peers?.length||0)+' participante(s)';}catch(e){}},1200);
  }
  function attachRemote(peerId,stream){
    let audio=document.querySelector(`audio[data-peer="${CSS.escape(peerId)}"]`); if(!audio){audio=document.createElement('audio');audio.dataset.peer=peerId;audio.autoplay=true;audio.playsInline=true;audio.className='remote-audio';$('#remoteAudios').appendChild(audio)} audio.srcObject=stream; audio.play().catch(()=>{});
  }
  function removePeer(peerId){voice.pcs.get(peerId)?.close();voice.pcs.delete(peerId);voice.pending.delete(peerId);document.querySelector(`audio[data-peer="${CSS.escape(peerId)}"]`)?.remove()}
  function toggleMute(){if(!voice.stream)return;voice.muted=!voice.muted;voice.stream.getAudioTracks().forEach(t=>t.enabled=!voice.muted);$('#voiceMute').textContent=voice.muted?'🎙️ Desmutar':'🔇 Mutar'}
  async function leaveVoice(){
    clearInterval(voice.pollTimer); voice.pollTimer=null;
    if(voice.peerId){try{await api('/api/community/voice/'+encodeURIComponent(sid)+'/'+encodeURIComponent(currentChannel)+'/leave',{method:'POST',body:JSON.stringify({peer_id:voice.peerId})})}catch(e){}}
    for(const pc of voice.pcs.values())pc.close(); voice.pcs.clear();voice.pending.clear();
    voice.stream?.getTracks().forEach(t=>t.stop());voice.stream=null;voice.peerId='';voice.roomId='';
    document.querySelectorAll('.remote-audio').forEach(x=>x.remove());
    if($('#livePanel')&&!$('#livePanel').classList.contains('hidden'))showVoicePanel();
  }
  async function openEvent(id){
    const d=await api('/api/community/events/'+encodeURIComponent(id)+'/join',{method:'POST',body:'{}'}); const e=d.event; $('#livePanel').classList.remove('hidden');
    if(e.embed_url){$('#livePanel').innerHTML=`<div class="live-title-row"><strong>🔴 ${esc(e.title)}</strong><span>${e.attendees?.length||0} participantes</span></div><iframe src="${esc(e.embed_url)}" allow="autoplay; encrypted-media; picture-in-picture; fullscreen" allowfullscreen title="${esc(e.title)}"></iframe><p class="muted">${esc(e.description||'Evento ao vivo')}</p>`}
    else{$('#livePanel').innerHTML=`<div class="live-title-row"><strong>🔴 ${esc(e.title)}</strong><span>${e.attendees?.length||0} participantes</span></div><p>${esc(e.description||'Evento ao vivo')}</p><p class="muted">Esse evento não possui vídeo externo. Use o canal de chat ou entre na call de voz da comunidade.</p>`}
  }
  $('#createEvent').onclick=()=>$('#eventCreator').classList.remove('hidden'); $('#closeEventCreator').onclick=()=>$('#eventCreator').classList.add('hidden');
  $('#saveEvent').onclick=async()=>{try{const title=$('#eventTitle').value.trim();if(!title)return alert('Digite um título.');await api('/api/community/events/'+encodeURIComponent(sid),{method:'POST',body:JSON.stringify({title,kind:$('#eventKind').value,starts_at:$('#eventDate').value,media_url:$('#eventMedia').value,description:$('#eventDesc').value})});$('#eventCreator').classList.add('hidden');$('#eventTitle').value='';$('#eventDesc').value='';$('#eventMedia').value='';await loadEvents()}catch(x){alert(x.message)}};
  $('#channelList').addEventListener('click',e=>{const b=e.target.closest('.channel');if(b)selectChannel(b.dataset.id,b.dataset.kind)});
  $('#eventList').addEventListener('click',e=>{const b=e.target.closest('[data-event]');if(b)openEvent(b.dataset.event).catch(showVoiceError)});
  $('#chatForm').addEventListener('submit',async e=>{e.preventDefault();const input=$('#chatInput'),content=input.value.trim();if(!content)return;try{await api('/api/community/chat/'+encodeURIComponent(sid)+'/'+encodeURIComponent(currentChannel),{method:'POST',body:JSON.stringify({content})});input.value='';await loadMessages()}catch(x){alert(x.message)}});
  $('#refreshChat').onclick=loadMessages; $('#addChannel').onclick=async()=>{const name=prompt('Nome do novo canal:');if(!name)return;try{await api('/api/community/channels/'+encodeURIComponent(sid),{method:'POST',body:JSON.stringify({name,kind:'text'})});await loadChannels()}catch(x){alert(x.message)}};
  window.addEventListener('beforeunload',()=>{clearInterval(timer);clearInterval(voice.pollTimer);if(voice.peerId)navigator.sendBeacon?.('/api/community/voice/'+encodeURIComponent(sid)+'/'+encodeURIComponent(currentChannel)+'/leave',new Blob([JSON.stringify({peer_id:voice.peerId})],{type:'application/json'}));voice.stream?.getTracks().forEach(t=>t.stop())});
  loadSpace().catch(e=>{$('#roomDesc').textContent=e.message}); timer=setInterval(()=>{if(currentChannel)loadMessages().catch(()=>{})},5000);
})();
