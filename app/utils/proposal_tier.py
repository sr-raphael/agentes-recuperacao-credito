"""Faixas de proposta (1=conservadora … 3=máximo desconto) e detecção no histórico."""

from __future__ import annotations

import re
from typing import Any

_TIER_KEYS = ("proposta_1", "proposta_2", "proposta_3")

_BRL_RE = re.compile(
    r"R\$\s*(\d{1,3}(?:\.\d{3})*,\d{2}|\d+(?:[.,]\d{2})?)",
    re.IGNORECASE,
)

_REFUSAL_HINTS = (
    "não posso",
    "nao posso",
    "caro",
    "alto",
    "difícil",
    "dificil",
    "sem condições",
    "sem condicoes",
    "recuso",
    "negociar melhor",
    "desconto maior",
    "abaixo",
    "menos",
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
    best_tier, best_diff = tiers[0]
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


def max_tier_from_history(
    history: list[dict[str, str]] | None, limits: dict[str, Any]
) -> int:
    """Maior faixa já citada pelo assistente (1–3). Default: 1."""
    best = 1
    for msg in history or []:
        if str(msg.get("role", "")).lower() != "assistant":
            continue
        tier = infer_tier_from_text(str(msg.get("content") or ""), limits)
        if tier is not None:
            best = max(best, tier)
    return best


def suggest_next_tier(
    min_tier: int,
    user_message: str,
    *,
    max_tier: int = 3,
) -> int:
    """Sugere faixa do turno: mantém a mínima ou sobe 1 se houver sinal de dificuldade."""
    folded = (user_message or "").lower()
    if any(h in folded for h in _REFUSAL_HINTS) and min_tier < max_tier:
        return min(min_tier + 1, max_tier)
    return min_tier


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
