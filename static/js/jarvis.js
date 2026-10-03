const chatEl = document.getElementById("jarvis-chat");
const inputEl = document.getElementById("jarvis-input");
const sendBtn = document.getElementById("send-btn");
const micBtn = document.getElementById("mic-btn");
const autoVoice = document.getElementById("auto-voice");
const continuousMode = document.getElementById("continuous-mode");
const pitagorasMode = document.getElementById("pitagoras-mode");
const codeMode = document.getElementById("code-mode");
const cyberMode = document.getElementById("cyber-mode");
const negociosMode = document.getElementById("negocios-mode");
const ctfMode = document.getElementById("ctf-mode");
const clearBtn = document.getElementById("clear-btn");
const attachBtn = document.getElementById("attach-btn");
const fileInput = document.getElementById("jarvis-file-input");
const attachmentPreviewEl = document.getElementById("jarvis-attachment-preview");
const orb = document.getElementById("jarvis-orb");
const statusEl = document.getElementById("jarvis-status");
const voiceSelect = document.getElementById("voice-select");
const stopBtn = document.getElementById("jarvis-stop-btn");
const developerModeBtn = document.getElementById("developer-mode-btn");
const quickActions = document.getElementById("jarvis-quick-actions");
let activeRequestController = null;
let developerMode = false;

const newChatBtn = document.getElementById("new-chat-btn");
const historyBtn = document.getElementById("history-btn");
const historyCloseBtn = document.getElementById("history-close-btn");
const historyPanel = document.getElementById("jarvis-history-panel");
const historyListEl = document.getElementById("jarvis-history-list");
const historySearch = document.getElementById("jarvis-history-search");
const settingsBtn = document.getElementById("jarvis-settings-btn");
const settingsCloseBtn = document.getElementById("settings-close-btn");
const settingsPanel = document.getElementById("jarvis-settings-panel");

const VOICE_KEY = "tf_jarvis_voice_index";

// ---------- Histórico em várias conversas (sessões) ----------
// Antes só existia UM histórico salvo (tf_jarvis_history). Agora cada
// conversa vira uma "sessão" independente, listada no painel de
// Histórico, para o usuário poder voltar em conversas antigas sem
// perder a atual.
const SESSIONS_KEY = "tf_jarvis_sessions";
const ACTIVE_SESSION_KEY = "tf_jarvis_active_session";
const OLD_STORAGE_KEY = "tf_jarvis_history"; // formato antigo, migrado uma vez

function loadSessions() {
  try { return JSON.parse(localStorage.getItem(SESSIONS_KEY)) || []; }
  catch (e) { return []; }
}

function saveSessions(sessions) {
  localStorage.setItem(SESSIONS_KEY, JSON.stringify(sessions.slice(-50)));
}

function makeSessionTitle(messages) {
  const firstUser = messages.find((m) => m.role === "user");
  if (!firstUser) return "Nova conversa";
  const text = firstUser.content.trim().replace(/\s+/g, " ");
  return text.length > 40 ? text.slice(0, 40) + "…" : text;
}

function createSession(messages) {
  return {
    id: "s" + Date.now() + Math.random().toString(36).slice(2, 7),
    title: makeSessionTitle(messages || []),
    updatedAt: Date.now(),
    messages: messages || [],
  };
}

let sessions = loadSessions();

// Migração única do formato antigo (uma conversa só) para sessões.
if (sessions.length === 0) {
  let oldMessages = [];
  try { oldMessages = JSON.parse(localStorage.getItem(OLD_STORAGE_KEY)) || []; }
  catch (e) { oldMessages = []; }
  const initial = createSession(oldMessages);
  sessions = [initial];
  saveSessions(sessions);
  localStorage.setItem(ACTIVE_SESSION_KEY, initial.id);
  localStorage.removeItem(OLD_STORAGE_KEY);
}

function getActiveSessionId() {
  let id = localStorage.getItem(ACTIVE_SESSION_KEY);
  if (!id || !sessions.find((s) => s.id === id)) {
    id = sessions[sessions.length - 1].id;
    localStorage.setItem(ACTIVE_SESSION_KEY, id);
  }
  return id;
}

function getActiveSession() {
  return sessions.find((s) => s.id === getActiveSessionId());
}

function loadHistory() {
  const active = getActiveSession();
  return active ? active.messages : [];
}

function saveHistory(newHistory) {
  const active = getActiveSession();
  if (!active) return;
  active.messages = newHistory.slice(-200);
  active.updatedAt = Date.now();
  if (newHistory.length && active.title === "Nova conversa") {
    active.title = makeSessionTitle(newHistory);
  }
  saveSessions(sessions);
}

function formatSessionDate(ts) {
  const d = new Date(ts);
  return d.toLocaleDateString("pt-BR") + " " + d.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function renderHistoryPanel() {
  historyListEl.innerHTML = "";
  if (sessions.length === 0) {
    historyListEl.innerHTML = '<div class="jarvis-history-empty">Nenhuma conversa salva ainda.</div>';
    return;
  }
  const activeId = getActiveSessionId();
  const q = (historySearch?.value || "").trim().toLowerCase();
  [...sessions].filter(s => !q || (s.title || "").toLowerCase().includes(q) || s.messages.some(m => String(m.content || "").toLowerCase().includes(q))).sort((a, b) => Number(b.favorite) - Number(a.favorite) || b.updatedAt - a.updatedAt).forEach((s) => {
    const item = document.createElement("div");
    item.className = "jarvis-history-item" + (s.id === activeId ? " active" : "");

    const info = document.createElement("div");
    info.className = "jarvis-history-item-info";
    const title = document.createElement("div");
    title.className = "jarvis-history-item-title";
    title.textContent = s.title || "Nova conversa";
    const date = document.createElement("div");
    date.className = "jarvis-history-item-date";
    date.textContent = formatSessionDate(s.updatedAt);
    info.appendChild(title);
    info.appendChild(date);

    const actions = document.createElement("div");
    actions.className = "jarvis-history-item-actions";

    const renameBtn = document.createElement("button");
    renameBtn.className = "jarvis-history-action";
    renameBtn.textContent = "✏️";
    renameBtn.title = "Renomear conversa";
    renameBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      const next = prompt("Novo nome da conversa:", s.title || "Nova conversa");
      if (next && next.trim()) { s.title = next.trim().slice(0, 80); s.updatedAt = Date.now(); saveSessions(sessions); renderHistoryPanel(); }
    });

    const favBtn = document.createElement("button");
    favBtn.className = "jarvis-history-action";
    favBtn.textContent = s.favorite ? "⭐" : "☆";
    favBtn.title = "Favoritar/desfavoritar";
    favBtn.addEventListener("click", (e) => { e.stopPropagation(); s.favorite = !s.favorite; saveSessions(sessions); renderHistoryPanel(); });

    const archiveBtn = document.createElement("button");
    archiveBtn.className = "jarvis-history-action";
    archiveBtn.textContent = s.archived ? "📦" : "🗂";
    archiveBtn.title = "Arquivar/desarquivar";
    archiveBtn.addEventListener("click", (e) => { e.stopPropagation(); s.archived = !s.archived; saveSessions(sessions); renderHistoryPanel(); });

    const delBtn = document.createElement("button");
    delBtn.className = "jarvis-history-action jarvis-history-item-delete";
    delBtn.textContent = "🗑";
    delBtn.title = "Excluir esta conversa";
    delBtn.addEventListener("click", (e) => {
      e.stopPropagation();
      if (!confirm("Excluir esta conversa salva?")) return;
      sessions = sessions.filter((x) => x.id !== s.id);
      if (sessions.length === 0) sessions = [createSession([])];
      saveSessions(sessions);
      if (s.id === activeId) {
        localStorage.setItem(ACTIVE_SESSION_KEY, sessions[sessions.length - 1].id);
        history = loadHistory();
        renderAll(history);
      }
      renderHistoryPanel();
    });

    item.addEventListener("click", () => {
      localStorage.setItem(ACTIVE_SESSION_KEY, s.id);
      history = loadHistory();
      renderAll(history);
      closePanels();
    });

    actions.appendChild(renameBtn);
    actions.appendChild(favBtn);
    actions.appendChild(archiveBtn);
    actions.appendChild(delBtn);
    item.appendChild(info);
    item.appendChild(actions);
    historyListEl.appendChild(item);
  });
}

function startNewChat() {
  const active = getActiveSession();
  // Evita empilhar várias conversas vazias seguidas.
  if (active && active.messages.length === 0) {
    closePanels();
    return;
  }
  const fresh = createSession([]);
  sessions.push(fresh);
  saveSessions(sessions);
  localStorage.setItem(ACTIVE_SESSION_KEY, fresh.id);
  history = [];
  pendingAttachment = null;
  renderAttachmentPreview();
  renderAll(history);
  closePanels();
}

function closePanels() {
  historyPanel.classList.add("hidden");
  settingsPanel.classList.add("hidden");
}

newChatBtn.addEventListener("click", startNewChat);

historyBtn.addEventListener("click", () => {
  settingsPanel.classList.add("hidden");
  renderHistoryPanel();
  historyPanel.classList.toggle("hidden");
});
historyCloseBtn.addEventListener("click", closePanels);
if (historySearch) historySearch.addEventListener("input", renderHistoryPanel);

settingsBtn.addEventListener("click", () => {
  historyPanel.classList.add("hidden");
  settingsPanel.classList.toggle("hidden");
});
settingsCloseBtn.addEventListener("click", closePanels);

// ---------- Markdown leve (sem libs externas) ----------
// Cobre o que a IA mais usa: **negrito**, *itálico*, `código`, blocos
// ```código```, listas e links — o suficiente pra ficar com cara de
// ChatGPT/Claude em vez de texto corrido numa bolha só.
function escapeHtml(s) {
  return s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
}

function renderMarkdown(raw) {
  const blocks = [];
  let text = raw.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
    blocks.push(code.replace(/\n$/, ""));
    return `\u0000CODEBLOCK${blocks.length - 1}\u0000`;
  });

  text = escapeHtml(text);
  text = text
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/(^|[^*])\*([^*\n]+)\*(?!\*)/g, "$1<em>$2</em>")
    .replace(/`([^`]+)`/g, "<code>$1</code>")
    .replace(/\[([^\]]+)\]\((https?:\/\/[^\s)]+)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

  const lines = text.split("\n");
  let html = "", inList = null, paragraph = [];

  function flushParagraph() {
    if (paragraph.length) { html += "<p>" + paragraph.join("<br>") + "</p>"; paragraph = []; }
  }
  function closeList() {
    if (inList) { html += `</${inList}>`; inList = null; }
  }

  for (const line of lines) {
    const placeholder = line.trim().match(/^\u0000CODEBLOCK(\d+)\u0000$/);
    const heading = line.match(/^(#{1,4})\s+(.*)/);
    const bullet = line.match(/^\s*[-*]\s+(.*)/);
    const numbered = line.match(/^\s*\d+[.)]\s+(.*)/);
    if (placeholder) {
      closeList(); flushParagraph();
      html += `\u0000CODEBLOCK${placeholder[1]}\u0000`;
    } else if (heading) {
      closeList(); flushParagraph();
      const level = Math.min(heading[1].length + 1, 4); // # vira h2, ## vira h3...
      html += `<h${level}>${heading[2]}</h${level}>`;
    } else if (bullet) {
      flushParagraph();
      if (inList !== "ul") { closeList(); html += "<ul>"; inList = "ul"; }
      html += `<li>${bullet[1]}</li>`;
    } else if (numbered) {
      flushParagraph();
      if (inList !== "ol") { closeList(); html += "<ol>"; inList = "ol"; }
      html += `<li>${numbered[1]}</li>`;
    } else if (line.trim() === "") {
      closeList(); flushParagraph();
    } else {
      closeList(); paragraph.push(line);
    }
  }
  closeList(); flushParagraph();

  html = html.replace(/\u0000CODEBLOCK(\d+)\u0000/g, (_, i) => {
    const code = blocks[i];
    return `<div class="code-block"><button type="button" class="code-copy-btn" data-code="${encodeURIComponent(code)}">Copiar</button><pre><code>${escapeHtml(code)}</code></pre></div>`;
  });

  return html;
}

// Remove marcações markdown antes de mandar pro speechSynthesis, senão
// o Jarvis fica falando "asterisco asterisco", "crase", "sustenido" e
// "traço traço traço" em voz alta. Cobre bem mais casos que antes:
// títulos (#), citações (>), linhas horizontais (---/***), tabelas (|),
// negrito/itálico com _ e **, tachado (~~), links/imagens e HTML solto.
function stripMarkdownForSpeech(text) {
  return text
    // blocos de código inteiros viram um aviso curto falado
    .replace(/```[\s\S]*?```/g, " bloco de código omitido. ")
    // linhas horizontais tipo ---, ***, ___
    .replace(/^\s*([-*_]\s*){3,}\s*$/gm, " ")
    // títulos markdown: "## Título" -> "Título"
    .replace(/^\s{0,3}#{1,6}\s+/gm, "")
    // citações: "> texto" -> "texto"
    .replace(/^\s{0,3}>\s?/gm, "")
    // imagens ![alt](url) antes dos links normais, senão sobra o "!"
    .replace(/!\[([^\]]*)\]\([^)]+\)/g, (_, alt) => (alt ? alt + ". " : " imagem. "))
    // links [texto](url) -> só o texto
    .replace(/\[([^\]]+)\]\(([^)]+)\)/g, "$1")
    // código inline `algo` -> algo
    .replace(/`([^`]+)`/g, "$1")
    // negrito/itálico/tachado com * ou _
    .replace(/(\*\*\*|___)(.+?)\1/g, "$2")
    .replace(/(\*\*|__)(.+?)\1/g, "$2")
    .replace(/~~(.+?)~~/g, "$1")
    .replace(/(^|[^*\w])\*([^*\n]+)\*(?!\*)/g, "$1$2")
    .replace(/(^|[^_\w])_([^_\n]+)_(?!_)/g, "$1$2")
    // marcadores de lista: "- item" / "* item" / "1. item"
    .replace(/^\s*[-*+]\s+/gm, "")
    .replace(/^\s*\d+[.)]\s+/gm, "")
    // linhas de tabela markdown: troca | por pausa e some com os traços de separação
    .replace(/^\s*\|?[\s:|-]+\|[\s:|-]+\|?\s*$/gm, " ")
    .replace(/\|/g, ", ")
    // qualquer tag HTML solta que a IA tenha colado na resposta
    .replace(/<[^>]+>/g, " ")
    // sobras de # e * que não casaram com nada acima (ex: hashtag isolada)
    .replace(/[#*_~`]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

// Cada mensagem vira uma "linha" com avatar + bolha, em vez de só uma
// bolha solta — dá mais cara de app de chat moderno (tipo ChatGPT/Claude)
// sem perder a identidade visual "painel futurista" do Jarvis.
function makeBubbleRow(role) {
  const row = document.createElement("div");
  row.className = "bubble-row " + (role === "user" ? "user" : "assistant");

  const avatar = document.createElement("div");
  avatar.className = "bubble-avatar " + (role === "user" ? "user" : "assistant");
  avatar.textContent = role === "user" ? "🧑" : "J";
  avatar.setAttribute("aria-hidden", "true");

  const bubble = document.createElement("div");
  bubble.className = "bubble " + (role === "user" ? "user" : "assistant");

  row.appendChild(avatar);
  row.appendChild(bubble);
  return { row, bubble };
}

function renderBubble(role, content, messageIndex = -1) {
  const { row, bubble } = makeBubbleRow(role);
  if (role === "user") bubble.textContent = content;
  else bubble.innerHTML = renderMarkdown(content);
  if (messageIndex >= 0 && !content.startsWith("⚠️")) {
    const actions = document.createElement("div");
    actions.className = "jarvis-message-actions";
    const copy = document.createElement("button"); copy.textContent = "Copiar"; copy.className = "jarvis-msg-btn";
    copy.onclick = () => navigator.clipboard?.writeText(content);
    actions.appendChild(copy);
    if (role === "user") {
      const edit = document.createElement("button"); edit.textContent = "Editar"; edit.className = "jarvis-msg-btn";
      edit.onclick = () => { inputEl.value = content; inputEl.focus(); }; actions.appendChild(edit);
    } else if (role === "assistant") {
      const regen = document.createElement("button"); regen.textContent = "Regenerar"; regen.className = "jarvis-msg-btn";
      regen.onclick = () => regenerateMessage(messageIndex); actions.appendChild(regen);
    }
    bubble.appendChild(actions);
  }
  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

function regenerateMessage(index) {
  if (isSending || index < 0 || !history[index] || history[index].role !== "assistant") return;
  const lastUser = history.slice(0, index).map((m,i)=>({m,i})).reverse().find(x => x.m.role === "user");
  if (!lastUser) return;
  history = history.slice(0, index);
  saveHistory(history);
  renderAll(history);
  inputEl.value = lastUser.m.content;
  sendMessage();
}

// Bolha do usuário quando a mensagem vem com uma foto/arquivo anexado —
// mostra uma miniatura (foto) ou um chip com ícone (arquivo) acima do
// texto digitado, sem usar innerHTML pra não precisar escapar nada.
function renderUserBubbleWithAttachment(text, attachment) {
  const { row, bubble } = makeBubbleRow("user");

  const chip = document.createElement("div");
  chip.className = "attach-chip";
  if (attachment.kind === "image") {
    const img = document.createElement("img");
    img.src = attachment.dataUrl;
    img.alt = attachment.name;
    chip.appendChild(img);
  } else {
    const icon = document.createElement("span");
    icon.textContent = "📄";
    chip.appendChild(icon);
  }
  const label = document.createElement("span");
  label.className = "attach-chip-name";
  label.textContent = attachment.name;
  chip.appendChild(label);
  bubble.appendChild(chip);

  if (text) {
    const p = document.createElement("div");
    p.style.marginTop = "8px";
    p.textContent = text;
    bubble.appendChild(p);
  }

  chatEl.appendChild(row);
  chatEl.scrollTop = chatEl.scrollHeight;
  return bubble;
}

// ---------- Anexar foto ou arquivo para o Jarvis revisar ----------
// O usuário clica no clipe 📎, escolhe uma imagem (foto de uma tela, um
// print de erro, um design...) ou um arquivo de texto/código, e isso
// fica "pendurado" pronto para ir junto da próxima mensagem enviada.
// Imagens: convertidas para base64 e reduzidas de tamanho no próprio
// navegador (Canvas) antes de enviar, pra não pesar o upload nem o
// modelo de IA. Arquivos de texto/código: lidos como texto puro e
// truncados a um tamanho razoável, e o conteúdo vira contexto extra
// pro Jarvis analisar (procurar erro, sugerir melhoria etc.).
const MAX_ATTACHMENT_IMAGE_DIM = 1280;
const MAX_ATTACHMENT_TEXT_CHARS = 12000;
const IMAGE_TYPE_RE = /^image\//;

let pendingAttachment = null; // { kind: "image"|"text", name, mime?, dataUrl?, content?, truncated? }

function downscaleImageFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Não consegui ler essa imagem."));
    reader.onload = () => {
      const img = new Image();
      img.onerror = () => reject(new Error("Arquivo de imagem inválido."));
      img.onload = () => {
        let { width, height } = img;
        const scale = Math.min(1, MAX_ATTACHMENT_IMAGE_DIM / Math.max(width, height));
        width = Math.max(1, Math.round(width * scale));
        height = Math.max(1, Math.round(height * scale));
        const canvas = document.createElement("canvas");
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext("2d");
        ctx.drawImage(img, 0, 0, width, height);
        resolve(canvas.toDataURL("image/jpeg", 0.82));
      };
      img.src = reader.result;
    };
    reader.readAsDataURL(file);
  });
}

function readTextFile(file) {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onerror = () => reject(new Error("Não consegui ler esse arquivo."));
    reader.onload = () => resolve(String(reader.result || ""));
    reader.readAsText(file);
  });
}

function renderAttachmentPreview() {
  attachmentPreviewEl.innerHTML = "";
  attachBtn.classList.toggle("has-attachment", !!pendingAttachment);
  if (!pendingAttachment) {
    attachmentPreviewEl.classList.add("hidden");
    return;
  }
  attachmentPreviewEl.classList.remove("hidden");

  if (pendingAttachment.kind === "image") {
    const img = document.createElement("img");
    img.src = pendingAttachment.dataUrl;
    img.alt = pendingAttachment.name;
    attachmentPreviewEl.appendChild(img);
  } else {
    const icon = document.createElement("span");
    icon.className = "attach-icon";
    icon.textContent = "📄";
    attachmentPreviewEl.appendChild(icon);
  }

  const info = document.createElement("div");
  info.className = "jarvis-attachment-preview-info";
  const name = document.createElement("div");
  name.className = "jarvis-attachment-preview-name";
  name.textContent = pendingAttachment.name;
  const hint = document.createElement("div");
  hint.className = "jarvis-attachment-preview-hint";
  hint.textContent = pendingAttachment.kind === "image"
    ? "Foto pronta — o Jarvis vai olhar ela na próxima mensagem"
    : (pendingAttachment.truncated ? "Arquivo de texto (parte inicial) — pronto para revisão" : "Arquivo de texto — pronto para revisão");
  info.appendChild(name);
  info.appendChild(hint);
  attachmentPreviewEl.appendChild(info);

  const removeBtn = document.createElement("button");
  removeBtn.type = "button";
  removeBtn.className = "jarvis-attachment-remove";
  removeBtn.title = "Remover anexo";
  removeBtn.textContent = "✕";
  removeBtn.addEventListener("click", () => {
    pendingAttachment = null;
    renderAttachmentPreview();
  });
  attachmentPreviewEl.appendChild(removeBtn);
}

attachBtn.addEventListener("click", () => fileInput.click());

fileInput.addEventListener("change", async () => {
  const file = fileInput.files && fileInput.files[0];
  fileInput.value = ""; // permite escolher o mesmo arquivo de novo depois
  if (!file) return;

  try {
    if (IMAGE_TYPE_RE.test(file.type)) {
      if (file.size > 15 * 1024 * 1024) throw new Error("Essa imagem é grande demais (máx. 15MB).");
      const dataUrl = await downscaleImageFile(file);
      pendingAttachment = { kind: "image", name: file.name, mime: "image/jpeg", dataUrl };
    } else {
      if (file.size > 1.5 * 1024 * 1024) throw new Error("Esse arquivo é grande demais (máx. 1.5MB para arquivos de texto/código).");
      let content = await readTextFile(file);
      const truncated = content.length > MAX_ATTACHMENT_TEXT_CHARS;
      if (truncated) content = content.slice(0, MAX_ATTACHMENT_TEXT_CHARS);
      pendingAttachment = { kind: "text", name: file.name, content, truncated };
    }
    renderAttachmentPreview();
  } catch (e) {
    renderBubble("assistant", "⚠️ " + (e.message || "Não consegui anexar esse arquivo."));
  }
});

// Efeito de "digitando" tipo ChatGPT/Claude pras respostas novas do
// Jarvis (o histórico recarregado aparece direto, sem animação).
function typeBubble(content) {
  const { row, bubble: div } = makeBubbleRow("assistant");
  chatEl.appendChild(row);

  // A resposta já chegou inteira do servidor — este efeito é só
  // cosmético (dá a sensação de "digitando"), então o teto de duração
  // é bem mais curto agora: nada disso deve ser confundido com atraso
  // de verdade. Miramos numa duração total agradável e calculamos o
  // passo a partir dela.
  const total = content.length;
  const targetDurationMs = Math.min(900, Math.max(150, total * 2));
  const steps = Math.max(15, Math.min(60, Math.round(total / 16)));
  const step = Math.max(1, Math.round(total / steps));
  const intervalMs = Math.max(6, targetDurationMs / steps);

  let i = 0;
  const timer = setInterval(() => {
    i += step;
    if (i >= total) {
      clearInterval(timer);
      div.innerHTML = renderMarkdown(content);
    } else {
      div.textContent = content.slice(0, i);
      div.innerHTML += '<span class="typing-cursor"></span>';
    }
    chatEl.scrollTop = chatEl.scrollHeight;
  }, intervalMs);
}

// Clique em "Copiar" dentro de um bloco de código
chatEl.addEventListener("click", (e) => {
  const btn = e.target.closest(".code-copy-btn");
  if (!btn || !navigator.clipboard) return;
  const code = decodeURIComponent(btn.dataset.code);
  navigator.clipboard.writeText(code).then(() => {
    const original = btn.textContent;
    btn.textContent = "Copiado!";
    setTimeout(() => { btn.textContent = original; }, 1500);
  });
});

function renderAll(history) {
  chatEl.innerHTML = "";
  history.forEach((m, i) => renderBubble(m.role, m.content, i));
  if (history.length === 0) {
    renderBubble("assistant", "Sistemas on-line. Bom te ver, senhor. Em que posso ajudar hoje?");
    renderSuggestions();
  }
}

// ---------- Sugestões rápidas (só aparecem numa conversa vazia) ----------
// Ajudam quem nunca usou o Jarvis a descobrir, de cara, algumas coisas
// que ele já sabe fazer de verdade (holograma, sites, estudos, clima).
function renderSuggestions() {
  const options = [
    { label: "🛰 Holograma real da Torre Eiffel", text: "Crie um holograma real da Torre Eiffel" },
    { label: "✨ Criar um site pro meu negócio", text: "Quero criar um site para o meu negócio" },
    { label: "🔺 Me ajuda com matemática", text: "Me ajuda a resolver uma questão de matemática" },
    { label: "🌦 Clima agora", text: "Como está o tempo agora?" },
  ];
  const wrap = document.createElement("div");
  wrap.className = "jarvis-suggestions";
  options.forEach((opt) => {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "jarvis-suggestion-chip";
    btn.textContent = opt.label;
    btn.addEventListener("click", () => {
      wrap.remove();
      inputEl.value = opt.text;
      sendMessage();
    });
    wrap.appendChild(btn);
  });
  chatEl.appendChild(wrap);
}

let history = loadHistory();
renderAll(history);

// ---------- HUD (o "arc reactor") ----------
// Estados completos do item 3 do briefing: IDLE (state=null), LISTENING,
// THINKING (interpretando o pedido), PROCESSING (trabalho em segundo
// plano mais longo, ex: job de site), EXECUTING (rodando uma ferramenta
// concreta), SPEAKING, SUCCESS e ERROR (feedback rápido no fim de uma
// ação, depois volta sozinho pro estado neutro).
const HUD_STATES = ["listening", "thinking", "processing", "executing", "speaking", "success", "error"];
let hudFlashTimer = null;
// Mapeia os estados internos do HUD para as 4 cores do Holograma global
// (azul/verde/vermelho/dourado) descritas no briefing do produto.
const HOLO_STATE_MAP = {
  null: "idle", undefined: "idle",
  listening: "thinking", thinking: "thinking", processing: "thinking", executing: "thinking",
  speaking: "waiting", success: "waiting",
  error: "alert",
};
function syncHoloStatus(state) {
  if (window.NeuralBg) window.NeuralBg.setState(state);
  if (!window.HoloStatus) return;
  const mapped = HOLO_STATE_MAP[state] || "waiting";
  if (mapped === "idle") window.HoloStatus.idle();
  else window.HoloStatus.set(mapped);
}

function setHudState(state, text) {
  if (hudFlashTimer) { clearTimeout(hudFlashTimer); hudFlashTimer = null; }
  orb.classList.remove(...HUD_STATES);
  if (state) orb.classList.add(state);
  statusEl.textContent = text || "";
  stopBtn.classList.toggle("hidden", state !== "speaking" && state !== "thinking" && state !== "executing");
  syncHoloStatus(state);
}
// Mostra um estado por um instante (sucesso/erro de uma ação pontual) e
// depois volta pro estado neutro sozinho — sem isso, cada callsite teria
// que agendar o próprio setTimeout(setHudState(null, ...)).
function flashHudState(state, text, holdMs) {
  if (hudFlashTimer) clearTimeout(hudFlashTimer);
  orb.classList.remove(...HUD_STATES);
  orb.classList.add(state);
  statusEl.textContent = text || "";
  stopBtn.classList.add("hidden");
  syncHoloStatus(state);
  hudFlashTimer = setTimeout(() => {
    hudFlashTimer = null;
    setHudState(null, "Ao seu dispor.");
  }, holdMs || 1600);
}

stopBtn.addEventListener("click", () => {
  if (activeRequestController && isSending) activeRequestController.abort();
  if (window.speechSynthesis) window.speechSynthesis.cancel();
  try { recognition && recognition.stop(); } catch (e) {}
  setHudState(null, "Ao seu dispor.");
});

// ---------- Voz (falar a resposta) ----------
// Deixamos o usuário escolher, entre as vozes que o navegador/celular
// já tem instaladas, a que mais parece um assistente tipo Jarvis. Por
// padrão tentamos achar uma voz em português e ajustamos tom/velocidade
// para soar mais calmo e "robótico-elegante".
let availableVoices = [];
let voicesReady = false;

// Nomes que costumam indicar uma voz masculina nas listas de vozes do
// navegador/celular (varia por fabricante, por isso a lista é grande).
const MALE_VOICE_HINTS = /\b(male|homem|masculin\w*|ricardo|daniel|felipe|bruno|thiago|marcos|antonio|antônio|rodrigo|diego|leandro|fabio|fábio|paulo|jorge|carlos|joao|joão|pedro|miguel|hans|george|guy|david|mark|roger|fred)\b/i;
const FEMALE_VOICE_HINTS = /\b(female|mulher|feminin\w*|luciana|camila|vitoria|vitória|helena|joana|maria|fernanda|leticia|letícia|raquel|patricia|patrícia|samantha|karen|victoria|susan|zira|siri)\b/i;

function pickDefaultVoiceIndex(voices) {
  const pt = (v) => v.lang && v.lang.toLowerCase().startsWith("pt");

  // 1) Prioridade máxima: voz em português que pareça masculina pelo nome.
  let idx = voices.findIndex((v) => pt(v) && MALE_VOICE_HINTS.test(v.name) && !FEMALE_VOICE_HINTS.test(v.name));
  if (idx !== -1) return idx;

  // 2) No Android, as vozes "Google" costumam soar melhor que a voz
  // padrão do sistema, mesmo quando o nome não indica o gênero.
  idx = voices.findIndex(
    (v) => pt(v) && /google/i.test(v.name) && !FEMALE_VOICE_HINTS.test(v.name)
  );
  if (idx !== -1) return idx;

  // 3) Qualquer voz em português que não pareça explicitamente feminina.
  idx = voices.findIndex((v) => pt(v) && !FEMALE_VOICE_HINTS.test(v.name));
  if (idx !== -1) return idx;

  // 4) Por fim, qualquer voz em português (mesmo que feminina) — melhor
  // que cair pra um idioma errado. O tom mais grave nas configurações
  // ajuda a disfarçar quando só existe voz feminina no aparelho.
  idx = voices.findIndex((v) => pt(v));
  return idx >= 0 ? idx : 0;
}

// ---------- Tom e velocidade da voz (ajustáveis, salvos por navegador) ----------
const PITCH_KEY = "tf_jarvis_voice_pitch";
const RATE_KEY = "tf_jarvis_voice_rate";
// Ajustado para soar mais perto do J.A.R.V.I.S. do Homem de Ferro: um
// tom mais grave e um ritmo levemente mais pausado/measured do que o
// padrão do navegador. Isso é o limite real do que dá pra fazer com a
// voz sintetizada do próprio navegador/celular (Web Speech API) — não
// existe uma voz "oficial" do Jarvis disponível nesse sistema, mas isso
// aproxima bastante, principalmente combinado com uma voz "Google"/
// "Microsoft" em português já preferida automaticamente acima.
const DEFAULT_PITCH = 0.68; // mais grave = mais "masculino" mesmo em voz feminina
const DEFAULT_RATE = 0.92;  // ritmo mais calmo e confiante, menos "robô lendo rápido"

const pitchSlider = document.getElementById("voice-pitch");
const rateSlider = document.getElementById("voice-rate");

function getVoicePitch() {
  const saved = parseFloat(localStorage.getItem(PITCH_KEY));
  return isNaN(saved) ? DEFAULT_PITCH : saved;
}
function getVoiceRate() {
  const saved = parseFloat(localStorage.getItem(RATE_KEY));
  return isNaN(saved) ? DEFAULT_RATE : saved;
}

if (pitchSlider) {
  pitchSlider.value = getVoicePitch();
  pitchSlider.addEventListener("input", () => {
    localStorage.setItem(PITCH_KEY, pitchSlider.value);
  });
}
if (rateSlider) {
  rateSlider.value = getVoiceRate();
  rateSlider.addEventListener("input", () => {
    localStorage.setItem(RATE_KEY, rateSlider.value);
  });
}

function populateVoiceList() {
  if (!window.speechSynthesis) return;
  const voices = window.speechSynthesis.getVoices();
  if (!voices.length) return; // Android às vezes demora — tentamos de novo depois
  availableVoices = voices;
  voicesReady = true;
  if (!voiceSelect) return;

  const saved = localStorage.getItem(VOICE_KEY);
  voiceSelect.innerHTML = "";
  availableVoices.forEach((v, i) => {
    const opt = document.createElement("option");
    opt.value = i;
    opt.textContent = `${v.name} (${v.lang})`;
    voiceSelect.appendChild(opt);
  });

  const defaultIndex = pickDefaultVoiceIndex(availableVoices);
  voiceSelect.value = (saved !== null && availableVoices[saved]) ? saved : defaultIndex;
}

if (window.speechSynthesis) {
  populateVoiceList();
  window.speechSynthesis.onvoiceschanged = populateVoiceList;
  // Fallback: em muitos celulares Android o evento onvoiceschanged não
  // dispara a tempo (ou nunca dispara), deixando a lista de vozes vazia.
  // Insistimos por alguns segundos até a lista aparecer.
  let voiceRetries = 0;
  const voiceRetryTimer = setInterval(() => {
    voiceRetries++;
    if (voicesReady || voiceRetries > 20) {
      clearInterval(voiceRetryTimer);
      return;
    }
    populateVoiceList();
  }, 300);
}

if (voiceSelect) {
  voiceSelect.addEventListener("change", () => {
    localStorage.setItem(VOICE_KEY, voiceSelect.value);
  });
}

// "Destrava" a síntese de voz no primeiro toque na página. No Chrome do
// Android, a primeira chamada a speechSynthesis.speak() só funciona de
// verdade se acontecer dentro de uma interação real do usuário — sem
// isso, a primeira resposta do Jarvis fica muda.
let speechUnlocked = false;
function unlockSpeech() {
  if (speechUnlocked || !window.speechSynthesis) return;
  speechUnlocked = true;
  const unlockUtter = new SpeechSynthesisUtterance(" ");
  unlockUtter.volume = 0;
  window.speechSynthesis.speak(unlockUtter);
}
document.addEventListener("click", unlockSpeech, { once: true, passive: true });
document.addEventListener("touchend", unlockSpeech, { once: true, passive: true });

// Contorna um bug conhecido do Chrome/Android: falas mais longas
// (cerca de 15s ou mais) travam sozinhas no meio da frase. Um
// pause/resume periódico mantém o motor de voz "acordado" até o fim.
let keepAliveTimer = null;
function startKeepAlive() {
  stopKeepAlive();
  keepAliveTimer = setInterval(() => {
    if (window.speechSynthesis.speaking && !window.speechSynthesis.paused) {
      window.speechSynthesis.pause();
      window.speechSynthesis.resume();
    }
  }, 12000);
}
function stopKeepAlive() {
  if (keepAliveTimer) {
    clearInterval(keepAliveTimer);
    keepAliveTimer = null;
  }
}

// Divide o texto em pedaços curtos (por frase, respeitando um teto de
// caracteres) antes de mandar pro speechSynthesis. Utterances muito
// longas são um bug conhecido do Chrome/Android: às vezes o motor de
// voz trava no meio e nunca dispara onend NEM onerror — o HUD ficava
// preso para sempre em "Processando..." porque nada mais avisava que
// aquela fala tinha morrido. Falando em pedaços pequenos e encadeados,
// cada trecho é curto o bastante para nunca disparar esse bug, e se um
// pedaço falhar mesmo assim, só ele é perdido — a fala continua.
const SPEECH_CHUNK_MAX_CHARS = 180;

function splitTextForSpeech(text) {
  const sentences = text
    .replace(/\s+/g, " ")
    .trim()
    .split(/(?<=[.!?;:])\s+/);

  const chunks = [];
  let current = "";
  for (const sentence of sentences) {
    if (!sentence) continue;
    if (sentence.length > SPEECH_CHUNK_MAX_CHARS) {
      // Frase sozinha já é longa demais (ex: parágrafo sem pontuação) —
      // corta em pedaços de tamanho fixo como último recurso.
      if (current) { chunks.push(current); current = ""; }
      for (let i = 0; i < sentence.length; i += SPEECH_CHUNK_MAX_CHARS) {
        chunks.push(sentence.slice(i, i + SPEECH_CHUNK_MAX_CHARS));
      }
      continue;
    }
    if ((current + " " + sentence).trim().length > SPEECH_CHUNK_MAX_CHARS) {
      if (current) chunks.push(current);
      current = sentence;
    } else {
      current = (current + " " + sentence).trim();
    }
  }
  if (current) chunks.push(current);
  return chunks.filter(Boolean);
}

let speechQueue = [];
let speechQueueIndex = 0;
let speechWatchdog = null;
let speechStartWatchdog = null;

function clearSpeechWatchdog() {
  if (speechWatchdog) { clearTimeout(speechWatchdog); speechWatchdog = null; }
}
function clearSpeechStartWatchdog() {
  if (speechStartWatchdog) { clearTimeout(speechStartWatchdog); speechStartWatchdog = null; }
}

// Estima quanto tempo um trecho leva pra ser falado, a partir do tamanho
// do texto e da velocidade escolhida. Antes o teto era fixo em 7s pra
// qualquer trecho — e um trecho um pouco mais longo (ou uma voz mais
// lenta) simplesmente estourava esse teto no meio da frase, cancelando a
// fala e pulando direto pro próximo pedaço. Isso é o que fazia o Jarvis
// "engolir" partes do texto. Agora o teto acompanha o tamanho real do
// trecho, com uma margem generosa por cima.
function estimateSpeechDurationMs(text, rate) {
  const charsPerSecond = 14 * (rate || 1);
  const estimated = (text.length / charsPerSecond) * 1000;
  return Math.max(4000, estimated + 4000);
}

function finishSpeech() {
  clearSpeechWatchdog();
  stopKeepAlive();
  speechQueue = [];
  speechQueueIndex = 0;
  setHudState(null, "Ao seu dispor.");
  // Modo "Homem de Ferro": depois de falar, já volta a ouvir sozinho
  if (continuousMode.checked) startListening();
}

function speakNextChunk() {
  if (speechQueueIndex >= speechQueue.length) {
    finishSpeech();
    return;
  }
  const chunkText = speechQueue[speechQueueIndex];
  speechQueueIndex++;

  const utter = new SpeechSynthesisUtterance(chunkText);
  const idx = voiceSelect ? parseInt(voiceSelect.value, 10) : NaN;
  const chosen = (!isNaN(idx) && availableVoices[idx]) ? availableVoices[idx] : null;
  if (chosen) {
    utter.voice = chosen;
    utter.lang = chosen.lang;
  } else {
    utter.lang = "pt-BR";
  }
  // Tom mais grave (masculino) e ritmo calmo, com uma variação bem
  // pequena e aleatória a cada trecho — fala 100% constante soa
  // robótica; um humano de verdade nunca fala duas frases com o tom e a
  // velocidade idênticos.
  const basePitch = getVoicePitch();
  const baseRate = getVoiceRate();
  utter.pitch = Math.max(0, Math.min(2, basePitch + (Math.random() - 0.5) * 0.06));
  utter.rate = Math.max(0.1, Math.min(2, baseRate + (Math.random() - 0.5) * 0.05));

  clearSpeechStartWatchdog();
  clearSpeechWatchdog();

  // Watchdog "de partida": só cuida do caso do motor de voz nunca chamar
  // onstart (trava silenciosa antes de começar). Não deve ser confundido
  // com o tempo de fala em si.
  speechStartWatchdog = setTimeout(() => {
    window.speechSynthesis.cancel();
    speakNextChunk();
  }, 6000);

  utter.onstart = () => {
    clearSpeechStartWatchdog();
    setHudState("speaking", "Falando...");
    startKeepAlive();
    // Watchdog "de duração": só é armado depois que a fala realmente
    // começou, e o prazo é calculado a partir do tamanho do próprio
    // trecho — assim uma frase mais longa tem tempo de terminar em vez
    // de ser cortada e pulada no meio.
    speechWatchdog = setTimeout(() => {
      window.speechSynthesis.cancel();
      speakNextChunk();
    }, estimateSpeechDurationMs(chunkText, utter.rate));
  };
  utter.onend = () => {
    clearSpeechStartWatchdog();
    clearSpeechWatchdog();
    speakNextChunk();
  };
  utter.onerror = () => {
    clearSpeechStartWatchdog();
    clearSpeechWatchdog();
    speakNextChunk();
  };
  window.speechSynthesis.speak(utter);
}

function speak(text) {
  if (!autoVoice.checked || !window.speechSynthesis) {
    // Sem voz ativada: o HUD tinha ficado preso em "Processando..." aqui
    // também, já que nada mais o tirava desse estado nesse caminho.
    setHudState(null, "Ao seu dispor.");
    if (continuousMode.checked) startListening();
    return;
  }
  // Para o microfone antes de falar, senão no Android o reconhecimento
  // às vezes capta a própria voz do Jarvis e entra em loop.
  try { recognition && recognition.stop(); } catch (e) {}
  window.speechSynthesis.cancel();
  clearSpeechWatchdog();

  speechQueue = splitTextForSpeech(stripMarkdownForSpeech(text));
  speechQueueIndex = 0;
  if (speechQueue.length === 0) { finishSpeech(); return; }
  speakNextChunk();
}

// ---------- Comando "crie um holograma de X" direto no chat ----------
// Detecta local (sem gastar chamada de IA) e aciona o projetor 3D
// embutido logo abaixo do chat (window.jarvisHolograma, de hologram.js).
//
// "holograma" tolera erro de digitação/ditado comum ("hologramo",
// "holograma3d" etc.) e a extração do assunto ignora um monte de
// verbos/enchimento de frase ("queria", "poderia", "cria", "bota",
// "pra mim", "aí", "então"...) para casar com frases bem mais
// naturais e desorganizadas, não só um template rígido de uma frase
// só.
const HOLO_WORD = /holog+ram+[ao]?/i; // holograma / hologramo / hologramaaa / holograma3d etc.

// Palavras de enchimento/verbos comuns que aparecem ANTES ou DEPOIS do
// assunto e não fazem parte dele — removidas na limpeza do texto
// extraído, em qualquer ordem, quantas vezes aparecerem.
const HOLO_FILLERS = [
  "por favor", "pra mim", "para mim", "pfvr", "pf",
  "eu queria", "eu quero", "eu gostaria de", "queria", "gostaria",
  "quero", "poderia", "pode", "consegue", "d[aá]\\s+pra",
  "cria", "crie", "criar", "gere", "gera", "gerar",
  "faz", "faça", "faca", "fazer", "monta", "monte", "montar",
  "mostra", "mostre", "mostrar", "projeta", "projete", "projetar",
  "materializa", "materialize", "bota", "bote", "coloca", "coloque",
  "p[oõ]e", "ponha", "abre", "abra", "ativa", "ative", "liga", "ligue",
  "manda", "mande", "traz", "traga", "quero ver", "deixa ver", "ver",
  "a[ií]", "ent[aã]o", "agora", "j[aá]", "de novo", "aqui",
  "um", "uma", "o", "a", "esse", "essa", "isso",
];
const HOLO_FILLER_RE = new RegExp(
  "\\b(?:" + HOLO_FILLERS.join("|") + ")\\b", "gi"
);

function _cleanHoloSubject(raw) {
  if (!raw) return "";
  let s = raw.trim().replace(/[.!?]+$/, "");
  // remove o próprio termo "holograma/hologramo (3d)" caso tenha
  // sobrado dentro do trecho extraído
  s = s.replace(new RegExp(HOLO_WORD.source + "(?:\\s*3d)?", "gi"), " ");
  s = s.replace(/\bde\s+verdade\b/gi, " ");
  s = s.replace(HOLO_FILLER_RE, " ");
  s = s.replace(/\s{2,}/g, " ").trim();
  s = s.replace(/^(?:de|do|da|dos|das|em|no|na|pra|para)\s+/i, "").trim();
  return s;
}

// Sinal de que a mensagem é, na verdade, feedback/reclamação/conversa
// sobre o PRÓPRIO Jarvis ou o holograma (bug, pedido de melhoria) —
// não um comando pra criar um holograma agora. Evita falso positivo
// tipo "deu erro no holograma, você pode melhorar o Jarvis..." virar
// um pedido de holograma chamado "deu erro".
const HOLO_META_TALK_RE = /\b(bug(?:ou)?|deu\s+erro|erro|n[aã]o\s+funciona|n[aã]o\s+consegui|quebrou|travou|sumiu|problema|consert[ae]|arruma|ajeita|corrig[ae]|melhora[r]?|melhorar|piorou|lento|lenta|ferramentas?)\b/i;

function detectHologramCommand(text) {
  const t = text.trim();
  if (!HOLO_WORD.test(t)) return null;
  // Mensagens longas e/ou de feedback sobre o app não são comandos —
  // um comando de verdade é curto e direto.
  if (t.length > 140 || HOLO_META_TALK_RE.test(t)) return null;

  let m = t.match(new RegExp(HOLO_WORD.source + "(?:\\s+3d)?\\s+(?:de|do|da|dos|das|pra|para)\\s+(.+)", "i"));
  if (m && m[1]) {
    const cleaned = _cleanHoloSubject(m[1]);
    if (cleaned) return cleaned;
  }

  m = t.match(new RegExp("(.+?)\\s+(?:em|no)\\s+" + HOLO_WORD.source, "i"));
  if (m && m[1] && m[1].trim().split(/\s+/).length <= 6) {
    const cleaned = _cleanHoloSubject(m[1]);
    if (cleaned) return cleaned;
  }

  m = t.match(new RegExp(HOLO_WORD.source + "\\s*[:\\-]?\\s*(.+)", "i"));
  if (m && m[1] && m[1].trim().length > 1) {
    const cleaned = _cleanHoloSubject(m[1]);
    if (cleaned) return cleaned;
  }

  // Última tentativa, bem mais solta: a frase inteira menos o próprio
  // termo "holograma" e as palavras de enchimento — cobre frases
  // desorganizadas tipo "jarvis queria tá holograma pra mim aí ele
  // cria [de/do assunto]" que não batem em nenhum padrão acima mas
  // ainda têm um assunto curto e reconhecível sobrando.
  const loose = _cleanHoloSubject(t);
  if (loose && loose.length > 1 && loose.split(/\s+/).length <= 6) return loose;

  return null; // nada reconhecível sobrando — deixa a IA responder normalmente
}

// ---------- FASE 7: Jarvis como controlador central do holograma ----------
// Depois que o holograma já está projetado, o usuário passa a dar
// comandos de AJUSTE em vez de criação ("gire mais rápido", "mude a cor
// pra azul", "aumenta o zoom") — isto aqui é a camada de "ferramentas"
// do Jarvis: um conjunto fixo e seguro de ações (setSpeed, setScale,
// setColors, applyDelta...) já expostas por hologram.js. O Jarvis NUNCA
// toca o DOM/three.js diretamente — só reconhece a intenção aqui e
// chama a função de ferramenta correspondente, com feedback falado,
// exatamente como pedido na seção 9 do briefing (comandos seguros e
// definidos pelo sistema, não controle livre da IA sobre a interface).
const HOLO_COLOR_MAP = {
  azul: ["#00e5ff", "#0057ff"], ciano: ["#00e5ff", "#18ffff"],
  vermelho: ["#ff3b3b", "#ff7043"], vermelha: ["#ff3b3b", "#ff7043"],
  verde: ["#00ff9d", "#00e676"], roxo: ["#b026ff", "#7c4dff"],
  violeta: ["#b026ff", "#7c4dff"], amarelo: ["#ffd600", "#ffab00"],
  laranja: ["#ff8a00", "#ff5252"], rosa: ["#ff4da6", "#ff79c6"],
  magenta: ["#ff00e5", "#ff4da6"], branco: ["#e8faff", "#ffffff"],
  dourado: ["#ffd700", "#ffb300"], ouro: ["#ffd700", "#ffb300"],
  prata: ["#c0c0c0", "#e0e0e0"],
};

// Comando de controle é sempre curto e direto — frases longas seguem
// para a IA normalmente, então não interceptamos nada fora do padrão.
function detectHologramControlCommand(text) {
  if (!window.jarvisHolograma || typeof window.jarvisHolograma.isActive !== "function" || !window.jarvisHolograma.isActive()) return null;
  const t = text.trim().toLowerCase();
  if (!t || t.length > 60) return null;

  if (/\b(pare|para|pausa|pause)\b[\s\w]*\bgir/.test(t) || /\b(pare|para|pausa|pause)\s+(a\s+)?rota[cç][aã]o\b/.test(t)) return { action: "pause" };
  if (/^\s*gire\s*$/.test(t) || /\bcontinue\s+girando\b/.test(t) || /\bretome\s+(a\s+)?rota[cç][aã]o\b/.test(t) || /\bgire\s+de\s+novo\b/.test(t)) return { action: "resume" };
  if (/\bmais\s+r[aá]pido\b|\bacelera\b|\bacelere\b|\baumente?\s+a\s+velocidade\b/.test(t)) return { action: "faster" };
  if (/\bmais\s+devagar\b|\bdesacelera\b|\bdesacelere\b|\bmais\s+lento\b|\bdiminu[ai]\s+a\s+velocidade\b/.test(t)) return { action: "slower" };
  if (/\baumente?\s+o?\s*zoom\b|\baproxim[ea]\b|\bmais\s+perto\b/.test(t)) return { action: "zoomIn" };
  if (/\bdiminu[ai]\s+o?\s*zoom\b|\bafast[ea]\b|\bmais\s+longe\b/.test(t)) return { action: "zoomOut" };
  if (/\baumente?\s+o\s+tamanho\b|\bfique\s+maior\b|^\s*maior\s*$/.test(t)) return { action: "scaleUp" };
  if (/\bdiminu[ai]\s+o\s+tamanho\b|\bfique\s+menor\b|^\s*menor\s*$/.test(t)) return { action: "scaleDown" };
  if (/\bmais\s+part[ií]culas\b/.test(t)) return { action: "particlesUp" };
  if (/\bmenos\s+part[ií]culas\b/.test(t)) return { action: "particlesDown" };
  if (/\blig(a|ue)\s+(a\s+)?grade\b|\bmostre?\s+a\s+grade\b/.test(t)) return { action: "gridOn" };
  if (/\bdesli(ga|gue)\s+(a\s+)?grade\b|\besconda\s+a\s+grade\b/.test(t)) return { action: "gridOff" };
  if (/\blig(a|ue)\s+o?\s*ambiente\b/.test(t)) return { action: "ambientOn" };
  if (/\bdesli(ga|gue)\s+o?\s*ambiente\b/.test(t)) return { action: "ambientOff" };
  if (/\breset[ae]\s+(a\s+)?vis[aã]o\b|\bcentraliz[ae]\b|\bvolte\s+ao\s+centro\b/.test(t)) return { action: "reset" };
  if (/\bfeche\s+o?\s*(holog+ram[ao]?|projetor)\b/.test(t)) return { action: "close" };

  const colorMatch = t.match(/\bmude?\s+a\s+cor\s+(?:para|pra)\s+([a-zçãáéíóúõâê ]+)$|\bcor\s+([a-zçãáéíóúõâê]+)\b/);
  if (colorMatch) {
    const name = (colorMatch[1] || colorMatch[2] || "").trim().replace(/[.!?]+$/, "");
    if (HOLO_COLOR_MAP[name]) return { action: "color", param: name };
  }
  return null;
}

// Executa a ação já validada acima chamando só as funções que
// hologram.js expõe publicamente (a "caixa de ferramentas" do
// holograma) e devolve a frase que o Jarvis vai falar/mostrar.
function executeHologramControlCommand(cmd) {
  const w = window.jarvisHolograma;
  if (!w) return "Não há nenhum holograma ativo agora, senhor.";
  const s = (w.getSettings && w.getSettings()) || {};
  switch (cmd.action) {
    case "pause": w.setAutoRotate(false); return "Rotação pausada, senhor.";
    case "resume": w.setAutoRotate(true); return "Girando novamente.";
    case "faster": w.setSpeed(Math.min(6, (s.speed || 1) * 1.6)); w.setAutoRotate(true); return "Acelerando a rotação.";
    case "slower": w.setSpeed(Math.max(0.1, (s.speed || 1) * 0.6)); return "Desacelerando a rotação.";
    case "zoomIn": w.applyDelta(0, 0, -1.6, 0, 0); return "Aproximando.";
    case "zoomOut": w.applyDelta(0, 0, 1.6, 0, 0); return "Afastando.";
    case "scaleUp": w.setScale(Math.min(3, (s.scale || 1) * 1.25)); return "Aumentando o tamanho.";
    case "scaleDown": w.setScale(Math.max(0.2, (s.scale || 1) * 0.8)); return "Diminuindo o tamanho.";
    case "particlesUp": w.setParticleDensity(Math.min(3, (s.particleDensity || 1) * 1.6 || 0.5)); return "Mais partículas no ar, senhor.";
    case "particlesDown": w.setParticleDensity(Math.max(0, (s.particleDensity || 1) * 0.4)); return "Reduzindo as partículas.";
    case "gridOn": w.toggleGrid(true); return "Grade ativada.";
    case "gridOff": w.toggleGrid(false); return "Grade desativada.";
    case "ambientOn": w.toggleAmbient(true); return "Modo ambiente ativado.";
    case "ambientOff": w.toggleAmbient(false); return "Modo ambiente desativado.";
    case "reset": w.resetView(); return "Visão centralizada.";
    case "close": w.close(); return "Fechando o holograma.";
    case "color": {
      const pair = HOLO_COLOR_MAP[cmd.param];
      w.setColors(pair[0], pair[1]);
      return `Cor alterada para ${cmd.param}, senhor.`;
    }
    default: return "Feito, senhor.";
  }
}

// ---------- Comando "holograma real de X" / "coloca X no holograma" ----------
// Diferente de detectHologramCommand(): este dispara o modo com dados
// reais do OpenStreetMap (coordenadas, relevo, mapa) em vez do
// terreno procedural — para "ver um lugar de verdade entrar" no
// holograma.
function detectRealPlaceCommand(text) {
  const t = text.trim();
  const mentionsHolo = new RegExp(HOLO_WORD.source + "|mapa|lugar|local", "i").test(t);
  const mentionsReal = /\breal\b/i.test(t) || /openstreetmap|open\s*street\s*map|google\s*maps/i.test(t);
  if (!mentionsHolo || !mentionsReal) return null;
  if (t.length > 140 || HOLO_META_TALK_RE.test(t)) return null;

  const clean = (s) => _cleanHoloSubject(s.replace(/^de\s+verdade\s+/i, ""));

  let m = t.match(new RegExp("(?:" + HOLO_WORD.source + "|mapa|lugar|local)\\s+real(?:\\s+(?:do|da|de|dos|das|em|pra|para))?\\s+(.+)", "i"));
  if (m && m[1]) {
    const cleaned = clean(m[1]);
    if (cleaned) return cleaned;
  }

  m = t.match(new RegExp("(?:coloca|coloque|p[oõ]e|ponha|bota|traz|traga|mostra|mostre|projeta|projete|quero ver)\\s+(.+?)\\s+(?:de verdade\\s+)?no\\s+(?:" + HOLO_WORD.source + "|mapa)(?:\\s+real)?", "i"));
  if (m && m[1]) {
    const cleaned = clean(m[1]);
    if (cleaned) return cleaned;
  }

  m = t.match(/(?:openstreetmap|open\s*street\s*map|google\s*maps)\s+(?:d[eo]|em|pra|para)?\s*(.+)/i);
  if (m && m[1]) {
    const cleaned = clean(m[1]);
    if (cleaned) return cleaned;
  }

  return null;
}

let isSending = false;
let jarvisRequestStartedAt = 0;
let jarvisRequestSeq = 0;

async function sendMessage() {
  if (isSending) return; // evita envio duplicado (ex: Enter + clique quase juntos)
  const text = inputEl.value.trim();
  const attachment = pendingAttachment;
  if (!text && !attachment) return;
  if (!attachment && typeof tryCyberVoiceNav === "function" && tryCyberVoiceNav(text)) {
    inputEl.value = "";
    return;
  }
  isSending = true;
  inputEl.value = "";
  pendingAttachment = null;
  renderAttachmentPreview();

  // Se o usuário só anexou a foto/arquivo sem escrever nada, mandamos
  // um pedido padrão pro Jarvis saber o que fazer com o anexo.
  const displayText = text || (attachment
    ? (attachment.kind === "image" ? "Dá uma olhada nessa imagem, por favor." : "Dá uma olhada nesse arquivo, por favor.")
    : "");
  let historyContent = displayText;
  if (attachment) historyContent += `\n\n[📎 anexo enviado: ${attachment.name}]`;
  history.push({ role: "user", content: historyContent });

  if (attachment) renderUserBubbleWithAttachment(displayText, attachment);
  else renderBubble("user", displayText);
  saveHistory(history);

  // Foto anexada + pedido de holograma na mesma mensagem (ex: "cria um
  // holograma dessa foto") — materializa o holograma de profundidade a
  // partir dos pixels da própria imagem (ver hologram.js:
  // generateFromPhoto/buildFromPhoto), em vez de só descrever a foto
  // no chat como um anexo comum faria.
  if (attachment && attachment.kind === "image" && window.jarvisHolograma && HOLO_WORD.test(text) && !HOLO_META_TALK_RE.test(text)) {
    sendBtn.disabled = true;
    setHudState("thinking", "Materializando holograma a partir da foto...");
    let ok = false;
    try {
      ok = await window.jarvisHolograma.generateFromPhoto(attachment.dataUrl);
    } catch (e) {
      ok = false;
    }
    const reply = ok
      ? "Pronto, senhor. Holograma materializado a partir da sua foto — relevo real construído a partir dos próprios pixels da imagem, com a foto projetada como textura holográfica por cima. Arraste para girar, role para zoom."
      : "Não consegui montar o holograma a partir dessa foto agora, senhor — seu navegador pode não ter aceleração 3D (WebGL) disponível.";
    history.push({ role: "assistant", content: reply });
    saveHistory(history);
    renderBubble("assistant", reply);
    speak(reply);
    setHudState(null, "Ao seu dispor.");
    sendBtn.disabled = false;
    isSending = false;
    return;
  }

  // Anexos disparam sempre a resposta normal da IA (não os atalhos de
  // holograma abaixo), já que o pedido é revisar a foto/arquivo.
  if (!attachment) {
  // TOOL ROUTER: se a frase é um pedido de ferramenta (auditar, DNS, TLS,
  // portas, logs, segredos…), o Jarvis executa a ferramenta de verdade no
  // backend, explica, mostra progresso/resultado e diagnostica erros.
  // Devolve false quando não é pedido de ferramenta -> segue o chat normal.
  if (window.JarvisTools) {
    sendBtn.disabled = true;
    let handled = false;
    try {
      handled = await window.JarvisTools.handle(text, {
        chatEl, setHudState, flashHudState, speak, history, saveHistory, renderBubble,
      });
    } catch (e) {
      handled = false;
    }
    if (handled) {
      sendBtn.disabled = false;
      isSending = false;
      return;
    }
    sendBtn.disabled = false;
  }
  // FASE 7: comando de AJUSTE sobre um holograma já ativo (girar mais
  // rápido, mudar cor, zoom, grade...) — checado antes de tudo porque é
  // instantâneo (sem IA) e só se aplica quando já existe algo projetado.
  const holoControl = detectHologramControlCommand(text);
  if (holoControl) {
    sendBtn.disabled = true;
    setHudState("executing", "Executando comando...");
    const reply = executeHologramControlCommand(holoControl);
    history.push({ role: "assistant", content: reply });
    saveHistory(history);
    renderBubble("assistant", reply);
    speak(reply);
    setHudState(null, "Ao seu dispor.");
    sendBtn.disabled = false;
    isSending = false;
    return;
  }

  const realPlace = detectRealPlaceCommand(text);
  if (realPlace && window.jarvisHolograma) {
    sendBtn.disabled = true;
    setHudState("thinking", "Buscando lugar real no OpenStreetMap...");
    let ok = false;
    try {
      ok = await window.jarvisHolograma.generateRealPlace(realPlace);
    } catch (e) {
      ok = false;
    }
    const reply = ok
      ? `Pronto, senhor. "${realPlace}" materializado no holograma com coordenadas, relevo e mapa reais do OpenStreetMap — arraste para girar, role para zoom.`
      : `Não consegui trazer "${realPlace}" de verdade agora, senhor — pode ser a conexão com a internet, ou o serviço do OpenStreetMap está temporariamente indisponível. Tente de novo em instantes.`;
    history.push({ role: "assistant", content: reply });
    saveHistory(history);
    renderBubble("assistant", reply);
    speak(reply);
    setHudState(null, "Ao seu dispor.");
    sendBtn.disabled = false;
    isSending = false;
    return;
  }

  const holoSubject = detectHologramCommand(text);
  if (holoSubject && window.jarvisHolograma) {
    sendBtn.disabled = true;
    setHudState("thinking", "Projetando holograma...");
    let ok = false;
    try {
      ok = await window.jarvisHolograma.generate(holoSubject);
    } catch (e) {
      ok = false;
    }
    const reply = ok
      ? `Já estou nisso, senhor. Holograma de "${holoSubject}" projetado logo abaixo — arraste para girar, e use a roda do mouse para o zoom.`
      : "Não consegui carregar o projetor holográfico agora, senhor — verifique a conexão com a internet.";
    history.push({ role: "assistant", content: reply });
    saveHistory(history);
    renderBubble("assistant", reply);
    speak(reply);
    setHudState(null, "Ao seu dispor.");
    sendBtn.disabled = false;
    isSending = false;
    return;
  }

  // ---------- Fallback via IA para frases fora do padrão ----------
  // Os atalhos acima são locais (rápidos, sem custo) mas seguem
  // padrões de frase fixos. Se a mensagem menciona holograma só de
  // leve e não é claramente feedback/reclamação sobre o app, deixamos
  // a própria IA decidir se é um pedido de holograma antes de tratar
  // como bate-papo normal — assim frases desorganizadas ou bem
  // diferentes do esperado também funcionam, não só um jeito certo de
  // falar.
  const mightBeHolo = HOLO_WORD.test(text) && !HOLO_META_TALK_RE.test(text) && text.length <= 220 && window.jarvisHolograma;
  if (mightBeHolo) {
    setHudState("thinking", "Entendendo o pedido...");
    try {
      const resp = await fetch("/api/jarvis/holograma-intent", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      const intent = await resp.json();
      if (resp.ok && intent.quer_holograma && intent.assunto) {
        sendBtn.disabled = true;
        setHudState("thinking", "Projetando holograma...");
        let ok = false;
        try {
          ok = intent.modo === "real"
            ? await window.jarvisHolograma.generateRealPlace(intent.assunto)
            : await window.jarvisHolograma.generate(intent.assunto);
        } catch (e) {
          ok = false;
        }
        const reply = ok
          ? `Já estou nisso, senhor. Holograma de "${intent.assunto}" projetado logo abaixo — arraste para girar, e use a roda do mouse para o zoom.`
          : `Não consegui projetar "${intent.assunto}" agora, senhor — verifique a conexão com a internet e tente de novo.`;
        history.push({ role: "assistant", content: reply });
        saveHistory(history);
        renderBubble("assistant", reply);
        speak(reply);
        setHudState(null, "Ao seu dispor.");
        sendBtn.disabled = false;
        isSending = false;
        return;
      }
    } catch (e) {
      // Falha na checagem via IA (sem internet, provedor fora do ar
      // etc.) — segue para a resposta normal do chat, sem travar nada.
    }
  }
  }

  sendBtn.disabled = true;
  setHudState("thinking", "Processando...");
  const { row: thinking, bubble: thinkingBubble } = makeBubbleRow("assistant");
  thinkingBubble.classList.add("thinking-dots");
  thinkingBubble.innerHTML = '<span class="jarvis-processing-label">JARVIS está processando...</span><span></span><span></span><span></span>';
  chatEl.appendChild(thinking);
  chatEl.scrollTop = chatEl.scrollHeight;

  try {
    activeRequestController = new AbortController();
    const page = location.pathname;
    const context = page.includes("game-lab") ? "GAME LAB" : page.includes("programming") || page.includes("learning") ? "PROGRAMMING / AULA / IDE" : page.includes("editor") ? "EDITOR" : page.includes("security") || page.includes("cyber") ? "SEGURANÇA DEFENSIVA" : "GERAL";
    const requestBody = {
      history,
      context,
      mode: cyberMode.checked ? "cyber" : (codeMode.checked ? "programacao" : (pitagorasMode.checked ? "pitagoras" : (negociosMode.checked ? "negocios" : (ctfMode && ctfMode.checked ? "ctf" : "padrao")))),
      developer: developerMode,
    };
    if (attachment) {
      requestBody.attachment = attachment.kind === "image"
        ? { type: "image", name: attachment.name, mime: attachment.mime, data: attachment.dataUrl }
        : { type: "text", name: attachment.name, content: attachment.content };
    }
    jarvisRequestStartedAt = performance.now();
    const requestId = `j8-${Date.now()}-${++jarvisRequestSeq}`;
    const timeout = setTimeout(() => activeRequestController?.abort(), 90000);
    const res = await fetch("/api/jarvis", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(requestBody),
      signal: activeRequestController.signal,
    });
    clearTimeout(timeout);
    // Lê como texto primeiro: se o servidor/hospedagem cair fora (proxy
    // com timeout, erro 502/504, etc.) a resposta vem como uma página
    // HTML de erro, não como JSON — e "res.json()" direto quebrava com
    // a mensagem confusa "Unexpected token '<'". Assim detectamos isso
    // e mostramos um aviso que faz sentido pra quem está usando o chat.
    const raw = await res.text();
    let data;
    try {
      data = JSON.parse(raw);
    } catch (parseErr) {
      throw new Error(
        res.ok
          ? "O servidor devolveu uma resposta inesperada. Tente de novo em alguns segundos."
          : `O servidor demorou demais ou está indisponível agora (erro ${res.status}). Tente de novo em alguns segundos.`
      );
    }
    thinking.remove();
    if (data.error) {
      const tech = String(data.error || "");
      // Sanitize: never surface secrets / keys / tokens / cookies
      const safeTech = tech
        .replace(/(api[_-]?key|token|secret|password|cookie|authorization)\s*[:=]\s*\S+/gi, "$1=[redacted]")
        .replace(/sk-[a-zA-Z0-9]{10,}/g, "[redacted]")
        .replace(/Bearer\s+\S+/gi, "Bearer [redacted]");
      const friendly = /timeout|timed?\s*out|abort/i.test(safeTech)
        ? "A resposta demorou demais. Tente de novo em alguns segundos."
        : /rate.?limit|429|quota|capacity/i.test(safeTech)
        ? "O serviço de IA está temporariamente sobrecarregado. Aguarde um momento e tente novamente."
        : /key|auth|401|403|invalid.*credential/i.test(safeTech)
        ? "Há um problema de configuração da IA. Verifique as chaves em Configurações (se você for administrador)."
        : "JARVIS encontrou um problema ao processar sua solicitação.";
      window.__jarvisLastDiag = {
        request_id: data.request_id || null,
        elapsed_ms: data.elapsed_ms || null,
        context: data.context || null,
        status: res.status,
        tech: safeTech.slice(0, 800),
        at: new Date().toISOString(),
      };
      throw new Error(friendly + "|||" + safeTech.slice(0, 400));
    }
    if (!data.reply) throw new Error("A IA respondeu sem conteúdo.");

    history.push({ role: "assistant", content: data.reply });
    saveHistory(history);
    typeBubble(data.reply);
    speak(data.reply);
    const elapsed = Number(data.elapsed_ms || 0);
    flashHudState("success", `Concluído${elapsed ? ` · ${elapsed} ms` : ""}${data.request_id ? ` · ${data.request_id}` : ""}`, 2200);
  } catch (err) {
    thinking.remove();
    if (err.name === "AbortError") {
      renderBubble("assistant", "⏹ Geração cancelada.");
      flashHudState(null, "Geração cancelada.");
      return;
    }
    let full = err.message || "Algo deu errado.";
    let friendly = full;
    let techPart = "";
    if (full.includes("|||")) {
      const parts = full.split("|||");
      friendly = parts[0];
      techPart = parts[1] || "";
    }
    if (friendly.length > 180) friendly = friendly.slice(0, 177) + "...";
    const wrap = document.createElement("div");
    wrap.className = "jarvis-error-card";
    wrap.innerHTML =
      "<p><strong>⚠️ " + friendly.replace(/</g, "&lt;") + "</strong></p>" +
      '<div class="jarvis-error-actions" style="display:flex;gap:8px;flex-wrap:wrap;margin-top:8px;">' +
      '<button type="button" class="btn btn-sm" data-err-retry>Tentar novamente</button>' +
      '<button type="button" class="btn btn-sm" data-err-diag>Copiar diagnóstico</button>' +
      '<button type="button" class="btn btn-sm" data-err-back>Voltar</button></div>' +
      '<details style="margin-top:8px;font-size:0.85em;opacity:0.85;">' +
      "<summary>Detalhes técnicos (sem segredos)</summary>" +
      '<pre style="white-space:pre-wrap;max-height:120px;overflow:auto;">' +
      ((techPart || (window.__jarvisLastDiag && window.__jarvisLastDiag.tech) || "sem detalhes").replace(/</g, "&lt;")) +
      "</pre></details>";
    const { row } = makeBubbleRow("assistant");
    const bubble = row.querySelector(".bubble");
    if (bubble) bubble.replaceWith(wrap); else row.appendChild(wrap);
    chatEl.appendChild(row);
    chatEl.scrollTop = chatEl.scrollHeight;
    wrap.querySelector("[data-err-retry]")?.addEventListener("click", () => sendMessage());
    wrap.querySelector("[data-err-diag]")?.addEventListener("click", () => {
      const d = window.__jarvisLastDiag || { tech: techPart, at: new Date().toISOString() };
      const text = JSON.stringify(d, null, 2);
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => flashHudState("success", "Diagnóstico copiado.", 2000));
      } else {
        prompt("Copie o diagnóstico:", text);
      }
    });
    wrap.querySelector("[data-err-back]")?.addEventListener("click", () => {
      row.remove();
      flashHudState(null, "Pronto.");
    });
    flashHudState("error", "⚠️ Não consegui responder.");
  } finally {
    sendBtn.disabled = false;
    isSending = false;
    activeRequestController = null;
  }
}

// Pitágoras, Programação, Cyber e Mentor de Negócios são modos
// exclusivos entre si (cada um tem um system prompt diferente) —
// marcar um desmarca os outros.
pitagorasMode.addEventListener("change", () => {
  if (pitagorasMode.checked) { if (ctfMode) ctfMode.checked = false; codeMode.checked = false; cyberMode.checked = false; negociosMode.checked = false; }
});
codeMode.addEventListener("change", () => {
  if (codeMode.checked) { if (ctfMode) ctfMode.checked = false; pitagorasMode.checked = false; cyberMode.checked = false; negociosMode.checked = false; }
});
cyberMode.addEventListener("change", () => {
  if (cyberMode.checked) { if (ctfMode) ctfMode.checked = false; pitagorasMode.checked = false; codeMode.checked = false; negociosMode.checked = false; }
});
if (ctfMode) ctfMode.addEventListener("change", () => {
  if (ctfMode.checked) { pitagorasMode.checked = false; codeMode.checked = false; cyberMode.checked = false; negociosMode.checked = false; }
});
negociosMode.addEventListener("change", () => {
  if (negociosMode.checked) { if (ctfMode) ctfMode.checked = false; pitagorasMode.checked = false; codeMode.checked = false; cyberMode.checked = false; }
});

if (quickActions) {
  quickActions.querySelectorAll("[data-quick]").forEach(btn => btn.addEventListener("click", () => {
    inputEl.value = btn.dataset.quick + ": "; inputEl.focus();
  }));
}

if (developerModeBtn) {
  developerModeBtn.addEventListener("click", async () => {
    try {
      const r = await fetch("/api/jarvis/developer"); const d = await r.json();
      developerMode = !!d.enabled;
      developerModeBtn.classList.toggle("active", developerMode);
      developerModeBtn.textContent = developerMode ? "🧑‍💻 Desenvolvedor ON" : "🧑‍💻 Desenvolvedor";
      setHudState(null, developerMode ? "Modo desenvolvedor ativo." : "Modo desenvolvedor desativado.");
    } catch (_) {}
  });
}

sendBtn.addEventListener("click", sendMessage);
inputEl.addEventListener("keydown", (e) => {
  // ignora repetição de tecla segurada e composição de teclado (IME/alguns teclados de celular)
  if (e.key === "Enter" && !e.repeat && !e.isComposing) {
    e.preventDefault();
    sendMessage();
  }
});

// ---------- Editar um site de verdade a partir do Jarvis ----------
// Reaproveita as mesmas rotas e a mesma IA do editor de sites — o Jarvis
// não finge editar, ele chama a mesma engine que já funciona lá.
const siteSelect = document.getElementById("jarvis-site-select");
const applyBtn = document.getElementById("jarvis-apply-btn");
const improveBtn = document.getElementById("jarvis-improve-btn");
const siteStatus = document.getElementById("jarvis-site-status");

function addAssistantMessage(text) {
  history.push({ role: "assistant", content: text });
  saveHistory(history);
  renderBubble("assistant", text);
  chatEl.scrollTop = chatEl.scrollHeight;
}

if (siteSelect) {
  siteSelect.addEventListener("change", () => {
    const has = !!siteSelect.value;
    applyBtn.disabled = !has;
    improveBtn.disabled = !has;
    siteStatus.textContent = "";
  });

  applyBtn.addEventListener("click", async () => {
    const slug = siteSelect.value;
    const instruction = inputEl.value.trim();
    if (!slug) return;
    if (!instruction) { alert("Escreva no campo de mensagem o que você quer mudar nesse site."); return; }

    const userNote = `🛠 Aplicar no site "${siteSelect.options[siteSelect.selectedIndex].text}": ${instruction}`;
    history.push({ role: "user", content: userNote });
    renderBubble("user", userNote);
    saveHistory(history);
    inputEl.value = "";

    applyBtn.disabled = true;
    improveBtn.disabled = true;
    setHudState("thinking", "Editando o site...");
    siteStatus.textContent = "Enviando instrução...";

    try {
      const res = await fetch(`/sites/${slug}/editor/ai-edit`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ instruction }),
      });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
    if (!data.reply) throw new Error("A IA respondeu sem conteúdo.");

      setHudState("processing", "Aplicando no arquivo do site...");
      const job = await pollJob(data.job_id, (job) => { siteStatus.textContent = job.message || "Aplicando..."; });
      if (job.status === "error") throw new Error(job.error);

      siteStatus.textContent = "✅ Alteração aplicada.";
      addAssistantMessage(`Pronto, senhor. Já apliquei essa alteração diretamente no arquivo do site. Pode conferir em "Meus sites → ${siteSelect.options[siteSelect.selectedIndex].text} → Pré-visualizar".`);
      flashHudState("success", "✅ Alteração aplicada.");
    } catch (err) {
      siteStatus.textContent = "❌ " + err.message;
      addAssistantMessage(`Não consegui aplicar essa alteração no site, senhor: ${err.message}`);
      flashHudState("error", "❌ Não consegui aplicar a alteração.");
    } finally {
      applyBtn.disabled = !siteSelect.value;
      improveBtn.disabled = !siteSelect.value;
    }
  });

  improveBtn.addEventListener("click", async () => {
    const slug = siteSelect.value;
    if (!slug) return;
    const siteName = siteSelect.options[siteSelect.selectedIndex].text;

    const userNote = `✨ Melhorar o site "${siteName}" automaticamente (sem instrução específica)`;
    history.push({ role: "user", content: userNote });
    renderBubble("user", userNote);
    saveHistory(history);

    applyBtn.disabled = true;
    improveBtn.disabled = true;
    setHudState("thinking", "Analisando o site...");
    siteStatus.textContent = "Analisando o arquivo...";

    try {
      const res = await fetch(`/sites/${slug}/editor/ai-improve`, { method: "POST" });
      const data = await res.json();
      if (data.error) throw new Error(data.error);
    if (!data.reply) throw new Error("A IA respondeu sem conteúdo.");

      setHudState("processing", "Aplicando melhorias no site...");
      const job = await pollJob(data.job_id, (job) => { siteStatus.textContent = job.message || "Melhorando..."; });
      if (job.status === "error") throw new Error(job.error);

      siteStatus.textContent = "✅ Melhorias aplicadas.";
      addAssistantMessage(`Feito, senhor. Revisei o site "${siteName}" por conta própria e apliquei correções de responsividade, acessibilidade e acabamento visual, sem mexer no conteúdo real.`);
      flashHudState("success", "✅ Melhorias aplicadas.");
    } catch (err) {
      siteStatus.textContent = "❌ " + err.message;
      addAssistantMessage(`Não consegui melhorar o site "${siteName}" agora, senhor: ${err.message}`);
      flashHudState("error", "❌ Não consegui melhorar o site.");
    } finally {
      applyBtn.disabled = !siteSelect.value;
      improveBtn.disabled = !siteSelect.value;
    }
  });
}

clearBtn.addEventListener("click", () => {
  if (confirm("Limpar esta conversa?")) {
    history = [];
    pendingAttachment = null;
    renderAttachmentPreview();
    saveHistory(history);
    renderAll(history);
  }
});

// Desligar a conversa contínua também para qualquer fala/escuta em andamento
continuousMode.addEventListener("change", () => {
  if (!continuousMode.checked) {
    try { recognition && recognition.stop(); } catch (e) {}
    window.speechSynthesis && window.speechSynthesis.cancel();
    setHudState(null, "Ao seu dispor.");
  }
});

// ---------- Reconhecimento de voz (opcional, depende do navegador) ----------
// A ideia é a mesma do Tony Stark chamando o Jarvis: clica (ou liga a
// conversa contínua) e simplesmente fala — sem precisar digitar nada.
const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
let recognition = null;

function startListening() {
  if (!recognition || isSending) return;
  // Não liga o microfone enquanto o Jarvis ainda está falando — no
  // Android isso quase sempre faz o reconhecimento captar a própria
  // voz do assistente e entrar em loop.
  if (window.speechSynthesis && window.speechSynthesis.speaking) return;
  try {
    setHudState("listening", "Ouvindo... pode falar.");
    micBtn.textContent = "🔴";
    recognition.start();
  } catch (e) {
    // já estava rodando — ignora
  }
}

if (SpeechRecognition) {
  recognition = new SpeechRecognition();
  recognition.lang = "pt-BR";
  recognition.interimResults = false;

  micBtn.addEventListener("click", () => startListening());

  recognition.onresult = (event) => {
    const transcript = event.results[0][0].transcript;
    inputEl.value = transcript;
    micBtn.textContent = "🎤";
    // ITEM 2 do briefing: InputManager normaliza isto em VOICE_COMMAND
    window.dispatchEvent(new CustomEvent("input:VOICE_COMMAND", { detail: { text: transcript, source: "speech" } }));
    sendMessage();
  };
  recognition.onerror = () => {
    micBtn.textContent = "🎤";
    setHudState(null, "Ao seu dispor.");
  };
  recognition.onend = () => {
    micBtn.textContent = "🎤";
  };
} else {
  micBtn.title = "Reconhecimento de voz não suportado neste navegador";
  micBtn.disabled = true;
  continuousMode.disabled = true;
}

// ---------- FASE 4/5: reage a eventos de gestos de mão e de palmas ----------
// gesture-control.js (mão) e clap-control.js (palma) não sabem nada sobre
// o Jarvis — só disparam CustomEvents no window. Aqui é o único lugar que
// traduz esses eventos em HUD/voz, então trocar a lógica de gestos nunca
// exige mexer neste arquivo além deste bloco.
window.addEventListener("jarvis:gesture", (e) => {
  const type = e.detail && e.detail.type;
  if (type === "started") setHudState(null, "✋ Controle por gestos ativado.");
  else if (type === "stopped") setHudState(null, "Controle por gestos desativado.");
  else if (type === "open") setHudState(null, "✋ Controlando o holograma pela mão.");
  else if (type === "closed") setHudState(null, "✊ Controle pausado.");
  else if (type === "pinch") setHudState(null, "🤏 Movendo o objeto.");
});

window.addEventListener("jarvis:clap", (e) => {
  const type = e.detail && e.detail.type;
  if (type === "wake") {
    // Mesmo fluxo de acordar que o botão do microfone já usa, só que
    // disparado por palma em vez de clique — reaproveita startListening()
    // e a resposta falada "Sim. Estou ouvindo." já existentes.
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    setHudState("listening", "👏 Acordei. Estou ouvindo.");
    speak("Sim. Estou ouvindo.");
    setTimeout(() => { try { startListening(); } catch (err) {} }, 900);
  } else if (type === "sleep") {
    if (window.speechSynthesis) window.speechSynthesis.cancel();
    try { recognition && recognition.stop(); } catch (err) {}
    setHudState(null, "Ao seu dispor.");
  }
});

// ---------- Aviso proativo de achados de segurança (Cyber Lab defensivo) ----
// Ao abrir o Jarvis, se houver achados high/critical não resolvidos nos
// alvos autorizados, mostra um aviso discreto no HUD (uma vez, silencioso
// se não for owner/admin — a rota já é protegida por RBAC no backend).
(function checkSecurityAlerts() {
  fetch("/api/cyber/dashboard", { credentials: "same-origin" })
    .then((r) => (r.ok ? r.json() : null))
    .then((data) => {
      if (!data || !data.totals) return;
      const urgent = (data.totals.critical || 0) + (data.totals.high || 0);
      if (urgent > 0) {
        flashHudState("error", `⚠️ ${urgent} achado(s) de risco alto/crítico no Cyber Lab.`, 4500);
        if (window.HoloStatus) window.HoloStatus.alert();
      }
    })
    .catch(() => {}); // sem acesso ao Cyber Lab (user/guest) — silencioso, não é erro pro usuário comum
})();

// ---------- Navegação rápida por voz entre ferramentas do Cyber Lab --------
// Comandos como "abrir mitre", "ir para playbooks", "mostrar ctf" navegam
// direto para a seção certa em /cyber sem precisar clicar. Não substitui o
// roteador de ferramentas do Jarvis: roda ANTES dele, e só intercepta se o
// texto bater com um destino conhecido (senão, segue o fluxo normal).
const CYBER_NAV_TARGETS = [
  { match: /\bmitre\b|att&?ck|t[aá]tica.*ataque/i, anchor: "mitre-query", label: "MITRE ATT&CK" },
  { match: /\bioc\b|indicador.*compromisso|feed.*ameaça/i, anchor: "ioc-hash", label: "Feed de IoCs" },
  { match: /analisad?or?.*log|\blogs?\b.*(analis|siem)/i, anchor: "logs-input", label: "Analisador de Logs" },
  { match: /\bwaf\b|regra.*firewall|gerar.*firewall/i, anchor: "waf-engine", label: "Gerador de WAF" },
  { match: /cabeçalh.*http|headers?.*http|\bcsp\b|\bhsts\b/i, anchor: "headers-input", label: "Auditoria de Headers" },
  { match: /phishing|cabeçalh.*e-?mail|spf|dkim|dmarc/i, anchor: "email-input", label: "Anti-Phishing" },
  { match: /\bfim\b|integridade.*arquiv/i, anchor: "fim-result", label: "Monitor de Integridade (FIM)" },
  { match: /playbook|resposta.*incidente|\bir\b.*incidente/i, anchor: "ir-select", label: "Playbooks de IR" },
  { match: /relat[óo]rio.*auditoria|security score|score.*seguran/i, anchor: "audit-target", label: "Relatório de Auditoria" },
  { match: /\bctf\b|desafio.*(segurança|código)|secure coding/i, anchor: "ctf-select", label: "Laboratório CTF" },
  { match: /gerar.*testes?.*seguran|pytest|jest/i, anchor: "tests-lang", label: "Gerador de Testes" },
  { match: /cheatsheet|owasp|guia.*codifica[çc][ãa]o segura/i, anchor: "cheatsheet-card", label: "Guia OWASP" },
];

function tryCyberVoiceNav(text) {
  const hit = CYBER_NAV_TARGETS.find((t) => t.match.test(text));
  if (!hit) return false;
  const goingThere = !location.pathname.endsWith("/cyber");
  const doScroll = () => {
    const el = document.getElementById(hit.anchor);
    if (el) { el.scrollIntoView({ behavior: "smooth", block: "center" }); el.focus && el.focus(); }
  };
  if (goingThere) {
    sessionStorage.setItem("cyber_nav_anchor", hit.anchor);
    location.href = "/cyber";
  } else {
    doScroll();
  }
  setHudState(null, `🧭 Abrindo: ${hit.label}`);
  speak(`Abrindo ${hit.label}.`);
  return true;
}

// Ao carregar /cyber vindo de uma navegação por voz, rola até a âncora salva.
if (location.pathname.endsWith("/cyber")) {
  const anchor = sessionStorage.getItem("cyber_nav_anchor");
  if (anchor) {
    sessionStorage.removeItem("cyber_nav_anchor");
    window.addEventListener("DOMContentLoaded", () => {
      setTimeout(() => {
        const el = document.getElementById(anchor);
        if (el) el.scrollIntoView({ behavior: "smooth", block: "center" });
      }, 300);
    });
  }
}
