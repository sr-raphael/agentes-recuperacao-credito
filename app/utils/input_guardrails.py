"""
Validação determinística de entradas antes de LLMs e ferramentas (guardrails).
Foco: prompt injection comum, abuso de tamanho e CPF claramente inválido.
"""

from __future__ import annotations

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


def _history_total_and_max_item(chat_history: list | None) -> tuple[int, int]:
    if not chat_history:
        return 0, 0
    total = 0
    max_one = 0
    for m in chat_history:
        if hasattr(m, "content"):
            chunk = str(getattr(m, "content", "") or "")
        elif isinstance(m, dict):
            chunk = str(m.get("content", "") or "")
        else:
            chunk = str(m)
        total += len(chunk)
        max_one = max(max_one, len(chunk))
    return total, max_one


def validate_debt_request(
    user_input: str,
    client_cpf: str,
    chat_history: list | None = None,
) -> GuardrailResult:
    """
    Valida mensagem do cliente, CPF e histórico antes de orquestrar agentes.

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
        return GuardrailResult(ok=False, user_message=generic, sanitized_input="", cpf_digits="")

    if len(sanitized) > MAX_USER_MESSAGE_CHARS:
        return GuardrailResult(ok=False, user_message=generic, sanitized_input="", cpf_digits="")

    if _injection_heuristic(sanitized):
        return GuardrailResult(ok=False, user_message=injection_msg, sanitized_input="", cpf_digits="")

    cpf = _cpf_digits(client_cpf)
    if len(cpf) != 11:
        return GuardrailResult(
            ok=False,
            user_message="CPF inválido. Informe os 11 dígitos do seu CPF.",
            sanitized_input="",
            cpf_digits="",
        )
    if not _valid_cpf_checksum(cpf):
        return GuardrailResult(
            ok=False,
            user_message="CPF inválido. Verifique os números e tente novamente.",
            sanitized_input="",
            cpf_digits="",
        )

    if chat_history is not None:
        if len(chat_history) > MAX_CHAT_HISTORY_ITEMS:
            return GuardrailResult(ok=False, user_message=generic, sanitized_input="", cpf_digits="")
        total_chars, max_item = _history_total_and_max_item(chat_history)
        if total_chars > MAX_CHAT_HISTORY_TOTAL_CHARS or max_item > MAX_SINGLE_HISTORY_MESSAGE_CHARS:
            return GuardrailResult(ok=False, user_message=generic, sanitized_input="", cpf_digits="")

    return GuardrailResult(
        ok=True,
        user_message="",
        sanitized_input=sanitized,
        cpf_digits=cpf,
    )
