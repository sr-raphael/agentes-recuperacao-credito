const API_URL = "/v1/negociar";
const HISTORY_URL = "/v1/negociar/historico";
const SESSIONS_URL = "/v1/negociar/sessoes";
const LOGIN_URL = "/v1/auth/login";
const SESSION_STORAGE_KEY = "chat_session_id";
const TOKEN_STORAGE_KEY = "chat_access_token";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const cpfEl = document.getElementById("cpf-input");
const senhaEl = document.getElementById("senha-input");
const btnSend = document.getElementById("btn-send");
const btnEntrar = document.getElementById("btn-entrar");
const btnSair = document.getElementById("btn-sair");
const typingEl = document.getElementById("typing");

/** @type {{ role: 'user' | 'assistant', content: string }[]} */
let historico = [];
let sessionId = localStorage.getItem(SESSION_STORAGE_KEY) || crypto.randomUUID();
let accessToken = localStorage.getItem(TOKEN_STORAGE_KEY) || "";

function onlyDigits(value) {
  return (value || "").replace(/\D/g, "");
}

function formatTime(date = new Date()) {
  return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function persistSessionId() {
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

function persistToken() {
  if (accessToken) {
    localStorage.setItem(TOKEN_STORAGE_KEY, accessToken);
  } else {
    localStorage.removeItem(TOKEN_STORAGE_KEY);
  }
}

function newSession() {
  sessionId = crypto.randomUUID();
  persistSessionId();
}

function authHeaders(extra = {}) {
  const headers = { ...extra };
  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }
  return headers;
}

function isAuthenticated() {
  return Boolean(accessToken);
}

function setAuthenticatedUI(loggedIn) {
  btnEntrar.disabled = loggedIn;
  btnSair.disabled = !loggedIn;
  cpfEl.disabled = loggedIn;
  senhaEl.disabled = loggedIn;
  inputEl.disabled = !loggedIn;
  btnSend.disabled = !loggedIn;
}

function scrollToBottom() {
  messagesEl.scrollTop = messagesEl.scrollHeight;
}

function clearMessagesUi() {
  messagesEl.innerHTML = "";
}

function appendMessage(role, content, meta = "") {
  const row = document.createElement("div");
  row.className = `row row--${role === "user" ? "user" : "agent"}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = content;

  if (meta) {
    const metaEl = document.createElement("span");
    metaEl.className = "meta";
    metaEl.textContent = meta;
    bubble.appendChild(metaEl);
  }

  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
}

function appendSystem(text, isError = false) {
  const row = document.createElement("div");
  row.className = "row row--agent";
  const bubble = document.createElement("div");
  bubble.className = "bubble bubble--system" + (isError ? " bubble--error" : "");
  bubble.textContent = text;
  row.appendChild(bubble);
  messagesEl.appendChild(row);
  scrollToBottom();
}

function renderHistorico(messages) {
  clearMessagesUi();
  historico = [];
  for (const msg of messages) {
    const role = msg.role === "user" ? "user" : "assistant";
    appendMessage(role, msg.content);
    historico.push({ role: msg.role, content: msg.content });
  }
}

function setLoading(loading) {
  btnSend.disabled = loading || !isAuthenticated();
  inputEl.disabled = loading || !isAuthenticated();
  typingEl.classList.toggle("hidden", !loading);
  typingEl.setAttribute("aria-hidden", loading ? "false" : "true");
}

async function loadSessionFromServer() {
  if (!isAuthenticated()) return;

  const cpf = onlyDigits(cpfEl.value);
  if (cpf.length !== 11) return;

  try {
    const params = new URLSearchParams({ cpf, session_id: sessionId });
    const res = await fetch(`${HISTORY_URL}?${params}`, { headers: authHeaders() });
    if (res.status === 401) {
      logout();
      appendSystem("Sessão expirada. Faça login novamente.", true);
      return;
    }
    if (!res.ok) return;

    const data = await res.json();
    if (data.session_id) {
      sessionId = data.session_id;
      persistSessionId();
    }
    if (Array.isArray(data.mensagens) && data.mensagens.length > 0) {
      renderHistorico(data.mensagens);
      appendSystem("Conversa restaurada do banco de dados.");
    }
  } catch {
    /* ignora falha silenciosa no restore */
  }
}

async function login() {
  const cpf = onlyDigits(cpfEl.value);
  const senha = (senhaEl.value || "").trim();

  if (cpf.length !== 11) {
    appendSystem("Informe um CPF válido com 11 dígitos.", true);
    return;
  }
  if (!senha) {
    appendSystem("Informe a senha para entrar.", true);
    return;
  }

  btnEntrar.disabled = true;
  try {
    const res = await fetch(LOGIN_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ cpf, senha }),
    });
    const data = await res.json().catch(() => ({}));

    if (!res.ok) {
      const detail =
        typeof data.detail === "string"
          ? data.detail
          : "Não foi possível autenticar. Verifique CPF e senha.";
      appendSystem(detail, true);
      return;
    }

    accessToken = data.access_token || "";
    persistToken();
    if (data.cpf) {
      cpfEl.value = data.cpf;
    }

    historico = [];
    clearMessagesUi();
    newSession();
    setAuthenticatedUI(true);
    senhaEl.value = "";

    const horas = Math.round((data.expires_in || 3600) / 3600);
    appendSystem(
      `Autenticado com sucesso. Token válido por ${horas} hora(s). Envie uma mensagem para começar.`
    );
    await loadSessionFromServer();
  } catch {
    appendSystem("Erro de conexão ao autenticar.", true);
  } finally {
    if (!isAuthenticated()) {
      btnEntrar.disabled = false;
    }
  }
}

function logout() {
  accessToken = "";
  persistToken();
  historico = [];
  clearMessagesUi();
  newSession();
  setAuthenticatedUI(false);
}

async function sair() {
  const cpf = onlyDigits(cpfEl.value);

  if (cpf.length === 11 && isAuthenticated()) {
    try {
      const params = new URLSearchParams({ cpf });
      await fetch(`${SESSIONS_URL}?${params}`, {
        method: "DELETE",
        headers: authHeaders(),
      });
    } catch {
      /* segue logout local */
    }
  }

  accessToken = "";
  persistToken();
  historico = [];
  clearMessagesUi();
  newSession();
  setAuthenticatedUI(false);
  appendSystem("Você saiu. Histórico local limpo.");
}

async function sendMessage(text) {
  if (!isAuthenticated()) {
    appendSystem("Faça login (Entrar) antes de enviar mensagens.", true);
    return;
  }

  const cpf = onlyDigits(cpfEl.value);
  if (cpf.length !== 11) {
    appendSystem("Informe um CPF válido com 11 dígitos.", true);
    return;
  }

  appendMessage("user", text, formatTime());
  historico.push({ role: "user", content: text });

  setLoading(true);
  try {
    const res = await fetch(API_URL, {
      method: "POST",
      headers: authHeaders({ "Content-Type": "application/json" }),
      body: JSON.stringify({
        cpf,
        mensagem: text,
        session_id: sessionId,
        historico: historico.slice(0, -1),
      }),
    });

    const data = await res.json().catch(() => ({}));

    if (res.status === 401) {
      historico.pop();
      logout();
      appendSystem("Token expirado ou inválido. Faça login novamente.", true);
      return;
    }

    if (!res.ok) {
      historico.pop();
      const detail =
        typeof data.detail === "string"
          ? data.detail
          : "Não foi possível processar sua mensagem. Tente novamente.";
      appendSystem(detail, true);
      return;
    }

    if (data.session_id) {
      sessionId = data.session_id;
      persistSessionId();
    }

    const resposta = data.resposta || "(sem resposta)";
    const status = data.status_auditoria || "";
    const etapa = data.etapa ? ` · ${data.etapa}` : "";
    const meta = status ? `${formatTime()} · ${status}${etapa}` : formatTime();

    appendMessage("assistant", resposta, meta);
    historico.push({ role: "assistant", content: resposta });
  } catch {
    historico.pop();
    appendSystem(
      "Erro de conexão com o servidor. Verifique se a API está rodando (uvicorn).",
      true
    );
  } finally {
    setLoading(false);
    inputEl.focus();
  }
}

formEl.addEventListener("submit", (e) => {
  e.preventDefault();
  const text = inputEl.value.trim();
  if (!text) return;
  inputEl.value = "";
  inputEl.style.height = "auto";
  sendMessage(text);
});

inputEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    formEl.requestSubmit();
  }
});

inputEl.addEventListener("input", () => {
  inputEl.style.height = "auto";
  inputEl.style.height = `${Math.min(inputEl.scrollHeight, 120)}px`;
});

senhaEl.addEventListener("keydown", (e) => {
  if (e.key === "Enter") {
    e.preventDefault();
    login();
  }
});

btnEntrar.addEventListener("click", () => login());
btnSair.addEventListener("click", () => sair());

persistSessionId();
setAuthenticatedUI(isAuthenticated());

if (isAuthenticated()) {
  appendSystem("Sessão restaurada. Você já está autenticado.");
  loadSessionFromServer();
} else {
  appendSystem(
    "Informe CPF e senha do cliente (seed: 12345) e clique em Entrar."
  );
}
