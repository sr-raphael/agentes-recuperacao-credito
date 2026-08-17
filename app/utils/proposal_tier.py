"""Faixas de proposta (1=conservadora … 3=máximo desconto) e detecção no histórico."""

from __future__ import annotations

import re
from typing import Any

_TIER_KEYS = ("proposta_1", "proposta_2", "proposta_3")

_BRL_RE = re.compile(
    r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:[.,]\d{2})?)",
    re.IGNORECASE,
)

def _parse_brl(raw: str) -> float | None:
    s = (raw or "").strip()
    if not s:
        return None
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def extract_brl_values(text: str) -> list[float]:
    values: list[float] = []
    for match in _BRL_RE.finditer(text or ""):
        parsed = _parse_brl(match.group(1))
        if parsed is not None and parsed > 0:
            values.append(parsed)
    return values


def infer_tier_from_amount(amount: float, limits: dict[str, Any]) -> int | None:
    tiers: list[tuple[int, float]] = []
    for i, key in enumerate(_TIER_KEYS, start=1):
        val = limits.get(key)
        if val is None:
            continue
        try:
            tiers.append((i, float(val)))
        except (TypeError, ValueError):
            continue
    if not tiers:
        return None

    amount_f = float(amount)
    best_tier, best_val = tiers[0]
    best_diff = abs(best_val - amount_f)
    for tier, val in tiers[1:]:
        diff = abs(val - amount_f)
        if diff < best_diff:
            best_tier, best_diff = tier, diff
    if best_diff > max(50.0, amount_f * 0.02):
        return None
    return best_tier


def infer_tier_from_text(text: str, limits: dict[str, Any]) -> int | None:
    tiers = [
        infer_tier_from_amount(v, limits)
        for v in extract_brl_values(text)
    ]
    tiers = [t for t in tiers if t is not None]
    return max(tiers) if tiers else None


def _total_debt(limits: dict[str, Any]) -> float:
    return float(limits.get("principal") or 0) + float(limits.get("juros") or 0)


def _is_debt_anchor(value: float, limits: dict[str, Any]) -> bool:
    total = _total_debt(limits)
    return total > 0 and abs(value - total) < 1.0


def offered_tier_from_history(
    history: list[dict[str, str]] | None, limits: dict[str, Any]
) -> int:
    """
    Maior faixa já ofertada pelo assistente na negociação.
    Retorna 0 se nenhuma proposta foi apresentada ainda.
    """
    best = 0
    for msg in history or []:
        if str(msg.get("role", "")).lower() != "assistant":
            continue
        for value in extract_brl_values(str(msg.get("content") or "")):
            if _is_debt_anchor(value, limits):
                continue
            tier = infer_tier_from_amount(value, limits)
            if tier is not None:
                best = max(best, tier)
    return best


def max_tier_from_history(
    history: list[dict[str, str]] | None, limits: dict[str, Any]
) -> int:
    """Maior faixa já citada pelo assistente (1–3). Default: 1."""
    offered = offered_tier_from_history(history, limits)
    return offered if offered > 0 else 1


def suggest_next_tier(
    offered_tier: int,
    user_message: str,
    *,
    max_tier: int = 3,
) -> int:
    """Sobe uma faixa somente após recusa explícita; caso contrário mantém a atual."""
    from app.utils.conversation import detect_proposal_refusal

    current = max(1, min(3, offered_tier)) if offered_tier > 0 else 1
    if detect_proposal_refusal(user_message) and current < max_tier:
        return min(current + 1, max_tier)
    return current if offered_tier > 0 else 1


def tier_exceeds_allowed(
    text: str, limits: dict[str, Any], max_allowed_tier: int
) -> int | None:
    """Retorna a faixa detectada se ultrapassar max_allowed_tier; caso contrário None."""
    tier = infer_tier_from_text(text, limits)
    if tier is not None and tier > max(1, max_allowed_tier):
        return tier
    return None


def extract_proposal_metadata(
    text: str, limits: dict[str, Any]
) -> tuple[int | None, float | None]:
    """
    Infere faixa (1–3) e valor em R$ a partir do texto do assistente.
    Retorna (None, None) se não houver valor monetário reconhecível.
    """
    values = extract_brl_values(text)
    if not values:
        return None, None

    tier = infer_tier_from_text(text, limits)
    if tier is not None:
        tier_val = proposta_value(limits, tier)
        valor = min(values, key=lambda v: abs(v - tier_val))
        return tier, round(valor, 2)

    return None, round(values[-1], 2)


def proposta_value(limits: dict[str, Any], tier: int) -> float:
    key = _TIER_KEYS[max(1, min(3, tier)) - 1]
    return float(limits.get(key) or 0)


def resolve_agreed_offer(
    history: list[dict[str, str]] | None,
    limits: dict[str, Any],
) -> tuple[int, float]:
    """
    Faixa e valor do acordo com base na maior proposta já citada pelo assistente.
    Fallback: faixa 1 (proposta conservadora).
    """
    tier = max_tier_from_history(history, limits)
    valor = proposta_value(limits, tier)
    if valor <= 0:
        tier = 1
        valor = proposta_value(limits, tier)
    return tier, round(valor, 2)


def tier_label(tier: int) -> str:
    return {
        1: "conservadora",
        2: "intermediária",
        3: "final autorizada",
    }.get(tier, "conservadora")
