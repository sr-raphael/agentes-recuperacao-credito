POLITICAS = [
    # CENARIO 1: Cliente Alto Risco / Atraso Curto (Conservador)
    # Objetivo: receber o principal logo. Pouco desconto, prazo rigido.
    ("Baixo Score - Atraso Recente", 0, 400, 0, 90, 0.0, 0.10, 0, 6),
    # CENARIO 2: Cliente Medio Risco / Atraso Medio (Flexivel)
    # Objetivo: facilitar o pagamento com parcelamento.
    ("Score Medio - Atraso Medio", 401, 700, 91, 180, 0.05, 0.50, 1, 12),
    # CENARIO 3: Recuperacao de Perda (Atraso Longo / Qualquer Score)
    # Objetivo: recuperar qualquer valor de dividas "podres".
    ("Recuperacao Critica - Atraso Longo", 0, 1000, 361, 9999, 0.30, 1.0, 1, 24),
    # CENARIO 4: Cliente VIP / Atraso Pontual (Relacionamento)
    # Objetivo: manter o cliente. Isencao de juros e prazo flexivel.
    ("Alto Score - Curto Prazo", 701, 1000, 0, 60, 0.0, 1.0, 1, 36),
]
