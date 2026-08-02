"""Carrega e achata métricas de historico_negociacao para análise/gráficos."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "database" / "credito.db"


def _default_db_path(db_path: str | Path | None) -> Path:
    return Path(db_path) if db_path else _DEFAULT_DB


def _flatten_metrics(row: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    raw = row.get("llm_metrics_json")
    if raw:
        try:
            metrics = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            metrics = {}

    agents = metrics.get("agents") or {}
    neg = agents.get("negociador") or {}
    aud = agents.get("auditor") or {}

    return {
        "llm_calls": int(metrics.get("llm_calls") or 0),
        "total_tokens": int(metrics.get("total_tokens") or 0),
        "total_latencia_ms": int(metrics.get("total_latencia_ms") or 0),
        "custo_json_usd": float(metrics.get("custo_estimado_usd") or 0),
        "negociador_model": neg.get("model") or "",
        "negociador_input_tokens": int(neg.get("input_tokens") or 0),
        "negociador_output_tokens": int(neg.get("output_tokens") or 0),
        "negociador_latencia_ms": int(neg.get("latencia_ms") or 0),
        "auditor_model": aud.get("model") or "",
        "auditor_input_tokens": int(aud.get("input_tokens") or 0),
        "auditor_output_tokens": int(aud.get("output_tokens") or 0),
        "auditor_latencia_ms": int(aud.get("latencia_ms") or 0),
    }


def load_turn_metrics_df(db_path: str | Path | None = None) -> pd.DataFrame:
    """
    Uma linha por turno em historico_negociacao, com métricas LLM achatadas
    e dados do cliente (score, cpf, nome).
    """
    path = _default_db_path(db_path)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row
    try:
        query = """
            SELECT
                h.id AS turno_id,
                h.session_id,
                h.etapa,
                h.data_interacao,
                h.custo_estimado_usd,
                h.acordo_fechado,
                h.resultado_auditoria,
                h.llm_metrics_json,
                c.id AS cliente_id,
                c.cpf,
                c.nome,
                c.score,
                ct.dias_atraso,
                ct.valor_original
            FROM historico_negociacao h
            JOIN clientes c ON c.id = h.cliente_id
            LEFT JOIN contratos ct ON ct.cliente_id = c.id
            ORDER BY h.data_interacao ASC, h.id ASC
        """
        rows = [dict(r) for r in conn.execute(query).fetchall()]
    finally:
        conn.close()

    if not rows:
        return pd.DataFrame()

    flat_rows: list[dict[str, Any]] = []
    for row in rows:
        base = {
            "turno_id": row["turno_id"],
            "session_id": row["session_id"],
            "etapa": row["etapa"] or "",
            "data_interacao": row["data_interacao"],
            "custo_estimado_usd": float(row["custo_estimado_usd"] or 0),
            "acordo_fechado": bool(row["acordo_fechado"]),
            "resultado_auditoria": row["resultado_auditoria"] or "",
            "cliente_id": row["cliente_id"],
            "cpf": row["cpf"],
            "nome": row["nome"],
            "score": int(row["score"]),
            "dias_atraso": row["dias_atraso"],
            "valor_original": row["valor_original"],
        }
        base.update(_flatten_metrics(row))
        flat_rows.append(base)

    df = pd.DataFrame(flat_rows)
    df["data_interacao"] = pd.to_datetime(df["data_interacao"], errors="coerce")
    df["score_faixa"] = pd.cut(
        df["score"],
        bins=[0, 400, 700, 1000],
        labels=["Baixo (0-400)", "Médio (401-700)", "Alto (701+)"],
        include_lowest=True,
    )
    df["com_llm"] = df["llm_calls"] > 0
    return df


def load_session_summary(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """Agrega métricas por session_id."""
    if df is None:
        df = load_turn_metrics_df(**kwargs)
    if df.empty:
        return pd.DataFrame()

    llm = df[df["com_llm"]]
    agg = df.groupby("session_id", as_index=False).agg(
        cpf=("cpf", "first"),
        nome=("nome", "first"),
        score=("score", "first"),
        turnos=("turno_id", "count"),
        inicio=("data_interacao", "min"),
        fim=("data_interacao", "max"),
        custo_total_usd=("custo_estimado_usd", "sum"),
        acordo_fechado=("acordo_fechado", "max"),
    )
    if not llm.empty:
        llm_agg = llm.groupby("session_id", as_index=False).agg(
            tokens_total=("total_tokens", "sum"),
            latencia_media_ms=("total_latencia_ms", "mean"),
            turnos_com_llm=("turno_id", "count"),
        )
        agg = agg.merge(llm_agg, on="session_id", how="left")
    return agg.fillna(0)


def load_etapa_summary(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """Agrega métricas por etapa do roteiro (somente turnos com LLM)."""
    if df is None:
        df = load_turn_metrics_df(**kwargs)
    if df.empty:
        return pd.DataFrame()

    llm = df[df["com_llm"]].copy()
    if llm.empty:
        return pd.DataFrame()

    return (
        llm.groupby("etapa", as_index=False)
        .agg(
            turnos=("turno_id", "count"),
            tokens_medio=("total_tokens", "mean"),
            latencia_media_ms=("total_latencia_ms", "mean"),
            custo_medio_usd=("custo_estimado_usd", "mean"),
        )
        .sort_values("turnos", ascending=False)
    )
