"""
Validação determinística de entradas antes de LLMs e ferramentas (guardrails).
Foco: prompt injection comum, abuso de tamanho e CPF claramente inválido.
"""

from __future__ import annotations

import hashlib
import re
import unicodedata
from dataclasses import dataclass

MAX_USER_MESSAGE_CHARS = 4_000
MAX_CHAT_HISTORY_ITEMS = 60
MAX_CHAT_HISTORY_TOTAL_CHARS = 80_000
MAX_SINGLE_HISTORY_MESSAGE_CHARS = 4_000

# Frases/tokens frequentes em jailbreak e exfiltração de instruções (PT/EN).
_INJECTION_SUBSTRINGS = (
    "ignore todas as instru",
    "ignore all previous",
    "ignore previous instructions",
    "disregard the above",
    "esqueça todas as regras",
    "esqueca todas as regras",
    "você agora é",
    "voce agora e",
    "you are now",
    "system prompt",
    "prompt do sistema",
    "reveal your instructions",
    "mostre seu prompt",
    "mostre o prompt",
    "jailbreak",
    "modo dan",
    "developer mode",
    "sudo mode",
    "ignore the above",
    "</system>",
    "<|system|>",
    "<|im_start|>",
    "[INST]",
    "### new instructions",
)

_REASON_TO_AUDITORIA: dict[str, str] = {
    "injection": "bloqueado_entrada_injection",
    "historico_injection": "bloqueado_entrada_injection",
    "mensagem_vazia": "bloqueado_entrada_vazio",
    "mensagem_tamanho": "bloqueado_entrada_tamanho",
    "historico_tamanho_itens": "bloqueado_entrada_tamanho",
    "historico_mensagem_vazia": "bloqueado_entrada_tamanho",
    "historico_mensagem_tamanho": "bloqueado_entrada_tamanho",
    "historico_tamanho_total": "bloqueado_entrada_tamanho",
    "cpf_formato": "bloqueado_entrada_cpf",
    "cpf_checksum": "bloqueado_entrada_cpf",
    "historico_role_invalido": "bloqueado_entrada_historico",
}

_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_ZERO_WIDTH_RE = re.compile(r"[\u200b-\u200f\u202a-\u202e\u2060-\u206f\ufeff]")
_REPEAT_CHAR_RE = re.compile(r"(.)\1{49,}")  # mesmo caractere 50+ vezes seguidas


@dataclass(frozen=True)
class GuardrailResult:
    ok: bool
    """Se False, não chamar agentes; retornar `user_message` ao cliente."""

    user_message: str
    """Mensagem segura para o usuário (genérica quando bloqueio por segurança)."""

    sanitized_input: str = ""
    """Texto do usuário após saneamento (usar só se ok)."""

    cpf_digits: str = ""
    """CPF somente dígitos (usar só se ok)."""

    reason_code: str = ""
    """Código interno do bloqueio (persistido em motivo_bloqueio; não expor ao cliente)."""


def hash_input(text: str) -> str:
    """SHA-256 do texto normalizado (utilitário para deduplicação offline)."""
    normalized = _normalize_text(str(text or ""))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


MAX_STORED_MESSAGE_CHARS = 2_000

_CPF_FORMATTED_RE = re.compile(r"\b\d{3}\.?\d{3}\.?\d{3}-?\d{2}\b")
_CPF_DIGITS_RE = re.compile(r"\b\d{11}\b")
_EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+", re.IGNORECASE)
_PHONE_RE = re.compile(
    r"\b(?:\+55\s?)?(?:\(\d{2}\)\s?|\d{2}\s)?\d{4,5}[-\s]?\d{4}\b"
)
_CARD_RE = re.compile(r"\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b")


def mask_for_storage(text: str) -> str:
    """
    Mascara PII antes de persistir em transcricao_json.
    Mantém frases de injection legíveis para auditoria no TCC/analytics.
    """
    s = _normalize_text(str(text or ""))
    if not s:
        return s

    s = _CPF_FORMATTED_RE.sub("[CPF]", s)
    s = _CPF_DIGITS_RE.sub("[CPF]", s)
    s = _EMAIL_RE.sub("[email]", s)
    s = _PHONE_RE.sub("[telefone]", s)
    s = _CARD_RE.sub("[cartao]", s)

    if len(s) > MAX_STORED_MESSAGE_CHARS:
        return s[:MAX_STORED_MESSAGE_CHARS] + "… [truncado]"
    return s


def auditoria_status_for_block(reason_code: str) -> str:
    if not reason_code:
        return "bloqueado_entrada"
    return _REASON_TO_AUDITORIA.get(reason_code, "bloqueado_entrada")


def _normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = _ZERO_WIDTH_RE.sub("", s)
    s = _CONTROL_CHARS_RE.sub("", s)
    return s.strip()


def _collapse_for_scan(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower())


def _cpf_digits(cpf: str) -> str:
    return re.sub(r"\D", "", cpf or "")


def _valid_cpf_checksum(d: str) -> bool:
    if len(d) != 11 or not d.isdigit():
        return False
    if d == d[0] * 11:
        return False

    def digit(body: str, factor_start: int) -> int:
        total = sum(int(body[i]) * (factor_start - i) for i in range(len(body)))
        rest = total % 11
        return 0 if rest < 2 else 11 - rest

    d1 = digit(d[:9], 10)
    if int(d[9]) != d1:
        return False
    d2 = digit(d[:10], 11)
    return int(d[10]) == d2


def _injection_heuristic(text: str) -> bool:
    folded = _collapse_for_scan(text)
    if any(p in folded for p in _INJECTION_SUBSTRINGS):
        return True
    if _REPEAT_CHAR_RE.search(text):
        return True
    return False


def _blocked(
    user_message: str,
    reason_code: str,
    *,
    sanitized_input: str = "",
    cpf_digits: str = "",
) -> GuardrailResult:
    return GuardrailResult(
        ok=False,
        user_message=user_message,
        sanitized_input=sanitized_input,
        cpf_digits=cpf_digits,
        reason_code=reason_code,
    )


def validate_debt_request(
    user_input: str,
    client_cpf: str,
) -> GuardrailResult:
    """
    Valida mensagem do cliente e CPF antes de orquestrar agentes.

    Em caso de bloqueio, a mensagem ao usuário é intencionalmente genérica
    para não facilitar tuning de ataques.
    """
    generic = (
        "Não foi possível processar sua solicitação. "
        "Use uma mensagem mais curta e objetiva sobre sua negociação, "
        "e confira o CPF informado."
    )
    injection_msg = (
        "Não foi possível seguir com esse pedido. "
        "Reformule sua mensagem em linguagem corrente, sobre pagamento ou renegociação da dívida."
    )

    raw_in = user_input if isinstance(user_input, str) else str(user_input)
    sanitized = _normalize_text(raw_in)
    if not sanitized:
        return _blocked(generic, "mensagem_vazia")

    if len(sanitized) > MAX_USER_MESSAGE_CHARS:
        return _blocked(generic, "mensagem_tamanho")

    if _injection_heuristic(sanitized):
        return _blocked(injection_msg, "injection")

    cpf = _cpf_digits(client_cpf)
    if len(cpf) != 11:
        return _blocked(
            "CPF inválido. Informe os 11 dígitos do seu CPF.",
            "cpf_formato",
        )
    if not _valid_cpf_checksum(cpf):
        return _blocked(
            "CPF inválido. Verifique os números e tente novamente.",
            "cpf_checksum",
        )

    return GuardrailResult(
        ok=True,
        user_message="",
        sanitized_input=sanitized,
        cpf_digits=cpf,
        reason_code="",
    )


def validate_chat_history(chat_history: list | None) -> GuardrailResult:
    """Valida o histórico enviado pelo cliente (stateless por requisição)."""
    generic = (
        "Não foi possível processar o histórico da conversa. "
        "Envie apenas as últimas mensagens ou inicie um novo atendimento."
    )
    if not chat_history:
        return GuardrailResult(ok=True, user_message="", sanitized_input="", cpf_digits="")

    if len(chat_history) > MAX_CHAT_HISTORY_ITEMS:
        return _blocked(generic, "historico_tamanho_itens")

    total_chars = 0
    for item in chat_history:
        if isinstance(item, dict):
            role = str(item.get("role") or "").lower()
            content = _normalize_text(str(item.get("content") or ""))
        else:
            role = str(getattr(item, "role", "") or "").lower()
            content = _normalize_text(str(getattr(item, "content", "") or ""))

        if role not in ("user", "assistant"):
            return _blocked(generic, "historico_role_invalido")
        if not content:
            return _blocked(generic, "historico_mensagem_vazia")
        if len(content) > MAX_SINGLE_HISTORY_MESSAGE_CHARS:
            return _blocked(generic, "historico_mensagem_tamanho")
        if _injection_heuristic(content):
            return _blocked(generic, "historico_injection")

        total_chars += len(content)
        if total_chars > MAX_CHAT_HISTORY_TOTAL_CHARS:
            return _blocked(generic, "historico_tamanho_total")

    return GuardrailResult(ok=True, user_message="", sanitized_input="", cpf_digits="")
