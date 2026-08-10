"""Métricas de LLM: tokens, custo estimado e latência por turno."""

from __future__ import annotations

import os
import time
from typing import Any

_DEFAULT_INPUT_PRICE = 0.15
_DEFAULT_OUTPUT_PRICE = 0.60

MODEL_PRICING_USD: dict[str, dict[str, float]] = {
    "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-3.5-flash": {"input": 0.15, "output": 0.60},
    "gemini-3.5-flash-lite": {"input": 0.10, "output": 0.40},
}


def _pricing_for_model(model: str) -> dict[str, float]:
    key = (model or "").strip().lower()
    if key in MODEL_PRICING_USD:
        return MODEL_PRICING_USD[key]
    return {
        "input": float(os.getenv("GEMINI_PRICE_INPUT_PER_1M", str(_DEFAULT_INPUT_PRICE))),
        "output": float(os.getenv("GEMINI_PRICE_OUTPUT_PER_1M", str(_DEFAULT_OUTPUT_PRICE))),
    }


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float:
    pricing = _pricing_for_model(model)
    cost = (
        input_tokens * pricing["input"] + output_tokens * pricing["output"]
    ) / 1_000_000
    return round(cost, 8)


def extract_agent_metrics(
    response: Any,
    agent: str,
    model: str,
    latencia_ms: int,
) -> dict[str, Any]:
    meta = getattr(response, "usage_metadata", None) or {}
    response_meta = getattr(response, "response_metadata", None) or {}
    input_tokens = int(meta.get("input_tokens") or 0)
    output_tokens = int(meta.get("output_tokens") or 0)
    resolved_model = str(response_meta.get("model_name") or model or "").strip()

    return {
        "agent": agent,
        "model": resolved_model or model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latencia_ms": latencia_ms,
    }


def empty_turn_metrics() -> dict[str, Any]:
    return {
        "llm_calls": 0,
        "total_tokens": 0,
        "custo_estimado_usd": 0.0,
        "total_latencia_ms": 0,
        "agents": {},
    }


def add_agent_metrics(
    turn_metrics: dict[str, Any], agent_metrics: dict[str, Any] | None
) -> None:
    if not agent_metrics:
        return

    agent = str(agent_metrics.get("agent") or "unknown")
    input_tokens = int(agent_metrics.get("input_tokens") or 0)
    output_tokens = int(agent_metrics.get("output_tokens") or 0)
    model = str(agent_metrics.get("model") or "")

    turn_metrics["agents"][agent] = {
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "latencia_ms": int(agent_metrics.get("latencia_ms") or 0),
    }
    turn_metrics["llm_calls"] += 1
    turn_metrics["total_tokens"] += input_tokens + output_tokens
    turn_metrics["custo_estimado_usd"] = round(
        float(turn_metrics["custo_estimado_usd"])
        + estimate_cost_usd(model, input_tokens, output_tokens),
        8,
    )


def finalize_turn_metrics(turn_metrics: dict[str, Any], started_at: float) -> None:
    turn_metrics["total_latencia_ms"] = round((time.perf_counter() - started_at) * 1000)
