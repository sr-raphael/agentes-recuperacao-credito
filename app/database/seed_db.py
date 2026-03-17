import sqlite3
from pathlib import Path


def setup_database(reset_db: bool = True) -> Path:
    base_dir = Path(__file__).resolve().parent
    db_path = base_dir / "credito.db"
    schema_path = base_dir / "schema.sql"

    base_dir.mkdir(parents=True, exist_ok=True)

    if reset_db and db_path.exists():
        db_path.unlink()

    conn = sqlite3.connect(str(db_path))
    try:
        cursor = conn.cursor()

        print("--- Criando Tabelas (schema.sql) ---")
        if not schema_path.exists():
            raise FileNotFoundError(f"schema.sql não encontrado em: {schema_path}")
        schema_sql = schema_path.read_text(encoding="utf-8")
        cursor.executescript(schema_sql)

        print("--- Populando Dados de Teste ---")

        # Perfis estratégicos para o TCC, compatíveis com app/database/schema.sql
        perfis = [
            # Cliente 1: Bom score, pouco atraso (fácil negociação)
            {
                "nome": "Fulano Silva",
                "cpf": "12345678901",
                "score": 850,
                "valor_contrato": 5000.00,
                "saldo_devedor": 1000.00,
                "numero_parcelas": 24,
                "parcelas_abertas": 4,
                "dias_atraso": 15,
                "situacao": "ABERTO",
            },
            # Cliente 2: Score médio, atraso longo (precisa de desconto agressivo)
            {
                "nome": "Ciclano Oliveira",
                "cpf": "98765432100",
                "score": 420,
                "valor_contrato": 12000.00,
                "saldo_devedor": 6000.00,
                "numero_parcelas": 24,
                "parcelas_abertas": 12,
                "dias_atraso": 45,
                "situacao": "ABERTO",
            },
            # Cliente 3: Score baixo, reincidente (maior risco)
            {
                "nome": "Beltrana Santos",
                "cpf": "11122233344",
                "score": 150,
                "valor_contrato": 2500.00,
                "saldo_devedor": 2500.00,
                "numero_parcelas": 10,
                "parcelas_abertas": 10,
                "dias_atraso": 720,
                "situacao": "ABERTO",
            },
        ]

        for p in perfis:
            cursor.execute(
                "INSERT INTO clientes (nome, cpf, score) VALUES (?, ?, ?)",
                (p["nome"], p["cpf"], int(p["score"])),
            )
            client_id = cursor.lastrowid

            cursor.execute(
                """
                INSERT INTO contratos (
                    cliente_id,
                    valor_contrato,
                    saldo_devedor,
                    numero_parcelas,
                    parcelas_abertas,
                    dias_atraso,
                    situacao
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    client_id,
                    float(p["valor_contrato"]),
                    float(p["saldo_devedor"]),
                    int(p["numero_parcelas"]),
                    int(p["parcelas_abertas"]),
                    int(p["dias_atraso"]),
                    p["situacao"],
                ),
            )

        conn.commit()
        print(f"✅ Banco de dados criado com sucesso em: {db_path}")
        return db_path
    finally:
        conn.close()


if __name__ == "__main__":
    setup_database()