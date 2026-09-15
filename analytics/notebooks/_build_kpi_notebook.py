"""Gera analytics/notebooks/analise_metricas.ipynb (sem outputs embutidos)."""
import json
from pathlib import Path

cells: list[dict] = []


def md(text: str) -> None:
    cells.append(
        {"cell_type": "markdown", "metadata": {}, "source": text.splitlines(keepends=True)}
    )


def code(text: str) -> None:
    cells.append(
        {
            "cell_type": "code",
            "metadata": {},
            "source": text.splitlines(keepends=True),
            "outputs": [],
            "execution_count": None,
        }
    )


md(
    """# Análise de KPIs — Agentes de Recuperação de Crédito

Notebook para o TCC: **eficácia da negociação**, **aderência às políticas**, métricas operacionais (LLM) e **segurança** (guardrails).

**Pré-requisitos:** `pip install -r requirements.txt`, banco seedado e negociações registradas em `historico_negociacao`.

**Saídas:** gráficos PNG e HTML em `analytics/output/`, tabela `kpis_resumo.csv`.
"""
)

code(
    '''import sys
from pathlib import Path

# Localiza a raiz do projeto procurando recursivamente pelo diretório 'app'
_cwd = Path.cwd().resolve()
ROOT = next((d for d in [_cwd, *_cwd.parents] if (d / "app").exists()), _cwd)
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns

from analytics.metrics_loader import (
    load_adherence_summary,
    load_benchmark_csv,
    load_benchmark_summary,
    load_effectiveness_summary,
    load_etapa_summary,
    load_funnel_df,
    load_kpi_table,
    load_security_summary,
    load_session_summary,
    load_turn_metrics_df,
)

DB_PATH = ROOT / "app" / "database" / "credito.db"
CSV_PATH = ROOT / "analytics" / "data" / "negociacoes.csv"
OUT_DIR = ROOT / "analytics" / "output"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CHART_COLOR = "steelblue"
ALERT_COLOR = "#B84A4A"  # vermelho suave que combina com steelblue


def is_security_alert(label) -> bool:
    s = str(label).lower()
    return s == "bloqueado_entrada" or s.startswith("bloqueado_entrada_")


def bar_colors(labels):
    return [ALERT_COLOR if is_security_alert(l) else CHART_COLOR for l in labels]


def steelblue_shades(n: int):
    n = max(n, 1)
    return sns.color_palette("light:steelblue", n_colors=n + 2)[1 : n + 1]


sns.set_theme(style="whitegrid")
sns.set_palette([CHART_COLOR])
plt.rcParams["figure.figsize"] = (10, 5)
plt.rcParams["figure.dpi"] = 120


def salvar(fig, nome: str):
    path = OUT_DIR / nome
    fig.tight_layout()
    fig.savefig(path, bbox_inches="tight")
    print(f"Salvo: {path}")
'''
)

code(
    '''df = load_turn_metrics_df(DB_PATH)
sessoes = load_session_summary(df)
etapas = load_etapa_summary(df)
eficacia = load_effectiveness_summary(df)
aderencia = load_adherence_summary(df)
funil = load_funnel_df(df)
seguranca = load_security_summary(df)
kpis = load_kpi_table(df)

print(f"Turnos: {len(df)} | Sessões: {df['session_id'].nunique() if not df.empty else 0}")
display(kpis)
kpis.to_csv(OUT_DIR / "kpis_resumo.csv", index=False)
print(f"CSV: {OUT_DIR / 'kpis_resumo.csv'}")
'''
)

md(
    """## A. Resumo executivo (KPIs)

| Categoria | Exemplos |
|-----------|----------|
| **Eficácia** | taxa de conversão, turnos até acordo, custo por acordo |
| **Aderência** | aprovação do auditor, ajustes pós-auditoria, faixa ofertada |
| **Operacional** | tokens, latência, custo LLM |
| **Segurança** | bloqueios por `motivo_bloqueio` |
"""
)

md("## B. Eficácia da negociação\n")

code(
    '''if funil.empty:
    print("Sem dados de funil.")
else:
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.barh(
        funil["etapa"],
        funil["pct_sessoes"],
        color=bar_colors(funil["etapa"]),
    )
    ax.set_xlabel("% sessões que atingiram a etapa")
    ax.set_title("Funil conversacional")
    ax.invert_yaxis()
    for i, v in enumerate(funil["pct_sessoes"]):
        ax.text(v + 0.5, i, f"{v}%", va="center", fontsize=9)
    salvar(fig, "09_funil_conversacional.png")
    plt.show()
'''
)

code(
    '''if eficacia.empty:
    print("Sem sessões.")
else:
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    conv = eficacia["converteu"].value_counts().rename({True: "Acordo", False: "Sem acordo"})
    conv.plot(kind="bar", ax=axes[0], color=CHART_COLOR)
    axes[0].set_title("Conversão por sessão")
    axes[0].set_ylabel("Sessões")
    axes[0].tick_params(axis="x", rotation=0)

    fechadas = eficacia[eficacia["converteu"]]
    if not fechadas.empty:
        sns.histplot(
            fechadas["turnos"],
            bins=max(3, fechadas["turnos"].nunique()),
            ax=axes[1],
            color="steelblue",
        )
    axes[1].set_title("Turnos até acordo (sessões convertidas)")
    axes[1].set_xlabel("Turnos")
    salvar(fig, "10_eficacia_conversao_turnos.png")
    plt.show()
'''
)

code(
    '''if eficacia.empty or eficacia["faixa_max"].dropna().empty:
    print("Sem faixa_proposta registrada (negocie na etapa negociacao).")
else:
    fig, ax = plt.subplots()
    eficacia["faixa_max"].dropna().astype(int).value_counts().sort_index().plot(
        kind="bar", ax=ax, color=CHART_COLOR
    )
    ax.set_xlabel("Maior faixa atingida na sessão (1–3)")
    ax.set_ylabel("Sessões")
    ax.set_title("Faixa máxima de proposta por sessão")
    salvar(fig, "11_faixa_max_sessao.png")
    plt.show()
'''
)

md("## C. Aderência às políticas\n")

code(
    '''if aderencia.empty:
    print("Sem turnos na etapa negociacao.")
else:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))
    aud_counts = aderencia["resultado_auditoria"].value_counts()
    aud_counts.plot(
        kind="barh",
        ax=axes[0],
        color=bar_colors(aud_counts.index),
    )
    axes[0].set_title("Resultado da auditoria (negociacao)")
    axes[0].set_xlabel("Turnos")

    faixa = aderencia["faixa_proposta"].dropna()
    if faixa.empty:
        axes[1].text(0.5, 0.5, "Sem faixa_proposta", ha="center", va="center")
    else:
        faixa.astype(int).value_counts().sort_index().plot(kind="bar", ax=axes[1], color=CHART_COLOR)
        axes[1].set_xlabel("Faixa ofertada (1–3)")
        axes[1].set_ylabel("Turnos")
        axes[1].set_title("Distribuição de faixa por turno")
    salvar(fig, "12_aderencia_auditoria_faixa.png")
    plt.show()
'''
)

code(
    '''if aderencia.empty:
    print("Sem turnos na etapa negociacao.")
else:
    rej = aderencia[aderencia["auditoria_motivo_rejeicao"].astype(str).str.len() > 0]
    if rej.empty:
        print("Nenhuma rejeição com motivo persistido em auditoria_json.")
    else:
        top = rej["auditoria_motivo_rejeicao"].value_counts().head(8)
        fig, ax = plt.subplots(figsize=(10, max(3, len(top) * 0.45)))
        top.plot(kind="barh", ax=ax, color=CHART_COLOR)
        ax.set_title("Motivos de rejeição do auditor (top 8)")
        ax.set_xlabel("Turnos")
        salvar(fig, "13_motivos_rejeicao_auditor.png")
        plt.show()
'''
)

code(
    '''if aderencia.empty or aderencia["valor_citado"].dropna().empty:
    print("Sem valor_citado nos turnos de negociacao.")
else:
    fig, ax = plt.subplots()
    sns.boxplot(data=aderencia, x="faixa_proposta", y="valor_citado", ax=ax, color=CHART_COLOR)
    ax.set_title("Valor citado (R$) por faixa de proposta")
    ax.set_xlabel("Faixa")
    ax.set_ylabel("Valor citado")
    salvar(fig, "14_valor_por_faixa.png")
    plt.show()
'''
)

md("## D. Segurança (guardrails)\n")

code(
    '''if seguranca.empty:
    print("Nenhum bloqueio de entrada registrado.")
else:
    fig, ax = plt.subplots(figsize=(8, max(3, len(seguranca) * 0.4)))
    ax.barh(seguranca["motivo_bloqueio"], seguranca["turnos"], color=ALERT_COLOR)
    ax.set_title("Bloqueios por motivo_bloqueio")
    ax.set_xlabel("Turnos")
    salvar(fig, "15_bloqueios_guardrail.png")
    plt.show()
'''
)

md("## E. Métricas operacionais (LLM)\n")

code(
    '''llm = df[df["com_llm"]].copy()
print(f"Turnos com LLM: {len(llm)}")
display(etapas)
'''
)

code(
    '''if sessoes.empty:
    print("Sem sessões para plotar.")
else:
    plot_df = sessoes.sort_values("custo_total_usd", ascending=False).head(15)
    fig, ax = plt.subplots(figsize=(10, max(4, len(plot_df) * 0.35)))
    ax.barh(
        plot_df["session_id"].str[:8] + "…",
        plot_df["custo_total_usd"],
        color=CHART_COLOR,
    )
    ax.set_xlabel("Custo total (USD)")
    ax.set_title("Custo LLM por sessão")
    ax.invert_yaxis()
    salvar(fig, "01_custo_por_sessao.png")
    plt.show()
'''
)

code(
    '''if llm.empty:
    print("Sem turnos com LLM.")
else:
    top_session = llm["session_id"].value_counts().idxmax()
    s = llm[llm["session_id"] == top_session].copy()
    s["turno_idx"] = range(1, len(s) + 1)
    fig, ax = plt.subplots()
    ax.plot(s["turno_idx"], s["total_tokens"], marker="o", color=CHART_COLOR)
    ax.set_xlabel("Turno")
    ax.set_ylabel("Tokens")
    ax.set_title(f"Tokens por turno — sessão {top_session[:8]}…")
    salvar(fig, "02_tokens_por_turno.png")
    plt.show()
'''
)

code(
    '''if llm.empty:
    print("Sem turnos com LLM.")
else:
    fig, ax = plt.subplots(figsize=(10, 5))
    order = llm.groupby("etapa")["total_latencia_ms"].median().sort_values().index
    palette = {e: ALERT_COLOR if is_security_alert(e) else CHART_COLOR for e in order}
    sns.boxplot(
        data=llm,
        x="etapa",
        y="total_latencia_ms",
        order=order,
        hue="etapa",
        palette=palette,
        dodge=False,
        legend=False,
        ax=ax,
    )
    ax.set_xlabel("Etapa")
    ax.set_ylabel("Latência (ms)")
    ax.set_title("Latência por etapa")
    plt.xticks(rotation=25, ha="right")
    salvar(fig, "03_latencia_por_etapa.png")
    plt.show()
'''
)

code(
    '''if llm.empty:
    print("Sem turnos com LLM.")
else:
    totais = pd.Series(
        {
            "Negociador": llm["negociador_input_tokens"].sum() + llm["negociador_output_tokens"].sum(),
            "Auditor": llm["auditor_input_tokens"].sum() + llm["auditor_output_tokens"].sum(),
        }
    )
    fig, ax = plt.subplots()
    totais.plot(kind="bar", ax=ax, color=CHART_COLOR)
    ax.set_ylabel("Tokens (input + output)")
    ax.set_title("Tokens totais por agente")
    ax.tick_params(axis="x", rotation=0)
    salvar(fig, "04_tokens_por_agente.png")
    plt.show()
'''
)

code(
    '''if llm.empty:
    print("Sem turnos com LLM.")
else:
    fig, ax = plt.subplots()
    etapas = llm["etapa"].unique()
    palette = {
        e: ALERT_COLOR if is_security_alert(e) else CHART_COLOR for e in etapas
    }
    sns.scatterplot(
        data=llm,
        x="total_tokens",
        y="total_latencia_ms",
        hue="etapa",
        palette=palette,
        ax=ax,
    )
    ax.set_title("Tokens vs latência")
    salvar(fig, "05_tokens_vs_latencia.png")
    plt.show()
'''
)

code(
    '''if df.empty:
    print("Sem dados.")
else:
    aud = df["resultado_auditoria"].value_counts()
    fig, ax = plt.subplots(figsize=(8, 4))
    aud.plot(kind="barh", ax=ax, color=bar_colors(aud.index))
    ax.set_title("Distribuição de resultado_auditoria (todos os turnos)")
    salvar(fig, "06_resultado_auditoria.png")
    plt.show()
'''
)

code(
    '''if llm.empty:
    print("Sem turnos com LLM.")
else:
    fig, ax = plt.subplots()
    sns.barplot(
        data=llm,
        x="score_faixa",
        y="custo_estimado_usd",
        estimator="mean",
        ax=ax,
        color=CHART_COLOR,
    )
    ax.set_title("Custo LLM médio por faixa de score")
    salvar(fig, "07_custo_por_score.png")
    plt.show()
'''
)

code(
    '''import plotly.express as px
import matplotlib.colors as mcolors

if llm.empty:
    print("Sem turnos com LLM.")
else:
    p = llm.copy()
    p["turno_idx"] = p.groupby("session_id").cumcount() + 1
    p["custo_acum_usd"] = p.groupby("session_id")["custo_estimado_usd"].cumsum()
    n_sess = p["session_id"].nunique()
    seq = [mcolors.to_hex(c) for c in steelblue_shades(n_sess)]
    fig = px.line(
        p,
        x="turno_idx",
        y="custo_acum_usd",
        color="session_id",
        markers=True,
        title="Custo acumulado por sessão",
        color_discrete_sequence=seq,
    )
    html_path = OUT_DIR / "08_custo_acumulado.html"
    fig.write_html(html_path)
    print(f"Salvo: {html_path}")
    fig.show()
'''
)

md(
    """## F. Avaliação por Categoria de Modelos (Benchmark)

Análise comparativa das configurações de agentes a partir de `negociacoes.csv`:
- **Modelos Leves**: `gemini-3.5-flash-lite` no Negociador e no Auditor
- **Modelos Mistos**: `gemini-3.5-flash-lite` (Negociador) e `gemini-3.5-flash` (Auditor)
- **Modelos Pesados**: `gemini-3.5-flash` em ambos os agentes
"""
)

code(
    '''df_benchmark = load_benchmark_csv(CSV_PATH)
resumo_benchmark = load_benchmark_summary(df_benchmark)

print(f"Total de negociações avaliadas: {len(df_benchmark)}")
display(resumo_benchmark)
resumo_benchmark.to_csv(OUT_DIR / "benchmark_modelos_resumo.csv", index=False)
print(f"CSV salvo: {OUT_DIR / 'benchmark_modelos_resumo.csv'}")
'''
)

code(
    '''# 1. Aderente à política por categoria de modelo
if df_benchmark.empty:
    print("Sem dados de benchmark.")
else:
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        resumo_benchmark["categoria_modelo"],
        resumo_benchmark["aderente_politica_pct"],
        color=CHART_COLOR,
        width=0.5,
    )
    ax.set_title("Aderência à Política por Categoria de Modelo", fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Aderência à Política (%)")
    ax.set_ylim(0, 115)
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{height:.1f}%",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )
    salvar(fig, "16_benchmark_aderencia_politica.png")
    plt.show()
'''
)

code(
    '''# 2. Ajuste do auditor por categoria de modelo
if df_benchmark.empty:
    print("Sem dados de benchmark.")
else:
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        resumo_benchmark["categoria_modelo"],
        resumo_benchmark["ajuste_auditor_pct"],
        color=CHART_COLOR,
        width=0.5,
    )
    ax.set_title("Taxa de Ajuste pelo Auditor por Categoria de Modelo", fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Turnos com Ajuste do Auditor (%)")
    max_val = resumo_benchmark["ajuste_auditor_pct"].max()
    ax.set_ylim(0, max(50, max_val + 15))
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{height:.1f}%",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )
    salvar(fig, "17_benchmark_ajuste_auditor.png")
    plt.show()
'''
)

code(
    '''# 3. Coesão textual por categoria de modelo
if df_benchmark.empty:
    print("Sem dados de benchmark.")
else:
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.bar(
        resumo_benchmark["categoria_modelo"],
        resumo_benchmark["coesao_textual_pct"],
        color=CHART_COLOR,
        width=0.5,
    )
    ax.set_title("Coesão Textual por Categoria de Modelo", fontsize=12, fontweight="bold", pad=12)
    ax.set_ylabel("Coesão Textual (%)")
    ax.set_ylim(0, 115)
    for bar in bars:
        height = bar.get_height()
        ax.annotate(
            f"{height:.1f}%",
            xy=(bar.get_x() + bar.get_width() / 2, height),
            xytext=(0, 4),
            textcoords="offset points",
            ha="center",
            va="bottom",
            fontsize=10,
            fontweight="bold",
        )
    salvar(fig, "18_benchmark_coesao_textual.png")
    plt.show()
'''
)

nb = {
    "nbformat": 4,
    "nbformat_minor": 5,
    "metadata": {
        "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
        "language_info": {"name": "python", "pygments_lexer": "ipython3"},
    },
    "cells": cells,
}

path = Path(__file__).resolve().parent / "analise_metricas.ipynb"
path.write_text(json.dumps(nb, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"Wrote {path} with {len(cells)} cells")
