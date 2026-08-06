# Matriz 3x3: score (alto/medio/baixo) x atraso (curto/medio/longo)
#
# perc_desc_* em escala 0-100 (ex.: 50.0 = 50% de desconto maximo).

POLITICAS = [
    (
        "Alto Score - Atraso Curto",
        701, 1000,
        0, 30,
        0.0, 100.0,
    ),
    (
        "Alto Score - Atraso Medio",
        701, 1000,
        31, 180,
        5.0, 80.0,
    ),
    (
        "Alto Score - Atraso Longo",
        701, 1000,
        181, 9999,
        50.0, 100.0,
    ),
    (
        "Score Medio - Atraso Curto",
        401, 700,
        0, 30,
        5.0, 50.0,
    ),
    (
        "Score Medio - Atraso Medio",
        401, 700,
        31, 180,
        10.0, 70.0,
    ),
    (
        "Score Medio - Atraso Longo",
        401, 700,
        181, 9999,
        20.0, 80.0,
    ),
    (
        "Baixo Score - Atraso Curto",
        0, 400,
        0, 30,
        0.0, 20.0,
    ),
    (
        "Baixo Score - Atraso Médio",
        0, 400,
        31, 180,
        35.0, 100.0,
    ),
    (
        "Baixo Score - Atraso Longo",
        0, 400,
        181, 9999,
        65.0, 100.0,
    ),
]
