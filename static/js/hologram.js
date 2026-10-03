// ============================================================
// Holograma 3D — componente reutilizável. Qualquer elemento com
// [data-holo-widget] vira um "projetor" independente, com seu
// próprio motor Three.js. Funciona tanto no card de Ferramentas
// quanto embutido dentro do Jarvis (window.jarvisHolograma).
//
// Importante: isto NÃO depende do objeto global "Tools" — cada
// widget se liga sozinho via addEventListener nos elementos
// [data-holo="..."] que encontrar dentro de si mesmo.
// ============================================================
(function () {
  "use strict";

  // ---------- PRNG determinístico a partir do texto ----------
  function seededRandom(str) {
    let h = 1779033703 ^ str.length;
    for (let i = 0; i < str.length; i++) {
      h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
      h = (h << 13) | (h >>> 19);
    }
    return function () {
      h = Math.imul(h ^ (h >>> 16), 2246822507);
      h = Math.imul(h ^ (h >>> 13), 3266489909);
      h ^= h >>> 16;
      return (h >>> 0) / 4294967296;
    };
  }

  // ---------- Catálogo de tipos de holograma pro seletor do painel ----------
  // Cada entrada mapeia um id estável (usado em data-holo-kind no HTML)
  // pra um texto que os detectores em buildObjeto()/detectType() já
  // reconhecem, evitando duplicar a lógica de detecção.
  const HOLO_KIND_LABELS = {
    dna: "molécula de DNA",
    molecula: "molécula",
    atomo: "átomo",
    planeta: "planeta Saturno",
    "sistema-solar": "sistema solar",
    globo: "globo terrestre",
    cristal: "cristal",
    coracao: "coração",
    cerebro: "cérebro",
    "rede-neural": "rede neural",
    particulas: "nuvem de partículas",
    portal: "portal",
    "esfera-holo": "esfera holográfica",
    grafico: "gráfico 3D",
    poliedro: "objeto geométrico",
  };

  function detectType(text) {
    const t = text.toLowerCase();
    if (/\b(mapa|terreno|bairro|cidade|regiao|regi\u00e3o|relevo|rua|zona|planta baixa|territorio|territ\u00f3rio|montanha|montanhas|monte|serra|vale|vulcao|vulc\u00e3o)\b/.test(t)) return "mapa";
    if (/\b(rede|conexao|conex\u00e3o|conexoes|conex\u00f5es|grafo|network|neural|liga\u00e7ao|liga\u00e7\u00e3o)\b/.test(t)) return "rede";
    return "objeto";
  }

  function makeGlowTexture() {
    // Resolução maior + curva de queda em mais estágios: um núcleo
    // branco-quente pequeno, um halo colorido suave e uma cauda bem
    // longa e fraca — é essa cauda longa que faz partículas pequenas
    // lerem como "pontos de luz real" em vez de bolinhas com borda dura.
    const c = document.createElement("canvas");
    c.width = c.height = 128;
    const ctx = c.getContext("2d");
    const g = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    g.addColorStop(0, "rgba(255,255,255,1)");
    g.addColorStop(0.12, "rgba(255,255,255,0.95)");
    g.addColorStop(0.32, "rgba(170,240,255,0.55)");
    g.addColorStop(0.6, "rgba(120,210,255,0.16)");
    g.addColorStop(1, "rgba(0,229,255,0)");
    ctx.fillStyle = g;
    ctx.fillRect(0, 0, 128, 128);
    const tex = new THREE.CanvasTexture(c);
    tex.needsUpdate = true;
    return tex;
  }

  // ---------- Textura em faixas pro feixe do projetor ----------
  // Faixas horizontais irregulares de opacidade que, com a UV
  // rolando ao longo do tempo (ver animate()), leem como poeira/ruído
  // subindo dentro do feixe de luz — o efeito "volumétrico" clássico
  // de projetor de holograma, sem precisar de shader custom.
  function makeBeamStreakTexture(rng) {
    const rnd = rng || Math.random;
    const c = document.createElement("canvas");
    c.width = 8;
    c.height = 256;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, 8, 256);
    for (let y = 0; y < 256; y++) {
      const n = rnd();
      const a = n > 0.86 ? 0.5 + rnd() * 0.5 : n * 0.25;
      ctx.fillStyle = "rgba(255,255,255," + a.toFixed(3) + ")";
      ctx.fillRect(0, y, 8, 1);
    }
    const tex = new THREE.CanvasTexture(c);
    tex.wrapS = THREE.RepeatWrapping;
    tex.wrapT = THREE.RepeatWrapping;
    tex.needsUpdate = true;
    return tex;
  }

  // ---------- Material "fresnel" (borda brilhante, centro translúcido) ----------
  // Isto é o que faz a diferença entre "esfera com opacidade fixa" e
  // um holograma que parece de verdade: a borda (onde a superfície é
  // vista de raspão) acende bem mais forte que o centro, exatamente
  // como uma projeção de luz vista contra o ar. Substitui as antigas
  // MeshBasicMaterial de opacidade fixa nos preenchimentos sólidos.
  function makeFresnelMaterial(colorHex, opacity, colorHex2) {
    const mat = new THREE.ShaderMaterial({
      uniforms: {
        uColor: { value: new THREE.Color(colorHex) },
        uColor2: { value: new THREE.Color(colorHex2 || colorHex) },
        uOpacity: { value: opacity },
        uTime: { value: 0 },
      },
      vertexShader: [
        "varying vec3 vNormal;",
        "varying vec3 vViewDir;",
        "varying float vPosY;",
        "void main() {",
        "  vNormal = normalize(normalMatrix * normal);",
        "  vec4 mvPosition = modelViewMatrix * vec4(position, 1.0);",
        "  vViewDir = normalize(-mvPosition.xyz);",
        "  vPosY = position.y;",
        "  gl_Position = projectionMatrix * mvPosition;",
        "}",
      ].join("\n"),
      fragmentShader: [
        "uniform vec3 uColor;",
        "uniform vec3 uColor2;",
        "uniform float uOpacity;",
        "uniform float uTime;",
        "varying vec3 vNormal;",
        "varying vec3 vViewDir;",
        "varying float vPosY;",
        "void main() {",
        "  float ndv = max(dot(normalize(vNormal), normalize(vViewDir)), 0.0);",
        "  float fresnel = pow(1.0 - ndv, 2.2);",
        // Leve trocar de cor na borda (iridescência sutil ciano/roxo) —
        // uma superfície de holograma "puro" nunca tem uma cor só.
        "  vec3 edgeColor = mix(uColor, uColor2, pow(1.0 - ndv, 1.4));",
        // Faixa de varredura de dados subindo/descendo pela superfície —
        // a leitura mais reconhecível de "isto é um holograma".
        "  float scan = smoothstep(0.82, 1.0, sin(vPosY * 2.6 - uTime * 1.7)) * 0.7;",
        "  vec3 col = mix(uColor, edgeColor, 0.6) + scan * uColor2;",
        "  gl_FragColor = vec4(col, uOpacity * (0.12 + fresnel * 1.05 + scan * 0.5));",
        "}",
      ].join("\n"),
      transparent: true,
      depthWrite: false,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      fog: false,
    });
    return mat;
  }

  // ---------- Feixe do projetor (base luminosa subindo) ----------
  // Um cone bem alongado e quase transparente saindo de um anel no
  // ch\u00e3o \u2014 a leitura cl\u00e1ssica de "luz de projetor" que faz o
  // holograma parecer estar sendo projetado de baixo pra cima, em vez
  // de só flutuar sozinho no ar sem explica\u00e7\u00e3o nenhuma.
  function addProjectorBeam(grp, accent, accent2, radius, height) {
    const beamGeo = new THREE.CylinderGeometry(radius * 0.05, radius, height, 24, 1, true);
    const streakTex = makeBeamStreakTexture();
    streakTex.repeat.set(3, 6);
    const beamMat = new THREE.MeshBasicMaterial({
      color: accent,
      map: streakTex,
      transparent: true,
      opacity: 0.1,
      side: THREE.DoubleSide,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const beam = new THREE.Mesh(beamGeo, beamMat);
    beam.position.y = -height / 2 - height * 0.02;
    grp.add(beam);

    const baseRing = new THREE.Mesh(
      new THREE.RingGeometry(radius * 0.9, radius * 1.05, 40),
      new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.55, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    baseRing.rotation.x = -Math.PI / 2;
    baseRing.position.y = -height * 0.02;
    grp.add(baseRing);
    grp.userData.beam = beam;
  }

  // ---------- Poeira ambiente (uma \u00fanica vez por cena) ----------
  // Um campo esparso de part\u00edculas bem fracas flutuando ao redor do
  // holograma inteiro \u2014 d\u00e1 profundidade e a sensa\u00e7\u00e3o de "part\u00edculas
  // de luz no ar" sem competir visualmente com o objeto principal.
  function addAmbientParticles(scene, accent, accent2, density) {
    const count = Math.max(10, Math.round(90 * (density || 1)));
    const positions = new Float32Array(count * 3);
    for (let i = 0; i < count; i++) {
      positions[i * 3] = (Math.random() * 2 - 1) * 9;
      positions[i * 3 + 1] = (Math.random() * 2 - 1) * 5.5;
      positions[i * 3 + 2] = (Math.random() * 2 - 1) * 9;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    const mat = new THREE.PointsMaterial({
      color: accent2,
      size: 0.05,
      map: makeGlowTexture(),
      transparent: true,
      opacity: 0.35,
      blending: THREE.AdditiveBlending,
      depthWrite: false,
    });
    const points = new THREE.Points(geo, mat);
    scene.add(points);
    return points;
  }

  function makeNoise2D(rng) {
    const layers = Array.from({ length: 4 }, (_, i) => ({
      fx: rng() * 0.18 + 0.04,
      fy: rng() * 0.18 + 0.04,
      amp: 1 / (i + 1.3),
      phX: rng() * Math.PI * 2,
      phY: rng() * Math.PI * 2,
    }));
    return function (x, y) {
      let v = 0;
      let norm = 0;
      layers.forEach((l) => {
        v += Math.sin(x * l.fx + l.phX) * Math.cos(y * l.fy + l.phY) * l.amp;
        norm += l.amp;
      });
      return v / norm;
    };
  }

  // ---------- Prédios procedurais (holograma "de cidade", sem lugar real) ----------
  // Diferente de addBuildings() (que usa contornos/alturas reais do
  // OpenStreetMap para um lugar de verdade), isto é só decoração
  // procedural: um punhado de caixas de altura aleatória "plantadas"
  // sobre o relevo procedural, pra quando a pessoa pede um holograma
  // de "cidade"/"prédios"/"skyline" sem nomear um lugar real — dá a
  // leitura de cidade sem precisar de nenhum dado de verdade.
  function addProceduralBuildings(rng, grp, accent, accent2, noiseFn, size) {
    const count = 14 + Math.floor(rng() * 10);
    const wallMat = new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.6 });
    const fillMat = new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.1, side: THREE.DoubleSide, depthWrite: false });
    // Agrupa os prédios num "bairro" só, em vez de espalhar por todo o
    // terreno — fica mais parecido com um centro/skyline de verdade.
    const clusterX = (rng() - 0.5) * size * 0.5;
    const clusterZ = (rng() - 0.5) * size * 0.5;
    for (let i = 0; i < count; i++) {
      const x = clusterX + (rng() - 0.5) * size * 0.42;
      const z = clusterZ + (rng() - 0.5) * size * 0.42;
      const w = 0.35 + rng() * 0.55;
      const d = 0.35 + rng() * 0.55;
      const h = 0.6 + rng() * rng() * 3.2;
      const baseY = noiseFn(x, z) * 2.6 + noiseFn(x * 2.4, z * 2.4) * 0.9;
      const geo = new THREE.BoxGeometry(w, h, d);
      const wire = new THREE.Mesh(geo, wallMat);
      wire.position.set(x, baseY + h / 2, z);
      grp.add(wire);
      const fill = new THREE.Mesh(geo, fillMat);
      fill.position.copy(wire.position);
      grp.add(fill);
    }
  }

  // ---------- Construtores de cena ----------
  function buildMapa(rng, grp, accent, accent2, text) {
    const size = 26;
    const seg = 42;
    const geo = new THREE.PlaneGeometry(size, size, seg, seg);
    geo.rotateX(-Math.PI / 2);
    const noise = makeNoise2D(rng);
    const pos = geo.attributes.position;
    let maxH = -Infinity;
    let maxIdx = 0;
    for (let i = 0; i < pos.count; i++) {
      const x = pos.getX(i);
      const z = pos.getZ(i);
      const hgt = noise(x, z) * 2.6 + noise(x * 2.4, z * 2.4) * 0.9;
      pos.setY(i, hgt);
      if (hgt > maxH) {
        maxH = hgt;
        maxIdx = i;
      }
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();

    grp.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.85 })));
    grp.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.045, side: THREE.DoubleSide })));

    const px = pos.getX(maxIdx);
    const py = pos.getY(maxIdx);
    const pz = pos.getZ(maxIdx);

    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.3, 1.3, 12), new THREE.MeshBasicMaterial({ color: accent2 }));
    cone.position.set(px, py + 1.5, pz);
    cone.rotation.x = Math.PI;
    grp.add(cone);

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.45, 0.6, 32),
      new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.7, side: THREE.DoubleSide })
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(px, py + 0.05, pz);
    grp.add(ring);
    grp.userData.pulseRings = [ring];

    const sweep = new THREE.Mesh(
      new THREE.CircleGeometry(size * 0.6, 48, 0, Math.PI / 5),
      new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.16, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    sweep.rotation.x = -Math.PI / 2;
    sweep.position.y = 0.02;
    grp.add(sweep);
    grp.userData.sweep = sweep;

    const grid = new THREE.GridHelper(size * 1.15, 20, accent2, accent);
    grid.material.transparent = true;
    grid.material.opacity = 0.22;
    grid.position.y = -0.03;
    grp.add(grid);
    grp.userData.gridMeshes = [grid];

    if (text && /\b(cidade|pr[ée]dios?|skyline|downtown|metr[oó]pole|centro urbano)\b/i.test(text)) {
      addProceduralBuildings(rng, grp, accent, accent2, noise, size);
    }
  }

  function buildHelix(rng, grp, accent, accent2) {
    const turns = 4;
    const pointsPerTurn = 22;
    const radius = 2.2;
    const height = 9;
    const n = turns * pointsPerTurn;
    const vertsA = [];
    const vertsB = [];
    const rungsGroup = new THREE.Group();
    const rungMat = new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: 0.35 });

    for (let i = 0; i <= n; i++) {
      const a = (i / pointsPerTurn) * Math.PI * 2;
      const y = (i / n) * height - height / 2;
      const ax = Math.cos(a) * radius;
      const az = Math.sin(a) * radius;
      const bx = Math.cos(a + Math.PI) * radius;
      const bz = Math.sin(a + Math.PI) * radius;
      vertsA.push(ax, y, az);
      vertsB.push(bx, y, bz);
      if (i % 3 === 0) {
        const rungGeo = new THREE.BufferGeometry().setFromPoints([new THREE.Vector3(ax, y, az), new THREE.Vector3(bx, y, bz)]);
        rungsGroup.add(new THREE.Line(rungGeo, rungMat));
      }
    }
    const geoA = new THREE.BufferGeometry();
    geoA.setAttribute("position", new THREE.Float32BufferAttribute(vertsA, 3));
    const geoB = new THREE.BufferGeometry();
    geoB.setAttribute("position", new THREE.Float32BufferAttribute(vertsB, 3));

    const glow = makeGlowTexture();
    grp.add(new THREE.Points(geoA, new THREE.PointsMaterial({ color: accent, size: 0.22, map: glow, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));
    grp.add(new THREE.Points(geoB, new THREE.PointsMaterial({ color: accent2, size: 0.22, map: glow, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));
    grp.add(rungsGroup);
  }

  function buildPlanet(text, rng, grp, accent, accent2) {
    const r = 2.6;
    const geo = new THREE.SphereGeometry(r, 24, 18);
    grp.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.55 })));
    grp.add(new THREE.Mesh(geo.clone(), makeFresnelMaterial(accent, 0.5, accent2)));

    if (/anel|saturno/.test(text)) {
      const ring = new THREE.Mesh(
        new THREE.RingGeometry(r * 1.5, r * 2.2, 64),
        new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.35, side: THREE.DoubleSide })
      );
      ring.rotation.x = Math.PI / 2.3;
      grp.add(ring);
    }

    const starCount = 110;
    const starPos = new Float32Array(starCount * 3);
    for (let i = 0; i < starCount; i++) {
      const rr = r * 1.5 + rng() * 2.4;
      const th = rng() * Math.PI * 2;
      const ph = Math.acos(rng() * 2 - 1);
      starPos[i * 3] = rr * Math.sin(ph) * Math.cos(th);
      starPos[i * 3 + 1] = rr * Math.sin(ph) * Math.sin(th);
      starPos[i * 3 + 2] = rr * Math.cos(ph);
    }
    const starGeo = new THREE.BufferGeometry();
    starGeo.setAttribute("position", new THREE.Float32BufferAttribute(starPos, 3));
    grp.add(new THREE.Points(starGeo, new THREE.PointsMaterial({ color: accent2, size: 0.12, map: makeGlowTexture(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));
  }

  function buildPolyhedron(rng, grp, accent, accent2) {
    const kinds = [
      () => new THREE.IcosahedronGeometry(2.6, 0),
      () => new THREE.TorusKnotGeometry(1.7, 0.45, 100, 12, Math.floor(rng() * 3) + 2, Math.floor(rng() * 3) + 2),
      () => new THREE.OctahedronGeometry(2.7, 0),
      () => new THREE.DodecahedronGeometry(2.3, 0),
    ];
    const geo = kinds[Math.floor(rng() * kinds.length)]();
    grp.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: accent, wireframe: true })));
    grp.add(new THREE.Mesh(geo.clone(), makeFresnelMaterial(accent2, 0.45)));
    grp.add(new THREE.Points(geo, new THREE.PointsMaterial({ color: accent2, size: 0.15, map: makeGlowTexture(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));
  }

  function buildAtomo(rng, grp, accent, accent2) {
    const nucleus = new THREE.Mesh(
      new THREE.IcosahedronGeometry(0.9, 1),
      new THREE.MeshBasicMaterial({ color: accent2, wireframe: true })
    );
    grp.add(nucleus);
    grp.add(new THREE.Mesh(nucleus.geometry.clone(), makeFresnelMaterial(accent2, 0.6)));
    grp.add(new THREE.Points(nucleus.geometry, new THREE.PointsMaterial({ color: accent2, size: 0.22, map: makeGlowTexture(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));

    const orbitCount = 3;
    const orbits = [];
    for (let i = 0; i < orbitCount; i++) {
      const radius = 2.3 + i * 0.55;
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(radius, 0.015, 8, 96),
        new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.5 })
      );
      ring.rotation.x = rng() * Math.PI;
      ring.rotation.y = rng() * Math.PI;
      grp.add(ring);

      const electron = new THREE.Mesh(new THREE.SphereGeometry(0.14, 12, 12), new THREE.MeshBasicMaterial({ color: accent2 }));
      ring.add(electron);
      electron.position.set(radius, 0, 0);
      orbits.push({ ring: ring, electron: electron, radius: radius, speed: 0.6 + rng() * 0.8, angle: rng() * Math.PI * 2 });
    }
    grp.userData.atomOrbits = orbits;
  }

  function buildCoracao(rng, grp, accent, accent2) {
    const shape = new THREE.Shape();
    const x = 0, y = 0;
    shape.moveTo(x, y);
    shape.bezierCurveTo(x, y - 1.8, x - 3.4, y - 1.8, x - 3.4, y + 0.6);
    shape.bezierCurveTo(x - 3.4, y + 2.6, x - 1.2, y + 3.4, x, y + 4.6);
    shape.bezierCurveTo(x + 1.2, y + 3.4, x + 3.4, y + 2.6, x + 3.4, y + 0.6);
    shape.bezierCurveTo(x + 3.4, y - 1.8, x, y - 1.8, x, y);
    const geo = new THREE.ExtrudeGeometry(shape, { depth: 0.6, bevelEnabled: true, bevelThickness: 0.15, bevelSize: 0.1, bevelSegments: 3 });
    geo.center();
    geo.scale(0.7, 0.7, 0.7);
    const heartGroup = new THREE.Group();
    heartGroup.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: accent2, wireframe: true })));
    heartGroup.add(new THREE.Points(geo, new THREE.PointsMaterial({ color: accent, size: 0.1, map: makeGlowTexture(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));
    grp.add(heartGroup);
    grp.userData.heartbeat = heartGroup;
  }

  function buildCristal(rng, grp, accent, accent2) {
    const count = 5 + Math.floor(rng() * 4);
    for (let i = 0; i < count; i++) {
      const h = 1.4 + rng() * 2.6;
      const geo = new THREE.ConeGeometry(0.35 + rng() * 0.3, h, 6);
      const mat = new THREE.MeshBasicMaterial({ color: rng() > 0.5 ? accent : accent2, wireframe: true, transparent: true, opacity: 0.85 });
      const cone = new THREE.Mesh(geo, mat);
      const a = (i / count) * Math.PI * 2 + rng() * 0.4;
      const r = rng() * 1.6;
      cone.position.set(Math.cos(a) * r, h / 2 - 1.4, Math.sin(a) * r);
      cone.rotation.z = (rng() - 0.5) * 0.3;
      cone.rotation.x = (rng() - 0.5) * 0.3;
      grp.add(cone);
      const glowPts = new THREE.Points(geo, new THREE.PointsMaterial({ color: accent2, size: 0.08, map: makeGlowTexture(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, opacity: 0.6 }));
      glowPts.position.copy(cone.position);
      glowPts.rotation.copy(cone.rotation);
      grp.add(glowPts);
    }
  }

  // ---------- Sistema solar: sol central + planetas orbitando ----------
  // Reaproveita o mesmo mecanismo de \u00f3rbita do \u00e1tomo (grp.userData.atomOrbits
  // j\u00e1 \u00e9 animado em animate()), s\u00f3 que com um "sol" brilhante no centro e
  // planetas de tamanhos/cores variados em vez de el\u00e9trons.
  function buildSolarSystem(rng, grp, accent, accent2) {
    const sun = new THREE.Mesh(new THREE.IcosahedronGeometry(0.85, 2), new THREE.MeshBasicMaterial({ color: accent2, wireframe: true }));
    grp.add(sun);
    grp.add(new THREE.Mesh(sun.geometry.clone(), makeFresnelMaterial(accent2, 0.8)));
    grp.add(new THREE.Points(sun.geometry, new THREE.PointsMaterial({ color: accent2, size: 0.2, map: makeGlowTexture(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));

    const planetCount = 4 + Math.floor(rng() * 3);
    const orbits = [];
    for (let i = 0; i < planetCount; i++) {
      const radius = 1.7 + i * 0.95;
      const ring = new THREE.Mesh(
        new THREE.TorusGeometry(radius, 0.012, 8, 96),
        new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.4 })
      );
      ring.rotation.x = Math.PI / 2 + (rng() - 0.5) * 0.5;
      grp.add(ring);

      const pr = 0.12 + rng() * 0.22;
      const planetColor = i % 2 === 0 ? accent : accent2;
      const planet = new THREE.Mesh(new THREE.SphereGeometry(pr, 14, 12), new THREE.MeshBasicMaterial({ color: planetColor, wireframe: rng() > 0.5 }));
      ring.add(planet);
      planet.position.set(radius, 0, 0);
      orbits.push({ ring: ring, electron: planet, radius: radius, speed: 0.5 + rng() * 0.5, angle: rng() * Math.PI * 2 });
    }
    grp.userData.atomOrbits = orbits;
  }

  // ---------- Globo terrestre: esfera com meridianos/paralelos + pontos "cidade" ----------
  function buildGlobe(rng, grp, accent, accent2) {
    const r = 2.7;
    const geo = new THREE.SphereGeometry(r, 28, 20);
    grp.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.4 })));
    grp.add(new THREE.Mesh(geo.clone(), makeFresnelMaterial(accent, 0.55, accent2)));

    const eq = new THREE.Mesh(new THREE.TorusGeometry(r, 0.015, 8, 96), new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.6 }));
    eq.rotation.x = Math.PI / 2;
    grp.add(eq);

    const cityCount = 10 + Math.floor(rng() * 6);
    const cities = [];
    const cityGeo = new THREE.BufferGeometry();
    const cityPos = new Float32Array(cityCount * 3);
    for (let i = 0; i < cityCount; i++) {
      const th = rng() * Math.PI * 2;
      const ph = Math.acos(rng() * 2 - 1);
      const p = new THREE.Vector3(r * Math.sin(ph) * Math.cos(th), r * Math.cos(ph), r * Math.sin(ph) * Math.sin(th));
      cityPos[i * 3] = p.x; cityPos[i * 3 + 1] = p.y; cityPos[i * 3 + 2] = p.z;
      cities.push(p);
    }
    cityGeo.setAttribute("position", new THREE.Float32BufferAttribute(cityPos, 3));
    grp.add(new THREE.Points(cityGeo, new THREE.PointsMaterial({ color: accent2, size: 0.16, map: makeGlowTexture(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));

    // Algumas rotas de conex\u00e3o entre "cidades", como linhas de v\u00f4o.
    const arcMat = new THREE.LineBasicMaterial({ color: accent2, transparent: true, opacity: 0.5 });
    for (let i = 0; i < Math.min(6, cities.length - 1); i++) {
      const a = cities[Math.floor(rng() * cities.length)];
      const b = cities[Math.floor(rng() * cities.length)];
      if (a === b) continue;
      const mid = a.clone().add(b).multiplyScalar(0.5).normalize().multiplyScalar(r * 1.35);
      const curve = new THREE.QuadraticBezierCurve3(a, mid, b);
      const pts = curve.getPoints(24);
      grp.add(new THREE.Line(new THREE.BufferGeometry().setFromPoints(pts), arcMat));
    }
  }

  // ---------- Rede neural / c\u00e9rebro estilizado: dois lobos de pontos conectados ----------
  function buildBrain(rng, grp, accent, accent2) {
    const perLobe = 26;
    const points = [];
    for (let side = -1; side <= 1; side += 2) {
      for (let i = 0; i < perLobe; i++) {
        const th = rng() * Math.PI * 2;
        const ph = Math.acos(rng() * 2 - 1);
        const rr = 1.5 + rng() * 0.5;
        points.push(new THREE.Vector3(
          side * 0.55 + Math.sin(ph) * Math.cos(th) * rr * 0.85,
          Math.cos(ph) * rr * 0.75,
          Math.sin(ph) * Math.sin(th) * rr
        ));
      }
    }
    const plainPoints = points.map((p) => ({ x: p.x, y: p.y, z: p.z }));
    const edges = nearestNeighborEdges(plainPoints, 3);

    const lineVerts = [];
    edges.forEach(([i, j]) => {
      lineVerts.push(points[i].x, points[i].y, points[i].z, points[j].x, points[j].y, points[j].z);
    });
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.Float32BufferAttribute(lineVerts, 3));
    grp.add(new THREE.LineSegments(lineGeo, new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: 0.4 })));

    const ptGeo = new THREE.BufferGeometry().setFromPoints(points);
    grp.add(new THREE.Points(ptGeo, new THREE.PointsMaterial({ color: accent2, size: 0.16, map: makeGlowTexture(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));

    const core = new THREE.Mesh(new THREE.IcosahedronGeometry(0.35, 1), new THREE.MeshBasicMaterial({ color: accent2, wireframe: true }));
    grp.add(core);
    grp.userData.heartbeat = core;
  }

  // ---------- Nuvem de part\u00edculas / nebulosa densa ----------
  function buildParticleCloud(rng, grp, accent, accent2) {
    const count = 420;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);
    const cA = new THREE.Color(accent);
    const cB = new THREE.Color(accent2);
    for (let i = 0; i < count; i++) {
      const th = rng() * Math.PI * 2;
      const ph = Math.acos(rng() * 2 - 1);
      const rr = Math.pow(rng(), 0.5) * 3.2 + (rng() - 0.5) * 0.6;
      positions[i * 3] = Math.sin(ph) * Math.cos(th) * rr;
      positions[i * 3 + 1] = Math.cos(ph) * rr * 0.8;
      positions[i * 3 + 2] = Math.sin(ph) * Math.sin(th) * rr;
      const mixed = cA.clone().lerp(cB, rng());
      colors[i * 3] = mixed.r; colors[i * 3 + 1] = mixed.g; colors[i * 3 + 2] = mixed.b;
    }
    const geo = new THREE.BufferGeometry();
    geo.setAttribute("position", new THREE.Float32BufferAttribute(positions, 3));
    geo.setAttribute("color", new THREE.Float32BufferAttribute(colors, 3));
    const mat = new THREE.PointsMaterial({ size: 0.09, map: makeGlowTexture(), vertexColors: true, transparent: true, opacity: 0.85, blending: THREE.AdditiveBlending, depthWrite: false });
    grp.add(new THREE.Points(geo, mat));
  }

  // ---------- Portal: an\u00e9is conc\u00eantricos pulsantes ----------
  function buildPortal(rng, grp, accent, accent2) {
    const ringCount = 4;
    const rings = [];
    for (let i = 0; i < ringCount; i++) {
      const r = 1.1 + i * 0.5;
      const ring = new THREE.Mesh(new THREE.TorusGeometry(r, 0.05 - i * 0.006, 12, 64), new THREE.MeshBasicMaterial({ color: i % 2 === 0 ? accent : accent2, transparent: true, opacity: 0.75 - i * 0.1 }));
      grp.add(ring);
      rings.push(ring);
    }
    const disc = new THREE.Mesh(new THREE.CircleGeometry(1.05, 48), makeFresnelMaterial(accent2, 0.5));
    grp.add(disc);
    grp.userData.pulseRings = rings;
  }

  // ---------- Esfera hologr\u00e1fica "pura": orbe de energia ----------
  function buildEnergySphere(rng, grp, accent, accent2) {
    const r = 2.3;
    const geo = new THREE.IcosahedronGeometry(r, 3);
    grp.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.5 })));
    grp.add(new THREE.Mesh(geo.clone(), makeFresnelMaterial(accent2, 0.65, accent)));
    const orbitCount = 2;
    const orbits = [];
    for (let i = 0; i < orbitCount; i++) {
      const ring = new THREE.Mesh(new THREE.TorusGeometry(r * 1.25, 0.02, 8, 96), new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.5 }));
      ring.rotation.x = rng() * Math.PI;
      ring.rotation.y = rng() * Math.PI;
      grp.add(ring);
      orbits.push({ ring: ring, electron: ring, radius: 0, speed: 0.3 + rng() * 0.3, angle: 0 });
    }
    grp.userData.pulseRings = [];
  }

  // ---------- Gr\u00e1fico 3D de barras ----------
  function buildBarChart3D(rng, grp, accent, accent2) {
    const cols = 6;
    const rows = 6;
    const spacing = 0.85;
    const wireMat = new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.7 });
    const fillMat = new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.16, side: THREE.DoubleSide, depthWrite: false });
    for (let ix = 0; ix < cols; ix++) {
      for (let iz = 0; iz < rows; iz++) {
        const h = 0.3 + rng() * rng() * 3.4;
        const geo = new THREE.BoxGeometry(0.5, h, 0.5);
        const x = (ix - cols / 2 + 0.5) * spacing;
        const z = (iz - rows / 2 + 0.5) * spacing;
        const wire = new THREE.Mesh(geo, wireMat);
        wire.position.set(x, h / 2 - 1.6, z);
        grp.add(wire);
        const fill = new THREE.Mesh(geo, fillMat);
        fill.position.copy(wire.position);
        grp.add(fill);
      }
    }
    const grid = new THREE.GridHelper(cols * spacing * 1.15, cols, accent2, accent);
    grid.material.transparent = true;
    grid.material.opacity = 0.18;
    grid.position.y = -1.6;
    grp.add(grid);
    grp.userData.gridMeshes = [grid];
  }

  // ---------- Texto hologr\u00e1fico / logo 3D (textura de canvas com glow) ----------
  function buildHoloText(label, rng, grp, accent, accent2) {
    const txt = (label || "TRISTAN THORNE").toUpperCase().slice(0, 18);
    const c = document.createElement("canvas");
    c.width = 1024; c.height = 320;
    const ctx = c.getContext("2d");
    ctx.clearRect(0, 0, c.width, c.height);
    ctx.textAlign = "center";
    ctx.textBaseline = "middle";
    ctx.font = "bold 150px 'Segoe UI', Arial, sans-serif";
    ctx.shadowColor = accent2 && accent2.getStyle ? accent2.getStyle() : "#00e5ff";
    ctx.shadowBlur = 40;
    ctx.strokeStyle = accent && accent.getStyle ? accent.getStyle() : "#00e5ff";
    ctx.lineWidth = 3;
    ctx.strokeText(txt, c.width / 2, c.height / 2);
    ctx.fillStyle = "rgba(255,255,255,0.9)";
    ctx.fillText(txt, c.width / 2, c.height / 2);
    const tex = new THREE.CanvasTexture(c);
    const mat = new THREE.MeshBasicMaterial({ map: tex, transparent: true, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide });
    const plane = new THREE.Mesh(new THREE.PlaneGeometry(6.5, 6.5 * (c.height / c.width)), mat);
    grp.add(plane);
    const backPlane = new THREE.Mesh(new THREE.PlaneGeometry(6.5, 6.5 * (c.height / c.width)), new THREE.MeshBasicMaterial({ map: tex, transparent: true, opacity: 0.3, blending: THREE.AdditiveBlending, depthWrite: false, side: THREE.DoubleSide }));
    backPlane.position.z = -0.4;
    backPlane.scale.set(1.08, 1.08, 1);
    grp.add(backPlane);
    const ring = new THREE.Mesh(new THREE.RingGeometry(3.6, 3.68, 64), new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.35, side: THREE.DoubleSide }));
    grp.add(ring);
    grp.userData.pulseRings = [ring];
  }

  function buildObjeto(text, rng, grp, accent, accent2) {
    const t = text.toLowerCase();
    if (/sistema solar|sistema planetario|sistema planet\u00e1rio/.test(t)) return buildSolarSystem(rng, grp, accent, accent2);
    if (/globo|planeta terra|mapa[\s-]mundi|\bterra\b/.test(t)) return buildGlobe(rng, grp, accent, accent2);
    if (/dna|helice|h\u00e9lice|molecula|mol\u00e9cula/.test(t)) return buildHelix(rng, grp, accent, accent2);
    if (/planeta|saturno|anel/.test(t)) return buildPlanet(t, rng, grp, accent, accent2);
    if (/atomo|\u00e1tomo|atom|eletron|el\u00e9tron|nucleo|n\u00facleo/.test(t)) return buildAtomo(rng, grp, accent, accent2);
    if (/cerebro|c\u00e9rebro|brain|mente/.test(t)) return buildBrain(rng, grp, accent, accent2);
    if (/particula|part\u00edcula|nebulosa|nuvem de pontos|poeira c\u00f3smica|poeira cosmica/.test(t)) return buildParticleCloud(rng, grp, accent, accent2);
    if (/portal|stargate|passagem dimensional/.test(t)) return buildPortal(rng, grp, accent, accent2);
    if (/esfera holo|esfera de energia|orbe|globo de luz/.test(t)) return buildEnergySphere(rng, grp, accent, accent2);
    if (/grafico|gr\u00e1fico|barras 3d|estatistica|estat\u00edstica|chart/.test(t)) return buildBarChart3D(rng, grp, accent, accent2);
    if (/texto holo|logo 3d|logotipo/.test(t)) return buildHoloText(text.replace(/texto holo(gr[a\u00e1]fico)?|logo\s*3d|logotipo/gi, "").trim() || text, rng, grp, accent, accent2);
    if (/coracao|cora\u00e7\u00e3o|heart|amor/.test(t)) return buildCoracao(rng, grp, accent, accent2);
    if (/cristal|crystal|gema|diamante/.test(t)) return buildCristal(rng, grp, accent, accent2);
    return buildPolyhedron(rng, grp, accent, accent2);
  }

  function buildRede(rng, grp, accent, accent2) {
    const nodeCount = 16 + Math.floor(rng() * 8);
    const nodes = [];
    for (let i = 0; i < nodeCount; i++) {
      nodes.push(new THREE.Vector3((rng() * 2 - 1) * 3.6, (rng() * 2 - 1) * 2.6, (rng() * 2 - 1) * 3.6));
    }
    const nodeGeo = new THREE.BufferGeometry().setFromPoints(nodes);
    grp.add(new THREE.Points(nodeGeo, new THREE.PointsMaterial({ color: accent2, size: 0.32, map: makeGlowTexture(), transparent: true, blending: THREE.AdditiveBlending, depthWrite: false })));

    const lineVerts = [];
    for (let i = 0; i < nodes.length; i++) {
      const neighbors = nodes
        .map((p, j) => ({ j: j, d: p.distanceTo(nodes[i]) }))
        .filter((o) => o.j !== i)
        .sort((a, b) => a.d - b.d)
        .slice(0, 2);
      neighbors.forEach((nb) => {
        lineVerts.push(nodes[i].x, nodes[i].y, nodes[i].z, nodes[nb.j].x, nodes[nb.j].y, nodes[nb.j].z);
      });
    }
    const lineGeo = new THREE.BufferGeometry();
    lineGeo.setAttribute("position", new THREE.Float32BufferAttribute(lineVerts, 3));
    grp.add(new THREE.LineSegments(lineGeo, new THREE.LineBasicMaterial({ color: accent, transparent: true, opacity: 0.4 })));
  }

  // ---------- Amostra a altura do terreno real num ponto (metros relativos ao centro) ----------
  // Usa a mesma malha de elevação e a mesma convenção de eixos do
  // terreno (ver buildLugarReal) para descobrir em que altura do
  // relevo real um prédio deve "pisar" — com interpolação bilinear
  // entre os 4 pontos da malha mais próximos, pra não ficar em degraus.
  function sampleTerrainHeight(data, dxMeters, dyMeters) {
    const gridSize = data.grid_size;
    const half = data.area_meters / 2;
    const grid = data.elevation_grid;
    const minH = data.elevation_min;
    const maxH = data.elevation_max;
    const range = Math.max(maxH - minH, 1);
    const verticalScale = 6.5; // igual ao usado em buildLugarReal()

    let fx = 0.5 + dxMeters / (2 * half);
    let fy = 0.5 - dyMeters / (2 * half);
    fx = Math.min(Math.max(fx, 0), 1);
    fy = Math.min(Math.max(fy, 0), 1);

    const gx = fx * (gridSize - 1);
    const gy = fy * (gridSize - 1);
    const ix0 = Math.floor(gx);
    const ix1 = Math.min(ix0 + 1, gridSize - 1);
    const iy0 = Math.floor(gy);
    const iy1 = Math.min(iy0 + 1, gridSize - 1);
    const tx = gx - ix0;
    const ty = gy - iy0;

    const h00 = grid[iy0][ix0];
    const h10 = grid[iy0][ix1];
    const h01 = grid[iy1][ix0];
    const h11 = grid[iy1][ix1];
    const hTop = h00 + (h10 - h00) * tx;
    const hBot = h01 + (h11 - h01) * tx;
    const rawH = hTop + (hBot - hTop) * ty;

    let normH = ((rawH - minH) / range) * verticalScale;
    if (data.elevation_degraded) {
      const microRng = seededRandom(data.formatted_address || "lugar");
      const microNoise = makeNoise2D(microRng);
      normH += microNoise(gx * 1.4, gy * 1.4) * 0.55;
    }
    return normH;
  }

  // ---------- Prédios reais extrudados (OpenStreetMap via Overpass API) ----------
  // Ao contrário dos serviços de "3D tiles" fotorrealistas (Google Maps
  // 3D, Cesium ion), que são pagos, isto usa só a pegada no chão e a
  // altura real de cada prédio — dados abertos do OpenStreetMap — para
  // extrudar caixas 3D no lugar certo, no estilo holograma (contorno
  // luminoso + preenchimento bem translúcido), em vez de textura
  // fotorrealista. 100% grátis, sem chave de API nenhuma.
  function addBuildings(data, grp, accent, accent2, worldSize) {
    if (!data.buildings || !data.buildings.length) return;

    // Metros -> unidades do mundo 3D, na mesma escala usada pelo
    // terreno (worldSize unidades cobrem data.area_meters metros).
    const scale = worldSize / data.area_meters;
    // Escala vertical dos prédios: independente do exagero do relevo
    // (verticalScale acima), calibrada só pra prédios ficarem visíveis
    // e proporcionais dentro do holograma sem estourar o tamanho dele.
    const heightScale = 0.07;

    const buildingsGroup = new THREE.Group();
    const wallMat = new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.55 });
    const fillMat = new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.09, side: THREE.DoubleSide, depthWrite: false });

    data.buildings.forEach((b) => {
      const fp = b.footprint;
      if (!fp || fp.length < 3) return;

      const shape = new THREE.Shape();
      fp.forEach((pt, idx) => {
        const sx = pt[0] * scale;
        // Negativo de propósito: THREE.ExtrudeGeometry extrude uma
        // shape 2D (local XY) ao longo de +Z; depois giramos a
        // geometria -90° em X pra deitar essa shape no chão (vira
        // XZ) e a extrusão virar altura (+Y). Essa rotação inverte o
        // sinal do eixo Y da shape, então pré-invertemos aqui pra o
        // prédio cair na mesma posição norte/sul que o terreno.
        const sy = -(pt[1] * scale);
        if (idx === 0) shape.moveTo(sx, sy);
        else shape.lineTo(sx, sy);
      });

      const depth = Math.max(b.height_m * heightScale, 0.12);
      const geo = new THREE.ExtrudeGeometry(shape, { depth, bevelEnabled: false, curveSegments: 1 });
      geo.rotateX(-Math.PI / 2);

      const cx = fp.reduce((s, p) => s + p[0], 0) / fp.length;
      const cy = fp.reduce((s, p) => s + p[1], 0) / fp.length;
      const baseY = sampleTerrainHeight(data, cx, cy);

      const wire = new THREE.Mesh(geo, wallMat);
      wire.position.y = baseY;
      buildingsGroup.add(wire);

      const fill = new THREE.Mesh(geo, fillMat);
      fill.position.y = baseY;
      buildingsGroup.add(fill);
    });

    grp.add(buildingsGroup);
    grp.userData.buildingsGroup = buildingsGroup;
  }

  // ---------- Lugar real (OpenStreetMap: geocoding + elevação + mapa real) ----------
  // Ao contrário de buildMapa() (terreno procedural, "fake"), esta função
  // recebe dado de verdade vindo do backend (services/maps_service.py):
  // uma malha real de altitudes do relevo e um mosaico real de tiles do
  // OpenStreetMap do lugar, e constrói o terreno 3D a partir disso —
  // 100% grátis, sem chave de API nenhuma.
  function buildLugarReal(data, grp, accent, accent2) {
    const gridSize = data.grid_size;
    const worldSize = 22; // tamanho do plano no mundo 3D (independe da escala real em metros)
    const seg = gridSize - 1;
    const geo = new THREE.PlaneGeometry(worldSize, worldSize, seg, seg);
    geo.rotateX(-Math.PI / 2);

    const grid = data.elevation_grid;
    const minH = data.elevation_min;
    const maxH = data.elevation_max;
    const range = Math.max(maxH - minH, 1);
    // Exagero vertical do relevo para o relevo real (que às vezes tem
    // pouca variação, ex: 3 metros numa cidade plana) ficar visível e
    // dramático no holograma, em vez de parecer uma tábua lisa.
    const verticalScale = 6.5;
    // Quando o serviço de elevação cai no modo de emergência (relevo
    // 100% plano — ver services/maps_service.py), o terreno fica uma
    // tábua reta e o holograma parece literalmente um mapa visto de
    // cima. Somamos um micro-relevo procedural (mesmo ruído usado no
    // modo procedural) só pra dar volume/textura 3D visível — nunca
    // deforma o relevo real de verdade, só evita a "tábua lisa".
    const microRng = seededRandom(data.formatted_address || "lugar");
    const microNoise = makeNoise2D(microRng);

    const pos = geo.attributes.position;
    let centerIdx = 0;
    const center = Math.floor(gridSize / 2);
    for (let iy = 0; iy < gridSize; iy++) {
      for (let ix = 0; ix < gridSize; ix++) {
        const i = iy * gridSize + ix;
        const rawH = grid[iy][ix];
        let normH = ((rawH - minH) / range) * verticalScale;
        if (data.elevation_degraded) {
          normH += microNoise(ix * 1.4, iy * 1.4) * 0.55;
        }
        pos.setY(i, normH);
        if (iy === center && ix === center) centerIdx = i;
      }
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();

    // Textura de mapa real do OpenStreetMap — usada com opacidade
    // reduzida e "tingida" pela cor de destaque do holograma, pra ler
    // como uma projeção holográfica translúcida em vez de uma foto de
    // mapa colada numa tábua (o efeito "parece o Google Maps" que
    // estava acontecendo antes).
    const texLoader = new THREE.TextureLoader();
    const satTexture = texLoader.load(data.satellite_image);
    satTexture.colorSpace = THREE.SRGBColorSpace || satTexture.colorSpace;

    const solidMat = new THREE.MeshBasicMaterial({
      map: satTexture,
      color: accent,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0,
      depthWrite: false,
    });
    const solidMesh = new THREE.Mesh(geo, solidMat);
    grp.add(solidMesh);
    grp.userData.fadeInMaterials = [solidMat];
    grp.userData.fadeInTargetOpacity = { material: solidMat, target: 0.55 };

    // Malha wireframe bem mais visível por cima — é ela que carrega a
    // leitura de "relevo 3D real" (picos e vales aparecendo como
    // linhas), em vez de deixar a textura plana dominar a leitura.
    grp.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.75 })));

    const px = pos.getX(centerIdx);
    const py = pos.getY(centerIdx);
    const pz = pos.getZ(centerIdx);

    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.32, 1.4, 12), new THREE.MeshBasicMaterial({ color: accent2 }));
    cone.position.set(px, py + 1.7, pz);
    cone.rotation.x = Math.PI;
    grp.add(cone);

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.5, 0.66, 32),
      new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.7, side: THREE.DoubleSide })
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(px, py + 0.05, pz);
    grp.add(ring);
    grp.userData.pulseRings = [ring];

    const sweep = new THREE.Mesh(
      new THREE.CircleGeometry(worldSize * 0.6, 48, 0, Math.PI / 5),
      new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.14, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    sweep.rotation.x = -Math.PI / 2;
    sweep.position.y = -0.02;
    grp.add(sweep);
    grp.userData.sweep = sweep;

    const helperGrid = new THREE.GridHelper(worldSize * 1.1, gridSize, accent2, accent);
    helperGrid.material.transparent = true;
    helperGrid.material.opacity = 0.15;
    helperGrid.position.y = -0.05;
    grp.add(helperGrid);

    addBuildings(data, grp, accent, accent2, worldSize);
  }

  // ---------- Holograma a partir de uma foto enviada pelo usuário ----------
  // Ao contrário de buildLugarReal() (dado real vindo do backend), aqui
  // TUDO acontece no navegador: lemos os pixels da própria foto (já
  // recortada em um canvas quadrado por generateFromPhoto) e usamos o
  // brilho (luminância) de cada ponto como altura de um relevo 3D —
  // um "mapa de profundidade" simples e honesto (não é reconstrução 3D
  // de verdade, mas dá volume real derivado da própria imagem, não
  // decoração genérica) — com a própria foto projetada como textura
  // holográfica por cima, no mesmo estilo do terreno de lugar real.
  function buildFromPhoto(sourceCanvas, grp, accent, accent2) {
    const gridSize = 48;
    const worldSize = 14;
    const seg = gridSize - 1;
    const geo = new THREE.PlaneGeometry(worldSize, worldSize, seg, seg);
    geo.rotateX(-Math.PI / 2);

    const sampleCanvas = document.createElement("canvas");
    sampleCanvas.width = gridSize;
    sampleCanvas.height = gridSize;
    const sctx = sampleCanvas.getContext("2d");
    sctx.drawImage(sourceCanvas, 0, 0, gridSize, gridSize);
    const imgData = sctx.getImageData(0, 0, gridSize, gridSize).data;

    const pos = geo.attributes.position;
    const verticalScale = 3.2;
    const center = Math.floor(gridSize / 2);
    let centerIdx = 0;
    for (let iy = 0; iy < gridSize; iy++) {
      for (let ix = 0; ix < gridSize; ix++) {
        const i = iy * gridSize + ix;
        const p = (iy * gridSize + ix) * 4;
        const lum = (0.299 * imgData[p] + 0.587 * imgData[p + 1] + 0.114 * imgData[p + 2]) / 255;
        pos.setY(i, lum * verticalScale);
        if (iy === center && ix === center) centerIdx = i;
      }
    }
    pos.needsUpdate = true;
    geo.computeVertexNormals();

    const texture = new THREE.CanvasTexture(sourceCanvas);
    texture.colorSpace = THREE.SRGBColorSpace || texture.colorSpace;

    const solidMat = new THREE.MeshBasicMaterial({
      map: texture,
      color: accent,
      blending: THREE.AdditiveBlending,
      transparent: true,
      opacity: 0,
      depthWrite: false,
    });
    const solidMesh = new THREE.Mesh(geo, solidMat);
    grp.add(solidMesh);
    grp.userData.fadeInMaterials = [solidMat];
    grp.userData.fadeInTargetOpacity = { material: solidMat, target: 0.65 };

    grp.add(new THREE.Mesh(geo, new THREE.MeshBasicMaterial({ color: accent, wireframe: true, transparent: true, opacity: 0.5 })));

    const px = pos.getX(centerIdx);
    const py = pos.getY(centerIdx);
    const pz = pos.getZ(centerIdx);

    const cone = new THREE.Mesh(new THREE.ConeGeometry(0.28, 1.2, 12), new THREE.MeshBasicMaterial({ color: accent2 }));
    cone.position.set(px, py + 1.6, pz);
    cone.rotation.x = Math.PI;
    grp.add(cone);

    const ring = new THREE.Mesh(
      new THREE.RingGeometry(0.42, 0.56, 32),
      new THREE.MeshBasicMaterial({ color: accent2, transparent: true, opacity: 0.7, side: THREE.DoubleSide })
    );
    ring.rotation.x = -Math.PI / 2;
    ring.position.set(px, py + 0.05, pz);
    grp.add(ring);
    grp.userData.pulseRings = [ring];

    const sweep = new THREE.Mesh(
      new THREE.CircleGeometry(worldSize * 0.6, 48, 0, Math.PI / 5),
      new THREE.MeshBasicMaterial({ color: accent, transparent: true, opacity: 0.14, side: THREE.DoubleSide, blending: THREE.AdditiveBlending, depthWrite: false })
    );
    sweep.rotation.x = -Math.PI / 2;
    sweep.position.y = -0.02;
    grp.add(sweep);
    grp.userData.sweep = sweep;

    const helperGrid = new THREE.GridHelper(worldSize * 1.1, Math.floor(gridSize / 2), accent2, accent);
    helperGrid.material.transparent = true;
    helperGrid.material.opacity = 0.12;
    helperGrid.position.y = -0.05;
    grp.add(helperGrid);
    grp.userData.gridMeshes = (grp.userData.gridMeshes || []).concat([helperGrid]);
  }

  // ---------- Carregamento do motor 3D (uma única vez pra página toda) ----------
  let threePromise = null;
  function ensureThree() {
    if (window.THREE) return Promise.resolve();
    if (threePromise) return threePromise;
    threePromise = new Promise((resolve, reject) => {
      const s = document.createElement("script");
      s.src = "https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js";
      s.onload = () => resolve();
      s.onerror = () => {
        threePromise = null;
        reject(new Error("N\u00e3o consegui carregar o motor 3D (verifique a conex\u00e3o com a internet)."));
      };
      document.head.appendChild(s);
    });
    return threePromise;
  }

  // ---------- FASE 2: pós-processamento (bloom real via EffectComposer) ----------
  // Carregado à parte do three.min.js porque o pacote da CDNJS não traz os
  // módulos de exemplo. Se qualquer um desses scripts falhar (rede lenta,
  // CDN fora do ar), postFXReady fica false e o holograma continua
  // funcionando normalmente com renderer.render() direto — nunca quebra
  // por causa do bloom, ele é estritamente um extra visual.
  let postFXPromise = null;
  let postFXReady = false;
  function loadScriptSeq(urls) {
    return urls.reduce(
      (p, url) =>
        p.then(
          () =>
            new Promise((resolve, reject) => {
              const s = document.createElement("script");
              s.src = url;
              s.onload = resolve;
              s.onerror = () => reject(new Error("falha ao carregar " + url));
              document.head.appendChild(s);
            })
        ),
      Promise.resolve()
    );
  }
  function ensurePostFX() {
    if (postFXReady) return Promise.resolve(true);
    if (postFXPromise) return postFXPromise;
    const base = "https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/";
    postFXPromise = loadScriptSeq(
      [
        "postprocessing/EffectComposer.js",
        "postprocessing/RenderPass.js",
        "postprocessing/ShaderPass.js",
        "shaders/CopyShader.js",
        "shaders/LuminosityHighPassShader.js",
        "postprocessing/UnrealBloomPass.js",
      ].map((p) => base + p)
    )
      .then(() => {
        postFXReady = !!(window.THREE && THREE.EffectComposer && THREE.UnrealBloomPass);
        return postFXReady;
      })
      .catch(() => {
        postFXReady = false;
        return false;
      });
    return postFXPromise;
  }

  // Cria (ou recria, se o tamanho mudou) o composer com bloom pro stage
  // atual. Retorna null se pós-processamento não está disponível — quem
  // chama deve continuar usando renderer.render(scene, camera) nesse caso.
  function buildComposer(renderer, scene, camera, w, h) {
    if (!postFXReady) return null;
    try {
      const composer = new THREE.EffectComposer(renderer);
      composer.addPass(new THREE.RenderPass(scene, camera));
      const bloom = new THREE.UnrealBloomPass(new THREE.Vector2(w, h), 0.85, 0.55, 0.15);
      // strength moderado, radius médio, threshold baixo: só o que já é
      // bem brilhante (as próprias cores emissivas do holograma) ganha
      // halo — não estoura a cena inteira em neon (regra do usuário).
      composer.addPass(bloom);
      composer.__bloom = bloom;
      // Passe final sutil: leve varredura (scanlines) + ruído, o "chassis"
      // óptico de uma projeção holográfica — propositalmente fraco pra não
      // virar filtro de neon (uOpacity baixo).
      // Além da varredura já existente, soma aberração cromática bem sutil
      // nas bordas (separação R/B radial) e um vinheta leve — dois efeitos
      // clássicos de "projeção óptica imperfeita" que ajudam a vender a
      // ilusão de holograma real sem qualquer custo de performance extra
      // (mesmo tDiffuse, um passe só). Continua fraco de propósito.
      const scanlineShader = {
        uniforms: { tDiffuse: { value: null }, uTime: { value: 0 }, uOpacity: { value: 0.05 } },
        vertexShader: "varying vec2 vUv; void main(){ vUv = uv; gl_Position = projectionMatrix * modelViewMatrix * vec4(position,1.0); }",
        fragmentShader:
          "uniform sampler2D tDiffuse; uniform float uTime; uniform float uOpacity; varying vec2 vUv;" +
          "float rand(vec2 co){ return fract(sin(dot(co.xy, vec2(12.9898,78.233))) * 43758.5453); }" +
          "void main(){" +
          "vec2 center = vUv - 0.5; float dist = length(center);" +
          "vec2 caOffset = center * dist * 0.0035;" +
          "float r = texture2D(tDiffuse, vUv + caOffset).r;" +
          "float g = texture2D(tDiffuse, vUv).g;" +
          "float b = texture2D(tDiffuse, vUv - caOffset).b;" +
          "vec4 c = vec4(r, g, b, texture2D(tDiffuse, vUv).a);" +
          "float scan = sin((vUv.y * 800.0) - uTime * 6.0) * 0.5 + 0.5;" +
          "float noise = rand(vUv + fract(uTime)) * 0.06;" +
          "c.rgb += (scan * 0.04 + noise) * uOpacity * 6.0;" +
          "float vig = smoothstep(0.85, 0.35, dist);" +
          "c.rgb *= mix(0.85, 1.0, vig);" +
          "gl_FragColor = c; }",
      };
      const scanPass = new THREE.ShaderPass(scanlineShader);
      scanPass.renderToScreen = true;
      composer.addPass(scanPass);
      composer.__scanPass = scanPass;
      return composer;
    } catch (e) {
      postFXReady = false;
      return null;
    }
  }

  // ---------- Geometria e proje\u00e7\u00e3o do modo compat\u00edvel (sem WebGL) ----------
  // Um "renderizador 3D" bem simples feito s\u00f3 com matem\u00e1tica e canvas 2D:
  // rotaciona pontos no espa\u00e7o (ioga/pitch) e projeta em perspectiva na
  // tela. N\u00e3o tenta imitar 1:1 o visual do Three.js, s\u00f3 garantir que o
  // holograma sempre apare\u00e7a e continue interativo mesmo sem WebGL.
  function projectPoint(p, rotY, rotX, dist, fl, cx, cy) {
    const cosY = Math.cos(rotY), sinY = Math.sin(rotY);
    const x1 = p.x * cosY + p.z * sinY;
    const z1 = -p.x * sinY + p.z * cosY;
    const cosX = Math.cos(rotX), sinX = Math.sin(rotX);
    const y2 = p.y * cosX - z1 * sinX;
    const z2 = p.y * sinX + z1 * cosX;
    const denom = dist - z2;
    const factor = fl / (denom > 0.5 ? denom : 0.5);
    return { x: cx + x1 * factor, y: cy - y2 * factor, z: z2 };
  }

  function nearestNeighborEdges(points, k) {
    const edges = [];
    const seen = new Set();
    for (let i = 0; i < points.length; i++) {
      const dists = [];
      for (let j = 0; j < points.length; j++) {
        if (j === i) continue;
        const dx = points[i].x - points[j].x, dy = points[i].y - points[j].y, dz = points[i].z - points[j].z;
        dists.push({ j: j, d: dx * dx + dy * dy + dz * dz });
      }
      dists.sort((a, b) => a.d - b.d);
      dists.slice(0, k).forEach((o) => {
        const key = i < o.j ? i + "-" + o.j : o.j + "-" + i;
        if (!seen.has(key)) {
          seen.add(key);
          edges.push([i, o.j]);
        }
      });
    }
    return edges;
  }

  function makeFallbackSphere(rng, count) {
    const radius = 4.3;
    const points = [];
    const offset = 2 / count;
    const increment = Math.PI * (3 - Math.sqrt(5));
    for (let i = 0; i < count; i++) {
      const y = i * offset - 1 + offset / 2;
      const r = Math.sqrt(Math.max(0, 1 - y * y));
      const phi = i * increment + rng() * 0.15;
      points.push({ x: Math.cos(phi) * r * radius, y: y * radius, z: Math.sin(phi) * r * radius });
    }
    return { points: points, edges: nearestNeighborEdges(points, 3) };
  }

  function makeFallbackNetwork(rng, count) {
    const points = [];
    for (let i = 0; i < count; i++) {
      points.push({ x: (rng() * 2 - 1) * 4.4, y: (rng() * 2 - 1) * 3.2, z: (rng() * 2 - 1) * 4.4 });
    }
    return { points: points, edges: nearestNeighborEdges(points, 2) };
  }

  function makeFallbackTerrain(rng, seg) {
    const noise = makeNoise2D(rng);
    const size = 8.6;
    const points = [];
    const idx = (ix, iy) => iy * (seg + 1) + ix;
    for (let iy = 0; iy <= seg; iy++) {
      for (let ix = 0; ix <= seg; ix++) {
        const x = (ix / seg - 0.5) * size;
        const z = (iy / seg - 0.5) * size;
        const hgt = noise(x, z) * 1.9 + noise(x * 2.3, z * 2.3) * 0.7;
        points.push({ x: x, y: hgt, z: z });
      }
    }
    const edges = [];
    for (let iy = 0; iy <= seg; iy++) {
      for (let ix = 0; ix <= seg; ix++) {
        if (ix < seg) edges.push([idx(ix, iy), idx(ix + 1, iy)]);
        if (iy < seg) edges.push([idx(ix, iy), idx(ix, iy + 1)]);
      }
    }
    return { points: points, edges: edges };
  }

  function makeFallbackTerrainFromElevation(data) {
    const gridSize = data.grid_size;
    const grid = data.elevation_grid;
    const minH = data.elevation_min;
    const maxH = data.elevation_max;
    const range = Math.max(maxH - minH, 1);
    const size = 8.6;
    const seg = gridSize - 1;
    const points = [];
    const idx = (ix, iy) => iy * gridSize + ix;
    for (let iy = 0; iy < gridSize; iy++) {
      for (let ix = 0; ix < gridSize; ix++) {
        const x = (ix / seg - 0.5) * size;
        const z = (iy / seg - 0.5) * size;
        const hgt = ((grid[iy][ix] - minH) / range) * 2.6;
        points.push({ x: x, y: hgt, z: z });
      }
    }
    const edges = [];
    for (let iy = 0; iy < gridSize; iy++) {
      for (let ix = 0; ix < gridSize; ix++) {
        if (ix < seg) edges.push([idx(ix, iy), idx(ix + 1, iy)]);
        if (iy < seg) edges.push([idx(ix, iy), idx(ix, iy + 1)]);
      }
    }
    return { points: points, edges: edges };
  }

  // ---------- Um "widget" = uma instância independente ----------
  function createHologramWidget(root) {
    const els = {
      input: root.querySelector('[data-holo="input"]'),
      type: root.querySelector('[data-holo="type"]'),
      open: root.querySelector('[data-holo="open"]'),
      close: root.querySelector('[data-holo="close"]'),
      result: root.querySelector('[data-holo="result"]'),
      stage: root.querySelector('[data-holo="stage"]'),
      canvas: root.querySelector('[data-holo="canvas"]'),
      label: root.querySelector('[data-holo="label"]'),
      realInput: root.querySelector('[data-holo="real-input"]'),
      realOpen: root.querySelector('[data-holo="real-open"]'),
      photoInput: root.querySelector('[data-holo="photo-input"]'),
      photoOpen: root.querySelector('[data-holo="photo-open"]'),
    };
    if (!els.stage || !els.canvas) return null;

    let renderer = null;
    let scene = null;
    let camera = null;
    let group = null;
    let composer = null;
    let animId = null;

    // ---------- Modo compat\u00edvel (sem WebGL) ----------
    // Alguns aparelhos/navegadores n\u00e3o conseguem criar um contexto WebGL
    // (GPU bloqueada, acelera\u00e7\u00e3o 3D desligada etc). Nesses casos, em vez
    // de mostrar s\u00f3 uma mensagem de erro, desenhamos o holograma com
    // canvas 2D puro (proje\u00e7\u00e3o 3D manual) — continua girando, reagindo
    // ao arraste e ao zoom normalmente.
    let usingFallback2D = false;
    let ctx2d = null;
    let fbShape = null;
    let fbLastT = performance.now();

    // Recria o campo de part\u00edculas ambiente com a densidade/cores atuais.
    // Precisa ser fun\u00e7\u00e3o \u00e0 parte (em vez de s\u00f3 rodar uma vez no boot da
    // cena) porque o slider de "densidade de part\u00edculas" e as trocas de
    // cor do painel de controles chamam isto de novo sem recriar a cena
    // inteira, evitando vazamento de mem\u00f3ria a cada regenera\u00e7\u00e3o.
    function rebuildAmbientParticles(accentHex, accent2Hex) {
      if (!scene) return;
      if (ambientParticlesRef) {
        scene.remove(ambientParticlesRef);
        if (ambientParticlesRef.geometry) ambientParticlesRef.geometry.dispose();
        if (ambientParticlesRef.material) {
          if (ambientParticlesRef.material.map) ambientParticlesRef.material.map.dispose();
          ambientParticlesRef.material.dispose();
        }
        ambientParticlesRef = null;
      }
      ambientParticlesRef = addAmbientParticles(scene, accentHex, accent2Hex, settings.particleDensity);
      ambientParticlesRef.visible = settings.showAmbient;
    }

    let isDragging = false;
    let prevX = 0;
    let prevY = 0;
    let rotY = 0.6;
    let rotX = 0.25;
    let autoRotate = true;
    let resumeTimer = null;
    let pinchDist = null;

    // ---------- FASE 3: pan, inércia e seleção ----------
    // panX/panY deslocam o grupo no plano da tela (não a câmera, pra não
    // atrapalhar o autoRotate/entrada). velRotY/velRotX guardam a
    // velocidade do último arraste pra continuar girando um pouco depois
    // de soltar (inércia), com atrito (INERTIA_DAMPING) até parar.
    let panX = 0;
    let panY = 0;
    let velRotY = 0;
    let velRotX = 0;
    const INERTIA_DAMPING = 0.92;
    const INERTIA_MIN = 0.0004;
    let isPanning = false; // botão direito (desktop) ou 2 dedos junto com o pinch (mobile)
    let midX = 0;
    let midY = 0;
    let downX = 0;
    let downY = 0;
    let downWasDrag = false;
    const CLICK_DRAG_THRESHOLD = 6; // px — abaixo disso, conta como clique/seleção, não arraste
    let lastClickTime = 0;
    let raycaster = null;
    let selectedObject = null;
    function touchMid(e) {
      const t0 = e.touches[0], t1 = e.touches[1];
      return { x: (t0.clientX + t1.clientX) / 2, y: (t0.clientY + t1.clientY) / 2 };
    }
    // Dispara um evento de fora pra quem quiser reagir (Jarvis, telemetria
    // etc) sem acoplar hologram.js a mais nada.
    function emitHoloEvent(name, detail) {
      window.dispatchEvent(new CustomEvent(name, { detail: detail || {} }));
    }
    function pickAt(clientX, clientY) {
      if (!group || !camera || !els.canvas) return null;
      if (!raycaster) raycaster = new THREE.Raycaster();
      const rect = els.canvas.getBoundingClientRect();
      const ndc = new THREE.Vector2(
        ((clientX - rect.left) / rect.width) * 2 - 1,
        -((clientY - rect.top) / rect.height) * 2 + 1
      );
      raycaster.setFromCamera(ndc, camera);
      const hits = raycaster.intersectObjects(group.children, true);
      return hits.length ? hits[0] : null;
    }
    function clearSelection() {
      if (selectedObject && selectedObject.material && selectedObject.userData.__baseEmissive !== undefined) {
        if ("emissiveIntensity" in selectedObject.material) {
          selectedObject.material.emissiveIntensity = selectedObject.userData.__baseEmissive;
        }
      }
      selectedObject = null;
    }
    function selectAt(clientX, clientY) {
      const hit = pickAt(clientX, clientY);
      clearSelection();
      if (!hit) {
        emitHoloEvent("holo:deselect", {});
        return;
      }
      selectedObject = hit.object;
      if (selectedObject.material && "emissiveIntensity" in selectedObject.material) {
        selectedObject.userData.__baseEmissive = selectedObject.material.emissiveIntensity || 0;
        selectedObject.material.emissiveIntensity = Math.max(1.4, selectedObject.userData.__baseEmissive * 1.8);
      }
      emitHoloEvent("holo:select", {
        name: selectedObject.name || lastType || "objeto",
        point: hit.point ? { x: hit.point.x, y: hit.point.y, z: hit.point.z } : null,
      });
    }

    // ---------- Controles do usu\u00e1rio (pain\u00e9is de Objeto/C\u00e2mera/Visual/Anima\u00e7\u00e3o/Cor) ----------
    // Tudo aqui \u00e9 lido de novo em cada _bootStage()/generate(), ent\u00e3o mudar
    // uma cor ou a densidade de part\u00edculas regera o holograma atual com o
    // texto/tipo que j\u00e1 estava na tela (ver setColors/setParticleDensity).
    const settings = {
      speed: 1,
      scale: 1,
      autoRotate: true,
      particleDensity: 1,
      showGrid: true,
      showAmbient: true,
      accentOverride: null,
      accent2Override: null,
      performanceTier: "auto",
    };
    let lastText = "";
    let lastType = "auto";
    let ambientParticlesRef = null;

    // ---------- ITEM 28 do briefing: níveis de performance ----------
    // "auto" escolhe um nível uma única vez (no boot) a partir de sinais
    // reais e confiáveis do navegador — não medimos FPS pra decidir o
    // nível porque isso oscilaria demais em telas fracas. Depois disso o
    // usuário pode forçar outro nível a qualquer momento.
    const PERF_TIERS = {
      low: { particleMul: 0.35, pixelRatioMax: 1, postFX: false },
      medium: { particleMul: 0.7, pixelRatioMax: 1.5, postFX: false },
      high: { particleMul: 1, pixelRatioMax: 2, postFX: true },
      ultra: { particleMul: 1.6, pixelRatioMax: 2, postFX: true },
    };
    let resolvedTier = "high";
    function detectAutoTier() {
      const cores = navigator.hardwareConcurrency || 4;
      const mem = navigator.deviceMemory || 4; // nem todo navegador expõe isso
      const isMobile = /Android|iPhone|iPad|iPod/i.test(navigator.userAgent || "");
      if (isMobile && (cores <= 4 || mem <= 4)) return "low";
      if (isMobile) return "medium";
      if (cores <= 4) return "medium";
      if (cores >= 8 && mem >= 8) return "ultra";
      return "high";
    }
    function applyPerformanceTier(tier) {
      const chosen = tier === "auto" ? detectAutoTier() : tier;
      resolvedTier = PERF_TIERS[chosen] ? chosen : "high";
      settings.performanceTier = tier || "auto";
      const cfg = PERF_TIERS[resolvedTier];
      if (renderer) renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, cfg.pixelRatioMax));
      // Densidade de partículas é settings.particleDensity (0 a ~2, controlado
      // pelo usuário) multiplicado pelo fator do tier — assim os dois
      // controles convivem sem se sobrescrever.
      const rootStyles = getComputedStyle(document.documentElement);
      const accentHex = settings.accentOverride || (rootStyles.getPropertyValue("--accent") || "#00e5ff").trim();
      const accent2Hex = settings.accent2Override || (rootStyles.getPropertyValue("--accent2") || "#b026ff").trim();
      if (scene) rebuildAmbientParticles(accentHex, accent2Hex);
      if (!cfg.postFX && composer) {
        composer = null; // volta a desenhar direto (ver animate()); nunca deixa a tela preta
      } else if (cfg.postFX && !composer && scene && camera && renderer) {
        ensurePostFX().then((ok) => {
          if (ok && resolvedTier === chosen && PERF_TIERS[resolvedTier].postFX) {
            composer = buildComposer(renderer, scene, camera, els.canvas.clientWidth || 320, els.canvas.clientHeight || 340);
          }
        });
      }
      return resolvedTier;
    }
    function setPerformanceTier(tier) { return applyPerformanceTier(tier); }
    function getPerformanceTier() { return { requested: settings.performanceTier, resolved: resolvedTier }; }

    // ---------- ITEM 27 do briefing: telemetria ----------
    // Só expõe números que dá pra obter de forma confiável do navegador
    // (nada de "GPU" real, "memória" exata etc — ver aviso no próprio
    // briefing). FPS é uma média móvel curta calculada dentro do
    // próprio animate(), não uma estimativa.
    let fpsEmaValue = 0;
    function sampleFPS(dt) {
      if (dt <= 0) return;
      const instant = 1 / dt;
      fpsEmaValue = fpsEmaValue === 0 ? instant : fpsEmaValue * 0.9 + instant * 0.1;
    }
    function countParticles() {
      let total = 0;
      if (ambientParticlesRef && ambientParticlesRef.geometry && ambientParticlesRef.geometry.attributes.position) {
        total += ambientParticlesRef.geometry.attributes.position.count;
      }
      if (group && group.traverse) {
        group.traverse((obj) => {
          if (obj.isPoints && obj !== ambientParticlesRef && obj.geometry && obj.geometry.attributes.position) {
            total += obj.geometry.attributes.position.count;
          }
        });
      }
      return total;
    }
    function countObjects() {
      let total = 0;
      if (group && group.traverse) group.traverse(() => { total += 1; });
      return total;
    }
    function getTelemetry() {
      return {
        active: isActive(),
        webgl: !usingFallback2D,
        fps: Math.round(fpsEmaValue),
        objects: countObjects(),
        particles: countParticles(),
        postFX: !!composer,
        performanceTier: getPerformanceTier(),
        currentType: lastType,
        currentText: lastText,
      };
    }

    // ---------- "Vida própria": o holograma percebe a tela ----------
    // Além de arrastar o holograma diretamente, ele reage a QUALQUER
    // movimento do mouse pela tela do computador (como se estivesse
    // "olhando" para o cursor, igual um holograma de verdade) e também
    // pisca/reajusta quando a janela é redimensionada ou rolada — dando
    // a sensação de que ele está de fato ligado ao que acontece na tela.
    let liveTiltX = 0;
    let liveTiltY = 0;
    let liveTargetX = 0;
    let liveTargetY = 0;
    let screenPulse = 0;

    // ---------- "Entrada" do lugar real: materializa em vez de já ----------
    // aparecer pronto — dá a sensação de "ver ele entrar" no holograma.
    let entranceActive = false;
    let entranceStart = 0;
    const ENTRANCE_MS = 1500;

    function onScreenPointerMove(e) {
      if (isDragging) return;
      const p = currentPointer(e);
      const nx = (p.x / (window.innerWidth || 1)) * 2 - 1; // -1..1
      const ny = (p.y / (window.innerHeight || 1)) * 2 - 1; // -1..1
      liveTargetY = nx * 0.35;
      liveTargetX = -ny * 0.22;
    }
    function onScreenReact() {
      // Redimensionar/rolar a tela do computador dá um "pulso" visível
      // no holograma, como se ele tivesse notado a mudança.
      screenPulse = 1;
    }
    window.addEventListener("mousemove", onScreenPointerMove, { passive: true });
    window.addEventListener("touchmove", onScreenPointerMove, { passive: true });
    window.addEventListener("resize", onScreenReact);
    window.addEventListener("scroll", onScreenReact, { passive: true });

    // ---------- Limpa s\u00f3 o CONTE\u00daDO do holograma anterior ----------
    // Importante: isto NUNCA destr\u00f3i o renderer/contexto em si (ver
    // coment\u00e1rio em _bootStage() abaixo sobre por que recriar o
    // contexto a cada holograma era a causa do bug "funciona uma vez e
    // depois quebra").
    function disposeSceneContents() {
      if (animId) cancelAnimationFrame(animId);
      animId = null;
      if (usingFallback2D) {
        fbShape = null;
        if (ctx2d) ctx2d.clearRect(0, 0, els.canvas.clientWidth || 320, els.canvas.clientHeight || 340);
        return;
      }
      if (group) {
        while (group.children.length) {
          const obj = group.children.pop();
          group.remove(obj);
          if (obj.geometry) obj.geometry.dispose();
          if (obj.material) {
            const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
            mats.forEach((m) => {
              if (m.map) m.map.dispose();
              m.dispose();
            });
          }
        }
        group.userData = {};
      }
    }

    function currentPointer(e) {
      if (e.touches && e.touches.length) return { x: e.touches[0].clientX, y: e.touches[0].clientY };
      return { x: e.clientX, y: e.clientY };
    }
    function touchDistance(e) {
      const t0 = e.touches[0], t1 = e.touches[1];
      const dx = t0.clientX - t1.clientX;
      const dy = t0.clientY - t1.clientY;
      return Math.sqrt(dx * dx + dy * dy);
    }
    function onPointerDown(e) {
      if (!group) return;
      // Dois dedos = pinça (zoom) + arraste do par (pan) ao mesmo tempo —
      // são duas medidas independentes do mesmo gesto (distância entre os
      // dedos vs. deslocamento do ponto médio), então não brigam entre si.
      if (e.touches && e.touches.length === 2) {
        isDragging = false;
        isPanning = true;
        pinchDist = touchDistance(e);
        const mid = touchMid(e);
        midX = mid.x;
        midY = mid.y;
        velRotY = 0;
        velRotX = 0;
        autoRotate = false;
        clearTimeout(resumeTimer);
        return;
      }
      // Botão direito do mouse = pan (configurável); botão esquerdo/touch = rotacionar.
      isPanning = !!(e.button === 2);
      isDragging = true;
      downWasDrag = false;
      autoRotate = false;
      velRotY = 0;
      velRotX = 0;
      clearTimeout(resumeTimer);
      const p = currentPointer(e);
      prevX = p.x;
      prevY = p.y;
      downX = p.x;
      downY = p.y;
    }
    function onPointerMove(e) {
      if (!group) return;
      if (e.touches && e.touches.length === 2) {
        const d = touchDistance(e);
        if (pinchDist != null && camera) {
          const delta = pinchDist - d;
          camera.position.z = Math.max(2.5, Math.min(24, camera.position.z + delta * 0.025));
        }
        pinchDist = d;
        const mid = touchMid(e);
        const mdx = mid.x - midX;
        const mdy = mid.y - midY;
        midX = mid.x;
        midY = mid.y;
        panX += mdx * 0.01;
        panY -= mdy * 0.01;
        return;
      }
      if (!isDragging) return;
      const p = currentPointer(e);
      const dx = p.x - prevX;
      const dy = p.y - prevY;
      prevX = p.x;
      prevY = p.y;
      if (Math.abs(p.x - downX) > CLICK_DRAG_THRESHOLD || Math.abs(p.y - downY) > CLICK_DRAG_THRESHOLD) {
        downWasDrag = true;
      }
      if (isPanning) {
        panX += dx * 0.01;
        panY -= dy * 0.01;
        return;
      }
      rotY += dx * 0.008;
      rotX = Math.max(-1.2, Math.min(1.2, rotX + dy * 0.008));
      // Guarda a velocidade do último trecho de arraste pra inércia ao soltar.
      velRotY = dx * 0.008;
      velRotX = dy * 0.008;
    }
    function onPointerUp(e) {
      const wasTouch = e.changedTouches && e.changedTouches.length;
      if (e.touches && e.touches.length > 0) return; // ainda tem dedo na tela
      // Clique/toque sem arraste relevante = seleção; sem soltar o dedo já
      // tratado acima quando ainda há outro dedo na tela.
      if (isDragging && !isPanning && !downWasDrag) {
        const p = wasTouch ? { x: e.changedTouches[0].clientX, y: e.changedTouches[0].clientY } : { x: e.clientX, y: e.clientY };
        const now = performance.now ? performance.now() : Date.now();
        if (now - lastClickTime < 320) {
          // duplo clique/duplo toque: recentra a câmera e o holograma.
          rotY = 0.6;
          rotX = 0.25;
          panX = 0;
          panY = 0;
          velRotY = 0;
          velRotX = 0;
          if (camera) camera.position.z = 9;
          emitHoloEvent("holo:reset-view", {});
          lastClickTime = 0;
        } else {
          selectAt(p.x, p.y);
          lastClickTime = now;
        }
      }
      pinchDist = null;
      // ITEM 2 do briefing: InputManager normaliza isto em ROTATE_HOLOGRAM/PAN_HOLOGRAM
      if (downWasDrag) emitHoloEvent(isPanning ? "holo:pan" : "holo:rotate", { rotY: rotY, rotX: rotX, panX: panX, panY: panY });
      isDragging = false;
      isPanning = false;
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(() => {
        autoRotate = true;
      }, 1400);
    }
    function onWheel(e) {
      if (!camera) return;
      e.preventDefault();
      camera.position.z = Math.max(2.5, Math.min(24, camera.position.z + e.deltaY * 0.01));
      emitHoloEvent("holo:zoom", { deltaY: e.deltaY, z: camera.position.z }); // ITEM 2: ZOOM_HOLOGRAM
    }
    function onResize() {
      const w = els.canvas.clientWidth || 320;
      const h = els.canvas.clientHeight || 340;
      if (w === 0 || h === 0) return;
      if (usingFallback2D) {
        const dpr = Math.min(window.devicePixelRatio || 1, 2);
        els.canvas.width = w * dpr;
        els.canvas.height = h * dpr;
        if (ctx2d) ctx2d.setTransform(dpr, 0, 0, dpr, 0, 0);
        return;
      }
      if (!renderer || !camera) return;
      renderer.setSize(w, h, false);
      camera.aspect = w / h;
      camera.updateProjectionMatrix();
      if (composer) composer.setSize(w, h);
    }

    els.canvas.addEventListener("mousedown", onPointerDown);
    els.canvas.addEventListener("touchstart", onPointerDown, { passive: true });
    els.canvas.addEventListener("wheel", onWheel, { passive: false });
    // Botão direito = pan em vez de abrir o menu de contexto do navegador.
    els.canvas.addEventListener("contextmenu", (e) => e.preventDefault());
    window.addEventListener("mousemove", onPointerMove);
    window.addEventListener("mouseup", onPointerUp);
    window.addEventListener("touchmove", onPointerMove, { passive: true });
    window.addEventListener("touchend", onPointerUp);
    window.addEventListener("resize", onResize);

    // ---------- Comandos externos (voz/Jarvis/gestos de mão) ----------
    // Qualquer parte do sistema pode pedir uma rotação/zoom/reset sem
    // conhecer a implementação interna, disparando um CustomEvent global.
    // Isso é o mesmo "barramento" usado pelo controle por gestos (FASE 4).
    // applyDelta() é o único ponto de entrada pra controle externo do
    // holograma (gestos de mão, comandos de voz do Jarvis, telemetria).
    // Nada fora daqui mexe em rotY/rotX/panX/panY/camera diretamente.
    function applyDelta(dRotY, dRotX, dZoom, dPanX, dPanY) {
      if (!group) return;
      if (dRotY) { rotY += dRotY; velRotY = dRotY * 0.4; }
      if (dRotX) { rotX = Math.max(-1.2, Math.min(1.2, rotX + dRotX)); velRotX = dRotX * 0.4; }
      if (dZoom && camera) camera.position.z = Math.max(2.5, Math.min(24, camera.position.z + dZoom));
      if (dPanX) panX += dPanX;
      if (dPanY) panY += dPanY;
      autoRotate = false;
      clearTimeout(resumeTimer);
      resumeTimer = setTimeout(() => { autoRotate = true; }, 1400);
    }
    function resetView() {
      rotY = 0.6; rotX = 0.25; panX = 0; panY = 0; velRotY = 0; velRotX = 0;
      if (camera) camera.position.z = 9;
    }
    els.canvas.__holoApplyDelta = applyDelta;
    els.canvas.__holoReset = resetView;

    // ---------- Micro-glitch peri\u00f3dico ----------
    // De vez em quando (n\u00e3o sempre), um tremor r\u00e1pido de posi\u00e7\u00e3o +
    // brilho no est\u00e1gio inteiro \u2014 puramente visual/CSS (ver
    // .holo-glitch em style.css) \u2014 pra parecer uma proje\u00e7\u00e3o de luz de
    // verdade "estabilizando" de vez em quando, em vez de uma imagem
    // 3D perfeitamente est\u00e1vel demais pra ser um holograma.
    setInterval(() => {
      if (els.stage.style.display === "none") return;
      if (Math.random() < 0.22) {
        els.stage.classList.add("holo-glitch");
        setTimeout(() => els.stage.classList.remove("holo-glitch"), 120 + Math.random() * 140);
      }
    }, 2600);

    // ---------- Prepara renderer/scene/camera/group ----------
    // Compartilhado por generate() (procedural) e generateRealPlace()
    // (lugar real via OpenStreetMap) para não duplicar a mesma lógica de
    // boot do Three.js duas vezes.
    async function _bootStage() {
      if (els.result) els.result.textContent = "";
      els.stage.style.display = "block";

      const rootStyles = getComputedStyle(document.documentElement);
      const accentHex = settings.accentOverride || (rootStyles.getPropertyValue("--accent") || "#00e5ff").trim() || "#00e5ff";
      const accent2Hex = settings.accent2Override || (rootStyles.getPropertyValue("--accent2") || "#b026ff").trim() || "#b026ff";

      // Brilho (bloom) do canvas é feito em CSS (drop-shadow), porque é
      // de graça em GPU e não depende de bibliotecas extras de
      // pós-processamento do Three.js. Só precisa saber a cor certa —
      // por isso ela é publicada aqui como variável CSS a cada geração.
      els.stage.style.setProperty("--holo-glow-color", accentHex);
      els.stage.style.setProperty("--holo-glow-color2", accent2Hex);

      // ---------- J\u00e1 tem um motor pronto? Reaproveita ----------
      // Bug corrigido aqui: antes, cada holograma novo destru\u00eda o
      // renderer (forceContextLoss) e criava um <canvas> WebGL do zero.
      // Isso é fr\u00e1gil em notebooks fracos (o 2\u00ba/3\u00ba contexto WebGL no
      // mesmo <canvas> pode falhar mesmo quando o 1\u00ba funcionou) — e pior:
      // uma vez que o navegador vincula aquele <canvas> ao modo "webgl",
      // ele NUNCA MAIS aceita um contexto "2d" nele, ent\u00e3o se o WebGL
      // falhasse na 2\u00aa vez, nem o modo compat\u00edvel conseguia entrar (era
      // exatamente o "funciona a primeira vez, quebra na segunda").
      // Agora o motor (WebGL real ou modo 2D) \u00e9 criado uma \u00fanica vez por
      // widget e reaproveitado — s\u00f3 o CONTE\u00daDO do holograma \u00e9 trocado.
      if (usingFallback2D && ctx2d) {
        disposeSceneContents();
        onResize();
        return { accent: accentHex, accent2: accent2Hex, fallback: true };
      }
      if (renderer && scene && camera) {
        disposeSceneContents();
        onResize();
        return { accent: new THREE.Color(accentHex), accent2: new THREE.Color(accent2Hex) };
      }

      els.stage.classList.add("holo-loading");
      try {
        await ensureThree();
      } catch (e) {
        els.stage.classList.remove("holo-loading");
        els.stage.style.display = "none";
        if (els.result) els.result.textContent = "\u274c " + e.message;
        return null;
      }
      els.stage.classList.remove("holo-loading");

      const w = els.canvas.clientWidth || 320;
      const h = els.canvas.clientHeight || 340;

      // Tenta o jeito normal e, se falhar, tenta de novo com op\u00e7\u00f5es bem
      // mais permissivas (sem antialias, sem exigir GPU "de verdade") —
      // isso sozinho j\u00e1 resolve boa parte dos notebooks fracos/GPU
      // bloqueada que antes ca\u00edam direto no erro de "sem WebGL".
      try {
        renderer = new THREE.WebGLRenderer({ canvas: els.canvas, antialias: true, alpha: true });
      } catch (e) {
        try {
          renderer = new THREE.WebGLRenderer({
            canvas: els.canvas,
            antialias: false,
            alpha: true,
            powerPreference: "default",
            failIfMajorPerformanceCaveat: false,
          });
        } catch (e2) {
          renderer = null;
        }
      }

      if (!renderer) {
        // ---------- Sem WebGL de jeito nenhum: modo compat\u00edvel em canvas 2D ----------
        ctx2d = els.canvas.getContext("2d");
        if (!ctx2d) {
          if (els.result) els.result.textContent = "\u274c Seu navegador n\u00e3o consegue projetar o holograma (sem WebGL e sem canvas 2D).";
          els.stage.style.display = "none";
          return null;
        }
        usingFallback2D = true;
        group = {}; // sentinela: mant\u00e9m arraste/zoom/rea\u00e7\u00e3o ao mouse ativos
        camera = { position: { z: 13 } };
        scene = null;
        onResize();
        return { accent: accentHex, accent2: accent2Hex, fallback: true };
      }

      usingFallback2D = false;
      resolvedTier = settings.performanceTier === "auto" ? detectAutoTier() : (PERF_TIERS[settings.performanceTier] ? settings.performanceTier : "high");
      renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, PERF_TIERS[resolvedTier].pixelRatioMax));
      renderer.setSize(w, h, false);
      // Tone mapping filmico: sem isso, tudo que usa AdditiveBlending
      // (a imensa maioria dos materiais do holograma) satura em branco
      // puro rapidinho. Com ele, o brilho "respira" de um jeito mais
      // parecido com uma câmera captando uma luz forte de verdade — e
      // dá um ponto único (toneMappingExposure) pra fazer a cena inteira
      // "respirar" no animate(), sem precisar tocar em cada material.
      if ("toneMapping" in renderer) {
        renderer.toneMapping = THREE.ReinhardToneMapping;
        renderer.toneMappingExposure = 1.15;
      }

      scene = new THREE.Scene();
      // Névoa sutil: o que está mais longe da câmera esmaece um pouco
      // em vez de manter o brilho constante até o infinito — é o que
      // faz o holograma ter profundidade de verdade em vez de parecer
      // recortado e colado na tela.
      scene.fog = new THREE.Fog(0x030712, 11, 34);
      camera = new THREE.PerspectiveCamera(45, w / h, 0.1, 100);
      camera.position.set(0, 2.4, 11);
      camera.lookAt(0, 0, 0);

      group = new THREE.Group();
      scene.add(group);
      rebuildAmbientParticles(accentHex, accent2Hex);

      // Pós-processamento é opcional e assíncrono: a cena já renderiza
      // normal (renderer.render) enquanto os módulos de bloom carregam em
      // segundo plano; quando (e se) terminarem, o composer entra a
      // partir do próximo frame sem nenhum corte visível.
      composer = null;
      if (PERF_TIERS[resolvedTier].postFX) {
        ensurePostFX().then((ok) => {
          if (ok && renderer && scene && camera && PERF_TIERS[resolvedTier].postFX) {
            composer = buildComposer(renderer, scene, camera, els.canvas.clientWidth || w, els.canvas.clientHeight || h);
          }
        });
      }

      return {
        accent: new THREE.Color(accentHex),
        accent2: new THREE.Color(accent2Hex),
      };
    }

    // ---------- Loop de anima\u00e7\u00e3o \u00fanico, compartilhado por todos os modos ----------
    let lastT = performance.now();
    function animate(now) {
      animId = requestAnimationFrame(animate);
      const dt = Math.min((now - lastT) / 1000, 0.1);
      lastT = now;
      sampleFPS(dt);
      if (autoRotate && settings.autoRotate) rotY += dt * 0.25 * settings.speed;

      // ---------- Inércia do arraste ----------
      // Quando o usuário solta o mouse/dedo em movimento, a rotação
      // continua com a velocidade do último trecho e vai freando (atrito
      // exponencial) até ficar imperceptível, em vez de travar seca.
      if (!isDragging && !isPanning && (Math.abs(velRotY) > INERTIA_MIN || Math.abs(velRotX) > INERTIA_MIN)) {
        rotY += velRotY;
        rotX = Math.max(-1.2, Math.min(1.2, rotX + velRotX));
        velRotY *= INERTIA_DAMPING;
        velRotX *= INERTIA_DAMPING;
      }
      group.position.x = panX;
      if (!entranceActive) group.position.y = panY;

      // Suaviza o holograma "seguindo" o cursor pela tela do
      // computador — só quando ninguém está arrastando o holograma
      // na mão, pra não brigar com o gesto do usuário.
      if (!isDragging) {
        liveTiltX += (liveTargetX - liveTiltX) * Math.min(dt * 3, 1);
        liveTiltY += (liveTargetY - liveTiltY) * Math.min(dt * 3, 1);
      } else {
        liveTiltX *= 0.9;
        liveTiltY *= 0.9;
      }
      group.rotation.y = rotY + liveTiltY;
      group.rotation.x = rotX + liveTiltX;

      // ---------- Anima\u00e7\u00e3o de "entrada" (materializa\u00e7\u00e3o) do lugar real ----------
      let entranceScale = 1;
      if (entranceActive) {
        const p = Math.min((now - entranceStart) / ENTRANCE_MS, 1);
        // ease-out-back: sobe r\u00e1pido e d\u00e1 uma leve "quicada" no final,
        // como se o holograma estivesse assentando no lugar certo.
        const eased = 1 + 2.4 * Math.pow(p - 1, 3) + 1.2 * Math.pow(p - 1, 2);
        entranceScale = Math.max(0.02, Math.min(eased, 1.06));
        group.position.y = (1 - p) * -3.5;
        const fadeTarget = (group.userData.fadeInTargetOpacity && group.userData.fadeInTargetOpacity.target) || 1;
        if (group.userData.fadeInMaterials) {
          group.userData.fadeInMaterials.forEach((m) => { m.opacity = Math.min(p * 1.4, 1) * fadeTarget; });
        }
        if (p >= 1) {
          entranceActive = false;
          group.position.y = 0;
          if (group.userData.fadeInMaterials) group.userData.fadeInMaterials.forEach((m) => { m.opacity = fadeTarget; });
        }
      }

      if (screenPulse > 0) {
        screenPulse = Math.max(0, screenPulse - dt * 1.6);
        const pulseScale = (1 + screenPulse * 0.04) * entranceScale * settings.scale;
        group.scale.set(pulseScale, pulseScale, pulseScale);
      } else {
        const s = entranceScale * settings.scale;
        group.scale.set(s, s, s);
      }

      if (group.userData.atomOrbits) {
        group.userData.atomOrbits.forEach((o) => {
          o.angle += dt * o.speed;
          o.electron.position.set(Math.cos(o.angle) * o.radius, 0, Math.sin(o.angle) * o.radius);
        });
      }
      if (group.userData.heartbeat) {
        const beat = 1 + Math.max(0, Math.sin(now * 0.0045)) * 0.12;
        group.userData.heartbeat.scale.set(beat, beat, beat);
      }
      if (group.userData.sweep) group.userData.sweep.rotation.z += dt * 0.6;
      if (group.userData.pulseRings) {
        const s = 1 + Math.sin(now * 0.004) * 0.15;
        group.userData.pulseRings.forEach((r) => {
          r.scale.set(s, s, s);
          r.material.opacity = 0.4 + Math.sin(now * 0.004) * 0.3;
        });
      }

      // ---------- Vida da luz: varredura por cima da superfície + ----------
      // instabilidade de energia, tipo um projetor de verdade. Roda todo
      // frame, em tudo que estiver na cena (fresnel/feixe), sem precisar
      // que cada função de construção registre nada à parte.
      const t = now * 0.001;
      const flicker = 1 + Math.sin(t * 5.3) * 0.02 + Math.sin(t * 17.0) * 0.012 + (Math.random() - 0.5) * 0.015;
      if ("toneMappingExposure" in renderer) {
        renderer.toneMappingExposure = 1.15 * flicker + Math.sin(t * 0.6) * 0.03;
      }
      group.traverse((obj) => {
        const m = obj.material;
        if (m && m.uniforms && m.uniforms.uTime) m.uniforms.uTime.value = t;
      });
      if (group.userData.beam) {
        group.userData.beam.material.opacity = (0.09 + Math.max(0, Math.sin(t * 3.1)) * 0.05) * flicker;
        if (group.userData.beam.material.map) group.userData.beam.material.map.offset.y = (group.userData.beam.material.map.offset.y + dt * 0.22) % 1;
      }

      if (composer) {
        try {
          if (composer.__scanPass) composer.__scanPass.uniforms.uTime.value = t;
          composer.render();
        } catch (e) {
          // Se o composer falhar em tempo de execução (driver estranho,
          // contexto perdido etc), desliga o bloom pro resto da sessão e
          // volta a desenhar direto — nunca deixa a tela preta.
          composer = null;
          postFXReady = false;
          renderer.render(scene, camera);
        }
      } else {
        renderer.render(scene, camera);
      }
    }

    // ---------- Loop de anima\u00e7\u00e3o do modo compat\u00edvel (sem WebGL) ----------
    function animateFallback2D(now) {
      animId = requestAnimationFrame(animateFallback2D);
      if (!ctx2d || !fbShape) return;
      const dt = Math.min((now - fbLastT) / 1000, 0.1);
      fbLastT = now;
      if (autoRotate && settings.autoRotate) rotY += dt * 0.25 * settings.speed;

      if (!isDragging) {
        liveTiltX += (liveTargetX - liveTiltX) * Math.min(dt * 3, 1);
        liveTiltY += (liveTargetY - liveTiltY) * Math.min(dt * 3, 1);
      } else {
        liveTiltX *= 0.9;
        liveTiltY *= 0.9;
      }

      const w = els.canvas.clientWidth || 320;
      const h = els.canvas.clientHeight || 340;
      ctx2d.clearRect(0, 0, w, h);

      const cx = w / 2;
      const cy = h / 2 + h * 0.05;
      const fl = Math.min(w, h) * 0.95;
      const dist = camera.position.z;
      const ry = rotY + liveTiltY;
      const rx = rotX + liveTiltX;

      const projected = fbShape.points.map((p) => projectPoint(p, ry, rx, dist, fl, cx, cy));

      ctx2d.lineWidth = 1;
      ctx2d.strokeStyle = fbShape.accent;
      fbShape.edges.forEach(([i, j]) => {
        const a = projected[i], b = projected[j];
        if (!a || !b) return;
        const depth = (a.z + b.z) / 2;
        const t = Math.max(0, Math.min(1, (depth + 5) / 10));
        ctx2d.globalAlpha = 0.12 + t * 0.35;
        ctx2d.beginPath();
        ctx2d.moveTo(a.x, a.y);
        ctx2d.lineTo(b.x, b.y);
        ctx2d.stroke();
      });

      projected.forEach((p) => {
        const t = Math.max(0, Math.min(1, (p.z + 5) / 10));
        ctx2d.save();
        ctx2d.globalAlpha = 0.4 + t * 0.6;
        ctx2d.shadowBlur = 8;
        ctx2d.shadowColor = fbShape.accent2;
        ctx2d.fillStyle = fbShape.accent2;
        ctx2d.beginPath();
        ctx2d.arc(p.x, p.y, 1.3 + t * 2.2, 0, Math.PI * 2);
        ctx2d.fill();
        ctx2d.restore();
      });

      // Anel de varredura na base — refor\u00e7a a leitura de "proje\u00e7\u00e3o hologr\u00e1fica"
      ctx2d.globalAlpha = 0.45;
      ctx2d.strokeStyle = fbShape.accent2;
      ctx2d.beginPath();
      ctx2d.ellipse(cx, cy + fl * 0.11, fl * 0.36, fl * 0.075, 0, 0, Math.PI * 2);
      ctx2d.stroke();
      ctx2d.globalAlpha = 1;
    }

    // ---------- generate(): gera (ou regera) o holograma procedural ----------
    async function generate(text, type) {
      const t = (text !== undefined && text !== null ? text : (els.input ? els.input.value : "")).trim();
      const ty = type !== undefined ? type : (els.type ? els.type.value : "auto");
      if (els.input && text !== undefined) els.input.value = t;
      if (!t) {
        if (els.result) els.result.textContent = "Digite o que voc\u00ea quer projetar primeiro.";
        return false;
      }
      lastText = t;
      lastType = ty;

      const colors = await _bootStage();
      if (!colors) return false;
      emitHoloEvent("holo:open", { type: ty, text: t }); // ITEM 2 do briefing: InputManager normaliza isto em OPEN_HOLOGRAM

      const rng = seededRandom(t.toLowerCase());
      const finalType = ty === "auto" ? detectType(t) : ty;

      if (colors.fallback) {
        let shape;
        if (finalType === "mapa") shape = makeFallbackTerrain(rng, 13);
        else if (finalType === "rede") shape = makeFallbackNetwork(rng, 20 + Math.floor(rng() * 6));
        else shape = makeFallbackSphere(rng, 90);
        fbShape = { points: shape.points, edges: shape.edges, accent: colors.accent, accent2: colors.accent2 };

        rotY = 0.6;
        rotX = 0.25;
        panX = 0; panY = 0; velRotY = 0; velRotX = 0;
        autoRotate = true;

        if (els.label) els.label.textContent = "\u25c8 " + t.toUpperCase();

        fbLastT = performance.now();
        animId = requestAnimationFrame(animateFallback2D);

        if (els.result) els.result.textContent = "\u2705 Holograma projetado em modo compat\u00edvel, sem acelera\u00e7\u00e3o 3D neste navegador. Arraste para girar, role para dar zoom.";
        if (els.stage.scrollIntoView) els.stage.scrollIntoView({ behavior: "smooth", block: "nearest" });
        return true;
      }

      const { accent, accent2 } = colors;
      if (finalType === "mapa") buildMapa(rng, group, accent, accent2, t);
      else if (finalType === "rede") buildRede(rng, group, accent, accent2);
      else buildObjeto(t, rng, group, accent, accent2);
      addProjectorBeam(group, accent, accent2, 3.2, 3.6);

      rotY = 0.6;
      rotX = 0.25;
        panX = 0; panY = 0; velRotY = 0; velRotX = 0;
      autoRotate = true;
      entranceActive = false;
      group.scale.set(settings.scale, settings.scale, settings.scale);
      group.position.y = 0;
      if (group.userData.gridMeshes) group.userData.gridMeshes.forEach((m) => { m.visible = settings.showGrid; });

      if (els.label) els.label.textContent = "\u25c8 " + t.toUpperCase();

      lastT = performance.now();
      animId = requestAnimationFrame(animate);

      if (els.result) els.result.textContent = "\u2705 Holograma projetado. Arraste para girar, role para dar zoom \u2014 e repare que ele tamb\u00e9m reage sozinho ao mouse se movendo pela tela.";
      if (els.stage.scrollIntoView) els.stage.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return true;
    }

    // ---------- generateRealPlace(): busca um lugar real (OpenStreetMap) ----------
    // e materializa o terreno de verdade no holograma, com anima\u00e7\u00e3o de
    // "entrada" (ver hist\u00f3rico: liga\u00e7\u00e3o em animate() acima).
    async function generateRealPlace(query) {
      const q = (query !== undefined && query !== null ? query : (els.realInput ? els.realInput.value : "")).trim();
      if (els.realInput && query !== undefined) els.realInput.value = q;
      if (!q) {
        if (els.result) els.result.textContent = "Diga qual lugar real voc\u00ea quer ver entrar no holograma.";
        return false;
      }

      if (els.result) els.result.textContent = "\ud83d\udef0 Buscando coordenadas, relevo e mapa reais de \"" + q + "\" no OpenStreetMap...";
      els.stage.style.display = "block";
      els.stage.classList.add("holo-loading");

      let data;
      try {
        const resp = await fetch("/api/hologram/lugar-real", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ query: q }),
        });
        // O servidor deveria SEMPRE responder JSON nesta rota (ver
        // app.py: _handle_api_errors_as_json) \u2014 mas se algum proxy/
        // hospedagem no meio do caminho devolver uma p\u00e1gina de erro em
        // HTML (ex: timeout do gateway), checar o content-type antes
        // de chamar resp.json() evita o erro cr\u00edptico "Unexpected
        // token '<'" e mostra uma mensagem que a pessoa entende.
        const ct = resp.headers.get("content-type") || "";
        if (!ct.includes("application/json")) {
          throw new Error("O servidor demorou demais ou est\u00e1 fora do ar (resposta n\u00e3o foi JSON). Tente de novo em instantes.");
        }
        data = await resp.json();
        if (!resp.ok || data.error) throw new Error(data.error || "N\u00e3o consegui buscar esse lugar agora.");
      } catch (e) {
        els.stage.classList.remove("holo-loading");
        if (els.result) els.result.textContent = "\u274c " + (e.message || "Falha ao buscar o lugar real.");
        return false;
      }

      const colors = await _bootStage();
      if (!colors) return false;

      if (colors.fallback) {
        const shape = makeFallbackTerrainFromElevation(data);
        fbShape = { points: shape.points, edges: shape.edges, accent: colors.accent, accent2: colors.accent2 };

        rotY = 0.5;
        rotX = 0.5;
        panX = 0; panY = 0; velRotY = 0; velRotX = 0;
        autoRotate = true;

        if (els.label) els.label.textContent = "\u25c8 " + data.formatted_address.toUpperCase();

        fbLastT = performance.now();
        animId = requestAnimationFrame(animateFallback2D);

        if (els.result) {
          els.result.textContent = "\u2705 " + data.formatted_address + " materializado em modo compat\u00edvel (sem acelera\u00e7\u00e3o 3D neste navegador), com o relevo real do OpenStreetMap \u2014 lat " +
            data.lat.toFixed(4) + ", lng " + data.lng.toFixed(4) + ".";
        }
        if (els.stage.scrollIntoView) els.stage.scrollIntoView({ behavior: "smooth", block: "nearest" });
        return true;
      }

      const { accent, accent2 } = colors;

      buildLugarReal(data, group, accent, accent2);
      addProjectorBeam(group, accent, accent2, 5, 4.2);

      // Ângulo mais raso e câmera mais baixa/próxima do que o modo
      // procedural: assim o terreno é visto quase de lado, como um
      // holograma projetado à sua frente, em vez de visto de cima
      // como um mapa (o efeito "parece o Google Maps" reportado).
      if (camera) {
        camera.position.set(0, 1.1, 8.5);
        camera.lookAt(0, 0.4, 0);
      }
      rotY = 0.5;
      rotX = 0.62;
        panX = 0; panY = 0; velRotY = 0; velRotX = 0;
      autoRotate = true;
      entranceActive = true;
      entranceStart = performance.now();
      group.scale.set(0.02, 0.02, 0.02);
      group.position.y = -3.5;
      if (group.userData.gridMeshes) group.userData.gridMeshes.forEach((m) => { m.visible = settings.showGrid; });

      if (els.label) els.label.textContent = "\u25c8 " + data.formatted_address.toUpperCase();

      lastT = performance.now();
      animId = requestAnimationFrame(animate);

      if (els.result) {
        const relevoTxt = data.elevation_degraded
          ? "Mapa real do OpenStreetMap (relevo detalhado indispon\u00edvel no momento \u2014 servi\u00e7o de eleva\u00e7\u00e3o ocupado; terreno mostrado nivelado na altitude real do local)."
          : "Relevo real e mapa real do OpenStreetMap.";
        const buildingsCount = (data.buildings && data.buildings.length) || 0;
        const prediosTxt = buildingsCount > 0
          ? " " + buildingsCount + " pr\u00e9dio" + (buildingsCount === 1 ? "" : "s") + " reais extrudados (contorno e altura do OpenStreetMap)."
          : "";
        els.result.textContent = "\u2705 " + data.formatted_address + " materializado \u2014 lat " +
          data.lat.toFixed(4) + ", lng " + data.lng.toFixed(4) + ". " + relevoTxt + prediosTxt;
      }
      if (els.stage.scrollIntoView) els.stage.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return true;
    }

    // ---------- generateFromPhoto(): monta o holograma a partir de uma foto ----------
    // Tudo o que faz o holograma aparecer (ler a foto, recortar,
    // montar o relevo 3D e a textura) acontece 100% no navegador —
    // n\u00e3o depende do servidor nem da IA responder. Só a LEGENDA final
    // (descri\u00e7\u00e3o da foto) vem da IA, em segundo plano, sem bloquear
    // nada: se a IA falhar, o holograma continua normal, só com um
    // r\u00f3tulo gen\u00e9rico.
    async function generateFromPhoto(fileOrDataUrl) {
      if (!fileOrDataUrl) {
        if (els.result) els.result.textContent = "Escolha uma foto primeiro.";
        return false;
      }

      if (els.result) els.result.textContent = "\ud83d\udcf7 Lendo a foto e materializando o holograma...";
      els.stage.style.display = "block";
      els.stage.classList.add("holo-loading");

      // Aceita tanto um File (input de upload na p\u00e1gina de Ferramentas)
      // quanto uma data URL j\u00e1 pronta (anexo de foto do Jarvis, que j\u00e1
      // guarda a imagem assim no navegador \u2014 ver static/js/jarvis.js).
      let dataUrl;
      if (typeof fileOrDataUrl === "string") {
        dataUrl = fileOrDataUrl;
      } else {
        try {
          dataUrl = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error("N\u00e3o consegui ler essa foto."));
            reader.readAsDataURL(fileOrDataUrl);
          });
        } catch (e) {
          els.stage.classList.remove("holo-loading");
          if (els.result) els.result.textContent = "\u274c " + e.message;
          return false;
        }
      }

      let img;
      try {
        img = await new Promise((resolve, reject) => {
          const im = new Image();
          im.onload = () => resolve(im);
          im.onerror = () => reject(new Error("Essa imagem n\u00e3o p\u00f4de ser carregada."));
          im.src = dataUrl;
        });
      } catch (e) {
        els.stage.classList.remove("holo-loading");
        if (els.result) els.result.textContent = "\u274c " + e.message;
        return false;
      }

      // Recorta pro centro num quadrado — mais previsível pra virar
      // malha de profundidade + textura do que preservar a proporção
      // original da foto.
      const texSize = 256;
      const texCanvas = document.createElement("canvas");
      texCanvas.width = texSize;
      texCanvas.height = texSize;
      const tctx = texCanvas.getContext("2d");
      const side = Math.min(img.width, img.height);
      const sx = (img.width - side) / 2;
      const sy = (img.height - side) / 2;
      tctx.drawImage(img, sx, sy, side, side, 0, 0, texSize, texSize);

      const colors = await _bootStage();
      if (!colors) return false;

      if (colors.fallback) {
        els.stage.classList.remove("holo-loading");
        if (els.result) els.result.textContent = "\u26a0\ufe0f O holograma a partir de foto precisa de acelera\u00e7\u00e3o 3D (WebGL), indispon\u00edvel neste navegador agora.";
        return false;
      }

      const { accent, accent2 } = colors;
      buildFromPhoto(texCanvas, group, accent, accent2);
      addProjectorBeam(group, accent, accent2, 4, 3.6);

      if (camera) {
        camera.position.set(0, 1.6, 9.5);
        camera.lookAt(0, 0.6, 0);
      }
      rotY = 0.5;
      rotX = 0.5;
        panX = 0; panY = 0; velRotY = 0; velRotX = 0;
      autoRotate = true;
      entranceActive = true;
      entranceStart = performance.now();
      group.scale.set(0.02, 0.02, 0.02);
      group.position.y = -3.5;

      if (els.label) els.label.textContent = "\u25c8 HOLOGRAMA DA FOTO";
      els.stage.classList.remove("holo-loading");

      lastT = performance.now();
      animId = requestAnimationFrame(animate);

      if (els.result) els.result.textContent = "\u2705 Holograma materializado a partir da sua foto \u2014 relevo real dos pixels + a pr\u00f3pria foto como textura. Arraste para girar, role para dar zoom.";
      if (els.stage.scrollIntoView) els.stage.scrollIntoView({ behavior: "smooth", block: "nearest" });

      // Legenda por IA, em segundo plano e melhor esforço — nunca
      // bloqueia o holograma, que já está materializado na tela antes
      // mesmo desta chamada começar.
      (async () => {
        try {
          const smallCanvas = document.createElement("canvas");
          smallCanvas.width = 160;
          smallCanvas.height = 160;
          smallCanvas.getContext("2d").drawImage(texCanvas, 0, 0, 160, 160);
          const smallDataUrl = smallCanvas.toDataURL("image/jpeg", 0.7);
          const resp = await fetch("/api/hologram/da-foto", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ image: smallDataUrl }),
          });
          const ct = resp.headers.get("content-type") || "";
          if (!ct.includes("application/json")) return;
          const data = await resp.json();
          if (data && data.legenda && els.label) {
            els.label.textContent = "\u25c8 " + data.legenda.toUpperCase();
          }
        } catch (e) {
          // sem legenda desta vez \u2014 o holograma continua normal.
        }
      })();

      return true;
    }

    // ---------- API do painel de controles ----------
    function setSpeed(v) { settings.speed = Math.max(0, Number(v) || 0); }
    function setScale(v) { settings.scale = Math.max(0.2, Math.min(3, Number(v) || 1)); }
    function setAutoRotate(v) { settings.autoRotate = !!v; autoRotate = !!v; }
    function setParticleDensity(v) {
      settings.particleDensity = Math.max(0, Number(v) || 0);
      const rootStyles = getComputedStyle(document.documentElement);
      const accentHex = settings.accentOverride || (rootStyles.getPropertyValue("--accent") || "#00e5ff").trim();
      const accent2Hex = settings.accent2Override || (rootStyles.getPropertyValue("--accent2") || "#b026ff").trim();
      rebuildAmbientParticles(accentHex, accent2Hex);
    }
    function toggleAmbient(v) {
      settings.showAmbient = !!v;
      if (ambientParticlesRef) ambientParticlesRef.visible = settings.showAmbient;
    }
    function toggleGrid(v) {
      settings.showGrid = !!v;
      if (group && group.userData && group.userData.gridMeshes) {
        group.userData.gridMeshes.forEach((m) => { m.visible = settings.showGrid; });
      }
    }
    function setColors(accentHex, accent2Hex) {
      settings.accentOverride = accentHex || null;
      settings.accent2Override = accent2Hex || null;
      if (scene) rebuildAmbientParticles(settings.accentOverride || "#00e5ff", settings.accent2Override || "#b026ff");
      if (lastText) generate(lastText, lastType);
    }
    function setObjectKind(kind) {
      // Atalho pro painel "escolher objeto": preenche o texto com uma
      // palavra-chave reconhecida por buildObjeto() e gera na hora,
      // sem precisar duplicar toda a lógica de detecção aqui.
      const label = HOLO_KIND_LABELS[kind] || kind;
      return generate(label, "auto");
    }
    // FASE 7: usado pelo Jarvis (jarvis.js) para saber se já existe um
    // holograma em tela antes de aceitar comandos de controle por voz
    // (girar mais rápido, mudar cor, zoom etc.) — sem isso, um comando
    // desses antes de qualquer generate() não teria o que controlar.
    function isActive() {
      return !!(group && lastText);
    }
    function getSettings() {
      return Object.assign({}, settings);
    }

    function close() {
      // S\u00f3 para a anima\u00e7\u00e3o e esconde — n\u00e3o destr\u00f3i o renderer/contexto,
      // pra reabrir depois ser sempre r\u00e1pido e confi\u00e1vel (ver coment\u00e1rio
      // em _bootStage() sobre por que recriar o contexto \u00e9 arriscado).
      if (animId) cancelAnimationFrame(animId);
      animId = null;
      els.stage.style.display = "none";
      emitHoloEvent("holo:close", {}); // ITEM 2 do briefing: InputManager normaliza isto em CLOSE_HOLOGRAM
    }

    if (els.open) els.open.addEventListener("click", () => generate());
    if (els.realOpen) els.realOpen.addEventListener("click", () => generateRealPlace());
    if (els.photoOpen && els.photoInput) {
      els.photoOpen.addEventListener("click", () => {
        const file = els.photoInput.files && els.photoInput.files[0];
        generateFromPhoto(file);
      });
    }
    if (els.realInput) {
      els.realInput.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          generateRealPlace();
        }
      });
    }
    if (els.close) els.close.addEventListener("click", close);
    if (els.input) {
      els.input.addEventListener("keydown", (e) => {
        if (e.key === "Enter") {
          e.preventDefault();
          generate();
        }
      });
    }

    return {
      generate: generate,
      generateRealPlace: generateRealPlace,
      generateFromPhoto: generateFromPhoto,
      close: close,
      setObjectKind: setObjectKind,
      setSpeed: setSpeed,
      setScale: setScale,
      setAutoRotate: setAutoRotate,
      setParticleDensity: setParticleDensity,
      toggleAmbient: toggleAmbient,
      toggleGrid: toggleGrid,
      setColors: setColors,
      getSettings: getSettings,
      kinds: HOLO_KIND_LABELS,
      // FASE 4/6: controle externo (gestos de mão via webcam, comandos de
      // voz do Jarvis) — ver gesture-control.js e a integração de voz.
      applyDelta: applyDelta,
      resetView: resetView,
      isActive: isActive,
      canvasEl: els.canvas,
      // ITEM 27/28 do briefing: telemetria + níveis de performance.
      getTelemetry: getTelemetry,
      setPerformanceTier: setPerformanceTier,
      getPerformanceTier: getPerformanceTier,
    };
  }

  document.addEventListener("DOMContentLoaded", function () {
    document.querySelectorAll("[data-holo-widget]").forEach(function (root) {
      const widget = createHologramWidget(root);
      if (!widget) return;
      root.__holoWidget = widget;
      if (root.id === "jarvis-holo-widget") window.jarvisHolograma = widget;
    });
  });
})();
