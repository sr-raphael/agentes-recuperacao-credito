const API_URL = "/v1/negociar";
const LOGIN_URL = "/v1/auth/login";

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
let sessionId = crypto.randomUUID();
let accessToken = "";

function onlyDigits(value) {
  return (value || "").replace(/\D/g, "");
}

function formatTime(date = new Date()) {
  return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function newSession() {
  sessionId = crypto.randomUUID();
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

function escapeHtml(text) {
  return String(text || "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}

/** Converte **negrito** e quebras de linha (markdown leve do agente). */
function formatMessageHtml(content) {
  let safe = escapeHtml(content);
  safe = safe.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
  safe = safe.replace(/\n/g, "<br>");
  return safe;
}

function appendMessage(role, content, meta = "") {
  const row = document.createElement("div");
  row.className = `row row--${role === "user" ? "user" : "agent"}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.innerHTML = formatMessageHtml(content);

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

function setLoading(loading) {
  btnSend.disabled = loading || !isAuthenticated();
  inputEl.disabled = loading || !isAuthenticated();
  typingEl.classList.toggle("hidden", !loading);
  typingEl.setAttribute("aria-hidden", loading ? "false" : "true");
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
      `Autenticado com sucesso. Nova conversa iniciada. Token válido por ${horas} hora(s).`
    );
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
  historico = [];
  clearMessagesUi();
  newSession();
  setAuthenticatedUI(false);
  cpfEl.value = "";
  senhaEl.value = "";
}

async function sair() {
  accessToken = "";
  historico = [];
  clearMessagesUi();
  newSession();
  setAuthenticatedUI(false);
  cpfEl.value = "";
  senhaEl.value = "";
  appendSystem("Você saiu. Informe CPF e senha para entrar novamente.");
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

// Limpa tokens/sessões antigos gravados em versões anteriores do chat.
localStorage.removeItem("chat_session_id");
localStorage.removeItem("chat_access_token");

setAuthenticatedUI(false);
appendSystem(
  "Informe CPF e senha do cliente (seed: 12345) e clique em Entrar."
);
