"""Carrega e achata métricas de historico_negociacao para análise/gráficos."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pandas as pd

_DEFAULT_DB = Path(__file__).resolve().parent.parent / "app" / "database" / "credito.db"
_DEFAULT_CSV = Path(__file__).resolve().parent / "data" / "negociacoes.csv"


def _default_db_path(db_path: str | Path | None) -> Path:
    return Path(db_path) if db_path else _DEFAULT_DB


def _default_csv_path(csv_path: str | Path | None) -> Path:
    return Path(csv_path) if csv_path else _DEFAULT_CSV


def _flatten_auditoria(row: dict[str, Any]) -> dict[str, Any]:
    audit: dict[str, Any] = {}
    raw = row.get("auditoria_json")
    if pd.notna(raw) and raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, dict):
                audit = parsed
        except (json.JSONDecodeError, TypeError):
            audit = {}
    return {
        "faixa_proposta": row.get("faixa_proposta"),
        "valor_citado": float(row["valor_citado"]) if row.get("valor_citado") is not None else None,
        "auditoria_aprovado": audit.get("aprovado"),
        "auditoria_motivo_rejeicao": audit.get("motivo_rejeicao") or "",
        "auditoria_risco": audit.get("risco_detectado") or "",
        "auditoria_correcao_sugerida": audit.get("correcao_sugerida") or "",
    }


def _flatten_metrics(row: dict[str, Any]) -> dict[str, Any]:
    metrics: dict[str, Any] = {}
    raw = row.get("llm_metrics_json")
    if pd.notna(raw) and raw:
        try:
            parsed = json.loads(raw) if isinstance(raw, str) else raw
            if isinstance(parsed, dict):
                metrics = parsed
        except (json.JSONDecodeError, TypeError):
            metrics = {}

    agents = metrics.get("agents") if isinstance(metrics.get("agents"), dict) else {}
    neg = agents.get("negociador") if isinstance(agents.get("negociador"), dict) else {}
    aud = agents.get("auditor") if isinstance(agents.get("auditor"), dict) else {}

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
                h.motivo_bloqueio,
                h.faixa_proposta,
                h.valor_citado,
                h.auditoria_json,
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
            "motivo_bloqueio": row["motivo_bloqueio"] or "",
            "cliente_id": row["cliente_id"],
            "cpf": row["cpf"],
            "nome": row["nome"],
            "score": int(row["score"]),
            "dias_atraso": row["dias_atraso"],
            "valor_original": row["valor_original"],
            "llm_metrics_json": row.get("llm_metrics_json"),
        }
        base.update(_flatten_metrics(row))
        base.update(_flatten_auditoria(row))
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


def load_model_cost_summary(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """
    Calcula custo total, custo médio, tokens médios e total de chamadas por modelo
    (ex: 'gemini-3.5-flash', 'gemini-3.5-flash-lite') a partir de llm_metrics_json.
    """
    if df is None:
        df = load_turn_metrics_df(**kwargs)
    if df.empty:
        return pd.DataFrame()

    pricing_map = {
        "gemini-3.5-flash": {"input": 0.15, "output": 0.60},
        "gemini-3.5-flash-lite": {"input": 0.10, "output": 0.40},
        "gemini-2.5-flash": {"input": 0.15, "output": 0.60},
        "gemini-2.0-flash": {"input": 0.10, "output": 0.40},
        "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    }

    records: list[dict[str, Any]] = []
    for raw in df["llm_metrics_json"].dropna():
        if not raw:
            continue
        try:
            data = json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            continue

        if not isinstance(data, dict):
            continue

        for agent_name, info in (data.get("agents") or {}).items():
            if not isinstance(info, dict):
                continue
            model = str(info.get("model") or "").strip()
            if not model:
                continue
            inp = int(info.get("input_tokens") or 0)
            out = int(info.get("output_tokens") or 0)
            lat = int(info.get("latencia_ms") or 0)

            p = pricing_map.get(model, {"input": 0.15, "output": 0.60})
            cost = (inp * p["input"] + out * p["output"]) / 1_000_000

            records.append({
                "modelo": model,
                "agente": agent_name,
                "input_tokens": inp,
                "output_tokens": out,
                "total_tokens": inp + out,
                "custo_usd": cost,
                "latencia_ms": lat,
            })

    if not records:
        return pd.DataFrame()

    df_models = pd.DataFrame(records)
    return (
        df_models.groupby("modelo", as_index=False)
        .agg(
            chamadas=("custo_usd", "count"),
            custo_total_usd=("custo_usd", "sum"),
            custo_medio_usd=("custo_usd", "mean"),
            tokens_medio=("total_tokens", "mean"),
            latencia_media_ms=("latencia_ms", "mean"),
        )
        .sort_values("custo_medio_usd", ascending=False)
    )


def _classify_session_models(models: set[str]) -> str:
    has_flash = any("flash" in m and "lite" not in m for m in models)
    has_lite = any("lite" in m for m in models)
    if has_flash and has_lite:
        return "Modelos Mistos"
    if has_flash:
        return "Modelos Pesados"
    if has_lite:
        return "Modelos Leves"
    return "Sem LLM"


def load_session_summary(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """Agrega métricas por session_id, incluindo a categoria dos modelos utilizados."""
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

    # Identifica os modelos de cada sessão a partir de llm_metrics_json
    session_models: dict[str, set[str]] = {}
    for _, row in df.iterrows():
        sid = row["session_id"]
        if sid not in session_models:
            session_models[sid] = set()
        raw = row.get("llm_metrics_json")
        if pd.notna(raw) and raw:
            try:
                data = json.loads(raw) if isinstance(raw, str) else raw
            except (json.JSONDecodeError, TypeError):
                data = {}
            if isinstance(data, dict):
                for info in (data.get("agents") or {}).values():
                    if isinstance(info, dict):
                        m = str(info.get("model") or "").strip()
                        if m:
                            session_models[sid].add(m)

    agg["categoria_modelo"] = agg["session_id"].map(
        lambda sid: _classify_session_models(session_models.get(sid, set()))
    )

    if not llm.empty:
        llm_agg = llm.groupby("session_id", as_index=False).agg(
            tokens_total=("total_tokens", "sum"),
            latencia_media_ms=("total_latencia_ms", "mean"),
            turnos_com_llm=("turno_id", "count"),
        )
        agg = agg.merge(llm_agg, on="session_id", how="left")
    return agg.fillna(0)


def load_category_cost_summary(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """
    Agrega o custo médio por sessão agrupado por categoria de modelo:
    - Modelos Leves (flash-lite)
    - Modelos Mistos (flash + flash-lite)
    - Modelos Pesados (flash)
    """
    if df is None:
        df = load_turn_metrics_df(**kwargs)
    if df.empty:
        return pd.DataFrame()

    sessoes = load_session_summary(df)
    sessoes_validas = sessoes[sessoes["categoria_modelo"] != "Sem LLM"]
    if sessoes_validas.empty:
        return pd.DataFrame()

    ordem = ["Modelos Leves", "Modelos Mistos", "Modelos Pesados"]
    cat_type = pd.CategoricalDtype(categories=ordem, ordered=True)

    summary = (
        sessoes_validas.groupby("categoria_modelo", observed=False, as_index=False)
        .agg(
            sessoes=("session_id", "count"),
            custo_total_usd=("custo_total_usd", "sum"),
            custo_medio_usd=("custo_total_usd", "mean"),
        )
    )
    summary["categoria_modelo"] = summary["categoria_modelo"].astype(cat_type)
    return summary.sort_values("categoria_modelo").reset_index(drop=True)


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


def load_effectiveness_summary(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """KPIs de eficácia agregados por sessão."""
    if df is None:
        df = load_turn_metrics_df(**kwargs)
    if df.empty:
        return pd.DataFrame()

    sessoes = load_session_summary(df)
    if sessoes.empty:
        return pd.DataFrame()

    neg = df[df["etapa"] == "negociacao"].copy()
    faixa_por_sessao = (
        neg.groupby("session_id", as_index=False)
        .agg(
            faixa_max=("faixa_proposta", "max"),
            valor_ultimo=("valor_citado", "last"),
        )
    )
    sessoes = sessoes.merge(faixa_por_sessao, on="session_id", how="left")
    sessoes["duracao_min"] = (
        (sessoes["fim"] - sessoes["inicio"]).dt.total_seconds() / 60.0
    ).round(1)
    sessoes["converteu"] = sessoes["acordo_fechado"].astype(bool)
    return sessoes


def load_funnel_df(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """Quantidade de sessões que atingiram cada etapa do roteiro."""
    if df is None:
        df = load_turn_metrics_df(**kwargs)
    if df.empty:
        return pd.DataFrame()

    ordem = [
        "saudacao",
        "detalhamento",
        "negociacao",
        "acordo_fechado",
        "bloqueado_entrada",
    ]
    por_sessao = df.groupby("session_id")["etapa"].apply(set)
    total = len(por_sessao)
    rows: list[dict[str, Any]] = []
    for etapa in ordem:
        n = sum(1 for etapas in por_sessao if etapa in etapas)
        rows.append(
            {
                "etapa": etapa,
                "sessoes": n,
                "pct_sessoes": round(100.0 * n / total, 1) if total else 0.0,
            }
        )
    return pd.DataFrame(rows)


def load_adherence_summary(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """Turnos de negociacao com métricas de aderência (auditor + faixa/valor)."""
    if df is None:
        df = load_turn_metrics_df(**kwargs)
    if df.empty:
        return pd.DataFrame()

    neg = df[df["etapa"] == "negociacao"].copy()
    if neg.empty:
        return pd.DataFrame()

    neg["auditoria_aprovado"] = neg["auditoria_aprovado"].fillna(False).astype(bool)
    return neg


def load_security_summary(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """Turnos bloqueados por guardrails de entrada."""
    if df is None:
        df = load_turn_metrics_df(**kwargs)
    if df.empty:
        return pd.DataFrame()

    bloq = df[df["etapa"] == "bloqueado_entrada"].copy()
    if bloq.empty:
        return pd.DataFrame()
    return (
        bloq.groupby("motivo_bloqueio", as_index=False)
        .agg(turnos=("turno_id", "count"))
        .sort_values("turnos", ascending=False)
    )


def load_kpi_table(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """
    Tabela única de KPIs para o TCC (eficácia, aderência, operacional, segurança).
    """
    if df is None:
        df = load_turn_metrics_df(**kwargs)
    if df.empty:
        return pd.DataFrame(columns=["categoria", "kpi", "valor"])

    sessoes = load_session_summary(df)
    neg = df[df["etapa"] == "negociacao"]
    bloq = df[df["etapa"] == "bloqueado_entrada"]
    llm = df[df["com_llm"]]

    n_sessoes = int(sessoes["session_id"].nunique()) if not sessoes.empty else 0
    n_acordos = int(sessoes["acordo_fechado"].sum()) if not sessoes.empty else 0
    n_neg = len(neg)
    n_aprov = int((neg["resultado_auditoria"] == "aprovado").sum()) if n_neg else 0
    n_ajuste = int((neg["resultado_auditoria"] == "ajustado_pos_auditoria").sum()) if n_neg else 0

    turnos_ate_acordo = None
    if n_acordos and not sessoes.empty:
        fechadas = sessoes[sessoes["acordo_fechado"]]
        turnos_ate_acordo = round(float(fechadas["turnos"].mean()), 1)

    custo_acordo = None
    if n_acordos and not sessoes.empty:
        custo_acordo = round(
            float(sessoes[sessoes["acordo_fechado"]]["custo_total_usd"].mean()), 6
        )

    rows = [
        ("Eficácia", "Sessões totais", n_sessoes),
        ("Eficácia", "Taxa de conversão (%)", round(100.0 * n_acordos / n_sessoes, 1) if n_sessoes else 0),
        ("Eficácia", "Acordos fechados", n_acordos),
        ("Eficácia", "Turnos médios até acordo", turnos_ate_acordo if turnos_ate_acordo is not None else "—"),
        ("Eficácia", "Custo médio por acordo (USD)", custo_acordo if custo_acordo is not None else "—"),
        ("Aderência", "Turnos em negociacao", n_neg),
        ("Aderência", "Taxa aprovação auditor (%)", round(100.0 * n_aprov / n_neg, 1) if n_neg else "—"),
        ("Aderência", "Taxa ajuste pós-auditoria (%)", round(100.0 * n_ajuste / n_neg, 1) if n_neg else "—"),
        ("Operacional", "Turnos totais", len(df)),
        ("Operacional", "Turnos com LLM", len(llm)),
        ("Operacional", "Custo total LLM (USD)", round(float(df["custo_estimado_usd"].sum()), 6)),
        ("Operacional", "Tokens totais", int(llm["total_tokens"].sum()) if not llm.empty else 0),
        ("Segurança", "Bloqueios de entrada", len(bloq)),
        ("Segurança", "Taxa bloqueio (%)", round(100.0 * len(bloq) / len(df), 1) if len(df) else 0),
    ]
    return pd.DataFrame(rows, columns=["categoria", "kpi", "valor"])


def _categorize_models(row: pd.Series | dict[str, Any]) -> str:
    """Classifica os pares de modelo em: Modelos Leves, Modelos Mistos ou Modelos Pesados."""
    neg = str(row.get("Modelo Negociador", "")).strip().lower()
    aud = str(row.get("Modelo Auditor", "")).strip().lower()

    if "flash-lite" in neg and "flash-lite" in aud:
        return "Modelos Leves"
    elif "flash-lite" in neg or "flash-lite" in aud:
        return "Modelos Mistos"
    elif "flash" in neg and "flash" in aud:
        return "Modelos Pesados"
    return "Outros"


def load_benchmark_csv(csv_path: str | Path | None = None) -> pd.DataFrame:
    """
    Carrega dados de benchmark qualitativo/quantitativo do arquivo negociacoes.csv,
    adicionando a classificação de categorias de modelos (Leves, Mistos, Pesados)
    e normalizando os indicadores booleanos.
    """
    path = _default_csv_path(csv_path)
    if not path.exists():
        return pd.DataFrame()

    try:
        df = pd.read_csv(path, sep=";", encoding="utf-8")
    except UnicodeDecodeError:
        df = pd.read_csv(path, sep=";", encoding="latin1")

    df_clean = df.copy()
    df_clean["categoria_modelo"] = df_clean.apply(_categorize_models, axis=1)

    aderente_col = next((c for c in df.columns if "aderente" in c.lower()), None)
    ajuste_col = next((c for c in df.columns if "ajuste" in c.lower()), None)
    coesao_col = next((c for c in df.columns if "coes" in c.lower()), None)

    df_clean["aderente_politica"] = (
        df_clean[aderente_col].astype(str).str.strip().str.upper() == "S"
        if aderente_col
        else False
    )
    df_clean["ajuste_auditor"] = (
        df_clean[ajuste_col].astype(str).str.strip().str.upper() == "S"
        if ajuste_col
        else False
    )
    df_clean["coesao_textual"] = (
        df_clean[coesao_col].astype(str).str.strip().str.upper() == "S"
        if coesao_col
        else False
    )

    cat_type = pd.CategoricalDtype(
        categories=["Modelos Leves", "Modelos Mistos", "Modelos Pesados"],
        ordered=True,
    )
    df_clean["categoria_modelo"] = df_clean["categoria_modelo"].astype(cat_type)

    return df_clean


def load_benchmark_summary(df: pd.DataFrame | None = None, **kwargs) -> pd.DataFrame:
    """
    Agrega as taxas de aderência à política, necessidade de ajuste do auditor
    e coesão textual por categoria de modelos.
    """
    if df is None:
        df = load_benchmark_csv(**kwargs)
    if df.empty:
        return pd.DataFrame()

    return (
        df.groupby("categoria_modelo", observed=False)
        .agg(
            total_amostras=("CPF", "count"),
            aderente_politica_pct=("aderente_politica", lambda x: round(float(x.mean() * 100), 1)),
            ajuste_auditor_pct=("ajuste_auditor", lambda x: round(float(x.mean() * 100), 1)),
            coesao_textual_pct=("coesao_textual", lambda x: round(float(x.mean() * 100), 1)),
        )
        .reset_index()
    )

