-- Tabela de Clientes
CREATE TABLE IF NOT EXISTS clientes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nome TEXT NOT NULL,
    cpf TEXT UNIQUE NOT NULL,
    score INTEGER NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Tabela de Contrato
CREATE TABLE IF NOT EXISTS contratos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    valor_contrato REAL NOT NULL,
    saldo_devedor REAL NOT NULL,
    numero_parcelas INTEGER NOT NULL,
    parcelas_abertas INTEGER NOT NULL,
    dias_atraso INTEGER NOT NULL,
    situacao TEXT DEFAULT 'ABERTO', -- ABERTO, ACORDADO, QUITADO
    FOREIGN KEY (cliente_id) REFERENCES clientes (id)
);

-- Tabela de Logs de Negociação
CREATE TABLE IF NOT EXISTS historico_negociacao (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cliente_id INTEGER NOT NULL,
    data_interacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    transcricao_json JSON,
    resultado_auditoria TEXT,
    acordo_fechado BOOLEAN DEFAULT FALSE,
    FOREIGN KEY (cliente_id) REFERENCES clientes (id)
);