# Matriz 3x2 alinhada aos clientes/contratos do seed:
#   score alto (701+) | medio (401-700) | baixo (0-400)
#   atraso curto (0-30) | medio (31-120) | longo (121+)
#
# perc_desc_* em escala 0-100 (ex.: 50.0 = 50% de desconto maximo).
# altera_prazo: 0 = prazo fixo, 1 = permite reparcelamento ate max_prazo.

POLITICAS = [
    # Cliente 1 — Flavio Silva (score 850, 6 dias): VIP, manter relacionamento
    (
        "Alto Score - Atraso Curto",
        701, 1000, # score
        0, 30, # atraso
        0.0, 100.0, # desconto
        1, # altera_prazo
        36, # prazo
    ),
    # Cliente 2 — Guilherme Dias (score 900, 70 dias): bom pagador em recuperacao
    (
        "Alto Score - Atraso Medio",
        701, 1000, # score
        31, 120, # atraso
        5.0, 80.0, # desconto
        0, # altera_prazo
        0, # prazo
    ),
    # Cliente 3 — Vagner Pereira (score 420, 11 dias): flexibilidade moderada
    (
        "Score Medio - Atraso Curto",
        401, 700, # score
        0, 30, # atraso
        5.0, 50.0, # desconto
        1, # altera_prazo
        12, # prazo
    ),
    # Cliente 4 — Joaquim Oliveira (score 450, 94 dias): divida alta, incentivar acordo
    (
        "Score Medio - Atraso Medio",
        401, 700, # score
        31, 120, # atraso
        10.0, 70.0, # desconto
        0, # altera_prazo
        0, # prazo
    ),
    # Cliente 5 — Mariana Santos (score 150, 13 dias): alto risco, cobranca rigida
    (
        "Baixo Score - Atraso Curto",
        0, 400, # score
        0, 30, # atraso
        0.0, 20.0, # desconto
        1, # altera_prazo
        12, # prazo
    ),
    # Cliente 6 — Rodrigo Ferreira (score 190, 540 dias): recuperacao critica
    (
        "Baixo Score - Atraso Longo",
        0, 400, # score
        121, 9999, # atraso
        35.0, 100.0, # desconto
        1, # altera_prazo
        24, # prazo
    ),
]
