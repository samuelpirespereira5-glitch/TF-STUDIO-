(function(){
  const canvas = document.getElementById('se-canvas');
  const ctx = canvas.getContext('2d');
  const preview = document.getElementById('se-preview');
  const pctx = preview.getContext('2d');
  const preview2 = document.getElementById('se-preview2');
  const pctx2 = preview2.getContext('2d');
  let size = 16;
  let pixels = [];
  let color = '#3b82f6';
  let eraser = false;
  let drawing = false;

  const PALETTE = ['#000000','#ffffff','#ef4444','#f97316','#eab308','#22c55e','#06b6d4','#3b82f6','#8b5cf6','#ec4899','#78716c','#1e293b'];

  function initPixels(){
    pixels = Array(size*size).fill(null);
  }

  function cell(){ return canvas.width / size; }

  function draw(){
    const c = cell();
    ctx.clearRect(0,0,canvas.width,canvas.height);
    for(let y=0;y<size;y++){
      for(let x=0;x<size;x++){
        const p = pixels[y*size+x];
        if(p){
          ctx.fillStyle = p;
          ctx.fillRect(x*c, y*c, c, c);
        }
      }
    }
    // grid
    ctx.strokeStyle = 'rgba(255,255,255,0.08)';
    ctx.lineWidth = 1;
    for(let i=0;i<=size;i++){
      ctx.beginPath(); ctx.moveTo(i*c,0); ctx.lineTo(i*c,canvas.height); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0,i*c); ctx.lineTo(canvas.width,i*c); ctx.stroke();
    }
    // previews
    [ [pctx, preview.width], [pctx2, preview2.width] ].forEach(([pc, w])=>{
      pc.clearRect(0,0,w,w);
      const s = w/size;
      for(let y=0;y<size;y++) for(let x=0;x<size;x++){
        const p = pixels[y*size+x];
        if(p){ pc.fillStyle=p; pc.fillRect(x*s,y*s,s,s); }
      }
    });
  }

  function pos(e){
    const r = canvas.getBoundingClientRect();
    const c = cell();
    const x = Math.floor((e.clientX - r.left) / (r.width/size));
    const y = Math.floor((e.clientY - r.top) / (r.height/size));
    return [Math.max(0,Math.min(size-1,x)), Math.max(0,Math.min(size-1,y))];
  }

  function paint(x,y){
    pixels[y*size+x] = eraser ? null : color;
    draw();
  }

  canvas.addEventListener('mousedown', e=>{ drawing=true; const [x,y]=pos(e); paint(x,y); });
  canvas.addEventListener('mousemove', e=>{ if(!drawing) return; const [x,y]=pos(e); paint(x,y); });
  window.addEventListener('mouseup', ()=> drawing=false);
  canvas.addEventListener('touchstart', e=>{ e.preventDefault(); drawing=true; const t=e.touches[0]; const [x,y]=pos(t); paint(x,y); }, {passive:false});
  canvas.addEventListener('touchmove', e=>{ e.preventDefault(); if(!drawing) return; const t=e.touches[0]; const [x,y]=pos(t); paint(x,y); }, {passive:false});
  canvas.addEventListener('touchend', ()=> drawing=false);

  document.getElementById('se-size').addEventListener('change', e=>{
    size = parseInt(e.target.value,10);
    initPixels();
    draw();
  });
  document.getElementById('se-color').addEventListener('input', e=>{ color=e.target.value; eraser=false; });
  document.getElementById('se-eraser').addEventListener('click', ()=>{ eraser=!eraser; document.getElementById('se-eraser').style.outline = eraser?'2px solid #ef4444':''; });
  document.getElementById('se-clear').addEventListener('click', ()=>{ initPixels(); draw(); });
  document.getElementById('se-fill').addEventListener('click', ()=>{
    pixels = pixels.map(()=> eraser ? null : color);
    draw();
  });

  const pal = document.getElementById('se-palette');
  PALETTE.forEach(c=>{
    const b = document.createElement('button');
    b.style.background = c;
    b.title = c;
    b.addEventListener('click', ()=>{
      color=c; eraser=false;
      document.getElementById('se-color').value = c;
      document.querySelectorAll('.se-palette button').forEach(x=>x.classList.remove('active'));
      b.classList.add('active');
    });
    pal.appendChild(b);
  });

  async function api(url, opts){
    const r = await fetch(url, {credentials:'same-origin', headers:{'Content-Type':'application/json'}, ...opts});
    return r.json();
  }

  document.getElementById('se-save').addEventListener('click', async ()=>{
    const name = document.getElementById('se-name').value.trim() || 'Sprite';
    const st = document.getElementById('se-status');
    st.textContent = 'Salvando…';
    const data = await api('/api/nf/sprites', {method:'POST', body: JSON.stringify({name, size, pixels})});
    if(data.ok){ st.textContent = 'Salvo: '+data.name+' ('+data.id+')'; loadList(); }
    else st.textContent = data.error || 'Erro';
  });

  async function loadList(){
    const data = await api('/api/nf/sprites');
    const el = document.getElementById('se-list');
    el.innerHTML = (data.sprites||[]).map(s=>`
      <div class="item" data-id="${s.id}">
        <span>${s.name} <small class="muted">${s.size}×${s.size}</small></span>
        <button class="btn" data-del="${s.id}" style="padding:2px 8px;font-size:.75rem">✕</button>
      </div>`).join('') || '<p class="muted small">Nenhum sprite ainda.</p>';
    el.querySelectorAll('.item').forEach(item=>{
      item.addEventListener('click', async (e)=>{
        if(e.target.dataset.del) return;
        const d = await api('/api/nf/sprites/'+item.dataset.id);
        if(d.sprite){
          size = d.sprite.size;
          document.getElementById('se-size').value = size;
          pixels = d.sprite.pixels;
          document.getElementById('se-name').value = d.sprite.name;
          draw();
        }
      });
    });
    el.querySelectorAll('[data-del]').forEach(btn=>{
      btn.addEventListener('click', async (e)=>{
        e.stopPropagation();
        await api('/api/nf/sprites/'+btn.dataset.del, {method:'DELETE'});
        loadList();
      });
    });
  }

  initPixels();
  draw();
  loadList();
})();
