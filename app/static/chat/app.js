const API_URL = "/v1/negociar";
const HISTORY_URL = "/v1/negociar/historico";
const SESSIONS_URL = "/v1/negociar/sessoes";
const SESSION_STORAGE_KEY = "chat_session_id";

const messagesEl = document.getElementById("messages");
const formEl = document.getElementById("chat-form");
const inputEl = document.getElementById("message-input");
const cpfEl = document.getElementById("cpf-input");
const btnSend = document.getElementById("btn-send");
const btnClear = document.getElementById("btn-clear");
const typingEl = document.getElementById("typing");

/** @type {{ role: 'user' | 'assistant', content: string }[]} */
let historico = [];
let sessionId = localStorage.getItem(SESSION_STORAGE_KEY) || crypto.randomUUID();

function onlyDigits(value) {
  return (value || "").replace(/\D/g, "");
}

function formatTime(date = new Date()) {
  return date.toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" });
}

function persistSessionId() {
  localStorage.setItem(SESSION_STORAGE_KEY, sessionId);
}

function newSession() {
  sessionId = crypto.randomUUID();
  persistSessionId();
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
  btnSend.disabled = loading;
  inputEl.disabled = loading;
  cpfEl.disabled = loading;
  typingEl.classList.toggle("hidden", !loading);
  typingEl.setAttribute("aria-hidden", loading ? "false" : "true");
}

async function loadSessionFromServer() {
  const cpf = onlyDigits(cpfEl.value);
  if (cpf.length !== 11) return;

  try {
    const params = new URLSearchParams({ cpf, session_id: sessionId });
    const res = await fetch(`${HISTORY_URL}?${params}`);
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

async function sendMessage(text) {
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
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        cpf,
        mensagem: text,
        session_id: sessionId,
        historico: historico.slice(0, -1),
      }),
    });

    const data = await res.json().catch(() => ({}));

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

cpfEl.addEventListener("change", () => {
  loadSessionFromServer();
});

btnClear.addEventListener("click", async () => {
  const cpf = onlyDigits(cpfEl.value);
  historico = [];
  clearMessagesUi();
  newSession();

  if (cpf.length === 11) {
    try {
      const params = new URLSearchParams({ cpf });
      await fetch(`${SESSIONS_URL}?${params}`, { method: "DELETE" });
    } catch {
      /* limpa só a UI se a API falhar */
    }
  }

  appendSystem("Nova conversa iniciada. Envie uma mensagem para começar.");
});

persistSessionId();
appendSystem(
  "Bem-vindo. Use o CPF de teste do seed (ex.: 12345678901) e digite sua mensagem."
);
loadSessionFromServer();
