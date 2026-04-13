-- Tabela de Clientes
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cpf TEXT UNIQUE NOT NULL,
    score INTEGER NOT NULL
);

-- Tabela de Contrato
CREATE TABLE IF NOT EXISTS contratos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    valor_original REAL NOT NULL,
    juros_acumulado REAL DEFAULT 0,
    numero_parcelas INTEGER NOT NULL,
    parcelas_abertas INTEGER NOT NULL,
    dias_atraso INTEGER NOT NULL,
    situacao TEXT DEFAULT 'ABERTO', -- ABERTO, RENEGOCIADO, QUITADO
    FOREIGN KEY (cliente_id) REFERENCES clientes (id)
);

-- Tabela de Políticas (Matriz de Decisão)
CREATE TABLE IF NOT EXISTS politicas_negociacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    descricao TEXT,
    score_min INTEGER NOT NULL,
    score_max INTEGER NOT NULL,
    atraso_min INTEGER NOT NULL,
    atraso_max INTEGER NOT NULL,
    perc_desc_principal_max REAL NOT NULL,
    perc_desc_juros_max REAL NOT NULL,
    altera_prazo BOOLEAN NOT NULL,
    max_prazo INTEGER NOT NULL
);

-- Tabela de Logs de Negociação
CREATE TABLE IF NOT EXISTS historico_negociacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    data_interacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    transcricao_json JSON,
    acordo_fechado BOOLEAN DEFAULT FALSE,
    resultado_auditoria TEXT,
    FOREIGN KEY (cliente_id) REFERENCES clientes (id)
);

-- Índices para performance em buscas por CPF e Faixas
CREATE INDEX IF NOT EXISTS idx_clientes_cpf ON clientes(cpf);
CREATE INDEX IF NOT EXISTS idx_politicas_busca ON politicas_negociacao(score_min, score_max, atraso_min, atraso_max);
